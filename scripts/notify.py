#!/usr/bin/env python3
"""Domain Hunter -- Travel-proof notification dispatcher.

Sends alerts via multiple channels so the user gets notified even when
away from their Mac. Channels:
  - ntfy.sh (free push notifications to mobile)
  - Resend email (transactional email API)
  - stdout (fallback, always active)

Priority routing:
  "critical" -> all channels (ntfy + email + stdout)
  "high"     -> email + ntfy + stdout
  "normal"   -> email + stdout

Config via environment variables:
  NOTIFY_EMAIL_TO      - recipient email address
  RESEND_API_KEY       - Resend.com API key for sending email
  NOTIFY_NTFY_TOPIC    - ntfy.sh topic (e.g., "domainhunter-alerts")

Run standalone: python scripts/notify.py --test
Use as library: from scripts.notify import send_alert

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# ── Constants (immutable) ─────────────────────────────────────────────
NTFY_BASE_URL: Final[str] = "https://ntfy.sh/"
RESEND_API_URL: Final[str] = "https://api.resend.com/emails"
RESEND_FROM_ADDRESS: Final[str] = "DomainHunter <alerts@domainhunter.dev>"
REQUEST_TIMEOUT: Final[int] = 15
MAX_BODY_LENGTH: Final[int] = 4000
PRIORITY_LEVELS: Final[tuple[str, ...]] = ("critical", "high", "normal")

# ntfy priority mapping
NTFY_PRIORITY_MAP: Final[dict[str, str]] = {
    "critical": "urgent",
    "high": "high",
    "normal": "default",
}


# ── Data Models (frozen) ──────────────────────────────────────────────
@dataclass(frozen=True)
class NotifyConfig:
    """Immutable notification configuration loaded from environment."""
    email_to: str
    resend_api_key: str
    ntfy_topic: str

    def __post_init__(self) -> None:
        assert isinstance(self.email_to, str), "email_to must be string"
        assert isinstance(self.ntfy_topic, str), "ntfy_topic must be string"

    @property
    def has_email(self) -> bool:
        return bool(self.email_to and self.resend_api_key)

    @property
    def has_ntfy(self) -> bool:
        return bool(self.ntfy_topic)


@dataclass(frozen=True)
class NotifyResult:
    """Immutable result of a notification dispatch attempt."""
    channel: str
    success: bool
    detail: str

    def __post_init__(self) -> None:
        assert self.channel in ("email", "ntfy", "stdout"), f"Unknown channel: {self.channel}"
        assert isinstance(self.success, bool), "success must be bool"


# ── Config Loader ─────────────────────────────────────────────────────
def load_config() -> NotifyConfig:
    """Load notification config from environment variables."""
    config = NotifyConfig(
        email_to=os.environ.get("NOTIFY_EMAIL_TO", ""),
        resend_api_key=os.environ.get("RESEND_API_KEY", ""),
        ntfy_topic=os.environ.get("NOTIFY_NTFY_TOPIC", ""),
    )
    assert isinstance(config, NotifyConfig), "Config creation failed"
    assert config is not None, "Config must not be None"
    return config


# ── Channel: stdout ───────────────────────────────────────────────────
def _send_stdout(subject: str, body: str) -> NotifyResult:
    """Print alert to stdout. Always succeeds."""
    assert subject, "Subject required"
    assert body, "Body required"

    print(f"\n{'='*60}")
    print(f"  ALERT: {subject}")
    print(f"{'='*60}")
    print(body)
    print(f"{'='*60}\n")
    return NotifyResult(channel="stdout", success=True, detail="printed")


# ── Channel: ntfy.sh ─────────────────────────────────────────────────
def _send_ntfy(subject: str, body: str, priority: str,
               config: NotifyConfig) -> NotifyResult:
    """Send push notification via ntfy.sh HTTP POST."""
    assert subject, "Subject required"
    assert config.has_ntfy, "ntfy topic not configured"

    url = f"{NTFY_BASE_URL}{config.ntfy_topic}"
    ntfy_priority = NTFY_PRIORITY_MAP.get(priority, "default")

    headers = {
        "Title": subject[:256],
        "Priority": ntfy_priority,
        "Tags": "warning" if priority == "critical" else "loudspeaker",
    }

    truncated_body = body[:MAX_BODY_LENGTH]
    data = truncated_body.encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            success = resp.status == 200
            detail = f"ntfy status={resp.status}"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        success = False
        detail = f"ntfy error: {exc}"

    return NotifyResult(channel="ntfy", success=success, detail=detail)


# ── Channel: Resend Email ─────────────────────────────────────────────
def _send_email(subject: str, body: str, config: NotifyConfig) -> NotifyResult:
    """Send email via Resend HTTP API."""
    assert subject, "Subject required"
    assert config.has_email, "Email not configured"

    payload = json.dumps({
        "from": RESEND_FROM_ADDRESS,
        "to": [config.email_to],
        "subject": subject,
        "text": body,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {config.resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            RESEND_API_URL, data=payload, headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            resp_body = resp.read().decode("utf-8")
            success = resp.status == 200
            detail = f"resend status={resp.status}"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        success = False
        detail = f"resend error: {exc}"

    return NotifyResult(channel="email", success=success, detail=detail)


# ── Main Dispatcher ──────────────────────────────────────────────────
def send_alert(subject: str, body: str,
               priority: str = "normal") -> list[NotifyResult]:
    """Dispatch alert across configured channels based on priority.

    Priority routing:
      "critical" -> ntfy + email + stdout
      "high"     -> ntfy + email + stdout
      "normal"   -> email + stdout

    Returns list of NotifyResult for each channel attempted.
    """
    assert subject and len(subject) > 0, "Subject required"
    assert body and len(body) > 0, "Body required"
    assert priority in PRIORITY_LEVELS, f"Invalid priority: {priority}"

    config = load_config()
    results: list[NotifyResult] = []

    # stdout always fires
    results.append(_send_stdout(subject, body))

    # ntfy for critical and high
    if priority in ("critical", "high") and config.has_ntfy:
        results.append(_send_ntfy(subject, body, priority, config))

    # email for all priorities when configured
    if config.has_email:
        results.append(_send_email(subject, body, config))

    return results


# ── Alert Formatters ─────────────────────────────────────────────────
def format_domain_alert(
    domain: str, event: str, price: float | None = None,
    action_url: str = "", extra: str = "",
) -> tuple[str, str]:
    """Format a domain alert into (subject, body) tuple.

    Returns standardized subject line and multi-line body.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert event, "Event type required"

    subject = f"DOMAIN ALERT: {domain} - {event}"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        f"Domain: {domain}",
        f"Event:  {event}",
        f"Time:   {timestamp}",
    ]
    if price is not None:
        lines.append(f"Price:  ${price:,.2f}")
    if action_url:
        lines.append(f"Action: {action_url}")
    if extra:
        lines.append(f"Detail: {extra}")

    body = "\n".join(lines)
    assert len(subject) > 0, "Subject must not be empty"
    assert len(body) > 0, "Body must not be empty"
    return (subject, body)


# ── CLI for Testing ──────────────────────────────────────────────────
def _run_test() -> int:
    """Send a test alert through all configured channels."""
    print("Domain Hunter -- Notification System Test")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    config = load_config()
    print(f"\nConfiguration:")
    print(f"  Email to:   {'CONFIGURED' if config.has_email else 'NOT SET'}")
    print(f"  ntfy topic: {config.ntfy_topic or 'NOT SET'}")
    print()

    subject, body = format_domain_alert(
        domain="test-notification.example.com",
        event="pendingDelete (TEST)",
        price=0.00,
        action_url="https://ntfy.sh/",
        extra="This is a test notification from Domain Hunter.",
    )

    results = send_alert(subject, body, priority="critical")

    print("\nResults:")
    all_ok = True
    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.channel}: {r.detail}")
        if not r.success:
            all_ok = False

    return 0 if all_ok else 1


def main() -> int:
    """CLI entry point."""
    if "--test" in sys.argv:
        return _run_test()
    print("Usage: python scripts/notify.py --test")
    print("  Or import: from scripts.notify import send_alert")
    return 0


if __name__ == "__main__":
    sys.exit(main())

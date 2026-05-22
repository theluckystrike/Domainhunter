"""ntfy.sh push notification client for Domain Hunter alerts.

Zero-cost, zero-account mobile push notifications via HTTP POST.
Subscribe to the topic in the ntfy.sh mobile app or at:
  https://ntfy.sh/dh-revenant-alerts

Topic can be overridden via the NTFY_TOPIC environment variable.

Usage (standalone):
    python clients/ntfy_client.py          # send test notification
    python clients/ntfy_client.py --test   # explicit test flag

Usage (library):
    from clients.ntfy_client import send_alert, send_domain_alert
    send_alert("pendingDelete", "ghostautonomy.com is dropping in 5 days")
    send_domain_alert(domain="ghost.com", event="pendingDelete",
                      urgency="IMMEDIATE", tier="critical")

Priority values accepted:
    "urgent"  - max priority (phone rings even on DND)
    "high"    - high priority
    "default" - normal priority
    "low"     - low priority
    "min"     - background only

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import os
import sys
from typing import Final

import httpx

# ── Constants (immutable) ─────────────────────────────────────────────
NTFY_DEFAULT_TOPIC: Final[str] = "dh-revenant-alerts"
NTFY_BASE_URL: Final[str] = "https://ntfy.sh/"
REQUEST_TIMEOUT: Final[float] = 10.0
MAX_TITLE_LEN: Final[int] = 256
MAX_MESSAGE_LEN: Final[int] = 4000

# Map Domain Hunter priority names to ntfy priority values
PRIORITY_MAP: Final[dict[str, str]] = {
    "critical": "urgent",
    "urgent":   "urgent",
    "high":     "high",
    "normal":   "default",
    "default":  "default",
    "medium":   "default",
    "low":      "low",
    "min":      "min",
}

# Tag sets per alert context
TAGS_DOMAIN_MATCH: Final[str] = "money_with_wings,domain"
TAGS_DROP_PENDING: Final[str] = "rotating_light,domain"
TAGS_DROP_AVAILABLE: Final[str] = "tada,domain"
TAGS_STATUS_CHANGE: Final[str] = "bell,domain"
TAGS_DEFAULT: Final[str] = "domain,loudspeaker"
TAGS_TEST: Final[str] = "white_check_mark,test"


def _get_topic() -> str:
    """Return active ntfy topic from env or default. Never empty."""
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        topic = os.environ.get("NOTIFY_NTFY_TOPIC", "").strip()
    return topic or NTFY_DEFAULT_TOPIC


def _build_url(topic: str) -> str:
    """Build ntfy POST URL for given topic."""
    assert topic and len(topic) > 0, "Topic must not be empty"
    assert not topic.startswith("http"), "Pass topic name, not full URL"
    return f"{NTFY_BASE_URL}{topic}"


def send_alert(
    title: str,
    message: str,
    priority: str = "default",
    tags: str = TAGS_DEFAULT,
) -> bool:
    """Send mobile push notification via ntfy.sh. Returns True on success.

    This is the low-level primitive. Prefer send_domain_alert() for
    domain-specific events with automatic priority/tag selection.

    Args:
        title:    Notification title shown in the app (max 256 chars).
        message:  Notification body text (max 4000 chars).
        priority: ntfy priority — "urgent", "high", "default", "low", "min".
                  Also accepts Domain Hunter names: "critical", "normal".
        tags:     Comma-separated ntfy emoji tag names.

    Returns:
        True if ntfy.sh returned HTTP 200, False on any error.
    """
    assert title and len(title) > 0, "Title must not be empty"
    assert message and len(message) > 0, "Message must not be empty"

    topic = _get_topic()
    url = _build_url(topic)
    ntfy_priority = PRIORITY_MAP.get(priority, "default")

    headers = {
        "Title":    title[:MAX_TITLE_LEN],
        "Priority": ntfy_priority,
        "Tags":     tags,
    }
    body = message[:MAX_MESSAGE_LEN].encode("utf-8")

    try:
        resp = httpx.post(url, content=body, headers=headers,
                          timeout=REQUEST_TIMEOUT)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def send_domain_alert(
    domain: str,
    event: str,
    urgency: str = "",
    tier: str = "",
    price: float | None = None,
    action_url: str = "",
) -> bool:
    """Send a formatted domain lifecycle alert via ntfy.sh.

    Automatically selects priority and tags based on the event type.
    Call this from drop_monitor.py and godaddy_monitor.py.

    Args:
        domain:     Domain name (e.g. "ghostautonomy.com").
        event:      Short event label (e.g. "pendingDelete", "MATCH_FOUND").
        urgency:    Urgency string from DropTransition (e.g. "IMMEDIATE").
        tier:       Domain tier: "critical", "high", "medium", "low".
        price:      Auction price in USD (optional).
        action_url: URL to open (DropCatch, GoDaddy auctions, etc.).

    Returns:
        True if ntfy.sh accepted the notification.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert event, "Event must not be empty"

    title, body, priority, tags = _format_domain_alert(
        domain, event, urgency, tier, price, action_url,
    )
    return send_alert(title, message=body, priority=priority, tags=tags)


def _format_domain_alert(
    domain: str,
    event: str,
    urgency: str,
    tier: str,
    price: float | None,
    action_url: str,
) -> tuple[str, str, str, str]:
    """Build (title, body, priority, tags) for a domain alert.

    Separated from send_domain_alert() to satisfy NASA P10 line limit.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert event, "Event required"

    # Select priority from tier / event type
    event_lower = event.lower()
    if tier in ("critical", "high") or "pendingdelete" in event_lower:
        priority = "high"
    elif "available" in event_lower or urgency.upper().startswith("IMMEDIATE"):
        priority = "urgent"
    elif "match" in event_lower or "found" in event_lower:
        priority = "high"
    else:
        priority = "default"

    # Select tag set from event type
    if "pendingdelete" in event_lower:
        tags = TAGS_DROP_PENDING
    elif "available" in event_lower:
        tags = TAGS_DROP_AVAILABLE
    elif "match" in event_lower or "found" in event_lower:
        tags = TAGS_DOMAIN_MATCH
    else:
        tags = TAGS_STATUS_CHANGE

    # Build title: keep under 60 chars for mobile readability
    title = f"{domain}: {event}"[:60]

    # Build body lines (bounded at 6)
    lines: list[str] = [f"Domain: {domain}", f"Event: {event}"]
    if urgency:
        lines.append(f"Urgency: {urgency}")
    if tier:
        lines.append(f"Tier: {tier}")
    if price is not None:
        lines.append(f"Price: ${price:,.2f}")
    if action_url:
        lines.append(f"Action: {action_url}")

    body = "\n".join(lines[:6])
    return title, body, priority, tags


# ── Standalone test ──────────────────────────────────────────────────
def _run_test() -> int:
    """Send a test notification to verify the ntfy.sh pipeline end-to-end.

    Prints the topic URL so you can open it in a browser to verify delivery.
    Returns 0 on success, 1 on failure.
    """
    topic = _get_topic()
    url = _build_url(topic)
    print("ntfy_client.py -- standalone test")
    print(f"  Topic : {topic}")
    print(f"  URL   : {url}")
    print(f"  Env NTFY_TOPIC        : {os.environ.get('NTFY_TOPIC', '(not set)')}")
    print(f"  Env NOTIFY_NTFY_TOPIC : {os.environ.get('NOTIFY_NTFY_TOPIC', '(not set)')}")
    print()

    ok = send_alert(
        title="Domain Hunter: ntfy test",
        message=(
            "ntfy_client.py wired successfully.\n"
            "If you see this on your phone, the mobile push pipeline works."
        ),
        priority="default",
        tags=TAGS_TEST,
    )

    if ok:
        print(f"  [OK] Notification sent.")
        print(f"  Verify at: https://ntfy.sh/{topic}")
        return 0

    print("  [FAIL] ntfy.sh POST failed.")
    print("  Check network connectivity.")
    return 1


if __name__ == "__main__":
    sys.exit(_run_test())

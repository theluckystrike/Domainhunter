"""Format domain status change alerts for Slack, desktop, and email channels.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
NASA Rule 5: >= 2 assertions per function.
"""
from __future__ import annotations

import html
import subprocess
from dataclasses import dataclass

_STATUS_EMOJI: dict[str, tuple[str, str]] = {
    "pendingDelete": ("\U0001f6a8", "BACKORDER NOW"),
    "redemptionPeriod": ("\u26a0\ufe0f", "30 DAYS TO DROP"),
}
_DEFAULT_EMOJI: tuple[str, str] = ("\U0001f4ca", "Status Update")


@dataclass(frozen=True)
class AlertData:
    """Immutable container for domain alert context."""
    domain: str
    old_status: str
    new_status: str
    etv: float
    max_bid: float
    registrar: str
    expiry: str
    drop_estimate: str


def format_slack_alert(
    domain: str, old_status: str, new_status: str, etv: float,
    max_bid: float, registrar: str, expiry: str, drop_estimate: str,
) -> str:
    """Return Slack mrkdwn-formatted status change message."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(new_status, str) and len(new_status) > 0, "new_status required"

    emoji, headline = _STATUS_EMOJI.get(new_status, _DEFAULT_EMOJI)
    lines: list[str] = [
        f"{emoji} *{headline}* {emoji}",
        "",
        f"*Domain:* `{domain}`",
        f"*Status:* {old_status} \u2192 {new_status}",
        f"*ETV:* ${etv:,.0f}",
        f"*Max Bid:* ${max_bid:,.0f}",
        f"*Registrar:* {registrar}",
        f"*Expiry:* {expiry}",
        f"*Drop Estimate:* {drop_estimate}",
    ]
    if new_status == "pendingDelete":
        lines.append("")
        lines.append(f":point_right: <https://www.dropcatch.com/snap/listing/{domain}|Place backorder on DropCatch>")

    result = "\n".join(lines)
    assert len(result) > 0, "formatted message must not be empty"
    return result


def format_desktop_alert(domain: str, new_status: str, etv: float) -> tuple[str, str]:
    """Return (title, body) tuple for macOS desktop notification."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(new_status, str) and len(new_status) > 0, "new_status required"

    emoji, headline = _STATUS_EMOJI.get(new_status, _DEFAULT_EMOJI)
    title = f"{emoji} {headline}: {domain}"
    body = f"Status: {new_status} | ETV: ${etv:,.0f}"
    assert len(title) > 0, "title must not be empty"
    assert len(body) > 0, "body must not be empty"
    return (title, body)


def format_email_alert(
    domain: str, old_status: str, new_status: str,
    etv: float, max_bid: float, drop_timeline: str,
) -> tuple[str, str]:
    """Return (subject, html_body) tuple for domain status change email."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(new_status, str) and len(new_status) > 0, "new_status required"

    _, headline = _STATUS_EMOJI.get(new_status, _DEFAULT_EMOJI)
    subject = f"[DomainHunter] {headline}: {domain}"
    safe_domain = html.escape(domain)
    dc_url = f"https://www.dropcatch.com/snap/listing/{safe_domain}"
    html_body = (
        "<html><body style='font-family:sans-serif;color:#222;'>"
        f"<h2 style='color:#c0392b;'>{headline}: {safe_domain}</h2>"
        f"<table style='border-collapse:collapse;'>"
        f"<tr><td><b>Domain</b></td><td>{safe_domain}</td></tr>"
        f"<tr><td><b>Status</b></td><td>{html.escape(old_status)} &rarr; {html.escape(new_status)}</td></tr>"
        f"<tr><td><b>ETV</b></td><td>${etv:,.0f}</td></tr>"
        f"<tr><td><b>Max Bid</b></td><td>${max_bid:,.0f}</td></tr>"
        f"<tr><td><b>Drop Timeline</b></td><td>{html.escape(drop_timeline)}</td></tr>"
        f"</table><h3>Action Items</h3><ul>"
        f"<li><a href='{dc_url}'>Place backorder on DropCatch</a></li>"
        f"<li>Verify ETV and backlink profile before bidding</li>"
        f"<li>Set calendar reminder for drop date</li>"
        f"</ul></body></html>"
    )
    assert len(subject) > 0, "subject must not be empty"
    assert "<html>" in html_body, "body must be valid HTML"
    return (subject, html_body)


def format_dropcatch_reminder(domain: str, max_bid: float) -> str:
    """Return plain-text reminder to place a DropCatch backorder."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(max_bid, (int, float)) and max_bid >= 0, "max_bid must be non-negative"

    dc_url = f"https://www.dropcatch.com/snap/listing/{domain}"
    reminder = (
        f"BACKORDER REMINDER: {domain}\n"
        f"Max bid: ${max_bid:,.0f}\n"
        f"Place backorder: {dc_url}\n\n"
        f"Steps:\n"
        f"1. Open {dc_url}\n"
        f"2. Place backorder with max bid ${max_bid:,.0f}\n"
        f"3. Confirm order and monitor auction"
    )
    assert len(reminder) > 0, "reminder must not be empty"
    assert dc_url in reminder, "reminder must contain DropCatch URL"
    return reminder


def send_desktop_notification(title: str, message: str) -> bool:
    """Send a macOS desktop notification via osascript. Returns True on success."""
    assert isinstance(title, str) and len(title) > 0, "title required"
    assert isinstance(message, str) and len(message) > 0, "message required"

    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, timeout=10,
        )
        sent_ok: bool = result.returncode == 0
        return sent_ok
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False

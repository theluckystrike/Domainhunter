#!/usr/bin/env python3
"""Sprint 24 — Drop Timeline with Lifecycle Phases and Action Windows.

Reads backorder_queue.json, calculates exact days until estimated drop,
determines domain lifecycle phase, and flags URGENT domains entering
pendingDelete within 14 days.

Domain lifecycle after expiry:
  Active -> clientRenewProhibited (day 0-30)
  clientRenewProhibited -> autoRenewPeriod (day 30-45)
  autoRenewPeriod -> redemptionPeriod (day 45-75)
  redemptionPeriod -> pendingDelete (day 75-80)
  pendingDelete -> Available (5-day window!)

Usage:
  python scripts/sprint24_drop_timeline.py

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_QUEUE_PATH: Final[Path] = _ROOT / "data" / "backorder_queue.json"
_DATA_DIR: Final[Path] = _ROOT / "data"
_TODAY: Final[str] = "2026-05-15"

# Lifecycle phase boundaries (days after expiry)
_PHASE_BOUNDARIES: Final[list[tuple[int, int, str]]] = [
    (0, 30, "clientRenewProhibited"),
    (30, 45, "autoRenewPeriod"),
    (45, 75, "redemptionPeriod"),
    (75, 80, "pendingDelete"),
    (80, 999, "available"),
]

# Monitoring cadence by days-until-drop
_MONITOR_THRESHOLDS: Final[list[tuple[int, str]]] = [
    (7, "URGENT: Place backorder NOW"),
    (14, "URGENT: Backorder imminent"),
    (30, "ACTION: Monitor daily"),
    (60, "ACTION: Monitor weekly"),
    (90, "ACTION: Monitor biweekly"),
    (999, "ACTION: Monitor monthly"),
]


def _load_queue() -> list[dict[str, Any]]:
    """Load backorder queue from JSON file."""
    assert _QUEUE_PATH.is_file(), f"Queue file not found: {_QUEUE_PATH}"
    with open(_QUEUE_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert "queue" in data, "Missing 'queue' key in backorder_queue.json"
    return data["queue"]


def _parse_today() -> datetime:
    """Parse today's date as timezone-aware datetime."""
    today = datetime.strptime(_TODAY, "%Y-%m-%d")
    today = today.replace(tzinfo=timezone.utc)
    assert today.year >= 2026, "Date sanity check failed"
    assert today.month >= 1 and today.month <= 12, "Month out of range"
    return today


def _days_until(today: datetime, drop_est: str) -> int | None:
    """Calculate exact days from today to estimated drop date.

    Returns None if drop_est is TBD or unparseable.
    """
    assert isinstance(drop_est, str), "drop_est must be string"
    if drop_est.upper() == "TBD" or len(drop_est) < 10:
        return None
    assert len(drop_est) >= 10, f"Invalid date format: {drop_est}"
    target = datetime.strptime(drop_est[:10], "%Y-%m-%d")
    target = target.replace(tzinfo=timezone.utc)
    delta = (target - today).days
    return delta


def _compute_lifecycle_phase(epp_status: str, days_left: int) -> str:
    """Determine current lifecycle phase from EPP status and days remaining."""
    assert isinstance(epp_status, str), "epp_status must be string"
    assert isinstance(days_left, int), "days_left must be int"
    # If EPP is already specific, trust it
    epp_lower = epp_status.lower()
    if "pendingdelete" in epp_lower:
        return "pendingDelete"
    if "redemption" in epp_lower:
        return "redemptionPeriod"
    if "autorenew" in epp_lower:
        return "autoRenewPeriod"
    if "clienthold" in epp_lower:
        return "clientHold (pre-pendingDelete)"
    if "clientrenew" in epp_lower:
        return "clientRenewProhibited"
    return epp_status


def _get_action(days_left: int) -> str:
    """Determine action based on days until drop."""
    assert isinstance(days_left, int), "days_left must be int"
    for threshold, action in _MONITOR_THRESHOLDS:
        if days_left <= threshold:
            return action
    assert False, "Unreachable: _MONITOR_THRESHOLDS must cover all values"
    return "ACTION: Monitor monthly"  # pragma: no cover


def _estimate_pending_delete_window(drop_est: str) -> tuple[str, str]:
    """Estimate the 5-day pendingDelete window before a domain drops.

    pendingDelete starts ~5 days before the drop date.
    """
    assert len(drop_est) >= 10, f"Invalid date: {drop_est}"
    from datetime import timedelta
    drop_dt = datetime.strptime(drop_est[:10], "%Y-%m-%d")
    pd_start = drop_dt - timedelta(days=5)
    pd_end = drop_dt
    assert pd_start < pd_end, "Window dates inverted"
    return pd_start.strftime("%Y-%m-%d"), pd_end.strftime("%Y-%m-%d")


def _is_urgent(days_left: int) -> bool:
    """Flag domain as urgent if pendingDelete within 14 days."""
    assert isinstance(days_left, int), "days_left must be int"
    # pendingDelete starts ~5 days before drop
    # So if drop is within 14+5=19 days, the pendingDelete window
    # starts within 14 days
    return days_left <= 19


def _build_timeline(queue: list[dict[str, Any]], today: datetime) -> list[dict[str, Any]]:
    """Build enriched timeline entries from queue."""
    assert len(queue) > 0, "Queue is empty"
    assert today.tzinfo is not None, "today must be timezone-aware"
    results: list[dict[str, Any]] = []
    tbd_results: list[dict[str, Any]] = []
    for i, entry in enumerate(queue):
        assert i < 1000, "Bounded loop guard"
        domain = entry["domain"]
        drop_est = entry["drop_est"]
        days_left = _days_until(today, drop_est)

        # Handle TBD domains separately
        if days_left is None:
            tbd_results.append({
                "domain": domain,
                "drop_est": "TBD",
                "days_until_drop": None,
                "lifecycle_phase": entry.get("epp_status", "unknown"),
                "epp_status": entry.get("epp_status", "unknown"),
                "pending_delete_window": {"start": "TBD", "end": "TBD"},
                "action": "ACTION: Needs WHOIS/RDAP probe for drop date",
                "urgent": False,
                "backorder_status": entry.get("backorder_status", "unknown"),
                "playbook": entry.get("playbook", ""),
                "etv": entry.get("etv", 0),
                "est_value_low": entry.get("est_value_low", 0),
                "est_value_high": entry.get("est_value_high", 0),
                "monitor_tier": entry.get("monitor_tier", "unknown"),
                "reaper_score": entry.get("reaper_score", 0),
            })
            continue

        phase = _compute_lifecycle_phase(entry.get("epp_status", "unknown"), days_left)
        action = _get_action(days_left)
        pd_start, pd_end = _estimate_pending_delete_window(drop_est)
        urgent = _is_urgent(days_left)
        results.append({
            "domain": domain,
            "drop_est": drop_est,
            "days_until_drop": days_left,
            "lifecycle_phase": phase,
            "epp_status": entry.get("epp_status", "unknown"),
            "pending_delete_window": {"start": pd_start, "end": pd_end},
            "action": action,
            "urgent": urgent,
            "backorder_status": entry.get("backorder_status", "unknown"),
            "playbook": entry.get("playbook", ""),
            "etv": entry.get("etv", 0),
            "est_value_low": entry.get("est_value_low", 0),
            "est_value_high": entry.get("est_value_high", 0),
            "monitor_tier": entry.get("monitor_tier", "unknown"),
            "reaper_score": entry.get("reaper_score", 0),
        })
    results.sort(key=lambda x: x["days_until_drop"])
    # Append TBD entries at the end
    results.extend(tbd_results)
    return results


def _format_ascii_timeline(entries: list[dict[str, Any]], today_str: str) -> str:
    """Format timeline as readable ASCII output."""
    assert len(entries) > 0, "No entries to format"
    assert len(today_str) == 10, "today_str must be YYYY-MM-DD"
    lines: list[str] = []
    lines.append(f"\nTODAY: {today_str}")
    lines.append("=" * 90)
    lines.append("  DOMAIN HUNTER — DROP TIMELINE (Sprint 24)")
    lines.append(f"  Generated: {today_str}")
    lines.append(f"  Domains tracked: {len(entries)}")
    urgent_count = sum(1 for e in entries if e["urgent"])
    if urgent_count > 0:
        lines.append(f"  *** {urgent_count} URGENT domain(s) entering pendingDelete within 14 days ***")
    lines.append("=" * 90)

    # Header
    lines.append("")
    lines.append(f"  {'Date':<12} {'Domain':<26} {'Days':>5}  {'Phase':<28} {'Action'}")
    lines.append(f"  {'─' * 84}")

    # Entries
    for i, e in enumerate(entries):
        assert i < 1000, "Bounded loop guard"
        if e["drop_est"] == "TBD" or e["days_until_drop"] is None:
            date_str = "TBD"
            days_str = "  TBD"
        else:
            drop_dt = datetime.strptime(e["drop_est"][:10], "%Y-%m-%d")
            date_str = drop_dt.strftime("%b %d")
            days_str = f"{e['days_until_drop']:>5}d"
        flag = " ***" if e["urgent"] else ""
        etv_str = f"ETV ${e['etv']:,}" if e['etv'] > 0 else ""
        lines.append(
            f"  {date_str:<12} {e['domain']:<26} {days_str} "
            f" [{e['action']}]{flag}"
        )
        if etv_str:
            lines.append(f"  {'':<12} {'':<26} {'':<5}   Phase: {e['lifecycle_phase']}, {etv_str}")
        else:
            lines.append(f"  {'':<12} {'':<26} {'':<5}   Phase: {e['lifecycle_phase']}")

    # Summary
    lines.append(f"\n  {'─' * 84}")
    lines.append("  BACKORDER ACTION WINDOWS (pendingDelete = 5-day catch window):")
    lines.append(f"  {'─' * 84}")
    for i, e in enumerate(entries):
        assert i < 1000, "Bounded loop guard"
        pd = e["pending_delete_window"]
        if pd["start"] == "TBD":
            pd_str = "TBD (needs RDAP probe)"
        else:
            pd_str = f"{pd['start']} -> {pd['end']}"
        status = "*** URGENT ***" if e["urgent"] else "Waiting"
        lines.append(
            f"  {e['domain']:<26} pendingDelete: {pd_str}  [{status}]"
        )
    lines.append(f"\n{'=' * 90}")
    return "\n".join(lines)


def _save_json(entries: list[dict[str, Any]], today_str: str) -> str:
    """Save timeline to JSON file."""
    assert len(entries) > 0, "No entries to save"
    out_path = _DATA_DIR / "sprint24_drop_timeline.json"
    output = {
        "generated_at": f"{today_str}T00:00:00Z",
        "sprint": "24",
        "today": today_str,
        "total_domains": len(entries),
        "urgent_count": sum(1 for e in entries if e["urgent"]),
        "timeline": entries,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
    assert out_path.is_file(), f"Failed to write: {out_path}"
    return str(out_path)


def main() -> None:
    """Run drop timeline generator."""
    print("Sprint 24 — Drop Timeline Generator", file=sys.stderr)
    today = _parse_today()
    today_str = _TODAY
    queue = _load_queue()
    print(f"  Loaded {len(queue)} domains from backorder queue", file=sys.stderr)

    timeline = _build_timeline(queue, today)
    ascii_output = _format_ascii_timeline(timeline, today_str)
    print(ascii_output)

    out_path = _save_json(timeline, today_str)
    print(f"\n  Saved to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

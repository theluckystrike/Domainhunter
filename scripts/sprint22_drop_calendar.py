#!/usr/bin/env python3
"""Sprint 22 — Agent 5: Drop Calendar Priority Queue.

Reads monitored_domains.json + reaper results, sorts by estimated
pendingDelete date, outputs a priority queue showing what backorders
are needed and when.

Domain lifecycle: active → clientRenewProhibited → autoRenewPeriod →
  redemptionPeriod → pendingDelete → available (5-day window)

Usage:
  python scripts/sprint22_drop_calendar.py
  python scripts/sprint22_drop_calendar.py --weeks 8     # Show next 8 weeks
  python scripts/sprint22_drop_calendar.py --json         # JSON output

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_MONITORED_PATH: Final[str] = os.path.join(_ROOT, "scripts", "monitored_domains.json")
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")

# Approximate days from EPP status to pendingDelete
_EPP_TO_DROP_DAYS: Final[dict[str, int]] = {
    "pendingDelete": 5,          # Already dropping, 5-day window
    "redemptionPeriod": 35,      # ~30 days redemption + 5 days pending
    "autoRenewPeriod": 75,       # ~45 days auto-renew + 30 redemption
    "clientHold": 45,            # Could drop any time, estimate ~45 days
    "clientRenewProhibited": 90, # Will enter autoRenew after expiry
    "active": 365,               # Not dropping soon
}

# Priority urgency labels
_URGENCY: Final[dict[str, str]] = {
    "pendingDelete": "IMMINENT",
    "redemptionPeriod": "SOON",
    "autoRenewPeriod": "WEEKS",
    "clientHold": "WATCH",
    "clientRenewProhibited": "MONTHS",
    "active": "MONITOR",
}


def _load_monitored() -> list[dict[str, Any]]:
    """Load all monitored domains with tier info."""
    assert os.path.isfile(_MONITORED_PATH), f"not found: {_MONITORED_PATH}"
    with open(_MONITORED_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert "domains" in data
    results: list[dict[str, Any]] = []
    for tier, entries in data["domains"].items():
        for entry in entries:
            entry["monitor_tier"] = tier
            results.append(entry)
    return results


def _load_reaper_data() -> dict[str, dict[str, Any]]:
    """Load latest reaper output for EPP status + scoring data."""
    assert os.path.isdir(_DATA_DIR), f"data dir missing: {_DATA_DIR}"
    candidates = sorted(
        [f for f in os.listdir(_DATA_DIR)
         if f.startswith("startup_reaper_") and f.endswith(".json")
         and not f.startswith("startup_reaper_existing")],
        reverse=True,
    )
    if not candidates:
        return {}
    path = os.path.join(_DATA_DIR, candidates[0])
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {r["domain"]: r for r in data.get("results", [])}


def _estimate_drop_date(entry: dict[str, Any], reaper: dict[str, Any] | None) -> datetime:
    """Estimate when a domain will become available for registration."""
    assert isinstance(entry, dict) and "domain" in entry
    assert reaper is None or isinstance(reaper, dict)
    now = datetime.now(timezone.utc)
    notes = entry.get("notes", "")

    # Try to parse explicit dates from notes (e.g., "~Jun 26", "Jul 6")
    import re
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"(?:~?\s*)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})", notes, re.I)
    if m:
        month_num = month_map.get(m.group(1).lower()[:3], 0)
        day = int(m.group(2))
        if month_num > 0:
            year = now.year if month_num >= now.month else now.year + 1
            return datetime(year, month_num, day, tzinfo=timezone.utc)

    # Try to parse expiry date from reaper data
    if reaper and reaper.get("expiry_date"):
        try:
            raw = reaper["expiry_date"].replace("Z", "+00:00")
            exp = datetime.fromisoformat(raw)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            epp = reaper.get("epp_status", "active")
            add_days = _EPP_TO_DROP_DAYS.get(epp, 90)
            return exp + timedelta(days=add_days)
        except (ValueError, TypeError):
            pass

    # Try expiry from notes (e.g., "expires 2026-09-13")
    m2 = re.search(r"expires?\s+(\d{4}-\d{2}-\d{2})", notes)
    if m2:
        try:
            exp = datetime.fromisoformat(m2.group(1))
            return exp.replace(tzinfo=timezone.utc) + timedelta(days=75)
        except (ValueError, TypeError):
            pass

    # Fallback: far future
    return now + timedelta(days=999)


def _get_epp(entry: dict[str, Any], reaper: dict[str, Any] | None) -> str:
    """Extract EPP status from entry notes or reaper data."""
    assert isinstance(entry, dict)
    assert reaper is None or isinstance(reaper, dict)
    if reaper and reaper.get("epp_status"):
        return reaper["epp_status"]
    notes = entry.get("notes", "").lower()
    for epp in _EPP_TO_DROP_DAYS:
        if epp.lower() in notes:
            return epp
    if "dns dead" in notes:
        return "clientHold"
    return "unknown"


def _format_week_section(
    week_entries: list[dict[str, Any]], week_num: int,
    week_start: datetime, week_end: datetime,
) -> list[str]:
    """Format a single week's entries for the drop calendar."""
    assert isinstance(week_entries, list) and len(week_entries) > 0
    assert week_num >= 1
    lines: list[str] = []
    lines.append(f"\n  WEEK {week_num}: {week_start.strftime('%b %d')} — {week_end.strftime('%b %d')}")
    lines.append(f"  {'─' * 94}")
    hdr = (f"  {'Domain':<28} {'Drop Est':>10}  {'EPP':<22} {'Tier':<8} "
           f"{'Urgency':<10} {'ETV':>7}  {'MaxBid':>7}")
    lines.append(hdr)
    lines.append(f"  {'─' * 94}")
    for e in sorted(week_entries, key=lambda x: x["est_drop"]):
        lines.append(
            f"  {e['domain']:<28} {e['est_drop'].strftime('%Y-%m-%d'):>10}  "
            f"{e['epp']:<22} {e['monitor_tier']:<8} {e['urgency']:<10} "
            f"${e.get('etv', 0):>6}  ${e.get('max_bid', 0):>6}"
        )
    return lines


def _format_calendar(entries: list[dict[str, Any]], weeks: int) -> str:
    """Format drop calendar as ASCII table grouped by week."""
    assert isinstance(entries, list)
    assert isinstance(weeks, int) and 0 < weeks <= 52
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(weeks=weeks)
    in_window = [e for e in entries if e["est_drop"] <= cutoff]
    past_due = [e for e in entries if e["est_drop"] < now]

    lines: list[str] = ["=" * 100]
    lines.append("  DOMAIN HUNTER — DROP CALENDAR (Sprint 22)")
    lines.append(f"  Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"  Window: next {weeks} weeks ({now.strftime('%b %d')} -> {cutoff.strftime('%b %d, %Y')})")
    lines.append(f"  Total monitored: {len(entries)}, dropping in window: {len(in_window)}")
    lines.append("=" * 100)

    if past_due:
        lines.append(f"\n  *** OVERDUE ({len(past_due)} domains may have already dropped!) ***")
        for e in past_due:
            lines.append(f"    {e['domain']:<28} est={e['est_drop'].strftime('%Y-%m-%d')}  "
                         f"epp={e['epp']:<22} tier={e['monitor_tier']:<8} "
                         f"urgency={e['urgency']}")

    for w in range(weeks):
        week_start = now + timedelta(weeks=w)
        week_end = week_start + timedelta(weeks=1)
        week_entries = [e for e in in_window if week_start <= e["est_drop"] < week_end]
        if week_entries:
            lines.extend(_format_week_section(week_entries, w + 1, week_start, week_end))

    need_backorder = [e for e in in_window
                      if e["urgency"] in ("IMMINENT", "SOON", "WEEKS")
                      and e.get("max_bid", 0) > 0]
    if need_backorder:
        lines.append(f"\n  BACKORDER RECOMMENDATIONS ({len(need_backorder)} domains)")
        lines.append(f"  {'─' * 94}")
        for e in need_backorder:
            lines.append(f"    -> {e['domain']:<26} urgency={e['urgency']:<10} "
                         f"est_drop={e['est_drop'].strftime('%Y-%m-%d')}  "
                         f"max_bid=${e.get('max_bid', 0)}")
        lines.append(f"\n  Total backorder cost: ${len(need_backorder) * 10.99:.2f} "
                     f"(Dynadot charges only on successful catch)")

    lines.append("\n" + "=" * 100)
    return "\n".join(lines)


def main() -> None:
    """Run drop calendar."""
    import argparse
    parser = argparse.ArgumentParser(description="Sprint 22: Drop Calendar Priority Queue")
    parser.add_argument("--weeks", type=int, default=12, help="Lookahead window in weeks (default: 12)")
    parser.add_argument("--json", action="store_true", help="JSON output instead of ASCII")
    args = parser.parse_args()
    assert 0 < args.weeks <= 52, f"weeks must be 1-52, got {args.weeks}"

    print("Sprint 22 — Agent 5: Drop Calendar", file=sys.stderr)

    monitored = _load_monitored()
    assert len(monitored) > 0, "No monitored domains loaded"
    reaper_data = _load_reaper_data()
    print(f"  Loaded {len(monitored)} monitored domains, {len(reaper_data)} reaper entries", file=sys.stderr)

    # Enrich with drop estimates
    enriched: list[dict[str, Any]] = []
    for entry in monitored:
        domain = entry["domain"]
        reaper = reaper_data.get(domain)
        epp = _get_epp(entry, reaper)
        est_drop = _estimate_drop_date(entry, reaper)
        urgency = _URGENCY.get(epp, "UNKNOWN")

        aware_drop = est_drop if est_drop.tzinfo else est_drop.replace(tzinfo=timezone.utc)
        enriched.append({
            **entry,
            "epp": epp,
            "est_drop": aware_drop,
            "urgency": urgency,
            "days_to_drop": max(0, (aware_drop - datetime.now(timezone.utc)).days),
        })

    enriched.sort(key=lambda x: x["est_drop"])

    if args.json:
        # JSON output
        for e in enriched:
            e["est_drop"] = e["est_drop"].isoformat()
        json.dump(enriched, sys.stdout, indent=2, ensure_ascii=False)
    else:
        print(f"\n{_format_calendar(enriched, args.weeks)}")

    # Save to data dir
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(_DATA_DIR, f"sprint22_drop_calendar_{date_str}.json")
    serializable = []
    for e in enriched:
        entry = dict(e)
        if isinstance(entry.get("est_drop"), datetime):
            entry["est_drop"] = entry["est_drop"].isoformat()
        serializable.append(entry)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

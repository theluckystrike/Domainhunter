#!/usr/bin/env python3
"""Domain Hunter -- Monitoring Health Check (Sprint 23).

Verifies:
  1. Log analysis: recent runs, ERROR lines, time since last success.
  2. Cron health: expected crontab entries exist.
  3. Domain status: backorder queue summary, closest drops.
  4. File freshness: key data files aren't stale.
  5. Heartbeat: run_drop_monitor.sh / run_startup_reaper.sh touch files.

Run:   python scripts/sprint23_monitoring_check.py
Cron:  0 9 * * * cd ~/Desktop/domainhunter && python scripts/sprint23_monitoring_check.py

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Final

# -- Constants (immutable) ---------------------------------------------------
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "scripts"

BACKORDER_QUEUE_PATH: Final[Path] = DATA_DIR / "backorder_queue.json"
MONITORED_DOMAINS_PATH: Final[Path] = SCRIPTS_DIR / "monitored_domains.json"

DROP_MONITOR_HEARTBEAT: Final[Path] = LOG_DIR / ".drop_monitor_heartbeat"
STARTUP_REAPER_HEARTBEAT: Final[Path] = LOG_DIR / ".startup_reaper_heartbeat"

# Staleness thresholds
HEARTBEAT_STALE_HOURS: Final[int] = 8       # drop_monitor runs every 6h
REAPER_HEARTBEAT_STALE_DAYS: Final[int] = 8  # startup_reaper runs weekly
MONITORED_DOMAINS_STALE_DAYS: Final[int] = 7
REAPER_OUTPUT_STALE_DAYS: Final[int] = 7

# Log scan limits
MAX_LOG_FILES: Final[int] = 50
MAX_ERROR_LINES: Final[int] = 20
MAX_QUEUE_DISPLAY: Final[int] = 10

# Expected cron patterns (substrings to match in crontab output)
EXPECTED_CRON_ENTRIES: Final[tuple[dict[str, str], ...]] = (
    {
        "label": "drop_monitor --tier critical (every 6h)",
        "pattern": "run_drop_monitor.sh --tier critical",
    },
    {
        "label": "drop_monitor --tier all (daily)",
        "pattern": "run_drop_monitor.sh --tier all",
    },
    {
        "label": "startup_reaper (weekly Monday)",
        "pattern": "run_startup_reaper.sh",
    },
)


# -- Status helpers ----------------------------------------------------------
@dataclass(frozen=True)
class CheckResult:
    """Single health check line item."""
    status: str   # OK, WARN, FAIL
    label: str
    detail: str


@dataclass
class HealthReport:
    """Accumulates check results across all sections."""
    sections: dict[str, list[CheckResult]] = field(default_factory=dict)

    def add(self, section: str, status: str, label: str, detail: str = "") -> None:
        assert status in ("OK", "WARN", "FAIL"), f"Bad status: {status}"
        assert len(label) > 0, "Label must not be empty"
        self.sections.setdefault(section, [])
        self.sections[section].append(CheckResult(status, label, detail))


def _file_age(path: Path) -> timedelta | None:
    """Return age of a file, or None if missing."""
    assert isinstance(path, Path), "path must be Path"
    assert len(str(path)) > 0, "path must not be empty"
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - mtime


def _format_age(td: timedelta) -> str:
    """Human-readable age string."""
    assert isinstance(td, timedelta), "Expected timedelta"
    assert td.total_seconds() >= 0, "age cannot be negative"
    total_seconds = int(td.total_seconds())
    if total_seconds < 3600:
        return f"{total_seconds // 60}m ago"
    if total_seconds < 86400:
        return f"{total_seconds // 3600}h ago"
    return f"{total_seconds // 86400}d ago"


# -- Section 1: Log Analysis ------------------------------------------------
def _find_latest_log(prefix: str) -> Path | None:
    """Find the most recently modified log file matching prefix."""
    assert isinstance(prefix, str), "prefix must be str"
    assert len(prefix) > 0, "prefix must not be empty"
    if not LOG_DIR.is_dir():
        return None
    candidates = sorted(
        LOG_DIR.glob(f"{prefix}*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _count_errors_in_log(path: Path) -> list[str]:
    """Extract ERROR lines from a log file (bounded).

    Matches lines containing 'ERROR' (uppercase) or 'FAILED' or 'Traceback'.
    Excludes known false-positives like rdap_error_fallback_whois (warning-level).
    """
    assert path.exists(), f"Log missing: {path}"
    assert isinstance(path, Path)
    # Patterns that look like errors but are actually warning-level fallbacks
    false_positive_patterns: tuple[str, ...] = (
        "rdap_error_fallback_whois",
        "rdap_blocked_fallback_whois",
        "rdap_404_but_whois_found",
    )
    errors: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 5000:  # fixed loop bound
                break
            stripped = line.strip()
            # Match real errors only
            is_error = (
                "ERROR" in line
                or "FAILED" in line
                or "Traceback" in line
                or "exit=1" in line
                or "exit=2" in line
            )
            if not is_error:
                continue
            # Exclude known false-positive patterns
            is_fp = any(fp in stripped for fp in false_positive_patterns)
            if is_fp:
                continue
            errors.append(stripped[:200])
            if len(errors) >= MAX_ERROR_LINES:
                break
    return errors


def check_logs(report: HealthReport) -> None:
    """Analyze recent logs for drop_monitor and startup_reaper."""
    section = "Log Analysis"

    # Drop monitor logs
    latest_dm = _find_latest_log("drop_monitor_")
    if latest_dm is None:
        report.add(section, "FAIL", "drop_monitor logs", "No log files found")
    else:
        age = _file_age(latest_dm)
        assert age is not None
        age_str = _format_age(age)
        if age > timedelta(hours=HEARTBEAT_STALE_HOURS):
            report.add(section, "WARN", "drop_monitor last run",
                       f"{latest_dm.name} ({age_str}) -- expected within {HEARTBEAT_STALE_HOURS}h")
        else:
            report.add(section, "OK", "drop_monitor last run",
                       f"{latest_dm.name} ({age_str})")
        errors = _count_errors_in_log(latest_dm)
        if errors:
            report.add(section, "WARN", "drop_monitor errors",
                       f"{len(errors)} error(s): {errors[0][:120]}")
        else:
            report.add(section, "OK", "drop_monitor errors", "None")

    # Startup reaper logs
    latest_sr = _find_latest_log("startup_reaper_")
    if latest_sr is None:
        report.add(section, "WARN", "startup_reaper logs",
                   "No log files found (may not have run yet)")
    else:
        age = _file_age(latest_sr)
        assert age is not None
        age_str = _format_age(age)
        if age > timedelta(days=REAPER_HEARTBEAT_STALE_DAYS):
            report.add(section, "WARN", "startup_reaper last run",
                       f"{latest_sr.name} ({age_str}) -- expected within {REAPER_HEARTBEAT_STALE_DAYS}d")
        else:
            report.add(section, "OK", "startup_reaper last run",
                       f"{latest_sr.name} ({age_str})")
        errors = _count_errors_in_log(latest_sr)
        if errors:
            report.add(section, "WARN", "startup_reaper errors",
                       f"{len(errors)} error(s): {errors[0][:120]}")
        else:
            report.add(section, "OK", "startup_reaper errors", "None")

    # Cron log files (appended by cron, not timestamped)
    for cron_log_name in ("cron_critical.log", "cron_all.log", "cron_reaper.log"):
        cron_log = LOG_DIR / cron_log_name
        if cron_log.exists():
            age = _file_age(cron_log)
            assert age is not None
            errors = _count_errors_in_log(cron_log)
            if errors:
                report.add(section, "WARN", f"cron log {cron_log_name}",
                           f"{len(errors)} error(s), last modified {_format_age(age)}")
            else:
                report.add(section, "OK", f"cron log {cron_log_name}",
                           f"Clean, last modified {_format_age(age)}")


# -- Section 2: Cron Health Check -------------------------------------------
def check_cron(report: HealthReport) -> None:
    """Verify expected crontab entries exist."""
    assert isinstance(report, HealthReport)
    assert len(EXPECTED_CRON_ENTRIES) > 0
    section = "Cron Health"

    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        crontab_text = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        report.add(section, "FAIL", "crontab", "Could not read crontab")
        return

    if not crontab_text.strip():
        report.add(section, "FAIL", "crontab", "Empty crontab")
        return

    for entry in EXPECTED_CRON_ENTRIES:
        assert "label" in entry and "pattern" in entry
        if entry["pattern"] in crontab_text:
            report.add(section, "OK", entry["label"], "Found in crontab")
        else:
            report.add(section, "FAIL", entry["label"], "MISSING from crontab")


# -- Section 3: Domain Status Summary ---------------------------------------
def _check_drop_schedule(
    report: HealthReport, section: str, queue: list[dict[str, Any]],
) -> None:
    """Check closest drop dates and upcoming schedule."""
    assert isinstance(queue, list)
    assert isinstance(section, str)
    now = datetime.now(timezone.utc).date()
    drops_with_date: list[tuple[str, int]] = []
    for item in queue[:MAX_QUEUE_DISPLAY * 2]:
        drop_est = item.get("drop_est", "")
        domain = item.get("domain", "unknown")
        if drop_est:
            try:
                drop_date = datetime.strptime(drop_est, "%Y-%m-%d").date()
                drops_with_date.append((domain, (drop_date - now).days))
            except ValueError:
                continue

    drops_with_date.sort(key=lambda x: x[1])
    if not drops_with_date:
        report.add(section, "WARN", "Drop dates", "No parseable drop_est dates")
        return

    closest = drops_with_date[0]
    if closest[1] <= 0:
        report.add(section, "FAIL", "Closest drop",
                   f"{closest[0]} -- PAST DUE by {abs(closest[1])}d!")
    elif closest[1] <= 7:
        report.add(section, "WARN", "Closest drop",
                   f"{closest[0]} in {closest[1]}d -- ACTION NEEDED")
    else:
        report.add(section, "OK", "Closest drop", f"{closest[0]} in {closest[1]}d")

    upcoming_lines: list[str] = []
    for domain, days in drops_with_date[:4]:
        tag = "OVERDUE" if days <= 0 else f"{days}d"
        upcoming_lines.append(f"{domain} ({tag})")
    report.add(section, "OK", "Upcoming drops", " | ".join(upcoming_lines))


def check_domain_queue(report: HealthReport) -> None:
    """Read backorder_queue.json and report status."""
    assert isinstance(report, HealthReport)
    section = "Domain Queue"

    if not BACKORDER_QUEUE_PATH.exists():
        report.add(section, "FAIL", "backorder_queue.json", "File not found")
        return

    try:
        with open(BACKORDER_QUEUE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        report.add(section, "FAIL", "backorder_queue.json", f"Parse error: {exc}")
        return

    queue = data.get("queue", [])
    assert isinstance(queue, list), "queue must be a list"
    report.add(section, "OK", "Queue size", f"{len(queue)} domain(s)")

    _check_drop_schedule(report, section, queue)

    budget = data.get("budget_summary", {})
    if budget:
        balance = budget.get("current_balance", "?")
        exposure = budget.get("budget_exposure_if_all_caught", "?")
        if isinstance(balance, (int, float)) and isinstance(exposure, (int, float)):
            if balance < exposure:
                report.add(section, "WARN", "Budget",
                           f"${balance:.2f} balance < ${exposure:.2f} exposure -- top up needed")
            else:
                report.add(section, "OK", "Budget",
                           f"${balance:.2f} balance, ${exposure:.2f} exposure")

    tier_counts: dict[str, int] = {}
    for item in queue[:500]:
        tier = item.get("monitor_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    tier_str = ", ".join(f"{t}: {c}" for t, c in sorted(tier_counts.items()))
    if tier_str:
        report.add(section, "OK", "Tier breakdown", tier_str)


# -- Section 4: File Freshness Check ----------------------------------------
def check_file_freshness(report: HealthReport) -> None:
    """Verify key data files aren't stale."""
    assert isinstance(report, HealthReport)
    assert isinstance(DATA_DIR, Path)
    section = "File Freshness"

    # monitored_domains.json
    age = _file_age(MONITORED_DOMAINS_PATH)
    if age is None:
        report.add(section, "FAIL", "monitored_domains.json", "File not found")
    elif age > timedelta(days=MONITORED_DOMAINS_STALE_DAYS):
        report.add(section, "WARN", "monitored_domains.json",
                   f"Stale ({_format_age(age)}) -- expected update within {MONITORED_DOMAINS_STALE_DAYS}d")
    else:
        report.add(section, "OK", "monitored_domains.json", _format_age(age))

    # backorder_queue.json
    age = _file_age(BACKORDER_QUEUE_PATH)
    if age is None:
        report.add(section, "FAIL", "backorder_queue.json", "File not found")
    elif age > timedelta(days=3):
        report.add(section, "WARN", "backorder_queue.json",
                   f"Stale ({_format_age(age)})")
    else:
        report.add(section, "OK", "backorder_queue.json", _format_age(age))

    # Latest startup_reaper output (data/startup_reaper_*.json)
    reaper_outputs = sorted(
        DATA_DIR.glob("startup_reaper_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not reaper_outputs:
        report.add(section, "WARN", "startup_reaper output", "No output files found")
    else:
        latest = reaper_outputs[0]
        age = _file_age(latest)
        assert age is not None
        if age > timedelta(days=REAPER_OUTPUT_STALE_DAYS):
            report.add(section, "WARN", "startup_reaper output",
                       f"{latest.name} is stale ({_format_age(age)})")
        else:
            report.add(section, "OK", "startup_reaper output",
                       f"{latest.name} ({_format_age(age)})")

    # drop_monitor.db
    db_path = SCRIPTS_DIR / "drop_monitor.db"
    age = _file_age(db_path)
    if age is None:
        report.add(section, "WARN", "drop_monitor.db", "Not found")
    elif age > timedelta(days=2):
        report.add(section, "WARN", "drop_monitor.db",
                   f"Stale ({_format_age(age)})")
    else:
        report.add(section, "OK", "drop_monitor.db", _format_age(age))


# -- Section 5: Heartbeat Check ---------------------------------------------
def check_heartbeats(report: HealthReport) -> None:
    """Verify heartbeat touchfiles from run scripts."""
    assert isinstance(report, HealthReport)
    assert isinstance(DROP_MONITOR_HEARTBEAT, Path)
    section = "Heartbeat"

    # Drop monitor heartbeat
    age = _file_age(DROP_MONITOR_HEARTBEAT)
    if age is None:
        report.add(section, "WARN", "drop_monitor heartbeat",
                   "No heartbeat file -- run_drop_monitor.sh may not have completed yet")
    elif age > timedelta(hours=HEARTBEAT_STALE_HOURS):
        report.add(section, "WARN", "drop_monitor heartbeat",
                   f"Stale ({_format_age(age)}) -- expected within {HEARTBEAT_STALE_HOURS}h")
    else:
        report.add(section, "OK", "drop_monitor heartbeat", _format_age(age))

    # Startup reaper heartbeat
    age = _file_age(STARTUP_REAPER_HEARTBEAT)
    if age is None:
        report.add(section, "WARN", "startup_reaper heartbeat",
                   "No heartbeat file -- run_startup_reaper.sh may not have completed yet")
    elif age > timedelta(days=REAPER_HEARTBEAT_STALE_DAYS):
        report.add(section, "WARN", "startup_reaper heartbeat",
                   f"Stale ({_format_age(age)}) -- expected within {REAPER_HEARTBEAT_STALE_DAYS}d")
    else:
        report.add(section, "OK", "startup_reaper heartbeat", _format_age(age))


# -- Report Printer ----------------------------------------------------------
STATUS_ICON: Final[dict[str, str]] = {
    "OK": "[OK]  ",
    "WARN": "[WARN]",
    "FAIL": "[FAIL]",
}


def print_report(report: HealthReport) -> int:
    """Print formatted health check report. Returns exit code."""
    assert isinstance(report, HealthReport)
    assert len(report.sections) > 0, "no check sections in report"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'=' * 70}")
    print(f"  DOMAIN HUNTER -- MONITORING HEALTH CHECK")
    print(f"  {now_str}")
    print(f"{'=' * 70}")

    total_ok = 0
    total_warn = 0
    total_fail = 0

    for section_name, checks in report.sections.items():
        print(f"\n--- {section_name} ---")
        for check in checks:
            icon = STATUS_ICON.get(check.status, "[??]  ")
            detail_str = f" -- {check.detail}" if check.detail else ""
            print(f"  {icon} {check.label}{detail_str}")
            if check.status == "OK":
                total_ok += 1
            elif check.status == "WARN":
                total_warn += 1
            else:
                total_fail += 1

    print(f"\n{'=' * 70}")
    print(f"  SUMMARY: {total_ok} OK, {total_warn} WARN, {total_fail} FAIL")
    if total_fail > 0:
        print(f"  STATUS: UNHEALTHY -- {total_fail} failure(s) need attention")
    elif total_warn > 0:
        print(f"  STATUS: DEGRADED -- {total_warn} warning(s)")
    else:
        print(f"  STATUS: HEALTHY")
    print(f"{'=' * 70}\n")

    return 2 if total_fail > 0 else (1 if total_warn > 0 else 0)


# -- Main --------------------------------------------------------------------
def main() -> int:
    """Run all health checks and print report."""
    assert isinstance(PROJECT_ROOT, Path)
    assert PROJECT_ROOT.is_dir(), f"project root missing: {PROJECT_ROOT}"
    report = HealthReport()

    check_logs(report)
    check_cron(report)
    check_domain_queue(report)
    check_file_freshness(report)
    check_heartbeats(report)

    return print_report(report)


if __name__ == "__main__":
    sys.exit(main())

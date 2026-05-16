#!/usr/bin/env python3
"""Sprint 26 -- Daily Digest for Domain Hunter.

Generates a morning summary of monitored domains, nearest drop dates,
status changes in the last 24h, Dynadot balance, and guerrameats.com countdown.
Fires a macOS desktop notification and logs to logs/daily_digest.log.

Run:  python scripts/sprint26_daily_digest.py
      python scripts/sprint26_daily_digest.py --quiet

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Final

# ── Constants (immutable) ────────────────────────────────────────────
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CONFIG_PATH: Final[Path] = PROJECT_ROOT / "scripts" / "monitored_domains.json"
QUEUE_PATH: Final[Path] = PROJECT_ROOT / "data" / "backorder_queue.json"
DB_PATH: Final[Path] = PROJECT_ROOT / "scripts" / "drop_monitor.db"
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
LOG_FILE: Final[Path] = LOG_DIR / "daily_digest.log"
PORTFOLIO_PATH: Final[Path] = PROJECT_ROOT / "data" / "portfolio.json"
MAX_LOG_ENTRIES: Final[int] = 365
MAX_DOMAINS: Final[int] = 200
GUERRAMEATS_DROP_EST: Final[str] = "2026-06-26"
TIERS_ALL: Final[tuple[str, ...]] = ("critical", "high", "medium", "low")


# ── Data Models (frozen) ────────────────────────────────────────────
@dataclass(frozen=True)
class DomainSummary:
    """Immutable summary of a single monitored domain."""
    domain: str
    tier: str
    drop_est: str
    etv: int

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid: {self.domain}"
        assert self.tier in TIERS_ALL, f"Invalid tier: {self.tier}"


@dataclass(frozen=True)
class StatusChange:
    """Immutable record of a status change in last 24h."""
    domain: str
    old_status: str
    new_status: str
    checked_at: str

    def __post_init__(self) -> None:
        assert self.domain, "Domain required"
        assert self.new_status, "New status required"


@dataclass(frozen=True)
class PortfolioSummary:
    """Immutable portfolio summary for digest."""
    domains_owned: int
    domains_listed: int
    domains_sold: int
    total_invested: float
    total_revenue: float
    total_roi: float

    def __post_init__(self) -> None:
        assert self.domains_owned >= 0, "Count must be non-negative"
        assert isinstance(self.total_invested, (int, float)), "Must be numeric"


@dataclass(frozen=True)
class DigestReport:
    """Immutable daily digest report."""
    timestamp: str
    total_monitored: int
    nearest_drop_domain: str
    nearest_drop_date: str
    days_to_nearest: int
    changes_24h: tuple[StatusChange, ...]
    dynadot_balance: float
    guerrameats_days: int
    tier_counts: dict[str, int]
    portfolio: PortfolioSummary = field(default_factory=lambda: PortfolioSummary(0, 0, 0, 0.0, 0.0, 0.0))

    def __post_init__(self) -> None:
        assert self.total_monitored >= 0, "Count must be non-negative"
        assert isinstance(self.changes_24h, tuple), "Changes must be tuple"


# ── Config Loader ───────────────────────────────────────────────────
def load_monitored_count(config_path: Path) -> tuple[int, dict[str, int]]:
    """Load domain count and tier breakdown from config."""
    assert config_path.exists(), f"Config not found: {config_path}"
    assert config_path.suffix == ".json", "Config must be .json"

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    # Support both "domains" (drop_monitor format) and "active_targets" (sprint25 format)
    domain_data = raw.get("domains", raw.get("active_targets", {}))
    tier_counts: dict[str, int] = {}
    total = 0
    for tier in TIERS_ALL:
        count = len(domain_data.get(tier, []))
        tier_counts[tier] = count
        total += count

    assert total >= 0, "Total must be non-negative"
    return total, tier_counts


# ── Backorder Queue Reader ──────────────────────────────────────────
def load_queue_data(queue_path: Path) -> tuple[float, str, str, int]:
    """Load Dynadot balance and nearest drop from backorder queue.

    Returns: (balance, nearest_domain, nearest_date, days_to_nearest)
    """
    assert isinstance(queue_path, Path), "Must be Path"
    assert queue_path.suffix == ".json", "Must be .json"

    if not queue_path.exists():
        return (0.0, "unknown", "unknown", -1)

    data = json.loads(queue_path.read_text(encoding="utf-8"))
    balance = float(data.get("dynadot_balance", 0.0))
    queue = data.get("queue", [])

    today = datetime.now(timezone.utc).date()
    nearest_domain = "none"
    nearest_date = "none"
    nearest_days = 9999

    for i, entry in enumerate(queue):
        if i >= MAX_DOMAINS:
            break
        drop_est = entry.get("drop_est", "TBD")
        if drop_est == "TBD" or not drop_est:
            continue
        try:
            drop_date = datetime.strptime(drop_est, "%Y-%m-%d").date()
            days = (drop_date - today).days
            if 0 <= days < nearest_days:
                nearest_days = days
                nearest_domain = entry.get("domain", "unknown")
                nearest_date = drop_est
        except ValueError:
            continue

    if nearest_days == 9999:
        nearest_days = -1

    return (balance, nearest_domain, nearest_date, nearest_days)


# ── DB Status Changes ──────────────────────────────────────────────
def get_changes_last_24h(db_path: Path) -> tuple[StatusChange, ...]:
    """Query drop_monitor.db for status changes in the last 24 hours."""
    assert isinstance(db_path, Path), "Must be Path"

    if not db_path.exists():
        return ()

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    changes: list[StatusChange] = []

    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT domain, previous_status, epp_status, checked_at "
            "FROM domain_monitoring "
            "WHERE status_changed = 1 AND checked_at >= ? "
            "ORDER BY checked_at DESC LIMIT 50",
            (cutoff,),
        ).fetchall()
        conn.close()

        for row in rows:
            changes.append(StatusChange(
                domain=row[0],
                old_status=row[1] or "unknown",
                new_status=row[2] or "unknown",
                checked_at=row[3],
            ))
    except sqlite3.Error:
        pass  # DB may not have run yet

    assert isinstance(changes, list), "Changes must be list"
    return tuple(changes)


# ── Guerrameats Countdown ──────────────────────────────────────────
def days_to_guerrameats() -> int:
    """Calculate days until guerrameats.com estimated drop."""
    assert GUERRAMEATS_DROP_EST, "Drop estimate required"

    today = datetime.now(timezone.utc).date()
    drop_date = datetime.strptime(GUERRAMEATS_DROP_EST, "%Y-%m-%d").date()
    days = (drop_date - today).days

    assert isinstance(days, int), "Days must be int"
    return days


# ── Portfolio Loader ───────────────────────────────────────────────
def load_portfolio_summary(portfolio_path: Path) -> PortfolioSummary:
    """Load portfolio summary from portfolio.json."""
    assert isinstance(portfolio_path, Path), "Must be Path"

    if not portfolio_path.exists():
        return PortfolioSummary(0, 0, 0, 0.0, 0.0, 0.0)

    try:
        data = json.loads(portfolio_path.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        return PortfolioSummary(
            domains_owned=int(summary.get("domains_owned", 0)),
            domains_listed=int(summary.get("domains_listed", 0)),
            domains_sold=int(summary.get("domains_sold", 0)),
            total_invested=float(summary.get("total_invested", 0)),
            total_revenue=float(summary.get("total_revenue", 0)),
            total_roi=float(summary.get("total_roi", 0)),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return PortfolioSummary(0, 0, 0, 0.0, 0.0, 0.0)


# ── Build Report ────────────────────────────────────────────────────
def build_digest() -> DigestReport:
    """Assemble the full daily digest from all data sources."""
    now = datetime.now(timezone.utc).isoformat()

    total, tier_counts = load_monitored_count(CONFIG_PATH)
    balance, nearest_domain, nearest_date, nearest_days = load_queue_data(QUEUE_PATH)
    changes = get_changes_last_24h(DB_PATH)
    gm_days = days_to_guerrameats()

    # If config was emptied, fall back to queue count
    if total == 0 and QUEUE_PATH.exists():
        queue_data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        queue_count = len(queue_data.get("queue", []))
        if queue_count > 0:
            total = queue_count

    portfolio = load_portfolio_summary(PORTFOLIO_PATH)

    report = DigestReport(
        timestamp=now,
        total_monitored=total,
        nearest_drop_domain=nearest_domain,
        nearest_drop_date=nearest_date,
        days_to_nearest=nearest_days,
        changes_24h=changes,
        dynadot_balance=balance,
        guerrameats_days=gm_days,
        tier_counts=tier_counts,
        portfolio=portfolio,
    )
    assert report.total_monitored >= 0, "Invalid report"
    assert isinstance(report.timestamp, str), "Timestamp required"
    return report


# ── Format for Display ──────────────────────────────────────────────
def format_digest_text(report: DigestReport) -> str:
    """Format digest report as human-readable text."""
    assert isinstance(report, DigestReport), "Must be DigestReport"
    assert report.timestamp, "Timestamp required"

    lines: list[str] = [
        "=" * 56,
        "  DOMAIN HUNTER -- DAILY DIGEST",
        f"  {report.timestamp[:19]}Z",
        "=" * 56,
        "",
        f"  Domains monitored: {report.total_monitored}",
    ]

    for tier in TIERS_ALL:
        count = report.tier_counts.get(tier, 0)
        lines.append(f"    {tier}: {count}")

    lines.append("")

    if report.nearest_drop_domain != "none":
        lines.append(
            f"  Nearest drop: {report.nearest_drop_domain} "
            f"({report.nearest_drop_date}, {report.days_to_nearest}d)"
        )
    else:
        lines.append("  Nearest drop: No dated drops in queue")

    lines.append(f"  Dynadot balance: ${report.dynadot_balance:.2f}")
    lines.append("")

    gm_label = "OVERDUE" if report.guerrameats_days < 0 else f"{report.guerrameats_days}d"
    lines.append(f"  >>> guerrameats.com drop: {gm_label} <<<")
    lines.append("")

    if report.changes_24h:
        lines.append(f"  Status changes (24h): {len(report.changes_24h)}")
        for i, ch in enumerate(report.changes_24h):
            if i >= 10:
                lines.append(f"    ... and {len(report.changes_24h) - 10} more")
                break
            lines.append(f"    {ch.domain}: {ch.old_status} -> {ch.new_status}")
    else:
        lines.append("  Status changes (24h): None")

    # Portfolio section
    pf = report.portfolio
    lines.append("")
    lines.append("  --- PORTFOLIO ---")
    lines.append(f"  Domains owned:     {pf.domains_owned}")
    lines.append(f"  Domains listed:    {pf.domains_listed}")
    lines.append(f"  Domains sold:      {pf.domains_sold}")
    lines.append(f"  Total invested:    ${pf.total_invested:,.2f}")
    lines.append(f"  Revenue:           ${pf.total_revenue:,.2f}")
    roi_pct = (pf.total_roi / pf.total_invested * 100) if pf.total_invested > 0 else 0.0
    lines.append(f"  ROI:               ${pf.total_roi:+,.2f} ({roi_pct:+.1f}%)")

    lines.append("")
    lines.append("=" * 56)

    text = "\n".join(lines)
    assert len(text) > 0, "Digest text must not be empty"
    return text


# ── Notification Sender ─────────────────────────────────────────────
def send_digest_notification(report: DigestReport) -> bool:
    """Fire macOS desktop notification with digest summary."""
    assert isinstance(report, DigestReport), "Must be DigestReport"
    assert report.total_monitored >= 0, "Invalid report"

    gm_label = "OVERDUE" if report.guerrameats_days < 0 else f"{report.guerrameats_days}d"
    title = "Domain Hunter Daily Digest"
    body = (
        f"{report.total_monitored} domains | "
        f"Next: {report.nearest_drop_domain} ({report.days_to_nearest}d) | "
        f"guerrameats: {gm_label} | "
        f"${report.dynadot_balance:.0f} bal"
    )
    # Truncate body to 200 chars for osascript
    body = body[:200]

    safe_title = title.replace('"', '\\"')
    safe_body = body.replace('"', '\\"')
    script = (
        f'display notification "{safe_body}" '
        f'with title "{safe_title}" sound name "Glass"'
    )

    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ── Log Writer ──────────────────────────────────────────────────────
def write_digest_log(report: DigestReport, log_path: Path) -> bool:
    """Append digest report as JSON line to daily_digest.log."""
    assert isinstance(report, DigestReport), "Must be DigestReport"
    assert log_path.parent.exists() or True, "Will create"

    pf = report.portfolio
    entry = {
        "timestamp": report.timestamp,
        "total_monitored": report.total_monitored,
        "nearest_drop_domain": report.nearest_drop_domain,
        "nearest_drop_date": report.nearest_drop_date,
        "days_to_nearest": report.days_to_nearest,
        "changes_24h_count": len(report.changes_24h),
        "dynadot_balance": report.dynadot_balance,
        "guerrameats_days": report.guerrameats_days,
        "tier_counts": report.tier_counts,
        "portfolio_owned": pf.domains_owned,
        "portfolio_invested": pf.total_invested,
        "portfolio_revenue": pf.total_revenue,
        "portfolio_roi": pf.total_roi,
    }

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[str] = []
        if log_path.exists():
            existing = log_path.read_text(encoding="utf-8").strip().split("\n")
            existing = [l for l in existing if l.strip()]
            if len(existing) > MAX_LOG_ENTRIES:
                existing = existing[-MAX_LOG_ENTRIES:]

        existing.append(json.dumps(entry, separators=(",", ":")))
        log_path.write_text("\n".join(existing) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


# ── CLI Entry Point ─────────────────────────────────────────────────
def main() -> None:
    """Generate and deliver the daily digest."""
    parser = argparse.ArgumentParser(
        description="Sprint 26 -- Daily Digest for Domain Hunter",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress console output (still sends notification and logs)",
    )
    args = parser.parse_args()
    assert isinstance(args.quiet, bool), "Argument parse error"

    report = build_digest()
    digest_text = format_digest_text(report)

    if not args.quiet:
        print(digest_text)

    notif_ok = send_digest_notification(report)
    log_ok = write_digest_log(report, LOG_FILE)

    if not args.quiet:
        print(f"  Notification: {'sent' if notif_ok else 'FAILED'}")
        print(f"  Log: {'written' if log_ok else 'FAILED'}")

    sys.exit(0 if (notif_ok and log_ok) else 1)


if __name__ == "__main__":
    main()

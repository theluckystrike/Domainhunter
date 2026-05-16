#!/usr/bin/env python3
"""
Domain Hunter — Automated WHOIS Expiry Monitor.

Checks domain status daily and alerts on changes.
Stores history in SQLite. Sends Slack/stdout alerts.

Run:   python watchlist_monitor.py
Cron:  0 8 * * * cd ~/Desktop/domainhunter && python watchlist_monitor.py
Test:  python watchlist_monitor.py --dry-run

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# ── Constants ──────────────────────────────────────────────────────────
MAX_DOMAINS: Final[int] = 128
MAX_WHOIS_TIMEOUT: Final[int] = 15
DB_PATH: Final[Path] = Path(__file__).parent / "watchlist.db"
SLACK_WEBHOOK_ENV: Final[str] = "DOMAIN_HUNTER_SLACK_WEBHOOK"

STATUS_REGISTERED: Final[str] = "REGISTERED"
STATUS_EXPIRING_SOON: Final[str] = "EXPIRING_SOON"
STATUS_GRACE_PERIOD: Final[str] = "GRACE_PERIOD"
STATUS_REDEMPTION: Final[str] = "REDEMPTION"
STATUS_PENDING_DELETE: Final[str] = "PENDING_DELETE"
STATUS_AVAILABLE: Final[str] = "AVAILABLE"
STATUS_UNKNOWN: Final[str] = "UNKNOWN"

PRIORITY_CRITICAL: Final[str] = "CRITICAL"
PRIORITY_HIGH: Final[str] = "HIGH"
PRIORITY_MEDIUM: Final[str] = "MEDIUM"
PRIORITY_LOW: Final[str] = "LOW"


# ── Data Models (frozen) ──────────────────────────────────────────────
@dataclass(frozen=True)
class WatchedDomain:
    """Immutable domain entry in the watchlist."""
    domain: str
    expiry: str  # YYYY-MM-DD
    priority: str
    notes: str = ""

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.priority in (
            PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW
        ), f"Invalid priority: {self.priority}"


@dataclass(frozen=True)
class WhoisResult:
    """Immutable WHOIS check result."""
    domain: str
    status: str
    registrar: str
    expiry_date: str
    nameservers: tuple[str, ...]
    status_codes: tuple[str, ...]
    raw_snippet: str
    checked_at: str

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.status in (
            STATUS_REGISTERED, STATUS_EXPIRING_SOON, STATUS_GRACE_PERIOD,
            STATUS_REDEMPTION, STATUS_PENDING_DELETE, STATUS_AVAILABLE,
            STATUS_UNKNOWN,
        ), f"Invalid status: {self.status}"


@dataclass(frozen=True)
class StatusChange:
    """Immutable record of a domain status change."""
    domain: str
    priority: str
    old_status: str
    new_status: str
    old_expiry: str
    new_expiry: str
    message: str

    def __post_init__(self) -> None:
        assert self.domain, "Domain required"
        assert self.message, "Message required"


# ── Watchlist ─────────────────────────────────────────────────────────
WATCHLIST: Final[tuple[WatchedDomain, ...]] = (
    # ── CRITICAL: Expired / Grace Period ──────────────────────────────
    WatchedDomain("aidevtools.com", "2026-05-06", PRIORITY_CRITICAL,
                  "EXPIRED May 6. NameSilo renew/clientHold. ParkLogic NS."),
    WatchedDomain("seochecker.com", "2026-05-08", PRIORITY_CRITICAL,
                  "EXPIRED May 8. 21yr .com. GoDaddy. DigitalOcean NS. SEO tool keyword."),
    WatchedDomain("builder.ai", "2026-06-04", PRIORITY_CRITICAL,
                  "$1.5B startup bankrupt 2025. 101domain. AWS NS. Extreme backlinks."),

    # ── HIGH: Expiring within 60 days ─────────────────────────────────
    WatchedDomain("bestdevtools.com", "2026-05-22", PRIORITY_HIGH,
                  "12yr domain. 1API/DNSimple. Expiring 16 days."),
    WatchedDomain("finetuneai.com", "2026-05-26", PRIORITY_HIGH,
                  "AI fine-tuning keyword. Namecheap. AWS NS. 20 days."),
    WatchedDomain("taskplanner.com", "2026-05-27", PRIORITY_HIGH,
                  "22yr .com. GoDaddy clientRenewProhibited. Productivity keyword. 21 days."),
    WatchedDomain("aitoolkit.com", "2026-06-12", PRIORITY_HIGH,
                  "26yr .com. Easyspace. NameCity parking NS. 37 days."),
    WatchedDomain("mortgagecalc.com", "2026-06-15", PRIORITY_HIGH,
                  "28yr premium finance .com. GCD/Brandsight registrar. 40 days."),
    WatchedDomain("loancompare.com", "2026-06-26", PRIORITY_HIGH,
                  "24yr finance .com. Moniker DNS. Wayback since 2002. 51 days."),

    # ── HIGH: Sprint 2 carry-forward (60-180 days) ────────────────────
    WatchedDomain("devtools.io", "2026-07-04", PRIORITY_HIGH,
                  "Premium keyword .io."),
    WatchedDomain("prompttools.com", "2026-07-18", PRIORITY_HIGH,
                  "26yr .com. AI prompt tools keyword."),
    WatchedDomain("devhub.io", "2026-10-17", PRIORITY_HIGH,
                  "25.9K archived URLs. Ethereum.org backlink. On Afternic."),
    WatchedDomain("apitools.com", "2026-12-14", PRIORITY_HIGH,
                  "Ex-3scale API proxy. Tech media backlinks."),

    # ── MEDIUM: Sprint 3 niche tool domains (expiring <180 days) ──────
    WatchedDomain("toolchain.io", "2026-07-07", PRIORITY_MEDIUM,
                  "Build system keyword. On Afternic."),
    WatchedDomain("saasmetrics.com", "2026-07-15", PRIORITY_MEDIUM,
                  "18yr domain. SaaS analytics keyword."),
    WatchedDomain("codehelper.com", "2026-07-17", PRIORITY_MEDIUM,
                  "On Afternic marketplace."),
    WatchedDomain("codeanalyzer.com", "2026-07-20", PRIORITY_MEDIUM,
                  "21yr domain. Code analysis keyword."),
    WatchedDomain("codingtools.com", "2026-07-31", PRIORITY_MEDIUM,
                  "21yr .com. PowWeb hosting."),
    WatchedDomain("macrocalculator.com", "2026-08-11", PRIORITY_MEDIUM,
                  "9yr health/fitness .com. GoDaddy. Active site whataremymacros."),
    WatchedDomain("fitnesstools.com", "2026-09-04", PRIORITY_MEDIUM,
                  "5yr .com. GoDaddy DomainControl NS. Health niche keyword."),
    WatchedDomain("analyticstools.com", "2026-09-18", PRIORITY_MEDIUM,
                  "20yr .com. GoDaddy. On Afternic. Wayback since 2007."),
    WatchedDomain("caloriecalc.com", "2026-09-20", PRIORITY_MEDIUM,
                  "14yr .com. HugeDomains listing. Health tool keyword."),
    WatchedDomain("colorpicker.com", "2026-09-26", PRIORITY_MEDIUM,
                  "26yr premium .com. GoDaddy. Cloudflare NS. Wayback since 1998."),
    WatchedDomain("pomodorotimer.com", "2026-09-29", PRIORITY_MEDIUM,
                  "12yr .com. IHS registrar. Cloudflare NS. Productivity keyword."),
    WatchedDomain("codetools.com", "2026-10-21", PRIORITY_MEDIUM,
                  "26yr .com. Former CodeProject redirect."),
    WatchedDomain("nutritioncalc.com", "2026-11-23", PRIORITY_MEDIUM,
                  "13yr .com. HugeDomains listing. Health tool keyword."),
    WatchedDomain("investcalculator.com", "2026-11-23", PRIORITY_MEDIUM,
                  "13yr .com. NameBright. Finance tool keyword."),
    WatchedDomain("bmicalculator.com", "2026-12-04", PRIORITY_MEDIUM,
                  "26yr premium .com. GoDaddy NameFind. Health tool keyword."),
    WatchedDomain("codeparrot.ai", "2026-12-15", PRIORITY_MEDIUM,
                  "YC W23 AI code generator. Shut down."),

    # ── LOW: Long-dated / marketplace listings ────────────────────────
    WatchedDomain("stackreview.com", "2026-07-08", PRIORITY_LOW,
                  "HugeDomains listing. Low SEO."),
    WatchedDomain("codecompare.com", "2026-08-27", PRIORITY_LOW,
                  "HugeDomains. Low SEO."),
    WatchedDomain("devaide.com", "2026-09-08", PRIORITY_LOW,
                  "BrandBucket premium. Coined word."),
    WatchedDomain("codebench.com", "2026-12-16", PRIORITY_LOW,
                  "HID Global owned. CSC registrar."),
    WatchedDomain("launchable.io", "2027-04-10", PRIORITY_LOW,
                  "CloudBees acquired. Auto-renewed via Park.io."),

    # ── LOW: Renewed / long-dated (monitor only) ─────────────────────
    WatchedDomain("codeguide.com", "2027-04-23", PRIORITY_LOW,
                  "RENEWED to 2027. 25yr .com. Schlundtech/InterNetX."),
    WatchedDomain("taxestimator.com", "2027-01-09", PRIORITY_LOW,
                  "26yr .com. GoDaddy. Bodis/Moniker NS. Finance keyword."),
    WatchedDomain("savingscalculator.com", "2027-02-07", PRIORITY_LOW,
                  "26yr .com. Dynadot. Finance tool keyword."),
    WatchedDomain("budgetcalc.com", "2027-04-23", PRIORITY_LOW,
                  "23yr .com. BuyDomains/for-sale NS. Finance keyword."),
    WatchedDomain("cookingtools.com", "2027-01-17", PRIORITY_LOW,
                  "28yr .com. Network Solutions. AWS NS. Active site."),
    WatchedDomain("keywordfinder.com", "2027-04-20", PRIORITY_LOW,
                  "24yr .com. Namecheap. On Afternic. SEO keyword."),
    WatchedDomain("ingredientfinder.com", "2027-02-01", PRIORITY_LOW,
                  "26yr .com. Network Solutions. Cooking niche."),
    WatchedDomain("imageresizer.com", "2030-10-09", PRIORITY_LOW,
                  "24yr .com. Namecheap. Cloudflare. Renewed to 2030."),
    WatchedDomain("mealcalculator.com", "2027-04-17", PRIORITY_LOW,
                  "10yr .com. NameBright. Cooking tool keyword."),
    WatchedDomain("recipescaler.com", "2027-05-05", PRIORITY_LOW,
                  "Newly registered May 2026. Juming NS. Cooking keyword."),
)

assert len(WATCHLIST) <= MAX_DOMAINS, f"Watchlist exceeds {MAX_DOMAINS}"


# ── Database ──────────────────────────────────────────────────────────
def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with schema. Returns connection."""
    assert db_path.parent.exists(), f"Parent dir missing: {db_path.parent}"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whois_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            status TEXT NOT NULL,
            registrar TEXT,
            expiry_date TEXT,
            nameservers TEXT,
            status_codes TEXT,
            raw_snippet TEXT,
            checked_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS status_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            priority TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            old_expiry TEXT,
            new_expiry TEXT,
            message TEXT NOT NULL,
            detected_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checks_domain
        ON whois_checks(domain, checked_at DESC)
    """)
    conn.commit()
    assert conn is not None, "DB init failed"
    return conn


def get_last_check(conn: sqlite3.Connection, domain: str) -> WhoisResult | None:
    """Get most recent WHOIS check for a domain."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    row = conn.execute(
        "SELECT domain, status, registrar, expiry_date, nameservers, "
        "status_codes, raw_snippet, checked_at "
        "FROM whois_checks WHERE domain = ? ORDER BY checked_at DESC LIMIT 1",
        (domain,),
    ).fetchone()
    if row is None:
        return None
    assert len(row) == 8, f"Unexpected row length: {len(row)}"
    return WhoisResult(
        domain=row[0], status=row[1], registrar=row[2] or "",
        expiry_date=row[3] or "", nameservers=tuple(json.loads(row[4] or "[]")),
        status_codes=tuple(json.loads(row[5] or "[]")),
        raw_snippet=row[6] or "", checked_at=row[7],
    )


def save_check(conn: sqlite3.Connection, result: WhoisResult) -> None:
    """Persist a WHOIS check result."""
    assert result.domain, "Domain required"
    assert result.checked_at, "Timestamp required"
    conn.execute(
        "INSERT INTO whois_checks "
        "(domain, status, registrar, expiry_date, nameservers, "
        "status_codes, raw_snippet, checked_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            result.domain, result.status, result.registrar,
            result.expiry_date, json.dumps(list(result.nameservers)),
            json.dumps(list(result.status_codes)), result.raw_snippet[:2000],
            result.checked_at,
        ),
    )
    conn.commit()


def save_change(conn: sqlite3.Connection, change: StatusChange) -> None:
    """Persist a status change event."""
    assert change.domain, "Domain required"
    conn.execute(
        "INSERT INTO status_changes "
        "(domain, priority, old_status, new_status, old_expiry, "
        "new_expiry, message, detected_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            change.domain, change.priority, change.old_status,
            change.new_status, change.old_expiry, change.new_expiry,
            change.message, datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


# ── WHOIS Checker ─────────────────────────────────────────────────────
def run_whois(domain: str) -> str:
    """Execute whois command and return raw output."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True,
            timeout=MAX_WHOIS_TIMEOUT,
        )
        assert isinstance(result.stdout, str), "WHOIS returned non-string"
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return f"ERROR: {exc}"


def parse_whois(domain: str, raw: str) -> WhoisResult:
    """Parse raw WHOIS output into structured result."""
    assert domain, "Domain required"
    assert isinstance(raw, str), "Raw must be string"

    now = datetime.now(timezone.utc).isoformat()
    lines = raw.lower().splitlines()

    # Extract registrar
    registrar = ""
    for line in lines[:100]:
        if "registrar:" in line and not registrar:
            registrar = line.split(":", 1)[1].strip()
            break

    # Extract expiry date
    expiry = ""
    expiry_keys = ("expir", "paid-till", "renewal date", "registry expiry")
    for line in lines[:100]:
        for key in expiry_keys:
            if key in line and ":" in line:
                val = line.split(":", 1)[1].strip()
                # Extract date portion (first 10 chars if ISO format)
                if len(val) >= 10:
                    expiry = val[:10]
                break
        if expiry:
            break

    # Extract nameservers
    nameservers: list[str] = []
    for line in lines[:200]:
        if line.strip().startswith("name server:") or line.strip().startswith("nserver:"):
            ns = line.split(":", 1)[1].strip().split()[0]
            if ns and ns not in nameservers:
                nameservers.append(ns)
    nameservers = nameservers[:8]  # Fixed bound

    # Extract status codes
    status_codes: list[str] = []
    for line in lines[:100]:
        if "status:" in line:
            code = line.split(":", 1)[1].strip().split()[0]
            if code and code not in status_codes:
                status_codes.append(code)
    status_codes = status_codes[:16]  # Fixed bound

    # Determine domain status
    status = _classify_status(raw, status_codes, expiry)

    snippet = raw[:500] if len(raw) > 500 else raw

    return WhoisResult(
        domain=domain, status=status, registrar=registrar,
        expiry_date=expiry, nameservers=tuple(nameservers),
        status_codes=tuple(status_codes), raw_snippet=snippet,
        checked_at=now,
    )


def _classify_status(raw: str, codes: list[str], expiry: str) -> str:
    """Classify domain status from WHOIS data."""
    assert isinstance(raw, str), "Raw must be string"
    assert isinstance(codes, list), "Codes must be list"
    raw_lower = raw.lower()

    if "no match" in raw_lower or "not found" in raw_lower:
        return STATUS_AVAILABLE
    if any("pendingdelete" in c for c in codes):
        return STATUS_PENDING_DELETE
    if any("redemption" in c for c in codes):
        return STATUS_REDEMPTION
    if any("renew" in c for c in codes) or "auto-renew" in raw_lower:
        return STATUS_GRACE_PERIOD
    if "clienthold" in " ".join(codes):
        return STATUS_GRACE_PERIOD

    # Check if expiring within 90 days
    if expiry and len(expiry) >= 10:
        try:
            exp_date = datetime.strptime(expiry[:10], "%Y-%m-%d")
            days_left = (exp_date - datetime.now()).days
            if days_left <= 0:
                return STATUS_GRACE_PERIOD
            if days_left <= 90:
                return STATUS_EXPIRING_SOON
        except ValueError:
            pass

    if "domain name:" in raw_lower or "registrar:" in raw_lower:
        return STATUS_REGISTERED

    return STATUS_UNKNOWN


# ── Change Detection ──────────────────────────────────────────────────
def detect_changes(
    watched: WatchedDomain,
    previous: WhoisResult | None,
    current: WhoisResult,
) -> StatusChange | None:
    """Compare previous and current WHOIS, return change if any."""
    assert current.domain == watched.domain, "Domain mismatch"

    old_status = previous.status if previous else "FIRST_CHECK"
    old_expiry = previous.expiry_date if previous else watched.expiry

    if old_status == current.status and old_expiry == current.expiry_date:
        return None  # No change

    # Build message
    messages: list[str] = []
    if old_status != current.status:
        messages.append(f"Status: {old_status} -> {current.status}")
    if old_expiry != current.expiry_date and current.expiry_date:
        messages.append(f"Expiry: {old_expiry} -> {current.expiry_date}")

    # Special alerts
    if current.status == STATUS_PENDING_DELETE:
        messages.append("DROPPING SOON — place backorders NOW")
    elif current.status == STATUS_AVAILABLE:
        messages.append("DOMAIN IS AVAILABLE — REGISTER NOW")
    elif current.status == STATUS_GRACE_PERIOD:
        messages.append("In grace period — owner may renew")
    elif current.status == STATUS_REDEMPTION:
        messages.append("In redemption — expensive recovery only")

    message = " | ".join(messages) if messages else "Status changed"

    return StatusChange(
        domain=watched.domain, priority=watched.priority,
        old_status=old_status, new_status=current.status,
        old_expiry=old_expiry, new_expiry=current.expiry_date,
        message=message,
    )


# ── Alerting ──────────────────────────────────────────────────────────
def format_alert(change: StatusChange) -> str:
    """Format a status change as a human-readable alert."""
    assert change.domain, "Domain required"
    icon = {
        PRIORITY_CRITICAL: "🚨", PRIORITY_HIGH: "⚠️",
        PRIORITY_MEDIUM: "📋", PRIORITY_LOW: "ℹ️",
    }.get(change.priority, "📋")

    return (
        f"{icon} [{change.priority}] {change.domain}\n"
        f"   {change.message}\n"
        f"   Registrar check: whois {change.domain}"
    )


def send_slack(webhook_url: str, text: str) -> bool:
    """Send alert to Slack webhook. Returns True on success."""
    assert webhook_url.startswith("https://"), "Invalid webhook URL"
    assert text, "Empty message"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── Main Orchestrator ─────────────────────────────────────────────────
def run_monitor(dry_run: bool = False) -> list[StatusChange]:
    """Run full watchlist check. Returns list of detected changes."""
    assert isinstance(dry_run, bool), "dry_run must be bool"

    conn = init_db(DB_PATH)
    changes: list[StatusChange] = []
    slack_url = os.environ.get(SLACK_WEBHOOK_ENV, "")

    print(f"{'[DRY RUN] ' if dry_run else ''}Domain Hunter Watchlist Monitor")
    print(f"Checking {len(WATCHLIST)} domains at {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    for i, watched in enumerate(WATCHLIST):
        assert i < MAX_DOMAINS, f"Loop bound exceeded: {i}"
        print(f"  [{i+1}/{len(WATCHLIST)}] {watched.domain} ...", end=" ", flush=True)

        # Get previous check
        previous = get_last_check(conn, watched.domain)

        # Run WHOIS
        if dry_run:
            print("SKIP (dry-run)")
            continue

        raw = run_whois(watched.domain)
        current = parse_whois(watched.domain, raw)

        # Save check
        save_check(conn, current)

        # Detect changes
        change = detect_changes(watched, previous, current)
        if change is not None:
            changes.append(change)
            save_change(conn, change)
            print(f"CHANGED -> {current.status}")
        else:
            print(f"OK ({current.status})")

    # Report changes
    print("\n" + "=" * 60)
    if not changes:
        print("No status changes detected.")
    else:
        print(f"{len(changes)} status change(s) detected:\n")
        for change in changes:
            alert_text = format_alert(change)
            print(alert_text)
            # Send Slack for CRITICAL/HIGH
            if slack_url and change.priority in (PRIORITY_CRITICAL, PRIORITY_HIGH):
                sent = send_slack(slack_url, alert_text)
                print(f"   Slack: {'sent' if sent else 'FAILED'}")

    conn.close()
    return changes


def main() -> None:
    """Entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Domain Hunter Watchlist Monitor",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Check configuration without running WHOIS lookups",
    )
    args = parser.parse_args()
    assert isinstance(args.dry_run, bool), "Argument parse error"

    changes = run_monitor(dry_run=args.dry_run)

    # Exit code: 0 = no changes, 1 = changes detected (useful for cron)
    sys.exit(1 if changes else 0)


if __name__ == "__main__":
    main()

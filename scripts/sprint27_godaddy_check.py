#!/usr/bin/env python3
"""Sprint 27 -- GoDaddy Auctions Monitoring Script.

Monitors GoDaddy Auctions inventory files for target domains.
Downloads the daily CSV/JSON inventory from inventory.auctions.godaddy.com
and checks whether any of our monitored GoDaddy domains have appeared
in auction or closeout listings.

Modes:
  --check-inventory    Download and scan GoDaddy inventory files (primary mode)
  --dates              Print upcoming key dates for all monitored domains
  --check DOMAIN       Quick manual check reminder for a specific domain

Run:   python3 scripts/sprint27_godaddy_check.py --check-inventory
       python3 scripts/sprint27_godaddy_check.py --dates
       python3 scripts/sprint27_godaddy_check.py --check ghostautonomy.com
Cron:  30 15 * * * cd ~/Desktop/domainhunter && python3 scripts/sprint27_godaddy_check.py --check-inventory

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Final, List, Optional, Tuple

# ── Constants (immutable) ────────────────────────────────────────────
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
CACHE_DIR: Final[Path] = DATA_DIR / "gd_inventory_cache"

INVENTORY_BASE_URL: Final[str] = "https://inventory.auctions.godaddy.com/"
METADATA_URL: Final[str] = INVENTORY_BASE_URL + "metadata.json"
AUCTION_SEARCH_URL: Final[str] = "https://auctions.godaddy.com/beta?q={domain}"

# Inventory files to check (in order of priority -- smallest first)
INVENTORY_FILES: Final[Tuple[str, ...]] = (
    "all_biddable_auctions_no_adult.csv.zip",
    "expiring_service_auctions.csv.zip",
    "closeout_service_auctions.csv.zip",
)

REQUEST_TIMEOUT: Final[int] = 60
MAX_DOMAINS: Final[int] = 50
MAX_FILE_SIZE_MB: Final[int] = 100
MAX_INVENTORY_FILES: Final[int] = 10

# ── Monitored GoDaddy Domains ────────────────────────────────────────
# Each entry: (domain, expiry_date, auction_start_est, auction_end_est,
#              closeout_end_est, drop_est, max_bid_usd, risk_level)


@dataclass(frozen=True)
class GoDaddyTarget:
    """Immutable GoDaddy auction monitoring target."""
    domain: str
    expiry_date: str
    auction_start_est: str
    auction_end_est: str
    closeout_end_est: str
    drop_est: str
    max_bid_usd: int
    risk_level: str

    def __post_init__(self) -> None:
        assert "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.risk_level in (
            "LOW", "LOW-MEDIUM", "MEDIUM", "MEDIUM-HIGH", "HIGH", "CERTAIN"
        ), f"Invalid risk: {self.risk_level}"


GODADDY_TARGETS: Final[Tuple[GoDaddyTarget, ...]] = (
    GoDaddyTarget(
        domain="ghostautonomy.com",
        expiry_date="2026-06-07",
        auction_start_est="2026-07-03",
        auction_end_est="2026-07-13",
        closeout_end_est="2026-07-18",
        drop_est="2026-08-23",
        max_bid_usd=100,
        risk_level="LOW-MEDIUM",
    ),
    GoDaddyTarget(
        domain="fiskerinc.com",
        expiry_date="2026-09-21",
        auction_start_est="2026-10-17",
        auction_end_est="2026-10-27",
        closeout_end_est="2026-11-01",
        drop_est="2026-12-07",
        max_bid_usd=100,
        risk_level="LOW",
    ),
    GoDaddyTarget(
        domain="northvolt.com",
        expiry_date="2027-01-24",
        auction_start_est="2027-02-19",
        auction_end_est="2027-03-01",
        closeout_end_est="2027-03-06",
        drop_est="2027-04-11",
        max_bid_usd=1000,
        risk_level="MEDIUM-HIGH",
    ),
    GoDaddyTarget(
        domain="infarm.com",
        expiry_date="2027-02-18",
        auction_start_est="2027-03-16",
        auction_end_est="2027-03-26",
        closeout_end_est="2027-03-31",
        drop_est="2027-05-06",
        max_bid_usd=2000,
        risk_level="HIGH",
    ),
    GoDaddyTarget(
        domain="veev.com",
        expiry_date="2027-07-02",
        auction_start_est="2027-07-28",
        auction_end_est="2027-08-07",
        closeout_end_est="2027-08-12",
        drop_est="2027-09-17",
        max_bid_usd=20000,
        risk_level="CERTAIN",
    ),
    GoDaddyTarget(
        domain="olive.com",
        expiry_date="2027-11-21",
        auction_start_est="2027-12-17",
        auction_end_est="2027-12-27",
        closeout_end_est="2028-01-01",
        drop_est="2028-02-06",
        max_bid_usd=50000,
        risk_level="CERTAIN",
    ),
)


@dataclass(frozen=True)
class InventoryMatch:
    """Immutable record of a domain found in GoDaddy inventory."""
    domain: str
    source_file: str
    auction_type: str
    current_bid: str
    end_time: str
    raw_row: str

    def __post_init__(self) -> None:
        assert "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.source_file, "source_file required"


# ── Utility Functions ────────────────────────────────────────────────

def _days_until(date_str: str) -> int:
    """Return days from today until the given date string (YYYY-MM-DD)."""
    assert len(date_str) == 10, f"Expected YYYY-MM-DD, got: {date_str}"
    target = datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    now = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = target - now
    return delta.days


def _send_notification(title: str, message: str) -> None:
    """Send macOS desktop notification."""
    assert title, "Notification title required"
    assert message, "Notification message required"
    if sys.platform != "darwin":
        return
    try:
        script = (
            f'display notification "{message}" '
            f'with title "{title}" sound name "Submarine"'
        )
        subprocess.run(
            ["osascript", "-e", script],
            timeout=10,
            check=False,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _fetch_url(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Fetch URL content as bytes. Raises on failure."""
    assert url.startswith("http"), f"Invalid URL: {url}"
    assert 1 <= timeout <= 300, f"Invalid timeout: {timeout}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DomainHunter/1.0 (auction-monitor)",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        assert len(data) < MAX_FILE_SIZE_MB * 1024 * 1024, (
            f"File too large: {len(data)} bytes"
        )
        return data


def _ensure_dirs() -> None:
    """Create required directories."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Inventory Download & Scan ────────────────────────────────────────

def fetch_metadata() -> Optional[Dict]:
    """Fetch the GoDaddy inventory metadata.json."""
    try:
        data = _fetch_url(METADATA_URL, timeout=30)
        result = json.loads(data)
        assert isinstance(result, (dict, list)), "Unexpected metadata format"
        return result
    except (urllib.error.URLError, json.JSONDecodeError, AssertionError) as exc:
        print(f"  [WARN] Could not fetch metadata: {exc}")
        return None


def download_and_scan_inventory(
    filename: str, target_domains: Tuple[str, ...]
) -> List[InventoryMatch]:
    """Download a GoDaddy inventory ZIP, extract CSV, scan for domains."""
    assert filename.endswith(".zip"), f"Expected ZIP: {filename}"
    assert len(target_domains) <= MAX_DOMAINS, "Too many domains"

    url = INVENTORY_BASE_URL + filename
    matches: List[InventoryMatch] = []

    try:
        print(f"  Downloading {filename}...")
        zip_data = _fetch_url(url, timeout=REQUEST_TIMEOUT)
        print(f"  Downloaded {len(zip_data) / 1024 / 1024:.1f} MB")
    except (urllib.error.URLError, AssertionError) as exc:
        print(f"  [WARN] Could not download {filename}: {exc}")
        return matches

    # Cache the zip for debugging
    cache_path = CACHE_DIR / filename
    cache_path.write_bytes(zip_data)

    # Extract and scan CSV inside the ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            csv_names = [
                n for n in zf.namelist()
                if n.endswith(".csv") or n.endswith(".txt")
            ]
            if not csv_names:
                print(f"  [WARN] No CSV/TXT found in {filename}")
                return matches

            for csv_name in csv_names[:MAX_INVENTORY_FILES]:
                with zf.open(csv_name) as csvf:
                    text = csvf.read().decode("utf-8", errors="replace")
                    matches.extend(
                        _scan_csv_text(text, csv_name, target_domains)
                    )
    except (zipfile.BadZipFile, KeyError) as exc:
        print(f"  [WARN] ZIP extraction failed for {filename}: {exc}")

    return matches


def _scan_csv_text(
    text: str, source_name: str, target_domains: Tuple[str, ...]
) -> List[InventoryMatch]:
    """Scan CSV text for target domains. Returns matches."""
    assert text, "Empty CSV text"
    assert source_name, "source_name required"

    matches: List[InventoryMatch] = []
    domain_set = set(d.lower() for d in target_domains)
    lines = text.splitlines()

    # Try to parse as CSV
    reader = csv.reader(lines)
    header: Optional[List[str]] = None
    domain_col_idx: int = -1
    row_count = 0

    for row in reader:
        if row_count == 0:
            # First row is likely header
            header = [col.lower().strip() for col in row]
            # Find domain column -- common names: domain, domainname,
            # domain_name, name
            for idx, col in enumerate(header):
                if col in (
                    "domain", "domainname", "domain_name", "name",
                    "domain name", "domainnm"
                ):
                    domain_col_idx = idx
                    break
            if domain_col_idx == -1:
                # Fallback: check all columns for domain patterns
                domain_col_idx = 0
            row_count += 1
            continue

        row_count += 1
        if row_count > 500000:
            break  # Safety bound

        # Check if any column contains a target domain
        for col_idx, cell in enumerate(row):
            cell_lower = cell.lower().strip()
            if cell_lower in domain_set:
                # Extract useful fields from row
                auction_type = ""
                current_bid = ""
                end_time = ""
                if header:
                    for h_idx, h_name in enumerate(header):
                        if h_idx < len(row):
                            if h_name in (
                                "auction type", "type", "listing type"
                            ):
                                auction_type = row[h_idx].strip()
                            elif h_name in (
                                "price", "bid", "current bid",
                                "current price", "bids"
                            ):
                                if not current_bid:
                                    current_bid = row[h_idx].strip()
                            elif h_name in (
                                "time left", "end time", "end date",
                                "close date", "closing"
                            ):
                                end_time = row[h_idx].strip()

                matches.append(InventoryMatch(
                    domain=cell_lower,
                    source_file=source_name,
                    auction_type=auction_type or "unknown",
                    current_bid=current_bid or "unknown",
                    end_time=end_time or "unknown",
                    raw_row=",".join(row[:8]),  # First 8 cols for context
                ))
                break  # Found in this row, move to next

    return matches


def check_inventory(quiet: bool = False) -> List[InventoryMatch]:
    """Main inventory check: download and scan all inventory files."""
    _ensure_dirs()
    target_domains = tuple(t.domain for t in GODADDY_TARGETS)
    all_matches: List[InventoryMatch] = []

    print("=" * 70)
    print("GoDaddy Auctions Inventory Check")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Targets: {', '.join(target_domains)}")
    print("=" * 70)

    # Step 1: Check metadata
    print("\n[1/2] Checking inventory metadata...")
    meta = fetch_metadata()
    if meta:
        print(f"  Metadata loaded: {type(meta).__name__}")
    else:
        print("  Metadata unavailable. Proceeding with direct downloads.")

    # Step 2: Download and scan each inventory file
    print(f"\n[2/2] Scanning {len(INVENTORY_FILES)} inventory files...")
    for filename in INVENTORY_FILES:
        matches = download_and_scan_inventory(filename, target_domains)
        all_matches.extend(matches)

    # Step 3: Report results
    print("\n" + "=" * 70)
    if all_matches:
        print(f"FOUND {len(all_matches)} DOMAIN(S) IN GODADDY AUCTIONS!")
        print("=" * 70)
        for m in all_matches:
            print(f"\n  DOMAIN:  {m.domain}")
            print(f"  SOURCE:  {m.source_file}")
            print(f"  TYPE:    {m.auction_type}")
            print(f"  BID:     {m.current_bid}")
            print(f"  ENDS:    {m.end_time}")
            print(f"  RAW:     {m.raw_row}")
            print(f"  ACTION:  https://auctions.godaddy.com/beta?q={m.domain}")

        # macOS notification for matches
        domains_found = set(m.domain for m in all_matches)
        _send_notification(
            "GoDaddy Auction ALERT",
            f"Found in auction: {', '.join(sorted(domains_found))}",
        )
    else:
        print("No target domains found in GoDaddy Auctions inventory.")
        print("=" * 70)

    # Step 4: Print upcoming dates reminder
    print("\nUpcoming auction windows:")
    _print_upcoming_dates(limit=3)

    # Step 5: Save results
    _save_results(all_matches)

    return all_matches


def _save_results(matches: List[InventoryMatch]) -> None:
    """Save scan results to JSON."""
    result = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "matches_found": len(matches),
        "matches": [
            {
                "domain": m.domain,
                "source_file": m.source_file,
                "auction_type": m.auction_type,
                "current_bid": m.current_bid,
                "end_time": m.end_time,
                "raw_row": m.raw_row,
            }
            for m in matches
        ],
        "targets_checked": [t.domain for t in GODADDY_TARGETS],
    }
    out_path = DATA_DIR / "sprint27_godaddy_scan_latest.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nResults saved to: {out_path}")


# ── Date Reporting ───────────────────────────────────────────────────

def _print_upcoming_dates(limit: int = 20) -> None:
    """Print upcoming key dates for all monitored domains."""
    assert 1 <= limit <= 50, f"Invalid limit: {limit}"

    events: List[Tuple[str, str, str]] = []  # (date, domain, event)
    for t in GODADDY_TARGETS:
        events.append((t.expiry_date, t.domain, "EXPIRES"))
        events.append((
            t.auction_start_est, t.domain,
            f"AUCTION STARTS (check daily!) risk={t.risk_level}"
        ))
        events.append((t.auction_end_est, t.domain, "AUCTION ENDS"))
        events.append((
            t.closeout_end_est, t.domain,
            "CLOSEOUT ENDS (if unsold, goes to redemption)"
        ))
        events.append((t.drop_est, t.domain, "ESTIMATED DROP"))

    events.sort(key=lambda x: x[0])
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Filter to future events only
    future = [e for e in events if e[0] >= now_str]
    printed = 0
    for date_str, domain, event in future:
        if printed >= limit:
            break
        days = _days_until(date_str)
        urgency = ""
        if days <= 7:
            urgency = " ** IMMINENT **"
        elif days <= 30:
            urgency = " * SOON *"
        print(f"  {date_str}  ({days:>4}d)  {domain:<25s}  {event}{urgency}")
        printed += 1


def print_all_dates() -> None:
    """Print comprehensive date report for all domains."""
    print("=" * 70)
    print("GoDaddy Auction Monitoring -- Key Dates")
    print(f"Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    print("=" * 70)

    for t in GODADDY_TARGETS:
        days_to_expiry = _days_until(t.expiry_date)
        days_to_auction = _days_until(t.auction_start_est)

        print(f"\n{'─' * 60}")
        print(f"  {t.domain}")
        print(f"  Risk: {t.risk_level}  |  Max Bid: ${t.max_bid_usd:,}")
        print(f"{'─' * 60}")
        print(f"  Expires:        {t.expiry_date}  ({days_to_expiry}d)")
        print(f"  Auction starts: {t.auction_start_est}  ({days_to_auction}d)")
        print(f"  Auction ends:   {t.auction_end_est}")
        print(f"  Closeout ends:  {t.closeout_end_est}")
        print(f"  Est. drop:      {t.drop_est}")
        print(f"  Manual check:   {AUCTION_SEARCH_URL.format(domain=t.domain)}")

        if days_to_auction <= 0:
            print(f"  STATUS: >>> AUCTION WINDOW OPEN -- CHECK NOW! <<<")
        elif days_to_expiry <= 0:
            print(f"  STATUS: Domain expired. Waiting for auction listing.")
        elif days_to_expiry <= 30:
            print(f"  STATUS: Expiring soon. Monitor RDAP for status changes.")
        else:
            print(f"  STATUS: Not yet expired. No action needed.")

    print(f"\n{'=' * 70}")
    print("Upcoming events (chronological):")
    print("=" * 70)
    _print_upcoming_dates(limit=30)


# ── Single Domain Check ──────────────────────────────────────────────

def check_single_domain(domain: str) -> None:
    """Print monitoring info and manual check URL for a single domain."""
    assert "." in domain, f"Invalid domain: {domain}"
    domain_lower = domain.lower().strip()

    print(f"\nGoDaddy Auction Check: {domain_lower}")
    print("=" * 50)

    # Find in our targets
    target: Optional[GoDaddyTarget] = None
    for t in GODADDY_TARGETS:
        if t.domain == domain_lower:
            target = t
            break

    if target:
        days_to_auction = _days_until(target.auction_start_est)
        print(f"  Registered target: YES")
        print(f"  Expiry:           {target.expiry_date}")
        print(f"  Auction starts:   {target.auction_start_est} ({days_to_auction}d)")
        print(f"  Auction ends:     {target.auction_end_est}")
        print(f"  Closeout ends:    {target.closeout_end_est}")
        print(f"  Est. drop:        {target.drop_est}")
        print(f"  Risk level:       {target.risk_level}")
        print(f"  Max bid:          ${target.max_bid_usd:,}")
    else:
        print(f"  Registered target: NO (not in monitoring list)")

    print(f"\n  Manual check URL:")
    print(f"  {AUCTION_SEARCH_URL.format(domain=domain_lower)}")
    print(f"\n  Steps:")
    print(f"  1. Open the URL above (requires GoDaddy login)")
    print(f"  2. If domain appears: note bid, time remaining, auction type")
    print(f"  3. If no results: domain is NOT in auction yet")
    print(f"  4. If found: click 'Watch' or place bid immediately")


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GoDaddy Auctions monitoring for Domain Hunter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/sprint27_godaddy_check.py --check-inventory\n"
            "  python3 scripts/sprint27_godaddy_check.py --dates\n"
            "  python3 scripts/sprint27_godaddy_check.py --check ghostautonomy.com\n"
        ),
    )
    parser.add_argument(
        "--check-inventory",
        action="store_true",
        help="Download and scan GoDaddy inventory files for target domains",
    )
    parser.add_argument(
        "--dates",
        action="store_true",
        help="Print all key dates for monitored GoDaddy domains",
    )
    parser.add_argument(
        "--check",
        type=str,
        metavar="DOMAIN",
        help="Print monitoring info for a specific domain",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()

    if args.check_inventory:
        matches = check_inventory(quiet=args.quiet)
        return 0 if not matches else 2  # Exit 2 = matches found (for cron alerting)
    elif args.dates:
        print_all_dates()
        return 0
    elif args.check:
        check_single_domain(args.check)
        return 0
    else:
        # Default: print dates + quick reminder
        print_all_dates()
        print("\n\nTip: Run with --check-inventory to scan GoDaddy inventory files.")
        print("Tip: Run with --check DOMAIN for single-domain lookup info.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

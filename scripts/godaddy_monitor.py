#!/usr/bin/env python3
"""Domain Hunter -- GoDaddy Auction Inventory Monitor.

Downloads GoDaddy's free daily inventory files (no auth required) and checks
for target domains in auctions, closeouts, and expiring listings.

Inventory files updated daily 7-8am PST at:
  https://inventory.auctions.godaddy.com/

Supports:
  - all_biddable_auctions.json.zip — currently in auction
  - closeout_listings.json.zip — closeout Buy Now (Dutch auction $9→$5)
  - all_expiring_auctions.json.zip — expiring soon
  - auctions_ending_today.json.zip — ending today
  - recent_listings.json.zip — newly listed

Run:   python scripts/godaddy_monitor.py
Cron:  0 8 * * * cd ~/Desktop/domainhunter && python scripts/godaddy_monitor.py
Test:  python scripts/godaddy_monitor.py --dry-run
Check: python scripts/godaddy_monitor.py --domain cytheris.com

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# -- Resolve project root --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog

# ── Constants ─────────────────────────────────────────────────────────
INVENTORY_BASE_URL: Final[str] = "https://inventory.auctions.godaddy.com/"
MAX_DOWNLOAD_SIZE: Final[int] = 100 * 1024 * 1024  # 100MB safety limit
REQUEST_TIMEOUT: Final[int] = 60
DATA_DIR: Final[Path] = _PROJECT_ROOT / "data"
RESULTS_DIR: Final[Path] = DATA_DIR / "godaddy_inventory"
CONFIG_PATH: Final[Path] = Path(__file__).parent / "monitored_domains.json"

INVENTORY_FILES: Final[dict[str, str]] = {
    "biddable": "all_biddable_auctions.json.zip",
    "closeout": "closeout_listings.json.zip",
    "expiring": "all_expiring_auctions.json.zip",
    "ending_today": "auctions_ending_today.json.zip",
    "ending_tomorrow": "auctions_ending_tomorrow.json.zip",
    "recent": "recent_listings.json.zip",
}

# Target domains to watch (loaded from config or defaults)
DEFAULT_TARGETS: Final[tuple[str, ...]] = (
    "cytheris.com",
    "ghostautonomy.com",
    "bside.com",
    "guerrameats.com",
    "infarm.com",
    "canoo.com",
    "northvolt.com",
)

logger = structlog.get_logger()


# ── Data Models ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class AuctionListing:
    """A domain found in GoDaddy inventory."""

    domain: str
    source: str  # biddable, closeout, expiring, ending_today, recent
    price: float = 0.0
    bid_count: int = 0
    end_time: str = ""
    traffic: int = 0
    domain_age: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert self.domain, "domain must not be empty"
        assert self.source in INVENTORY_FILES, f"unknown source: {self.source}"


@dataclass(frozen=True)
class MonitorResult:
    """Results from a single monitoring run."""

    timestamp: str
    targets_checked: int
    matches_found: int
    listings: list[dict[str, Any]]
    errors: list[str]

    def __post_init__(self) -> None:
        assert self.targets_checked >= 0
        assert self.matches_found >= 0


# ── Core Functions ────────────────────────────────────────────────────
def load_targets(config_path: Path) -> set[str]:
    """Load target domains from monitored_domains.json + defaults."""
    targets: set[str] = set(d.lower() for d in DEFAULT_TARGETS)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            assert "active_targets" in config
            for tier_domains in config["active_targets"].values():
                for entry in tier_domains[:200]:  # bounded
                    if isinstance(entry, dict) and "domain" in entry:
                        targets.add(entry["domain"].lower())
                    elif isinstance(entry, str):
                        targets.add(entry.lower())
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("config_load_error", error=str(e))

    logger.info("targets_loaded", count=len(targets))
    return targets


def download_inventory(file_key: str, dry_run: bool = False) -> list[dict[str, Any]]:
    """Download and extract a GoDaddy inventory ZIP file. Returns JSON list."""
    import urllib.request

    assert file_key in INVENTORY_FILES, f"unknown file_key: {file_key}"
    filename = INVENTORY_FILES[file_key]
    url = INVENTORY_BASE_URL + filename

    if dry_run:
        logger.info("dry_run_skip", file=filename)
        return []

    logger.info("downloading", file=filename)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DomainHunter/5.2"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            content = resp.read(MAX_DOWNLOAD_SIZE)

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist()[:5]:  # bounded
                if name.endswith(".json"):
                    with zf.open(name) as jf:
                        raw = json.loads(jf.read())
                        # GoDaddy uses {"meta": {...}, "data": [...]} wrapper
                        if isinstance(raw, dict) and "data" in raw:
                            data = raw["data"]
                        elif isinstance(raw, list):
                            data = raw
                        else:
                            logger.warning("unexpected_format", file=filename, type=type(raw).__name__)
                            return []
                        assert isinstance(data, list), "expected data to be a list"
                        logger.info("inventory_loaded", file=filename, count=len(data))
                        return data[:500_000]  # safety bound
        logger.warning("no_json_in_zip", file=filename)
        return []

    except Exception as e:
        logger.error("download_failed", file=filename, error=str(e))
        return []


def search_inventory(
    data: list[dict[str, Any]], targets: set[str], source: str
) -> list[AuctionListing]:
    """Search inventory data for target domains."""
    assert source in INVENTORY_FILES
    matches: list[AuctionListing] = []

    # GoDaddy JSON uses "domainName" (confirmed from actual inventory files)
    domain_keys = ("domainName", "DomainName", "domain", "Domain", "name")

    for item in data[:500_000]:  # bounded
        domain_val = ""
        for key in domain_keys:
            if key in item:
                domain_val = str(item[key]).lower().strip()
                break

        if domain_val in targets:
            price = float(item.get("Price", item.get("price", item.get("MinBid", 0))))
            bid_count = int(item.get("Bids", item.get("bids", item.get("BidCount", 0))))
            end_time = str(item.get("EndTime", item.get("endTime", item.get("AuctionEndTime", ""))))
            traffic = int(item.get("Traffic", item.get("traffic", 0)))
            age = int(item.get("DomainAge", item.get("domainAge", 0)))

            listing = AuctionListing(
                domain=domain_val,
                source=source,
                price=price,
                bid_count=bid_count,
                end_time=end_time,
                traffic=traffic,
                domain_age=age,
                raw=item,
            )
            matches.append(listing)
            logger.info(
                "MATCH_FOUND",
                domain=domain_val,
                source=source,
                price=price,
                bids=bid_count,
                end_time=end_time,
            )

    return matches


def run_monitor(
    targets: set[str],
    sources: tuple[str, ...] | None = None,
    dry_run: bool = False,
) -> MonitorResult:
    """Run the full monitoring sweep across all inventory files."""
    assert len(targets) > 0, "no targets to monitor"

    sources_to_check = sources or tuple(INVENTORY_FILES.keys())
    all_matches: list[AuctionListing] = []
    errors: list[str] = []

    for source_key in sources_to_check:
        data = download_inventory(source_key, dry_run=dry_run)
        if data:
            matches = search_inventory(data, targets, source_key)
            all_matches.extend(matches)
        elif not dry_run:
            errors.append(f"No data from {source_key}")

    # Serialize matches
    listings_data = [
        {
            "domain": m.domain,
            "source": m.source,
            "price": m.price,
            "bid_count": m.bid_count,
            "end_time": m.end_time,
            "traffic": m.traffic,
            "domain_age": m.domain_age,
        }
        for m in all_matches
    ]

    result = MonitorResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        targets_checked=len(targets),
        matches_found=len(all_matches),
        listings=listings_data,
        errors=errors,
    )
    return result


def save_results(result: MonitorResult) -> Path:
    """Save monitoring results to data/godaddy_inventory/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = RESULTS_DIR / f"gd_monitor_{date_str}.json"

    with open(out_path, "w") as f:
        json.dump(
            {
                "timestamp": result.timestamp,
                "targets_checked": result.targets_checked,
                "matches_found": result.matches_found,
                "listings": result.listings,
                "errors": result.errors,
            },
            f,
            indent=2,
        )
    logger.info("results_saved", path=str(out_path))
    return out_path


def format_report(result: MonitorResult) -> str:
    """Format a human-readable report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  GODADDY INVENTORY MONITOR — RESULTS")
    lines.append(f"  {result.timestamp}")
    lines.append("=" * 60)
    lines.append(f"\n  Targets checked: {result.targets_checked}")
    lines.append(f"  Matches found:   {result.matches_found}")

    if result.matches_found > 0:
        lines.append("\n  *** DOMAINS FOUND IN GODADDY INVENTORY ***\n")
        lines.append(f"  {'Domain':<25} {'Source':<15} {'Price':>8} {'Bids':>5} {'Ends':<20}")
        lines.append("  " + "-" * 75)
        for listing in result.listings:
            lines.append(
                f"  {listing['domain']:<25} "
                f"{listing['source']:<15} "
                f"${listing['price']:>7.2f} "
                f"{listing['bid_count']:>5} "
                f"{listing['end_time'][:19]:<20}"
            )
        lines.append("\n  ACTION: Buy at closeout or place bid at auctions.godaddy.com")
        lines.append("  MEMBERSHIP: $4.99/year required to bid/buy")
    else:
        lines.append("\n  No target domains found in current inventory.")
        lines.append("  (Domains appear ~26 days after expiry)")

    if result.errors:
        lines.append(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors[:10]:
            lines.append(f"    - {err}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def send_alert(result: MonitorResult) -> None:
    """Send alert if matches found (Slack webhook or stdout)."""
    if result.matches_found == 0:
        return

    webhook_url = os.environ.get("DOMAIN_HUNTER_SLACK_WEBHOOK")
    if not webhook_url:
        # Print to stdout for cron capture
        print("\n🚨 GODADDY INVENTORY ALERT: Target domains found!")
        for listing in result.listings:
            print(f"   → {listing['domain']} in {listing['source']} at ${listing['price']}")
        return

    import urllib.request

    payload = json.dumps({
        "text": f"🚨 GoDaddy Monitor: {result.matches_found} target(s) found!\n"
        + "\n".join(
            f"• {l['domain']} — {l['source']} — ${l['price']}"
            for l in result.listings[:5]
        )
    }).encode()

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("slack_alert_failed", error=str(e))


# ── CLI ───────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor GoDaddy inventory files for target domains"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip downloads, validate config only"
    )
    parser.add_argument(
        "--domain", type=str, help="Check a single domain (overrides config)"
    )
    parser.add_argument(
        "--source",
        choices=list(INVENTORY_FILES.keys()),
        help="Check only one inventory file",
    )
    parser.add_argument(
        "--closeout-only",
        action="store_true",
        help="Only check closeout listings (fastest)",
    )
    parser.add_argument(
        "--save", action="store_true", default=True, help="Save results to JSON"
    )
    parser.add_argument(
        "--no-alert", action="store_true", help="Suppress alerts"
    )
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()

    # Load targets
    if args.domain:
        targets = {args.domain.lower()}
    else:
        targets = load_targets(CONFIG_PATH)

    # Determine sources
    sources: tuple[str, ...] | None = None
    if args.source:
        sources = (args.source,)
    elif args.closeout_only:
        sources = ("closeout",)

    # Run monitor
    result = run_monitor(targets, sources=sources, dry_run=args.dry_run)

    # Output
    report = format_report(result)
    print(report)

    # Save
    if args.save and not args.dry_run:
        save_results(result)

    # Alert
    if not args.no_alert:
        send_alert(result)

    return 0 if not result.errors or result.matches_found > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

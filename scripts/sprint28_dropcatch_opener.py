#!/usr/bin/env python3
"""Open DropCatch backorder pages for batch domain processing.

Opens each domain's DropCatch backorder page in the default browser.
The user then manually clicks "Place Backorder" for each.

DropCatch URL format (confirmed):
  - Listing page: https://www.dropcatch.com/snap/listing/{domain}
  - Domain page:  https://www.dropcatch.com/domain/{domain}

DropCatch ALSO has a REST API (v2) via NameBright OAuth2:
  - Auth:      POST https://api.namebright.com/auth/token
  - Backorder: PUT  https://api.dropcatch.com/v2/backorders
  - Cancel:    DELETE https://api.dropcatch.com/v2/backorders
  - Legacy:    POST https://www.dropcatch.com/api/BackorderDomainsApi/BackOrderDomains
  See: clients/dropcatch_client.py for programmatic access.

Usage:
    python3 scripts/sprint28_dropcatch_opener.py
    python3 scripts/sprint28_dropcatch_opener.py --domains ghost.com foo.com
    python3 scripts/sprint28_dropcatch_opener.py --tier critical
    python3 scripts/sprint28_dropcatch_opener.py --tier critical,high
    python3 scripts/sprint28_dropcatch_opener.py --max-cost 200
    python3 scripts/sprint28_dropcatch_opener.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKORDER_QUEUE = PROJECT_ROOT / "data" / "backorder_queue.json"
DROPCATCH_LISTING_URL = "https://www.dropcatch.com/snap/listing/{domain}"
DROPCATCH_DOMAIN_URL = "https://www.dropcatch.com/domain/{domain}"
OPEN_DELAY_SEC = 2.0
MAX_BATCH_SIZE = 30


# ---------------------------------------------------------------------------
# Domain loading
# ---------------------------------------------------------------------------
def load_queue(queue_path: Path) -> list[dict]:
    """Load backorder_queue.json and return the queue list."""
    assert queue_path.exists(), f"Queue file not found: {queue_path}"
    with open(queue_path, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict), "Expected JSON object with 'queue' key"
    queue = data.get("queue", [])
    assert isinstance(queue, list), "Expected 'queue' to be an array"
    return queue


def filter_by_tier(queue: list[dict], tiers: list[str]) -> list[dict]:
    """Filter queue entries by tier values (S, A, B, C)."""
    assert len(tiers) > 0, "At least one tier must be specified"
    allowed = {t.strip().upper() for t in tiers}
    return [d for d in queue if d.get("tier", "").upper() in allowed]


def filter_by_max_cost(queue: list[dict], max_cost: float) -> list[dict]:
    """Filter queue entries by estimated value (est_value_low <= max_cost)."""
    assert max_cost > 0, "max_cost must be positive"
    return [d for d in queue if d.get("est_value_low", 0) <= max_cost]


def extract_domains(queue: list[dict]) -> list[str]:
    """Extract domain names from queue entries, deduplicating."""
    seen: set[str] = set()
    result: list[str] = []
    for entry in queue:
        domain = entry.get("domain", "").strip().lower()
        if domain and domain not in seen:
            seen.add(domain)
            result.append(domain)
    return result


# ---------------------------------------------------------------------------
# Browser opening
# ---------------------------------------------------------------------------
def open_dropcatch_pages(domains: list[str], dry_run: bool = False) -> dict:
    """Open DropCatch listing pages in the default browser.

    Returns dict with counts: opened, failed, total.
    """
    assert len(domains) > 0, "No domains to open"
    assert len(domains) <= MAX_BATCH_SIZE, (
        f"Batch too large ({len(domains)}). Max {MAX_BATCH_SIZE}."
    )

    opened = 0
    failed = 0

    for i, domain in enumerate(domains):
        url = DROPCATCH_LISTING_URL.format(domain=domain)
        if dry_run:
            print(f"  [DRY RUN] Would open: {url}")
            opened += 1
        else:
            try:
                webbrowser.open(url)
                print(f"  Opened: {url}")
                opened += 1
            except Exception as exc:
                print(f"  FAILED: {url} — {exc}")
                failed += 1

        # Delay between opens (skip after last)
        if i < len(domains) - 1 and not dry_run:
            time.sleep(OPEN_DELAY_SEC)

    return {"opened": opened, "failed": failed, "total": len(domains)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the DropCatch opener."""
    parser = argparse.ArgumentParser(
        description="Open DropCatch backorder pages in default browser."
    )
    parser.add_argument(
        "--domains", nargs="*", default=None,
        help="Specific domain names to open (overrides queue file)"
    )
    parser.add_argument(
        "--queue-file", type=str, default=str(BACKORDER_QUEUE),
        help="Path to backorder_queue.json"
    )
    parser.add_argument(
        "--tier", type=str, default=None,
        help="Comma-separated monitor tiers to filter (e.g. critical,high)"
    )
    parser.add_argument(
        "--max-cost", type=float, default=None,
        help="Filter domains with est_value_low <= this amount"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print URLs without opening browser"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on partial failure, 2 on total failure."""
    args = build_parser().parse_args(argv)

    # Collect domains
    if args.domains:
        domains = [d.strip().lower() for d in args.domains if d.strip()]
    else:
        queue = load_queue(Path(args.queue_file))
        if args.tier:
            tiers = [t.strip() for t in args.tier.split(",")]
            queue = filter_by_tier(queue, tiers)
        if args.max_cost is not None:
            queue = filter_by_max_cost(queue, args.max_cost)
        domains = extract_domains(queue)

    if not domains:
        print("No domains matched the filters.")
        return 0

    print(f"\nDropCatch Opener — {len(domains)} domain(s)")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Opening pages...\n")

    result = open_dropcatch_pages(domains, dry_run=args.dry_run)

    print(f"\nDone: {result['opened']} opened, {result['failed']} failed")

    if result["failed"] == result["total"]:
        return 2
    if result["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

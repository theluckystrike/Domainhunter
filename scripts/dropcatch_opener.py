#!/usr/bin/env python3
"""
dropcatch_opener.py — Batch-open DropCatch backorder pages via AppleScript.

DropCatch DOES have a REST API (v2) via NameBright OAuth2.
See clients/dropcatch_client.py for programmatic access.
This wrapper opens each domain's page in Chrome as a manual alternative.

Usage:
    python scripts/dropcatch_opener.py guerrameats.com sunnyray.org
    python scripts/dropcatch_opener.py --from-file domains.json --tier critical
    python scripts/dropcatch_opener.py --dry-run guerrameats.com
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

MAX_DOMAINS = 50
OPEN_DELAY_SEC = 3.0
SCRIPT_DIR = Path(__file__).resolve().parent
APPLESCRIPT_PATH = SCRIPT_DIR / "dropcatch_backorder.scpt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dropcatch_opener")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments. Returns namespace with domains list."""
    parser = argparse.ArgumentParser(
        description="Batch-open DropCatch backorder pages in Chrome."
    )
    parser.add_argument("domains", nargs="*", help="Domain names to open")
    parser.add_argument(
        "--from-file", type=str, default=None,
        help="JSON file with domain list (array or {tier: [domains]})"
    )
    parser.add_argument(
        "--tier", type=str, default=None,
        help="Filter tier when using --from-file with tiered JSON"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without opening anything"
    )
    args = parser.parse_args(argv)
    assert args.domains or args.from_file, \
        "Provide domain names as args or use --from-file"
    return args


def load_domains_from_file(filepath: str, tier: str | None) -> list[str]:
    """Load domain list from a JSON file. Supports flat array or tiered dict."""
    path = Path(filepath)
    assert path.exists(), f"File not found: {filepath}"
    with open(path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [str(d) for d in data]

    if isinstance(data, dict):
        if tier:
            assert tier in data, f"Tier '{tier}' not in file. Available: {list(data.keys())}"
            return [str(d) for d in data[tier]]
        # No tier specified: flatten all tiers
        all_domains = []
        for key in sorted(data.keys()):
            val = data[key]
            if isinstance(val, list):
                all_domains.extend(str(d) for d in val)
        assert len(all_domains) > 0, "No domains found in file"
        return all_domains

    raise ValueError(f"Unexpected JSON structure in {filepath}")


def validate_domain(domain: str) -> bool:
    """Basic domain name validation."""
    assert isinstance(domain, str), f"Domain must be a string, got {type(domain)}"
    if "." not in domain:
        return False
    if len(domain) > 253:
        return False
    if domain.startswith("-") or domain.startswith("."):
        return False
    return True


def open_dropcatch_page(domain: str, dry_run: bool = False) -> bool:
    """Open a single DropCatch backorder page via AppleScript. Returns success."""
    assert validate_domain(domain), f"Invalid domain: {domain}"
    assert APPLESCRIPT_PATH.exists(), f"AppleScript not found: {APPLESCRIPT_PATH}"

    url = f"https://www.dropcatch.com/snap/listing/{domain}"

    if dry_run:
        log.info("[DRY RUN] Would open: %s", url)
        return True

    result = subprocess.run(
        ["osascript", str(APPLESCRIPT_PATH), domain],
        capture_output=True, text=True, timeout=15,
    )

    if result.returncode != 0:
        log.error("Failed to open %s — osascript exit %d: %s",
                  domain, result.returncode, result.stderr.strip())
        return False

    log.info("Opened: %s", url)
    return True


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code (0=success, 1=partial, 2=total fail)."""
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # Collect domains from args and/or file
    domains: list[str] = list(args.domains) if args.domains else []
    if args.from_file:
        domains.extend(load_domains_from_file(args.from_file, args.tier))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for d in domains:
        d_lower = d.lower().strip()
        if d_lower not in seen:
            seen.add(d_lower)
            unique.append(d_lower)
    domains = unique

    assert len(domains) > 0, "No domains to process"
    assert len(domains) <= MAX_DOMAINS, \
        f"Too many domains ({len(domains)}). Max is {MAX_DOMAINS}."

    # Filter invalid domains
    valid = [d for d in domains if validate_domain(d)]
    invalid = [d for d in domains if not validate_domain(d)]
    for d in invalid:
        log.warning("Skipping invalid domain: %s", d)

    assert len(valid) > 0, "No valid domains after filtering"

    log.info("Opening %d domain(s) on DropCatch%s",
             len(valid), " [DRY RUN]" if args.dry_run else "")

    opened = 0
    failed = 0
    for i, domain in enumerate(valid):
        success = open_dropcatch_page(domain, dry_run=args.dry_run)
        if success:
            opened += 1
        else:
            failed += 1
        # Delay between tabs (skip after last one)
        if i < len(valid) - 1 and not args.dry_run:
            time.sleep(OPEN_DELAY_SEC)

    log.info("Done: %d opened, %d failed, %d skipped",
             opened, failed, len(invalid))

    if failed == len(valid):
        return 2
    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())

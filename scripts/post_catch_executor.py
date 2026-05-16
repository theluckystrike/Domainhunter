#!/usr/bin/env python3
"""Sprint 23 — Post-Catch Executor.

When a domain is caught via Dynadot backorder, this script executes the
post-catch playbook: DNS setup, landing page, marketplace listing.

Usage:
  python scripts/post_catch_executor.py ghostautonomy.com        # Full execution
  python scripts/post_catch_executor.py ghostautonomy.com --dry-run  # Preview
  python scripts/post_catch_executor.py --list                    # Show playbooks

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_QUEUE_PATH: Final[str] = os.path.join(_DATA_DIR, "backorder_queue.json")


def _load_queue() -> list[dict[str, Any]]:
    """Load backorder queue."""
    assert isinstance(_QUEUE_PATH, str)
    assert isinstance(_DATA_DIR, str)
    if not os.path.isfile(_QUEUE_PATH):
        return []
    with open(_QUEUE_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("queue", [])


def _load_playbook(domain: str) -> dict[str, Any] | None:
    """Load playbook for a specific domain from sprint22_playbooks."""
    assert isinstance(domain, str) and "." in domain
    assert os.path.isdir(_DATA_DIR), f"data dir missing: {_DATA_DIR}"
    candidates = sorted(
        [f for f in os.listdir(_DATA_DIR)
         if f.startswith("sprint22_playbooks") and f.endswith(".json")],
        reverse=True,
    )
    for fname in candidates[:3]:  # bounded
        path = os.path.join(_DATA_DIR, fname)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in data:
            if entry.get("domain", "").lower() == domain.lower():
                return entry
    return None


def _step_dns_setup(domain: str, dry_run: bool) -> str:
    """Step 1: Configure DNS for the caught domain."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    if dry_run:
        return f"DRY-RUN: Would set DNS for {domain} -> Cloudflare/parking page"

    # In production: use Dynadot API to set nameservers to Cloudflare
    # Then create A record pointing to landing page
    settings: dict[str, str] = {}
    env_path = os.path.join(_ROOT, ".env")
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    settings[k.strip()] = v.strip()

    api_key = settings.get("DYNADOT_API_KEY", "")
    if not api_key:
        return "ERROR: No Dynadot API key. Set DNS manually."

    try:
        import httpx
        # Set nameservers to Dynadot parking
        params = {
            "key": api_key,
            "command": "set_ns",
            "domain": domain,
            "ns0": "ns1.dynadot.com",
            "ns1": "ns2.dynadot.com",
        }
        resp = httpx.get("https://api.dynadot.com/api3.json", params=params, timeout=30)
        data = resp.json()
        return f"DNS set: {json.dumps(data.get('SetNsResponse', {}))}"
    except Exception as exc:
        return f"DNS ERROR: {exc}"


def _step_landing_page(domain: str, playbook: dict[str, Any] | None, dry_run: bool) -> str:
    """Step 2: Deploy initial landing page content."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    company = (playbook or {}).get("company_name", domain.split(".")[0].title())
    strategy = "FLIP"
    if playbook and playbook.get("playbook"):
        strategy = playbook["playbook"].get("primary", "FLIP")

    if strategy == "FLIP":
        content = f"""This premium domain is available for acquisition.

Domain: {domain}
Previously: {company}

For inquiries: Contact via Dan.com or Afternic marketplace listings.
"""
    elif strategy == "REDIRECT":
        content = f"""Coming soon: New content for {domain}.
Previously home of {company}.
"""
    else:
        content = f"""{domain} — Under new management.
Previously {company}. New content coming soon.
"""

    if dry_run:
        return f"DRY-RUN: Would deploy landing page for {domain} (strategy={strategy})"

    # Save landing page content for manual deployment
    page_dir = os.path.join(_DATA_DIR, "landing_pages")
    os.makedirs(page_dir, exist_ok=True)
    page_path = os.path.join(page_dir, f"{domain}.txt")
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"Landing page saved to {page_path}"


def _step_marketplace_listing(domain: str, playbook: dict[str, Any] | None, dry_run: bool) -> str:
    """Step 3: Prepare marketplace listing details."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    value = (playbook or {}).get("value_estimate", {})
    low = value.get("low", 500)
    high = value.get("high", 5000)
    buy_now = int(high * 0.8)  # BIN at 80% of high estimate
    min_offer = int(low * 0.5)  # Min offer at 50% of low estimate

    listing = {
        "domain": domain,
        "buy_now_price": buy_now,
        "min_offer": min_offer,
        "marketplaces": ["Dan.com", "Afternic", "Sedo"],
        "description": f"Premium domain previously used by funded startup. Strong backlink profile.",
    }

    if dry_run:
        return f"DRY-RUN: Would list {domain} — BIN=${buy_now:,}, min offer=${min_offer:,}"

    listing_dir = os.path.join(_DATA_DIR, "marketplace_listings")
    os.makedirs(listing_dir, exist_ok=True)
    listing_path = os.path.join(listing_dir, f"{domain}.json")
    with open(listing_path, "w", encoding="utf-8") as fh:
        json.dump(listing, fh, indent=2)
    return f"Listing saved to {listing_path}"


def _step_notify(domain: str, dry_run: bool) -> str:
    """Step 4: Send notification about successful catch."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    if dry_run:
        return f"DRY-RUN: Would send notification for {domain} catch"
    try:
        import subprocess
        result = subprocess.run(
            ["osascript", "-e",
             f'display notification "DOMAIN CAUGHT: {domain}" '
             f'with title "Domain Hunter" sound name "Glass"'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"Notification warning: osascript exit={result.returncode}"
        return f"macOS notification sent for {domain}"
    except Exception as exc:
        return f"Notification failed (non-critical): {exc}"


def _step_portfolio_add(domain: str, dry_run: bool) -> str:
    """Step 5: Add caught domain to portfolio tracker."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    if dry_run:
        return f"DRY-RUN: Would add {domain} to portfolio"

    try:
        import subprocess
        tracker = os.path.join(_ROOT, "scripts", "portfolio_tracker.py")
        if not os.path.isfile(tracker):
            return f"Portfolio tracker not found at {tracker}"
        result = subprocess.run(
            [sys.executable, tracker, "add", domain,
             "--cost", "10.99", "--method", "backorder_catch",
             "--source", "drop_monitor"],
            capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"Portfolio add warning: {err or output}"
        return output or f"Added {domain} to portfolio"
    except Exception as exc:
        return f"Portfolio tracking failed (non-critical): {exc}"


def execute_post_catch(domain: str, dry_run: bool = False) -> dict[str, str]:
    """Execute full post-catch playbook for a domain."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  POST-CATCH EXECUTOR: {domain}", file=sys.stderr)
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'}", file=sys.stderr)
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    playbook = _load_playbook(domain)
    if playbook:
        print(f"  Playbook found: strategy={playbook.get('playbook', {}).get('primary', '?')}", file=sys.stderr)
    else:
        print(f"  No playbook found for {domain}, using defaults", file=sys.stderr)

    results: dict[str, str] = {}

    # Step 1: DNS
    print(f"\n  Step 1: DNS Setup", file=sys.stderr)
    results["dns"] = _step_dns_setup(domain, dry_run)
    print(f"    {results['dns']}", file=sys.stderr)

    # Step 2: Landing Page
    print(f"\n  Step 2: Landing Page", file=sys.stderr)
    results["landing"] = _step_landing_page(domain, playbook, dry_run)
    print(f"    {results['landing']}", file=sys.stderr)

    # Step 3: Marketplace Listing
    print(f"\n  Step 3: Marketplace Listing", file=sys.stderr)
    results["listing"] = _step_marketplace_listing(domain, playbook, dry_run)
    print(f"    {results['listing']}", file=sys.stderr)

    # Step 4: Notification
    print(f"\n  Step 4: Notification", file=sys.stderr)
    results["notify"] = _step_notify(domain, dry_run)
    print(f"    {results['notify']}", file=sys.stderr)

    # Step 5: Portfolio Tracking
    print(f"\n  Step 5: Portfolio Tracking", file=sys.stderr)
    results["portfolio"] = _step_portfolio_add(domain, dry_run)
    print(f"    {results['portfolio']}", file=sys.stderr)

    # Log
    log_dir = os.path.join(_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"post_catch_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump({"domain": domain, "dry_run": dry_run, "results": results,
                    "timestamp": datetime.now(timezone.utc).isoformat()}, fh, indent=2)
    print(f"\n  Log saved to: {log_path}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return results


def main() -> None:
    """CLI entry point."""
    assert os.path.isdir(_ROOT)
    assert isinstance(_DATA_DIR, str)
    import argparse
    parser = argparse.ArgumentParser(description="Post-Catch Executor — domain acquisition workflow")
    parser.add_argument("domain", nargs="?", help="Domain that was caught")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--list", action="store_true", help="List domains with playbooks")
    args = parser.parse_args()

    if args.list:
        queue = _load_queue()
        print(f"Backorder Queue ({len(queue)} domains):")
        for q in queue:
            print(f"  {q['domain']:<28} status={q['backorder_status']:<10} "
                  f"playbook={q.get('playbook', '?'):<10} "
                  f"drop={q.get('drop_est', '?')}")
        return

    if not args.domain:
        parser.error("domain is required (or use --list)")

    execute_post_catch(args.domain, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

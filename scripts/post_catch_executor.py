#!/usr/bin/env python3
"""Sprint 23 — Post-Catch Executor.

When a domain is caught via Dynadot backorder or DropCatch, this script
executes the post-catch playbook: DNS setup, landing page, marketplace listing.

Usage:
  python scripts/post_catch_executor.py ghostautonomy.com                  # Full (auto-detect)
  python scripts/post_catch_executor.py ghostautonomy.com --dry-run        # Preview
  python scripts/post_catch_executor.py ghostautonomy.com --source dropcatch  # Force DropCatch path
  python scripts/post_catch_executor.py ghostautonomy.com --source dynadot    # Force Dynadot path
  python scripts/post_catch_executor.py --list                             # Show playbooks

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

# Default Cloudflare nameservers (overridable via .env CLOUDFLARE_NS1 / CLOUDFLARE_NS2)
_DEFAULT_CF_NS1: Final[str] = "ns1.cloudflare.com"
_DEFAULT_CF_NS2: Final[str] = "ns2.cloudflare.com"

# Valid source values for --source flag
_VALID_SOURCES: Final[tuple[str, ...]] = ("dynadot", "dropcatch", "auto")

# DropCatch registrar identifiers used for auto-detection
_DROPCATCH_REGISTRAR_KEYWORDS: Final[tuple[str, ...]] = (
    "dropcatch", "namebright", "turbodns",
)


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


def _detect_source(domain: str, source_flag: str) -> str:
    """Detect whether domain was caught via Dynadot or DropCatch.

    Args:
        domain: The caught domain name.
        source_flag: CLI --source value ("dynadot", "dropcatch", or "auto").

    Returns:
        "dynadot" or "dropcatch".
    """
    assert isinstance(domain, str) and "." in domain
    assert source_flag in _VALID_SOURCES, f"Invalid source: {source_flag}"

    if source_flag != "auto":
        return source_flag

    # Auto-detect: check backorder queue for registrar/source metadata
    queue = _load_queue()
    for entry in queue[:500]:  # bounded
        if entry.get("domain", "").lower() == domain.lower():
            registrar = entry.get("registrar", "").lower()
            source = entry.get("source", "").lower()
            combined = f"{registrar} {source}"
            for keyword in _DROPCATCH_REGISTRAR_KEYWORDS:
                if keyword in combined:
                    return "dropcatch"
            return "dynadot"

    # Default to Dynadot if no queue entry found
    return "dynadot"


def _load_namebright_ns() -> tuple[str, str]:
    """Load Cloudflare nameserver overrides from .env, or use defaults."""
    env_path = os.path.join(_ROOT, ".env")
    ns1 = _DEFAULT_CF_NS1
    ns2 = _DEFAULT_CF_NS2
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "CLOUDFLARE_NS1":
                        ns1 = v
                    elif k == "CLOUDFLARE_NS2":
                        ns2 = v
    assert "." in ns1, f"Invalid NS1: {ns1}"
    assert "." in ns2, f"Invalid NS2: {ns2}"
    return (ns1, ns2)


def _step_dns_namebright(domain: str, landing_ip: str, dry_run: bool) -> str:
    """Step 1b: Configure DNS via NameBright API for DropCatch-caught domains.

    Sets nameservers to Cloudflare and adds an A record pointing to the
    for-sale landing page.
    """
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)

    ns1, ns2 = _load_namebright_ns()

    if dry_run:
        return (
            f"DRY-RUN: Would set NameBright DNS for {domain} -> "
            f"NS=[{ns1}, {ns2}], A=@->{landing_ip}"
        )

    try:
        from config.settings import Settings
        settings = Settings()
        client_id = settings.dropcatch_client_id
        client_secret = settings.dropcatch_api_secret
        if not client_id or not client_secret:
            return "ERROR: No DropCatch/NameBright credentials. Set DNS manually."

        from clients.namebright_client import NameBrightClient
        client = NameBrightClient(client_id, client_secret)

        # Set nameservers to Cloudflare
        ns_result = client.set_nameservers(domain, [ns1, ns2])

        # Add A record for landing page
        a_result = client.add_dns_record(domain, "A", "@", landing_ip, 300)

        return (
            f"NameBright DNS set: NS=[{ns1}, {ns2}], "
            f"A=@->{landing_ip} (ns={ns_result}, a={a_result})"
        )
    except Exception as exc:
        return f"NameBright DNS ERROR: {exc}"


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


def _step_notify(domain: str, source: str, dry_run: bool) -> str:
    """Step 4: Send notification about successful catch via notify.py.

    Uses the multi-channel notification dispatcher (ntfy, email, stdout)
    instead of macOS-only osascript.
    """
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    if dry_run:
        return f"DRY-RUN: Would send notification for {domain} catch (source={source})"
    try:
        from scripts.notify import send_alert, format_domain_alert
        subject, body = format_domain_alert(
            domain=domain,
            event=f"CAUGHT via {source}",
            extra=f"Post-catch executor completed. Source: {source}.",
        )
        results = send_alert(subject, body, priority="high")
        channels = [f"{r.channel}={'OK' if r.success else 'FAIL'}" for r in results]
        return f"Notification sent: {', '.join(channels)}"
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


def execute_post_catch(
    domain: str,
    dry_run: bool = False,
    source: str = "auto",
    landing_ip: str = "185.199.108.153",
) -> dict[str, str]:
    """Execute full post-catch playbook for a domain.

    Args:
        domain: The caught domain name.
        dry_run: If True, preview actions without executing.
        source: Catch source — "dynadot", "dropcatch", or "auto" (auto-detect).
        landing_ip: IP address for the for-sale landing page A record.
    """
    assert isinstance(domain, str) and "." in domain
    assert isinstance(dry_run, bool)
    assert source in _VALID_SOURCES, f"Invalid source: {source}"

    detected_source = _detect_source(domain, source)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  POST-CATCH EXECUTOR: {domain}", file=sys.stderr)
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'}", file=sys.stderr)
    print(f"  Source: {detected_source} (flag={source})", file=sys.stderr)
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    playbook = _load_playbook(domain)
    if playbook:
        print(f"  Playbook found: strategy={playbook.get('playbook', {}).get('primary', '?')}", file=sys.stderr)
    else:
        print(f"  No playbook found for {domain}, using defaults", file=sys.stderr)

    results: dict[str, str] = {}

    # Step 1: DNS Setup (Dynadot)
    print(f"\n  Step 1: DNS Setup (Dynadot)", file=sys.stderr)
    if detected_source == "dynadot":
        results["dns_dynadot"] = _step_dns_setup(domain, dry_run)
    else:
        results["dns_dynadot"] = f"SKIPPED: source={detected_source}, not dynadot"
    print(f"    {results['dns_dynadot']}", file=sys.stderr)

    # Step 1b: DNS Setup (NameBright — for DropCatch catches)
    print(f"\n  Step 1b: DNS Setup (NameBright)", file=sys.stderr)
    if detected_source == "dropcatch":
        results["dns_namebright"] = _step_dns_namebright(domain, landing_ip, dry_run)
    else:
        results["dns_namebright"] = f"SKIPPED: source={detected_source}, not dropcatch"
    print(f"    {results['dns_namebright']}", file=sys.stderr)

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
    results["notify"] = _step_notify(domain, detected_source, dry_run)
    print(f"    {results['notify']}", file=sys.stderr)

    # Step 5: Portfolio Tracking
    print(f"\n  Step 5: Portfolio Tracking", file=sys.stderr)
    results["portfolio"] = _step_portfolio_add(domain, dry_run)
    print(f"    {results['portfolio']}", file=sys.stderr)

    # Log
    log_dir = os.path.join(_ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(
        log_dir,
        f"post_catch_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump({
            "domain": domain, "dry_run": dry_run, "source": detected_source,
            "results": results, "timestamp": datetime.now(timezone.utc).isoformat(),
        }, fh, indent=2)
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
    parser.add_argument(
        "--source",
        choices=list(_VALID_SOURCES),
        default="auto",
        help="Catch source: dynadot, dropcatch, or auto (default: auto-detect)",
    )
    parser.add_argument(
        "--landing-ip",
        default="185.199.108.153",
        help="Landing page IP for DNS A record (default: 185.199.108.153)",
    )
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

    execute_post_catch(
        args.domain,
        dry_run=args.dry_run,
        source=args.source,
        landing_ip=args.landing_ip,
    )


if __name__ == "__main__":
    main()

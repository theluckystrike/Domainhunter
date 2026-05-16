#!/usr/bin/env python3
"""Sprint 29 — Register top 2 Kaggle domains via Dynadot API.

First revenue-generating acquisitions in the pipeline's history.
Domains selected from sprint28_kaggle_validated.json (43 available).

Selection criteria:
  1. viryd.com — 5-letter .com, shortest in pool, cleantech, $9.8M funding,
     est $1K-$10K aftermarket. 5L .coms have liquid resale market.
  2. neovistainc.com — biotech/healthtech, $130M NeoVista funding,
     press backlinks from TechCrunch/Crunchbase, est $500-$5K.

NASA P10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -- Resolve project root so imports work from scripts/ --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from clients.dynadot_client import (  # noqa: E402
    DynadotAuthError,
    DynadotClient,
    DynadotError,
    DomainSearchResult,
    RegisterResult,
    SetNameserversResult,
)
from config.settings import Settings  # noqa: E402

# --- Constants ---

_TARGETS: list[dict[str, Any]] = [
    {
        "domain": "viryd.com",
        "company": "Viryd Technologies",
        "funding": 9800000,
        "sector": "cleantech",
        "score": 0.0,
        "estimated_value": "$1,000-$10,000",
        "rationale": "5-letter .com, shortest in pool. 5L .coms have liquid aftermarket ($200-$2000+).",
    },
    {
        "domain": "neovistainc.com",
        "company": "NeoVista",
        "funding": 130000000,
        "sector": "healthtech",
        "score": 74.0,
        "estimated_value": "$500-$5,000",
        "rationale": "$130M funded biotech. Press backlinks from TechCrunch/Crunchbase/PitchBook.",
    },
]

_CLOUDFLARE_NS: list[str] = [
    "greg.ns.cloudflare.com",
    "janet.ns.cloudflare.com",
]

_COST_PER_DOMAIN: float = 10.99
_DYNADOT_BALANCE: float = 25.00
_RESULTS_PATH: Path = _PROJECT_ROOT / "data" / "sprint29_acquisitions.json"


# --- Frozen result ---

@dataclass(frozen=True)
class AcquisitionRecord:
    """Single domain acquisition outcome."""

    domain: str
    search_available: bool
    search_price_usd: float
    registered: bool
    register_message: str
    register_expiration: str
    ns_set: bool
    ns_message: str
    cost: float
    company: str
    funding: int
    sector: str
    estimated_value: str
    rationale: str


# --- Core logic ---


async def check_and_register(
    client: DynadotClient, target: dict[str, Any], dry_run: bool
) -> AcquisitionRecord:
    """Search, register, and set NS for a single domain.

    Args:
        client: Dynadot API client instance.
        target: Domain target dict with metadata.
        dry_run: If True, skip actual registration.

    Returns:
        AcquisitionRecord with full outcome.
    """
    assert isinstance(target, dict), "target must be a dict"
    assert "domain" in target, "target must have 'domain' key"

    domain: str = target["domain"]
    print(f"\n  === {domain} ===")

    # Step 1: Search to confirm availability
    print(f"  [1/3] Searching availability...")
    try:
        search_result: DomainSearchResult = await client.search(domain)
        print(f"        Available: {search_result.available}, "
              f"Price: ${search_result.price_usd}")
    except DynadotError as exc:
        print(f"        Search FAILED: {exc}")
        return AcquisitionRecord(
            domain=domain, search_available=False, search_price_usd=0.0,
            registered=False, register_message=f"Search failed: {exc}",
            register_expiration="", ns_set=False, ns_message="",
            cost=0.0, company=target.get("company", ""),
            funding=target.get("funding", 0), sector=target.get("sector", ""),
            estimated_value=target.get("estimated_value", ""),
            rationale=target.get("rationale", ""),
        )

    if not search_result.available:
        print(f"        ABORT: Domain is NOT available (already registered)")
        return AcquisitionRecord(
            domain=domain, search_available=False,
            search_price_usd=search_result.price_usd,
            registered=False, register_message="Domain not available",
            register_expiration="", ns_set=False, ns_message="",
            cost=0.0, company=target.get("company", ""),
            funding=target.get("funding", 0), sector=target.get("sector", ""),
            estimated_value=target.get("estimated_value", ""),
            rationale=target.get("rationale", ""),
        )

    # Step 2: Register
    print(f"  [2/3] Registering domain (1 year, ${_COST_PER_DOMAIN})...")
    if dry_run:
        print(f"        [DRY RUN] Skipping actual registration")
        reg_success: bool = False
        reg_msg: str = "[DRY RUN] Would register"
        reg_exp: str = ""
    else:
        try:
            reg_result: RegisterResult = await client.register_domain(
                domain, duration=1, currency="USD"
            )
            reg_success = reg_result.success
            reg_msg = reg_result.message
            reg_exp = reg_result.expiration
            print(f"        Success: {reg_success}, Message: {reg_msg}")
            if reg_exp:
                print(f"        Expiration: {reg_exp}")
        except DynadotError as exc:
            reg_success = False
            reg_msg = f"Registration failed: {exc}"
            reg_exp = ""
            print(f"        FAILED: {exc}")

    # Step 3: Set nameservers (only if registration succeeded)
    ns_ok: bool = False
    ns_msg: str = ""
    if reg_success and not dry_run:
        print(f"  [3/3] Setting nameservers to Cloudflare...")
        try:
            ns_result: SetNameserversResult = await client.set_nameservers(
                domain, _CLOUDFLARE_NS
            )
            ns_ok = ns_result.success
            ns_msg = ns_result.message
            print(f"        NS set: {ns_ok}, Message: {ns_msg}")
        except DynadotError as exc:
            ns_msg = f"NS update failed: {exc}"
            print(f"        NS FAILED: {exc}")
    elif dry_run:
        print(f"  [3/3] [DRY RUN] Would set NS to {_CLOUDFLARE_NS}")
        ns_msg = "[DRY RUN] Would set NS"
    else:
        print(f"  [3/3] Skipping NS (registration did not succeed)")

    cost: float = _COST_PER_DOMAIN if reg_success else 0.0

    return AcquisitionRecord(
        domain=domain, search_available=True,
        search_price_usd=search_result.price_usd,
        registered=reg_success, register_message=reg_msg,
        register_expiration=reg_exp, ns_set=ns_ok, ns_message=ns_msg,
        cost=cost, company=target.get("company", ""),
        funding=target.get("funding", 0), sector=target.get("sector", ""),
        estimated_value=target.get("estimated_value", ""),
        rationale=target.get("rationale", ""),
    )


def save_acquisitions(records: list[AcquisitionRecord], path: Path) -> None:
    """Save acquisition results to JSON."""
    assert isinstance(records, list), "records must be a list"
    assert path.parent.exists(), f"Directory not found: {path.parent}"

    total_cost: float = sum(r.cost for r in records)
    successful: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for r in records:
        entry: dict[str, Any] = {
            "domain": r.domain,
            "cost": r.cost,
            "method": "direct_registration",
            "source": "kaggle_rdap_probe",
            "registrar": "Dynadot",
            "company": r.company,
            "funding": r.funding,
            "sector": r.sector,
            "strategy": "FLIP",
            "estimated_value": r.estimated_value,
            "rationale": r.rationale,
            "search_available": r.search_available,
            "search_price_usd": r.search_price_usd,
            "register_message": r.register_message,
            "register_expiration": r.register_expiration,
            "ns_set": r.ns_set,
            "ns_message": r.ns_message,
        }
        if r.registered:
            successful.append(entry)
        else:
            failed.append(entry)

    output: dict[str, Any] = {
        "acquisition_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "acquisition_timestamp": datetime.now(timezone.utc).isoformat(),
        "sprint": 29,
        "domains_registered": successful,
        "domains_failed": failed,
        "total_cost": round(total_cost, 2),
        "balance_before": _DYNADOT_BALANCE,
        "balance_remaining": round(_DYNADOT_BALANCE - total_cost, 2),
        "summary": (
            f"Attempted {len(records)} registrations. "
            f"{len(successful)} succeeded, {len(failed)} failed. "
            f"Total cost: ${total_cost:.2f}."
        ),
    }

    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"\n  Results saved to {path}")


def print_summary(records: list[AcquisitionRecord]) -> None:
    """Print a human-readable summary."""
    assert isinstance(records, list), "records must be a list"

    total_cost: float = sum(r.cost for r in records)
    ok: int = sum(1 for r in records if r.registered)
    fail: int = len(records) - ok

    print("\n" + "=" * 60)
    print("  SPRINT 29 — ACQUISITION SUMMARY")
    print("=" * 60)
    for r in records:
        tag: str = "REGISTERED" if r.registered else "FAILED"
        print(f"  [{tag}] {r.domain}")
        print(f"    Company: {r.company} | Sector: {r.sector}")
        print(f"    Funding: ${r.funding:,.0f} | Est. Value: {r.estimated_value}")
        print(f"    Available: {r.search_available} | Price: ${r.search_price_usd}")
        print(f"    Message: {r.register_message}")
        if r.registered:
            print(f"    Cost: ${r.cost:.2f} | NS Set: {r.ns_set}")
        print()
    print(f"  Total: {ok} registered, {fail} failed, ${total_cost:.2f} spent")
    print(f"  Balance remaining: ${_DYNADOT_BALANCE - total_cost:.2f}")
    print("=" * 60)


# --- Entry point ---


async def run(dry_run: bool = False) -> int:
    """Execute domain registrations.

    Args:
        dry_run: If True, search only, no actual registration.

    Returns:
        0 on success, 1 on error.
    """
    assert isinstance(dry_run, bool), "dry_run must be a boolean"

    print("\n  Sprint 29 — Domain Registration")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Targets: {len(_TARGETS)} domains")
    print(f"  Budget: ${_DYNADOT_BALANCE:.2f} (${_COST_PER_DOMAIN}/domain)")

    # Load settings
    try:
        settings: Settings = Settings()
    except Exception as exc:
        print(f"  Settings error: {exc}", file=sys.stderr)
        return 1

    if not settings.dynadot_api_key:
        print("  ERROR: DYNADOT_API_KEY not set in .env")
        return 1

    # Budget check
    total_needed: float = _COST_PER_DOMAIN * len(_TARGETS)
    if total_needed > _DYNADOT_BALANCE:
        print(f"  WARNING: Need ${total_needed:.2f} but balance is ${_DYNADOT_BALANCE:.2f}")
        print(f"  Proceeding anyway — API will reject if insufficient funds")

    # Create client (NOT dry_run in client — we want real search results)
    client: DynadotClient = DynadotClient(settings, dry_run=False)

    # Process each target
    records: list[AcquisitionRecord] = []
    for target in _TARGETS:
        record: AcquisitionRecord = await check_and_register(client, target, dry_run)
        records.append(record)

    # Report and save
    print_summary(records)
    save_acquisitions(records, _RESULTS_PATH)

    ok: int = sum(1 for r in records if r.registered)
    return 0 if ok > 0 else 1


def main() -> int:
    """CLI entry point."""
    dry_run: bool = "--dry-run" in sys.argv
    return asyncio.run(run(dry_run=dry_run))


if __name__ == "__main__":
    raise SystemExit(main())

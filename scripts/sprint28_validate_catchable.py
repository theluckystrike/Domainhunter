#!/usr/bin/env python3
"""Sprint 28 — Validate 53 CATCHABLE domains from Kaggle RDAP probe.

RDAP 404 can mean genuinely available, re-registered with stale cache,
subdomain not independently registrable, or TLD-specific RDAP gap.
This script filters subdomains, runs HTTP HEAD checks, and queries
Dynadot for direct registration availability.

NASA P10: functions <60 lines, 2+ assertions, bounded loops.
No global mutable state.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
INPUT_PATH: Path = (
    Path(__file__).resolve().parent.parent / "data" / "sprint27_kaggle_rdap_results.json"
)
OUTPUT_PATH: Path = (
    Path(__file__).resolve().parent.parent / "data" / "sprint28_kaggle_validated.json"
)
HTTP_TIMEOUT_S: float = 5.0
DYNADOT_TIMEOUT_S: float = 15.0
DYNADOT_BASE_URL: str = "https://api.dynadot.com/api3.json"
DYNADOT_COM_PRICE_USD: float = 10.99  # Standard Dynadot .com registration price
MAX_DOMAINS: int = 100  # bounded-loop guard
MAX_CONCURRENT: int = 10  # parallel HTTP checks
USER_AGENT: str = "DomainHunter-Validator/1.0"

# Ultra-premium 4-letter .coms from Sprint 26
ULTRA_PREMIUM_4L: list[dict[str, Any]] = [
    {"domain": "sbio.com", "funding_label": "$144M"},
    {"domain": "sddt.com", "funding_label": "-"},
    {"domain": "htch.com", "funding_label": "-"},
    {"domain": "ants.com", "funding_label": "$28M"},
    {"domain": "moli.com", "funding_label": "-"},
    {"domain": "aryx.com", "funding_label": "-"},
    {"domain": "eons.com", "funding_label": "$32M"},
    {"domain": "cozi.com", "funding_label": "-"},
    {"domain": "5g.com", "funding_label": "-"},
]


# ---------------------------------------------------------------------------
# Step 1: Load data
# ---------------------------------------------------------------------------
def load_catchable(path: Path) -> list[dict[str, Any]]:
    """Load CATCHABLE domains from Sprint 27 RDAP results."""
    assert path.exists(), f"Input file missing: {path}"
    with open(path, "r") as fh:
        data: dict[str, Any] = json.load(fh)
    assert "catchable" in data, "Expected 'catchable' key in JSON"
    catchable: list[dict[str, Any]] = data["catchable"]
    assert isinstance(catchable, list), "catchable must be a list"
    assert len(catchable) <= MAX_DOMAINS, f"Too many domains: {len(catchable)}"
    return catchable


# ---------------------------------------------------------------------------
# Step 2: Filter subdomains
# ---------------------------------------------------------------------------
def is_subdomain(domain: str) -> bool:
    """Check if domain has more than one dot (i.e., is a subdomain).

    Examples:
        corp.mail.com -> True (2 dots)
        example.com -> False (1 dot)
        in2games.uk.com -> True (2 dots, but .uk.com is a ccTLD combo — still not registrable as-is)
    """
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) > 0, "domain must not be empty"
    return domain.count(".") > 1


def filter_subdomains(
    catchable: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split catchable into registrable domains and filtered subdomains."""
    assert isinstance(catchable, list), "catchable must be a list"
    registrable: list[dict[str, Any]] = []
    subdomains: list[dict[str, Any]] = []
    for idx, entry in enumerate(catchable):
        if idx >= MAX_DOMAINS:
            break
        domain: str = entry.get("domain", "")
        assert isinstance(domain, str) and len(domain) > 0, f"Invalid domain at index {idx}"
        if is_subdomain(domain):
            subdomains.append(entry)
        else:
            registrable.append(entry)
    assert len(registrable) + len(subdomains) == min(len(catchable), MAX_DOMAINS)
    return registrable, subdomains


# ---------------------------------------------------------------------------
# Step 3: HTTP HEAD check
# ---------------------------------------------------------------------------
async def http_head_check(
    domain: str, client: httpx.AsyncClient
) -> dict[str, Any]:
    """HTTP HEAD request to determine if domain is live.

    Returns dict with domain, http_status, status_label, and error fields.
    """
    assert isinstance(domain, str) and len(domain) > 0
    assert "." in domain
    result: dict[str, Any] = {
        "domain": domain,
        "http_status": 0,
        "status_label": "UNKNOWN",
        "error": None,
    }
    url: str = f"https://{domain}"
    try:
        resp: httpx.Response = await client.head(
            url, follow_redirects=True, timeout=HTTP_TIMEOUT_S
        )
        result["http_status"] = resp.status_code
        if resp.status_code in (200, 301, 302, 303, 307, 308, 403):
            result["status_label"] = "REGISTERED"
        else:
            result["status_label"] = "MAYBE_AVAILABLE"
    except (httpx.ConnectError, httpx.ConnectTimeout):
        result["status_label"] = "NO_CONNECT"
        result["error"] = "connection_failed"
    except httpx.TimeoutException:
        result["status_label"] = "TIMEOUT"
        result["error"] = "timeout"
    except httpx.TooManyRedirects:
        result["status_label"] = "REGISTERED"
        result["error"] = "too_many_redirects"
    except Exception as exc:
        result["status_label"] = "ERROR"
        result["error"] = str(exc)[:200]

    # If HTTPS failed with connection error, try HTTP as fallback
    if result["status_label"] in ("NO_CONNECT", "TIMEOUT", "ERROR"):
        http_url: str = f"http://{domain}"
        try:
            resp2: httpx.Response = await client.head(
                http_url, follow_redirects=True, timeout=HTTP_TIMEOUT_S
            )
            result["http_status"] = resp2.status_code
            if resp2.status_code in (200, 301, 302, 303, 307, 308, 403):
                result["status_label"] = "REGISTERED"
                result["error"] = None
        except Exception:
            pass  # Keep original status

    return result


async def batch_http_checks(
    domains: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run HTTP HEAD checks on all domains with bounded concurrency."""
    assert isinstance(domains, list), "domains must be a list"
    assert len(domains) <= MAX_DOMAINS, f"Too many domains: {len(domains)}"

    semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        verify=False,  # Some expired domains have bad certs
    ) as client:

        async def check_with_semaphore(entry: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                domain: str = entry["domain"]
                http_result = await http_head_check(domain, client)
                # Merge original entry data
                merged: dict[str, Any] = {**entry, **http_result}
                return merged

        tasks = [check_with_semaphore(entry) for entry in domains[:MAX_DOMAINS]]
        results = await asyncio.gather(*tasks)

    assert len(results) == min(len(domains), MAX_DOMAINS)
    return results


# ---------------------------------------------------------------------------
# Step 4: Dynadot availability check
# ---------------------------------------------------------------------------
def load_dynadot_api_key() -> str:
    """Load Dynadot API key from .env file."""
    env_path: Path = Path(__file__).resolve().parent.parent / ".env"
    assert env_path.exists(), f".env file missing: {env_path}"
    api_key: str = ""
    with open(env_path, "r") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("DYNADOT_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
    assert len(api_key) > 0, "DYNADOT_API_KEY not found in .env"
    return api_key


async def dynadot_search(
    domain: str, api_key: str, client: httpx.AsyncClient
) -> dict[str, Any]:
    """Check domain availability via Dynadot search API.

    Dynadot search returns {SearchResponse: {SearchResults: [{Available: "yes"/"no"}]}}.
    No price field is returned; we use known Dynadot .com pricing.
    Rate limit: 10 requests/minute, called only for potential candidates.
    """
    assert isinstance(domain, str) and len(domain) > 3
    assert "." in domain
    assert len(api_key) > 0

    # Estimate price by TLD
    tld: str = "." + domain.rsplit(".", 1)[-1]
    est_price: float = DYNADOT_COM_PRICE_USD if tld == ".com" else 12.99

    result: dict[str, Any] = {
        "domain": domain,
        "dynadot_available": False,
        "dynadot_price_usd": 0.0,
        "dynadot_error": None,
    }
    params: dict[str, str] = {
        "key": api_key,
        "command": "search",
        "domain0": domain,
    }
    try:
        resp: httpx.Response = await client.get(
            DYNADOT_BASE_URL, params=params, timeout=DYNADOT_TIMEOUT_S
        )
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            search_resp: Any = data.get("SearchResponse", data)
            if isinstance(search_resp, dict):
                results_list: Any = search_resp.get("SearchResults", [])
                if isinstance(results_list, list) and len(results_list) > 0:
                    first: dict[str, Any] = (
                        results_list[0] if isinstance(results_list[0], dict) else {}
                    )
                    available_str: str = str(first.get("Available", "no"))
                    result["dynadot_available"] = available_str.lower() == "yes"
                    if result["dynadot_available"]:
                        result["dynadot_price_usd"] = est_price
        else:
            result["dynadot_error"] = f"http_{resp.status_code}"
    except httpx.TimeoutException:
        result["dynadot_error"] = "timeout"
    except Exception as exc:
        result["dynadot_error"] = str(exc)[:200]

    return result


async def batch_dynadot_checks(
    domains: list[dict[str, Any]], api_key: str
) -> list[dict[str, Any]]:
    """Check Dynadot availability for domains that appear available.

    Rate-limited to ~8 requests/minute (7.5s between) for safety.
    """
    assert isinstance(domains, list)
    assert len(api_key) > 0

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for idx, entry in enumerate(domains[:MAX_DOMAINS]):
            domain: str = entry["domain"]
            print(
                f"  [{idx + 1}/{len(domains)}] Dynadot search: {domain}...",
                file=sys.stderr,
                end=" ",
            )
            dynadot_result = await dynadot_search(domain, api_key, client)
            merged: dict[str, Any] = {**entry, **dynadot_result}
            results.append(merged)
            is_avail: bool = dynadot_result["dynadot_available"]
            status: str = "AVAILABLE" if is_avail else "taken"
            price: float = dynadot_result["dynadot_price_usd"]
            price_str: str = f"~${price:.2f}" if is_avail else "n/a"
            print(f"-> {status} ({price_str})", file=sys.stderr)
            # Rate limit: 7.5s between requests (8/min, under 10/min limit)
            if idx < len(domains) - 1:
                await asyncio.sleep(7.5)

    assert len(results) == min(len(domains), MAX_DOMAINS)
    return results


# ---------------------------------------------------------------------------
# Step 5: Ultra-premium 4-letter .com check
# ---------------------------------------------------------------------------
async def check_ultra_premium(
    entries: list[dict[str, Any]], api_key: str
) -> list[dict[str, Any]]:
    """HTTP HEAD + Dynadot check for the 9 ultra-premium 4-letter .coms."""
    assert isinstance(entries, list)
    assert len(entries) <= 20, "Too many ultra-premium entries"
    assert len(api_key) > 0

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        verify=False,
    ) as client:
        for entry in entries:
            domain: str = entry["domain"]
            http_result = await http_head_check(domain, client)
            # Always check Dynadot for authoritative availability
            dynadot_result = await dynadot_search(domain, api_key, client)
            merged: dict[str, Any] = {**entry, **http_result, **dynadot_result}
            results.append(merged)
            http_label: str = http_result["status_label"]
            dynadot_avail: str = (
                "DYNADOT:YES" if dynadot_result["dynadot_available"] else "DYNADOT:NO"
            )
            print(
                f"  Ultra-premium: {domain:12s} -> HTTP:{http_label:12s} {dynadot_avail}",
                file=sys.stderr,
            )
            # Rate limit for Dynadot
            await asyncio.sleep(7.5)

    assert len(results) == len(entries)
    return results


# ---------------------------------------------------------------------------
# Step 6: Scoring
# ---------------------------------------------------------------------------
def compute_priority(
    funding_usd: int,
    domain: str,
    dynadot_available: bool,
) -> str:
    """Compute priority level based on funding and domain quality."""
    assert isinstance(funding_usd, (int, float))
    assert isinstance(domain, str) and len(domain) > 0

    name_part: str = domain.split(".")[0]
    is_short: bool = len(name_part) <= 4
    is_com: bool = domain.endswith(".com")

    if funding_usd >= 50_000_000:
        return "HIGH"
    if funding_usd >= 20_000_000:
        return "HIGH" if (is_short and is_com) else "MEDIUM"
    if is_short and is_com:
        return "HIGH"
    if dynadot_available and funding_usd >= 10_000_000:
        return "MEDIUM"
    if dynadot_available:
        return "MEDIUM"
    return "LOW"


def estimate_value(
    funding_usd: int, domain: str
) -> str:
    """Rough domain value estimate based on funding and name quality."""
    assert isinstance(funding_usd, (int, float))
    assert isinstance(domain, str)

    name_part: str = domain.split(".")[0]
    length: int = len(name_part)

    # Short .com domains are inherently valuable
    if domain.endswith(".com") and length <= 4:
        return "$5,000-$50,000+"
    if domain.endswith(".com") and length <= 6:
        return "$1,000-$10,000"

    # Funding-based valuation
    if funding_usd >= 100_000_000:
        return "$500-$5,000"
    if funding_usd >= 50_000_000:
        return "$300-$2,000"
    if funding_usd >= 20_000_000:
        return "$200-$1,000"
    if funding_usd >= 10_000_000:
        return "$100-$500"
    return "$50-$200"


def compute_action(
    dynadot_available: bool, priority: str, funding_usd: int
) -> str:
    """Determine recommended action for a validated domain."""
    assert isinstance(dynadot_available, bool)
    assert isinstance(priority, str)
    assert isinstance(funding_usd, (int, float))

    if dynadot_available:
        return "REGISTER_NOW"
    if priority == "HIGH":
        return "BACKORDER"
    if funding_usd >= 10_000_000:
        return "BACKORDER"
    return "WATCH"


def score_domain(entry: dict[str, Any]) -> dict[str, Any]:
    """Score a validated domain and add priority/value/action fields."""
    assert isinstance(entry, dict)
    assert "domain" in entry

    domain: str = entry["domain"]
    funding: int = int(entry.get("funding_usd", 0))
    dynadot_avail: bool = entry.get("dynadot_available", False)

    name_part: str = domain.split(".")[0]
    is_ultra_premium: bool = len(name_part) <= 4 and domain.endswith(".com")

    priority: str = compute_priority(funding, domain, dynadot_avail)
    value: str = estimate_value(funding, domain)
    action: str = compute_action(dynadot_avail, priority, funding)

    scored: dict[str, Any] = {
        "domain": domain,
        "company": entry.get("company_name", ""),
        "funding": funding,
        "sector": entry.get("sector", ""),
        "http_status": entry.get("http_status", 0),
        "http_label": entry.get("status_label", "UNKNOWN"),
        "direct_registration": dynadot_avail,
        "dynadot_price_usd": entry.get("dynadot_price_usd", 0.0),
        "priority": priority,
        "estimated_value": value,
        "action": action,
        "is_ultra_premium": is_ultra_premium,
    }
    return scored


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
async def run_validation() -> dict[str, Any]:
    """Run the full validation pipeline."""

    print("=" * 70, file=sys.stderr)
    print("Sprint 28 — Validate CATCHABLE Domains from Kaggle RDAP Probe", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(file=sys.stderr)

    # Step 1: Load data
    print("[Step 1] Loading catchable domains...", file=sys.stderr)
    catchable: list[dict[str, Any]] = load_catchable(INPUT_PATH)
    print(f"  Loaded {len(catchable)} CATCHABLE domains", file=sys.stderr)
    print(file=sys.stderr)

    # Step 2: Filter subdomains
    print("[Step 2] Filtering subdomains...", file=sys.stderr)
    registrable, subdomains = filter_subdomains(catchable)
    print(f"  Registrable: {len(registrable)}", file=sys.stderr)
    print(f"  Subdomains filtered: {len(subdomains)}", file=sys.stderr)
    for sd in subdomains:
        print(f"    FILTERED: {sd['domain']} ({sd.get('company_name', '')})", file=sys.stderr)
    print(file=sys.stderr)

    # Step 3: HTTP HEAD checks
    print("[Step 3] Running HTTP HEAD checks on registrable domains...", file=sys.stderr)
    http_results: list[dict[str, Any]] = await batch_http_checks(registrable)

    available_http: list[dict[str, Any]] = []
    registered_http: list[dict[str, Any]] = []
    error_http: list[dict[str, Any]] = []

    for r in http_results:
        label: str = r.get("status_label", "UNKNOWN")
        if label == "REGISTERED":
            registered_http.append(r)
        elif label in ("NO_CONNECT", "TIMEOUT", "MAYBE_AVAILABLE"):
            available_http.append(r)
        else:
            error_http.append(r)

    print(f"  REGISTERED (active): {len(registered_http)}", file=sys.stderr)
    print(f"  AVAILABLE (no connect/timeout): {len(available_http)}", file=sys.stderr)
    print(f"  ERROR: {len(error_http)}", file=sys.stderr)
    print(file=sys.stderr)

    # Print HTTP check detail table
    print("  HTTP Check Results:", file=sys.stderr)
    print(f"  {'#':>3} {'Domain':40s} {'HTTP':>5} {'Status':15s} {'Error'}", file=sys.stderr)
    print(f"  {'-'*3} {'-'*40} {'-'*5} {'-'*15} {'-'*30}", file=sys.stderr)
    for idx, r in enumerate(http_results, 1):
        err: str = r.get("error", "") or ""
        print(
            f"  {idx:3d} {r['domain']:40s} {r.get('http_status', 0):5d} "
            f"{r.get('status_label', 'UNKNOWN'):15s} {err[:30]}",
            file=sys.stderr,
        )
    print(file=sys.stderr)

    # Step 4: Dynadot availability check for "available" domains
    print("[Step 4] Checking Dynadot availability for potentially available domains...", file=sys.stderr)
    api_key: str = load_dynadot_api_key()

    # Combine available + error for Dynadot check (be thorough)
    candidates_for_dynadot: list[dict[str, Any]] = available_http + error_http
    dynadot_results: list[dict[str, Any]] = []

    if len(candidates_for_dynadot) > 0:
        dynadot_results = await batch_dynadot_checks(candidates_for_dynadot, api_key)
    else:
        print("  No domains to check with Dynadot (all appear registered)", file=sys.stderr)
    print(file=sys.stderr)

    # Step 5: Ultra-premium 4-letter .com check
    print("[Step 5] Checking ultra-premium 4-letter .coms from Sprint 26...", file=sys.stderr)
    ultra_results: list[dict[str, Any]] = await check_ultra_premium(ULTRA_PREMIUM_4L, api_key)
    print(file=sys.stderr)

    # Step 6: Score validated domains
    print("[Step 6] Scoring validated domains...", file=sys.stderr)

    # Score dynadot-checked domains
    validated_available: list[dict[str, Any]] = []
    for entry in dynadot_results:
        scored = score_domain(entry)
        validated_available.append(scored)

    # Sort by funding descending, then by priority
    priority_order: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    validated_available.sort(
        key=lambda x: (priority_order.get(x["priority"], 3), -x["funding"])
    )

    # Identify immediate registration candidates
    immediate_reg: list[dict[str, Any]] = [
        d for d in validated_available if d.get("direct_registration") is True
    ]

    # Format ultra-premium results (Dynadot is authoritative, not HTTP)
    ultra_premium_output: list[dict[str, Any]] = []
    for r in ultra_results:
        dynadot_avail: bool = r.get("dynadot_available", False)
        ultra_premium_output.append({
            "domain": r["domain"],
            "funding_label": r.get("funding_label", "-"),
            "http_status": r.get("http_status", 0),
            "http_label": r.get("status_label", "UNKNOWN"),
            "dynadot_available": dynadot_avail,
            "dynadot_price_usd": r.get("dynadot_price_usd", 0.0),
            "available": dynadot_avail,
        })

    # Build summary
    total_direct_reg: int = len(immediate_reg)
    high_priority_count: int = sum(
        1 for d in validated_available if d["priority"] == "HIGH"
    )

    summary_text: str = (
        f"Validated {len(catchable)} CATCHABLE domains. "
        f"Filtered {len(subdomains)} subdomains. "
        f"HTTP check: {len(registered_http)} registered, "
        f"{len(available_http)} potentially available, "
        f"{len(error_http)} errors. "
        f"Dynadot checked {len(dynadot_results)} candidates. "
        f"{total_direct_reg} available for direct registration. "
        f"{high_priority_count} HIGH priority domains. "
        f"Ultra-premium 4L .coms: {sum(1 for u in ultra_premium_output if u['available'])} "
        f"of {len(ultra_premium_output)} appear available."
    )

    # Print summary
    print(file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("VALIDATION SUMMARY", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"  Input CATCHABLE:          {len(catchable)}", file=sys.stderr)
    print(f"  Subdomains filtered:      {len(subdomains)}", file=sys.stderr)
    print(f"  HTTP registered:          {len(registered_http)}", file=sys.stderr)
    print(f"  HTTP available/error:     {len(available_http) + len(error_http)}", file=sys.stderr)
    print(f"  Dynadot checked:          {len(dynadot_results)}", file=sys.stderr)
    print(f"  Direct registration:      {total_direct_reg}", file=sys.stderr)
    print(f"  HIGH priority:            {high_priority_count}", file=sys.stderr)
    print(file=sys.stderr)

    if immediate_reg:
        print("  *** IMMEDIATE REGISTRATION CANDIDATES ***", file=sys.stderr)
        for d in immediate_reg:
            price_val: float = d.get("dynadot_price_usd", DYNADOT_COM_PRICE_USD)
            print(
                f"    -> {d['domain']:35s} ~${price_val:.2f}  "
                f"(funding: ${d['funding']:,}, priority: {d['priority']}, "
                f"value: {d.get('estimated_value', '?')})",
                file=sys.stderr,
            )
        print(file=sys.stderr)

    print("  Ultra-premium 4L .com status:", file=sys.stderr)
    for u in ultra_premium_output:
        avail_str: str = "AVAILABLE" if u["available"] else "REGISTERED"
        price_str: str = f"${u['dynadot_price_usd']:.2f}" if u["available"] else "-"
        print(
            f"    {u['domain']:12s} -> {avail_str:12s} "
            f"(HTTP:{u['http_label']:12s} Dynadot:{avail_str:10s} Price:{price_str})",
            file=sys.stderr,
        )
    print(file=sys.stderr)

    # Build output JSON
    output: dict[str, Any] = {
        "validation_date": "2026-05-16",
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "input_catchable": len(catchable),
        "subdomains_filtered": len(subdomains),
        "subdomains_list": [
            {"domain": sd["domain"], "company": sd.get("company_name", "")}
            for sd in subdomains
        ],
        "http_check_results": {
            "available": len(available_http),
            "registered": len(registered_http),
            "error": len(error_http),
        },
        "registered_domains": [
            {
                "domain": r["domain"],
                "company": r.get("company_name", ""),
                "funding": r.get("funding_usd", 0),
                "http_status": r.get("http_status", 0),
            }
            for r in registered_http
        ],
        "ultra_premium_check": ultra_premium_output,
        "validated_available": validated_available,
        "immediate_registration_candidates": immediate_reg,
        "summary": summary_text,
    }

    return output


def main() -> None:
    """Entrypoint: run validation and save results."""
    start_time: float = time.monotonic()
    output: dict[str, Any] = asyncio.run(run_validation())

    elapsed: float = time.monotonic() - start_time
    output["elapsed_seconds"] = round(elapsed, 1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, default=str)

    print(f"Results saved to {OUTPUT_PATH}", file=sys.stderr)
    print(f"Elapsed: {elapsed:.1f}s", file=sys.stderr)

    # Print JSON to stdout for piping
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()

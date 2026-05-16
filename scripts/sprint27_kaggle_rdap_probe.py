#!/usr/bin/env python3
"""Sprint 27 -- Async RDAP probe for 500 Kaggle dead-startup domains.

Probes each domain via RDAP, classifies by EPP status:
  CATCHABLE  = drop signals (pendingDelete, redemptionPeriod, 404, etc.)
  MAYBE      = weaker signals (clientHold, clientRenewProhibited, autoRenewPeriod)
  REGISTERED = active, no drop signals
  UNKNOWN    = .co TLD (no functional RDAP)
  ERROR      = timeout, connection, or unexpected HTTP status

Uses async httpx with semaphore rate-limiting (20 concurrent, 0.5s gap).
NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Constants (immutable -- NASA Rule 2)
# ---------------------------------------------------------------------------
_MAX_CONCURRENT: int = 20
_REQUEST_GAP_S: float = 0.5
_TIMEOUT_S: int = 20
_MAX_RETRIES: int = 2
_MAX_DOMAINS: int = 600  # bounded loop guard
_USER_AGENT: str = "DomainHunter-Sprint27/1.0 (+https://github.com/domain-hunter)"

_RDAP_SERVERS: dict[str, str] = {
    ".com": "https://rdap.verisign.com/com/v1/domain/",
    ".net": "https://rdap.verisign.com/net/v1/domain/",
    ".org": "https://rdap.publicinterestregistry.org/rdap/domain/",
    ".io": "https://rdap.nic.io/domain/",
    ".ai": "https://rdap.nic.ai/domain/",
    ".dev": "https://rdap.nic.google/domain/",
}

_CATCHABLE_STATUSES: frozenset[str] = frozenset({
    "pending delete",
    "pendingdelete",
    "redemption period",
    "redemptionperiod",
})

_MAYBE_STATUSES: frozenset[str] = frozenset({
    "client renew prohibited",
    "clientrenewprohibited",
    "auto renew period",
    "autorenewperiod",
    "client hold",
    "clienthold",
    "server hold",
    "serverhold",
})

_SKIP_TLDS: frozenset[str] = frozenset({".co"})

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_INPUT_PATH: Path = _PROJECT_ROOT / "data" / "sprint26_kaggle_new_targets.json"
_OUTPUT_PATH: Path = _PROJECT_ROOT / "data" / "sprint27_kaggle_rdap_results.json"


# ---------------------------------------------------------------------------
# Target loading
# ---------------------------------------------------------------------------

def load_targets(path: Path) -> list[dict[str, Any]]:
    """Load target domains from the Kaggle analysis JSON."""
    assert path.exists(), f"Input file missing: {path}"
    with open(path, "r") as fh:
        data: dict[str, Any] = json.load(fh)
    assert "targets" in data, "Expected 'targets' key in JSON"
    targets: list[dict[str, Any]] = data["targets"]
    assert 1 <= len(targets) <= _MAX_DOMAINS, f"Target count out of range: {len(targets)}"
    return targets


# ---------------------------------------------------------------------------
# RDAP parsing helpers
# ---------------------------------------------------------------------------

def extract_epp_statuses(rdap_json: dict[str, Any]) -> list[str]:
    """Pull EPP status strings from RDAP response."""
    assert isinstance(rdap_json, dict), "RDAP response must be dict"
    raw: list[Any] = rdap_json.get("status", [])
    assert isinstance(raw, list), "status must be a list"
    return [str(s) for s in raw[:50]]


def extract_registrar(rdap_json: dict[str, Any]) -> str:
    """Extract registrar name from RDAP entities."""
    assert isinstance(rdap_json, dict)
    entities: list[Any] = rdap_json.get("entities", [])
    assert isinstance(entities, list)
    for idx, entity in enumerate(entities):
        if idx >= 20:
            break
        roles: list[str] = entity.get("roles", [])
        if "registrar" in roles:
            vcard: list[Any] = entity.get("vcardArray", [None, []])
            if len(vcard) >= 2 and isinstance(vcard[1], list):
                for field_idx, field in enumerate(vcard[1]):
                    if field_idx >= 50:
                        break
                    if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                        return str(field[3])
            handle: str = entity.get("handle", "")
            if handle:
                return handle
    return ""


def extract_expiry(rdap_json: dict[str, Any]) -> str:
    """Extract expiry date from RDAP events."""
    assert isinstance(rdap_json, dict)
    events: list[Any] = rdap_json.get("events", [])
    assert isinstance(events, list)
    for idx, event in enumerate(events):
        if idx >= 50:
            break
        if event.get("eventAction") == "expiration":
            return str(event.get("eventDate", ""))
    return ""


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_domain(http_status: int, epp_codes: list[str]) -> str:
    """Classify domain based on RDAP HTTP status and EPP codes.

    Returns one of: CATCHABLE, MAYBE, REGISTERED, ERROR.
    """
    assert isinstance(http_status, int), "http_status must be int"
    assert isinstance(epp_codes, list), "epp_codes must be list"

    if http_status == 404:
        return "CATCHABLE"

    if http_status != 200:
        return "ERROR"

    # Check EPP codes for drop signals
    for code in epp_codes:
        normalized: str = code.lower().strip()
        if normalized in _CATCHABLE_STATUSES:
            return "CATCHABLE"

    for code in epp_codes:
        normalized = code.lower().strip()
        if normalized in _MAYBE_STATUSES:
            return "MAYBE"

    return "REGISTERED"


# ---------------------------------------------------------------------------
# Async RDAP probing
# ---------------------------------------------------------------------------

def _get_rdap_url(domain: str) -> Optional[str]:
    """Build direct RDAP URL for a domain, or None if TLD unsupported."""
    assert isinstance(domain, str) and len(domain) > 0
    dot_idx: int = domain.rfind(".")
    assert dot_idx > 0, f"Invalid domain: {domain}"
    tld: str = domain[dot_idx:].lower()
    base: Optional[str] = _RDAP_SERVERS.get(tld)
    if base is None:
        return None
    return f"{base}{domain}"


async def probe_single(
    domain: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    rate_lock: asyncio.Lock,
    last_request_time: list[float],
) -> dict[str, Any]:
    """Probe a single domain via RDAP with rate limiting.

    Returns a result dict with domain, http_status, epp_codes, etc.
    """
    assert isinstance(domain, str) and len(domain) > 0
    assert "." in domain

    url: Optional[str] = _get_rdap_url(domain)
    if url is None:
        return {
            "domain": domain,
            "http_status": 0,
            "epp_codes": [],
            "expiry_date": "",
            "registrar": "",
            "rdap_status": "UNKNOWN",
            "error": "unsupported_tld",
        }

    result: dict[str, Any] = {
        "domain": domain,
        "http_status": 0,
        "epp_codes": [],
        "expiry_date": "",
        "registrar": "",
        "rdap_status": "ERROR",
        "error": None,
    }

    async with semaphore:
        # Enforce minimum gap between requests
        async with rate_lock:
            elapsed: float = time.monotonic() - last_request_time[0]
            if elapsed < _REQUEST_GAP_S:
                await asyncio.sleep(_REQUEST_GAP_S - elapsed)
            last_request_time[0] = time.monotonic()

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp: httpx.Response = await client.get(url)
                result["http_status"] = resp.status_code
                break
            except httpx.TimeoutException:
                result["error"] = "timeout"
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                return result
            except httpx.HTTPError as exc:
                result["error"] = f"http_error: {str(exc)[:150]}"
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                return result

    # Parse response
    if resp.status_code == 200:
        try:
            data: dict[str, Any] = resp.json()
            result["epp_codes"] = extract_epp_statuses(data)
            result["registrar"] = extract_registrar(data)
            result["expiry_date"] = extract_expiry(data)
        except Exception as exc:
            result["error"] = f"parse_error: {str(exc)[:100]}"
    elif resp.status_code == 404:
        pass  # Not found = CATCHABLE
    elif resp.status_code == 429:
        result["error"] = "rate_limited"
    else:
        result["error"] = f"http_{resp.status_code}"

    result["rdap_status"] = classify_domain(resp.status_code, result["epp_codes"])
    return result


async def probe_all(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Probe all target domains asynchronously with rate limiting."""
    assert isinstance(targets, list)
    assert 1 <= len(targets) <= _MAX_DOMAINS

    semaphore: asyncio.Semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    rate_lock: asyncio.Lock = asyncio.Lock()
    last_request_time: list[float] = [0.0]

    headers: dict[str, str] = {
        "Accept": "application/rdap+json, application/json",
        "User-Agent": _USER_AGENT,
    }

    results: list[dict[str, Any]] = []
    start_time: float = time.monotonic()

    async with httpx.AsyncClient(
        timeout=float(_TIMEOUT_S),
        headers=headers,
        follow_redirects=True,
    ) as client:
        # Process in batches of _MAX_CONCURRENT to maintain progress output
        batch_size: int = _MAX_CONCURRENT
        total: int = len(targets)

        for batch_start in range(0, total, batch_size):
            batch_end: int = min(batch_start + batch_size, total)
            batch: list[dict[str, Any]] = targets[batch_start:batch_end]

            tasks: list[asyncio.Task[dict[str, Any]]] = []
            for target in batch:
                domain: str = target["domain"]
                task = asyncio.create_task(
                    probe_single(domain, client, semaphore, rate_lock, last_request_time)
                )
                tasks.append(task)

            batch_results: list[dict[str, Any]] = await asyncio.gather(*tasks)

            # Enrich results with target metadata
            for i, result in enumerate(batch_results):
                target_data: dict[str, Any] = batch[i]
                result["company_name"] = target_data.get("company_name", "")
                result["funding_usd"] = target_data.get("funding_usd", 0)
                result["sector"] = target_data.get("sector", "")
                results.append(result)

            elapsed_s: float = time.monotonic() - start_time
            done: int = len(results)
            catchable_so_far: int = sum(
                1 for r in results if r["rdap_status"] == "CATCHABLE"
            )
            maybe_so_far: int = sum(
                1 for r in results if r["rdap_status"] == "MAYBE"
            )
            print(
                f"  [{done:3d}/{total}] "
                f"elapsed={elapsed_s:5.1f}s  "
                f"catchable={catchable_so_far}  "
                f"maybe={maybe_so_far}  "
                f"batch={batch_start+1}-{batch_end}",
                file=sys.stderr,
            )

    assert len(results) == len(targets), "Result count mismatch"
    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def build_output(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the final output JSON structure."""
    assert isinstance(results, list) and len(results) > 0

    catchable: list[dict[str, Any]] = []
    maybe: list[dict[str, Any]] = []
    registered: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    error: list[dict[str, Any]] = []

    for r in results:
        entry: dict[str, Any] = {
            "domain": r["domain"],
            "company_name": r.get("company_name", ""),
            "funding_usd": r.get("funding_usd", 0),
            "sector": r.get("sector", ""),
            "rdap_status": r["rdap_status"],
            "epp_codes": r["epp_codes"],
            "expiry_date": r.get("expiry_date", ""),
            "registrar": r.get("registrar", ""),
        }
        status: str = r["rdap_status"]
        if status == "CATCHABLE":
            catchable.append(entry)
        elif status == "MAYBE":
            maybe.append(entry)
        elif status == "REGISTERED":
            registered.append(entry)
        elif status == "UNKNOWN":
            unknown.append(entry)
        else:
            entry["error"] = r.get("error", "unknown")
            error.append(entry)

    # Sort catchable + maybe by funding descending
    catchable.sort(key=lambda x: x.get("funding_usd", 0), reverse=True)
    maybe.sort(key=lambda x: x.get("funding_usd", 0), reverse=True)

    summary: dict[str, int] = {
        "catchable": len(catchable),
        "maybe": len(maybe),
        "registered": len(registered),
        "unknown": len(unknown),
        "error": len(error),
    }

    return {
        "probe_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "probe_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_probed": len(results),
        "catchable": catchable,
        "maybe": maybe,
        "registered": registered,
        "unknown": unknown,
        "error": error,
        "summary": summary,
    }


def print_summary_table(output: dict[str, Any]) -> None:
    """Print ASCII summary table to stderr."""
    assert isinstance(output, dict)
    summary: dict[str, int] = output["summary"]
    total: int = output["total_probed"]

    print("\n" + "=" * 72, file=sys.stderr)
    print("  SPRINT 27 -- KAGGLE RDAP PROBE RESULTS", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print(f"  Probe date:    {output['probe_date']}", file=sys.stderr)
    print(f"  Total probed:  {total}", file=sys.stderr)
    print("-" * 72, file=sys.stderr)
    print(f"  {'Category':<15s} {'Count':>6s} {'Pct':>7s}", file=sys.stderr)
    print(f"  {'-'*15:<15s} {'-'*6:>6s} {'-'*7:>7s}", file=sys.stderr)

    for cat in ("catchable", "maybe", "registered", "unknown", "error"):
        count: int = summary.get(cat, 0)
        pct: float = (count / total * 100) if total > 0 else 0.0
        label: str = cat.upper()
        print(f"  {label:<15s} {count:6d} {pct:6.1f}%", file=sys.stderr)

    print("-" * 72, file=sys.stderr)

    # Print CATCHABLE domains
    catchable: list[dict[str, Any]] = output.get("catchable", [])
    if catchable:
        print(f"\n  CATCHABLE DOMAINS ({len(catchable)}):", file=sys.stderr)
        print(f"  {'#':>3s} {'Domain':35s} {'Funding':>14s} {'Sector':15s} {'EPP / Signal':30s}", file=sys.stderr)
        print(f"  {'---':>3s} {'---':35s} {'---':>14s} {'---':15s} {'---':30s}", file=sys.stderr)
        for i, d in enumerate(catchable[:50], 1):
            funding_str: str = f"${d['funding_usd']:,.0f}" if d.get("funding_usd") else "N/A"
            epp_str: str = ", ".join(d.get("epp_codes", [])[:3]) or "404 (not found)"
            sector: str = (d.get("sector") or "")[:15]
            print(
                f"  {i:3d} {d['domain']:35s} {funding_str:>14s} {sector:15s} {epp_str[:30]:30s}",
                file=sys.stderr,
            )

    # Print MAYBE domains
    maybe: list[dict[str, Any]] = output.get("maybe", [])
    if maybe:
        print(f"\n  MAYBE DOMAINS ({len(maybe)}):", file=sys.stderr)
        print(f"  {'#':>3s} {'Domain':35s} {'Funding':>14s} {'Sector':15s} {'EPP Codes':30s}", file=sys.stderr)
        print(f"  {'---':>3s} {'---':35s} {'---':>14s} {'---':15s} {'---':30s}", file=sys.stderr)
        for i, d in enumerate(maybe[:50], 1):
            funding_str = f"${d['funding_usd']:,.0f}" if d.get("funding_usd") else "N/A"
            epp_str = ", ".join(d.get("epp_codes", [])[:3])
            sector = (d.get("sector") or "")[:15]
            print(
                f"  {i:3d} {d['domain']:35s} {funding_str:>14s} {sector:15s} {epp_str[:30]:30s}",
                file=sys.stderr,
            )

    # Print ERROR domains (first 10)
    errors: list[dict[str, Any]] = output.get("error", [])
    if errors:
        print(f"\n  ERROR DOMAINS ({len(errors)}, showing first 10):", file=sys.stderr)
        for i, d in enumerate(errors[:10], 1):
            print(f"  {i:3d} {d['domain']:35s} error={d.get('error', 'unknown')}", file=sys.stderr)

    print("\n" + "=" * 72, file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entrypoint: load targets, probe via RDAP, save results."""
    print("[SPRINT 27] Loading Kaggle targets...", file=sys.stderr)
    targets: list[dict[str, Any]] = load_targets(_INPUT_PATH)
    print(f"[SPRINT 27] Loaded {len(targets)} targets", file=sys.stderr)

    # Filter .co domains to UNKNOWN (no functional RDAP)
    co_domains: list[dict[str, Any]] = [t for t in targets if t.get("tld") == ".co"]
    probe_targets: list[dict[str, Any]] = [t for t in targets if t.get("tld") != ".co"]

    print(f"[SPRINT 27] Probing {len(probe_targets)} domains (skipping {len(co_domains)} .co)", file=sys.stderr)
    print(f"[SPRINT 27] Rate limit: {_REQUEST_GAP_S}s gap, {_MAX_CONCURRENT} concurrent", file=sys.stderr)
    print(f"[SPRINT 27] Timeout: {_TIMEOUT_S}s per request, {_MAX_RETRIES} retries", file=sys.stderr)
    print(file=sys.stderr)

    # Run async probe
    probe_results: list[dict[str, Any]] = asyncio.run(probe_all(probe_targets))

    # Add .co domains as UNKNOWN
    for co_target in co_domains:
        probe_results.append({
            "domain": co_target["domain"],
            "company_name": co_target.get("company_name", ""),
            "funding_usd": co_target.get("funding_usd", 0),
            "sector": co_target.get("sector", ""),
            "http_status": 0,
            "epp_codes": [],
            "expiry_date": "",
            "registrar": "",
            "rdap_status": "UNKNOWN",
            "error": "co_tld_no_rdap",
        })

    assert len(probe_results) == len(targets), (
        f"Result count mismatch: {len(probe_results)} != {len(targets)}"
    )

    # Build output and save
    output: dict[str, Any] = build_output(probe_results)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, default=str)

    print(f"\n[SPRINT 27] Results saved to {_OUTPUT_PATH}", file=sys.stderr)
    print_summary_table(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Sprint 28 — Agent 4: Triage 166 MAYBE Domains.

Sprint 27 RDAP probe found 166 domains with ambiguous EPP locks:
  clientDeleteProhibited + clientRenewProhibited +
  clientTransferProhibited + clientUpdateProhibited

This script runs async HTTP HEAD checks to distinguish active sites
from abandoned ones, then scores the abandoned subset and produces
a watch list of the top 20-30 candidates for monthly RDAP re-check.

Usage:
  python3 scripts/sprint28_triage_maybe.py
  python3 scripts/sprint28_triage_maybe.py --top 25
  python3 scripts/sprint28_triage_maybe.py --concurrency 10

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_INPUT_PATH: Final[str] = os.path.join(_ROOT, "data", "sprint27_kaggle_rdap_results.json")
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")

# HTTP probe settings
_DEFAULT_CONCURRENCY: Final[int] = 20
_HTTP_TIMEOUT_SEC: Final[float] = 5.0
_MAX_REDIRECTS: Final[int] = 3

# Scoring weights (sum to 1.0)
_W_FUNDING: Final[float] = 0.35
_W_DOMAIN_LEN: Final[float] = 0.20
_W_SECTOR: Final[float] = 0.15
_W_EXPIRY_PROXIMITY: Final[float] = 0.15
_W_REGISTRAR: Final[float] = 0.05
_W_PATTERN: Final[float] = 0.10

# Sectors with higher resale / affiliate value
_HIGH_VALUE_SECTORS: Final[frozenset] = frozenset({
    "fintech", "saas", "healthtech", "biotech", "ecommerce",
    "adtech", "gaming", "mobile", "cleantech",
})

# Domain patterns that reduce quality (hyphens, numbers, long words)
_PENALTY_CHARS: Final[str] = "-0123456789"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_maybe_domains() -> List[Dict[str, Any]]:
    """Load the 166 MAYBE domains from Sprint 27 RDAP results."""
    assert os.path.isfile(_INPUT_PATH), f"input not found: {_INPUT_PATH}"
    with open(_INPUT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert "maybe" in data, "missing 'maybe' key in input data"
    maybe = data["maybe"]
    assert len(maybe) > 0, "empty maybe list"
    return maybe


# ---------------------------------------------------------------------------
# HTTP HEAD probe
# ---------------------------------------------------------------------------

async def _probe_one(
    session: "aiohttp.ClientSession",
    domain: str,
    sem: asyncio.Semaphore,
) -> Tuple[str, str, int, str]:
    """Probe a single domain with HTTP HEAD. Returns (domain, status, code, detail).

    status is one of: "active", "abandoned", "error"
    """
    import aiohttp

    assert isinstance(domain, str) and len(domain) > 0
    assert isinstance(sem, asyncio.Semaphore)

    url = f"https://{domain}"
    async with sem:
        try:
            async with session.head(
                url,
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_SEC),
                allow_redirects=True,
                max_redirects=_MAX_REDIRECTS,
                ssl=False,  # skip cert verification for probing
            ) as resp:
                # Any 2xx/3xx = site is active
                if resp.status < 400:
                    return (domain, "active", resp.status, f"HTTP {resp.status}")
                # 403/401 often means parked or protected — still active
                if resp.status in (401, 403):
                    return (domain, "active", resp.status, f"HTTP {resp.status} (protected)")
                # 5xx could be temp error, but site infrastructure exists
                if 500 <= resp.status < 600:
                    return (domain, "active", resp.status, f"HTTP {resp.status} (server error)")
                # 404, 410 etc — domain resolves but nothing there
                return (domain, "abandoned", resp.status, f"HTTP {resp.status}")
        except Exception:
            pass

        # Retry with HTTP (not HTTPS) for domains without TLS
        url_http = f"http://{domain}"
        try:
            async with session.head(
                url_http,
                timeout=aiohttp.ClientTimeout(total=_HTTP_TIMEOUT_SEC),
                allow_redirects=True,
                max_redirects=_MAX_REDIRECTS,
            ) as resp:
                if resp.status < 500:
                    return (domain, "active", resp.status, f"HTTP {resp.status} (plain)")
                return (domain, "active", resp.status, f"HTTP {resp.status} (server error, plain)")
        except Exception as exc:
            # DNS failure, connection refused, timeout = abandoned
            exc_name = type(exc).__name__
            return (domain, "abandoned", 0, exc_name)


async def probe_all(
    domains: List[str],
    concurrency: int,
) -> Dict[str, Tuple[str, int, str]]:
    """Probe all domains concurrently. Returns {domain: (status, code, detail)}."""
    import aiohttp

    assert len(domains) > 0
    assert 1 <= concurrency <= 100

    sem = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=concurrency, ttl_dns_cache=300)
    results: Dict[str, Tuple[str, int, str]] = {}

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_probe_one(session, d, sem) for d in domains]
        for coro in asyncio.as_completed(tasks):
            domain, status, code, detail = await coro
            results[domain] = (status, code, detail)
            # Progress indicator
            done = len(results)
            if done % 20 == 0 or done == len(domains):
                print(f"  Probed {done}/{len(domains)}...", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_funding(funding_usd: float, max_funding: float) -> float:
    """Score 0-1 based on log-scaled funding relative to max."""
    assert funding_usd >= 0 and max_funding > 0
    if funding_usd <= 0:
        return 0.0
    return math.log1p(funding_usd) / math.log1p(max_funding)


def _score_domain_length(domain: str) -> float:
    """Score 0-1 based on SLD length. Shorter = better."""
    assert "." in domain
    sld = domain.split(".")[0]
    length = len(sld)
    # Ideal: 3-6 chars = 1.0, degrades linearly to 0.0 at 20+
    if length <= 6:
        return 1.0
    if length >= 20:
        return 0.0
    return 1.0 - (length - 6) / 14.0


def _score_pattern(domain: str) -> float:
    """Score 0-1 based on domain name quality. Penalize hyphens, digits."""
    assert "." in domain
    sld = domain.split(".")[0].lower()
    if len(sld) == 0:
        return 0.0
    penalty_count = sum(1 for ch in sld if ch in _PENALTY_CHARS)
    penalty_ratio = penalty_count / len(sld)
    # All-alpha short domain = 1.0. Each penalty char degrades.
    score = max(0.0, 1.0 - penalty_ratio * 2.5)
    # Bonus for dictionary-like single-word feel (no hyphens)
    if "-" not in sld and not any(c.isdigit() for c in sld):
        score = min(1.0, score + 0.1)
    return score


def _score_sector(sector: str) -> float:
    """Score 0-1 based on sector value for domain resale."""
    assert isinstance(sector, str)
    return 1.0 if sector.lower() in _HIGH_VALUE_SECTORS else 0.4


def _score_expiry_proximity(expiry_str: str) -> float:
    """Score 0-1 based on how soon the domain expires. Sooner = higher."""
    assert isinstance(expiry_str, str)
    if not expiry_str:
        return 0.3  # Unknown — neutral
    try:
        exp = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_until = (exp - now).days
        # Already expired or <30 days: 1.0
        if days_until <= 30:
            return 1.0
        # 30-180 days: linear scale 1.0 -> 0.3
        if days_until <= 180:
            return 1.0 - 0.7 * (days_until - 30) / 150.0
        # 180-365: low
        if days_until <= 365:
            return 0.2
        # >1 year: very low
        return 0.1
    except (ValueError, TypeError):
        return 0.3


def _score_registrar(registrar: str) -> float:
    """Score 0-1 based on registrar (GoDaddy domains drop predictably)."""
    assert isinstance(registrar, str)
    reg_lower = registrar.lower()
    if "godaddy" in reg_lower or "wild west" in reg_lower:
        return 1.0  # GoDaddy drop lifecycle is well-documented
    if "namecheap" in reg_lower or "tucows" in reg_lower:
        return 0.7
    return 0.3  # Unknown registrar — less predictable


def score_domain(entry: Dict[str, Any], max_funding: float) -> float:
    """Compute composite priority score (0-100) for a MAYBE domain."""
    assert isinstance(entry, dict)
    assert "domain" in entry and "funding_usd" in entry
    assert max_funding > 0

    s_fund = _score_funding(entry["funding_usd"], max_funding)
    s_len = _score_domain_length(entry["domain"])
    s_pat = _score_pattern(entry["domain"])
    s_sec = _score_sector(entry.get("sector", "other"))
    s_exp = _score_expiry_proximity(entry.get("expiry_date", ""))
    s_reg = _score_registrar(entry.get("registrar", ""))

    composite = (
        _W_FUNDING * s_fund
        + _W_DOMAIN_LEN * s_len
        + _W_PATTERN * s_pat
        + _W_SECTOR * s_sec
        + _W_EXPIRY_PROXIMITY * s_exp
        + _W_REGISTRAR * s_reg
    )
    return round(composite * 100, 1)


# ---------------------------------------------------------------------------
# Watch list builder
# ---------------------------------------------------------------------------

def build_watch_list(
    abandoned: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """Score abandoned domains and return the top N as watch list entries."""
    assert len(abandoned) > 0
    assert 1 <= top_n <= len(abandoned)

    max_funding = max(e["funding_usd"] for e in abandoned)
    assert max_funding > 0

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for entry in abandoned:
        priority = score_domain(entry, max_funding)
        scored.append((priority, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    recheck_date = "2026-06-16"  # 30-day re-check
    watch_list: List[Dict[str, Any]] = []
    for priority, entry in scored[:top_n]:
        watch_list.append({
            "domain": entry["domain"],
            "company": entry["company_name"],
            "funding": entry["funding_usd"],
            "sector": entry["sector"],
            "epp_codes": entry["epp_codes"],
            "registrar": entry["registrar"],
            "expiry": entry["expiry_date"],
            "priority_score": priority,
            "recheck_date": recheck_date,
        })

    return watch_list


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _build_output(
    maybe: List[Dict[str, Any]],
    probe_results: Dict[str, Tuple[str, int, str]],
    watch_list: List[Dict[str, Any]],
    active_domains: List[Dict[str, Any]],
    abandoned_domains: List[Dict[str, Any]],
    error_domains: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the final output JSON structure."""
    assert isinstance(maybe, list) and len(maybe) > 0
    assert isinstance(watch_list, list)

    return {
        "triage_date": "2026-05-16",
        "input_maybe": len(maybe),
        "http_results": {
            "active_sites": len(active_domains),
            "abandoned": len(abandoned_domains),
            "error": len(error_domains),
        },
        "watch_list": watch_list,
        "removed_active": [
            {
                "domain": e["domain"],
                "company": e["company_name"],
                "http_status": probe_results[e["domain"]][1],
                "http_detail": probe_results[e["domain"]][2],
            }
            for e in active_domains
        ],
        "abandoned_all": [
            {
                "domain": e["domain"],
                "company": e["company_name"],
                "funding": e["funding_usd"],
                "sector": e["sector"],
                "http_detail": probe_results[e["domain"]][2],
            }
            for e in abandoned_domains
        ],
        "summary": (
            f"{len(maybe)} MAYBE -> {len(abandoned_domains)} abandoned "
            f"-> top {len(watch_list)} on watch list"
        ),
    }


async def _async_main(concurrency: int, top_n: int) -> None:
    """Async entry point for probing and triage."""
    assert 1 <= concurrency <= 100
    assert top_n >= 1

    print("Sprint 28 — Agent 4: Triage MAYBE Domains", file=sys.stderr)
    print(f"  Concurrency: {concurrency}, Watch list size: {top_n}", file=sys.stderr)

    # Load data
    maybe = load_maybe_domains()
    print(f"  Loaded {len(maybe)} MAYBE domains", file=sys.stderr)

    # Extract domain list
    domains = [e["domain"] for e in maybe]
    assert len(domains) == len(set(domains)), "duplicate domains in input"

    # Run HTTP HEAD probes
    print(f"\n  Starting HTTP HEAD probes ({len(domains)} domains)...", file=sys.stderr)
    probe_results = await probe_all(domains, concurrency)
    assert len(probe_results) == len(domains)

    # Classify
    active_domains: List[Dict[str, Any]] = []
    abandoned_domains: List[Dict[str, Any]] = []
    error_domains: List[Dict[str, Any]] = []

    for entry in maybe:
        domain = entry["domain"]
        status, code, detail = probe_results[domain]
        if status == "active":
            active_domains.append(entry)
        elif status == "abandoned":
            abandoned_domains.append(entry)
        else:
            error_domains.append(entry)

    print(f"\n  Results:", file=sys.stderr)
    print(f"    Active sites (REGISTERED, removed): {len(active_domains)}", file=sys.stderr)
    print(f"    Abandoned (LIKELY ABANDONED):        {len(abandoned_domains)}", file=sys.stderr)
    print(f"    Error:                               {len(error_domains)}", file=sys.stderr)

    # Score and build watch list
    if len(abandoned_domains) == 0:
        print("  No abandoned domains found. Nothing to watch.", file=sys.stderr)
        watch_list: List[Dict[str, Any]] = []
    else:
        effective_top = min(top_n, len(abandoned_domains))
        watch_list = build_watch_list(abandoned_domains, effective_top)
        print(f"\n  Watch list ({len(watch_list)} domains):", file=sys.stderr)
        for i, w in enumerate(watch_list, 1):
            print(
                f"    {i:>2}. {w['domain']:<30} score={w['priority_score']:>5.1f}  "
                f"funding=${w['funding']:>12,}  sector={w['sector']}",
                file=sys.stderr,
            )

    # Build output
    output = _build_output(
        maybe, probe_results, watch_list,
        active_domains, abandoned_domains, error_domains,
    )

    # Save
    out_path = os.path.join(_DATA_DIR, "sprint28_maybe_triage.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}", file=sys.stderr)

    # Print summary to stdout
    print(json.dumps(output["http_results"], indent=2))
    print(f"\nWatch list: {len(watch_list)} domains")
    if watch_list:
        print(f"Top domain: {watch_list[0]['domain']} (score {watch_list[0]['priority_score']})")


def main() -> None:
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Sprint 28: Triage MAYBE domains via HTTP HEAD probes"
    )
    parser.add_argument(
        "--concurrency", type=int, default=_DEFAULT_CONCURRENCY,
        help=f"Max concurrent HTTP requests (default: {_DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--top", type=int, default=25,
        help="Number of domains for watch list (default: 25)",
    )
    args = parser.parse_args()
    assert 1 <= args.concurrency <= 100, f"concurrency must be 1-100, got {args.concurrency}"
    assert 1 <= args.top <= 166, f"top must be 1-166, got {args.top}"

    asyncio.run(_async_main(args.concurrency, args.top))


if __name__ == "__main__":
    main()

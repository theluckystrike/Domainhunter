#!/usr/bin/env python3
"""Sprint 25 — Deep .co availability probe for bench.co and tally.co.

Sprint 24 RDAP returned 404 for both domains. That could mean available
OR that .co TLD RDAP is not indexed at rdap.org. This script uses four
independent signals to triangulate actual availability:

  1. RDAP via rdap.org (generic bootstrap)
  2. RDAP via rdap.nic.co (.co registry direct)
  3. HTTP HEAD (does the domain resolve?)
  4. Dynadot search API (registrar availability check)

NASA P10: functions <60 lines, 2+ assertions, bounded loops (max 10).
No global mutable state.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
DOMAINS: tuple[str, ...] = ("bench.co", "tally.co")
MAX_DOMAINS = 10  # bounded-loop guard
TIMEOUT_S = 15
RATE_LIMIT_S = 1.0

RDAP_GENERIC_BASE = "https://rdap.org/domain"
RDAP_NIC_CO_BASE = "https://rdap.nic.co/domain"
DYNADOT_API_BASE = "https://api.dynadot.com/api3.json"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_PATH = PROJECT_ROOT / "data" / "sprint25_co_availability_2026-05-15.json"


# ---------------------------------------------------------------------------
# Probe functions — each returns a structured dict
# ---------------------------------------------------------------------------

def probe_rdap_generic(domain: str, client: httpx.Client) -> dict[str, Any]:
    """Probe rdap.org bootstrap for the domain."""
    assert isinstance(domain, str) and "." in domain
    url = f"{RDAP_GENERIC_BASE}/{domain}"
    result: dict[str, Any] = {"source": "rdap_generic", "url": url}
    try:
        resp = client.get(url, timeout=TIMEOUT_S)
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            result["status"] = data.get("status", [])
            result["registrar"] = _extract_registrar(data)
            result["events"] = _extract_events(data)
            result["signal"] = "REGISTERED"
        elif resp.status_code == 404:
            result["signal"] = "NOT_FOUND"
            result["note"] = "404 — domain not in RDAP bootstrap (available or TLD not indexed)"
        else:
            result["signal"] = "ERROR"
            result["note"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        result["signal"] = "ERROR"
        result["error"] = str(exc)[:200]
    return result


def probe_rdap_nic_co(domain: str, client: httpx.Client) -> dict[str, Any]:
    """Probe .co registry RDAP directly at rdap.nic.co."""
    assert isinstance(domain, str) and domain.endswith(".co")
    url = f"{RDAP_NIC_CO_BASE}/{domain}"
    result: dict[str, Any] = {"source": "rdap_nic_co", "url": url}
    try:
        resp = client.get(url, timeout=TIMEOUT_S)
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            result["status"] = data.get("status", [])
            result["registrar"] = _extract_registrar(data)
            result["events"] = _extract_events(data)
            result["signal"] = "REGISTERED"
        elif resp.status_code == 404:
            result["signal"] = "NOT_FOUND"
            result["note"] = "404 from .co registry RDAP — strong availability signal"
        else:
            result["signal"] = "ERROR"
            result["note"] = f"HTTP {resp.status_code}"
    except Exception as exc:
        result["signal"] = "ERROR"
        result["error"] = str(exc)[:200]
    return result


def probe_http_head(domain: str, client: httpx.Client) -> dict[str, Any]:
    """HTTP HEAD to see if domain resolves and serves content."""
    assert isinstance(domain, str) and "." in domain
    result: dict[str, Any] = {"source": "http_head"}
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            resp = client.head(url, timeout=TIMEOUT_S, follow_redirects=True)
            result["url"] = url
            result["http_status"] = resp.status_code
            result["final_url"] = str(resp.url)
            result["signal"] = "RESOLVES"
            result["note"] = f"Domain resolves via {scheme} -> {resp.status_code}"
            return result
        except httpx.ConnectError:
            result[f"{scheme}_error"] = "connect_error"
        except httpx.ConnectTimeout:
            result[f"{scheme}_error"] = "connect_timeout"
        except httpx.ReadTimeout:
            result[f"{scheme}_error"] = "read_timeout"
        except Exception as exc:
            result[f"{scheme}_error"] = str(exc)[:150]
    result["signal"] = "NO_RESOLVE"
    result["note"] = "Domain does not resolve via HTTP or HTTPS"
    return result


def probe_dynadot_search(domain: str, api_key: str, client: httpx.Client) -> dict[str, Any]:
    """Check availability via Dynadot search API."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(api_key, str) and len(api_key) > 10
    params = {
        "key": api_key,
        "command": "search",
        "domain0": domain,
    }
    result: dict[str, Any] = {"source": "dynadot_search"}
    try:
        resp = client.get(DYNADOT_API_BASE, params=params, timeout=TIMEOUT_S)
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            result["raw_response"] = data
            # Parse Dynadot response structure
            search_resp = data.get("SearchResponse", {})
            results_list = search_resp.get("SearchResults", [])
            if results_list:
                first = results_list[0] if isinstance(results_list, list) else results_list
                avail = first.get("Available", first.get("available", ""))
                result["dynadot_available"] = avail
                if avail in ("yes", True, "true"):
                    result["signal"] = "AVAILABLE"
                    result["note"] = "Dynadot confirms domain is available for registration"
                elif avail in ("no", False, "false"):
                    result["signal"] = "REGISTERED"
                    result["note"] = "Dynadot confirms domain is registered"
                else:
                    result["signal"] = "UNKNOWN"
                    result["note"] = f"Dynadot returned availability={avail}"
            else:
                result["signal"] = "UNKNOWN"
                result["note"] = "No SearchResults in Dynadot response"
        else:
            result["signal"] = "ERROR"
            result["note"] = f"Dynadot API HTTP {resp.status_code}"
    except Exception as exc:
        result["signal"] = "ERROR"
        result["error"] = str(exc)[:200]
    return result


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _extract_registrar(rdap_json: dict[str, Any]) -> str:
    """Extract registrar name from RDAP entities."""
    assert isinstance(rdap_json, dict)
    for entity in rdap_json.get("entities", []):
        roles = entity.get("roles", [])
        if "registrar" in roles:
            vcard = entity.get("vcardArray", [])
            if len(vcard) >= 2:
                for field in vcard[1]:
                    if len(field) >= 4 and field[0] == "fn":
                        return str(field[3])
            handle = entity.get("handle", "")
            if handle:
                return handle
    return "unknown"


def _extract_events(rdap_json: dict[str, Any]) -> dict[str, str]:
    """Extract key dates from RDAP events."""
    assert isinstance(rdap_json, dict)
    events: dict[str, str] = {}
    for event in rdap_json.get("events", []):
        action = event.get("eventAction", "")
        date_val = event.get("eventDate", "")
        if action in ("registration", "expiration", "last changed"):
            events[action] = date_val
    return events


def conclude_availability(probes: list[dict[str, Any]]) -> str:
    """Determine final verdict from all probe signals.

    Decision matrix:
      - Any probe says REGISTERED or RESOLVES -> REGISTERED
      - Dynadot says AVAILABLE and no probe says REGISTERED -> AVAILABLE
      - All probes NOT_FOUND/NO_RESOLVE and Dynadot UNKNOWN/ERROR -> UNKNOWN
    """
    assert isinstance(probes, list) and len(probes) > 0
    signals = [p.get("signal", "ERROR") for p in probes]
    assert len(signals) <= 10

    if "REGISTERED" in signals or "RESOLVES" in signals:
        return "REGISTERED"
    if "AVAILABLE" in signals:
        return "AVAILABLE"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_probes(api_key: str) -> list[dict[str, Any]]:
    """Run all four probes for each domain. Returns structured results."""
    assert isinstance(api_key, str) and len(api_key) > 10
    assert len(DOMAINS) <= MAX_DOMAINS

    client = httpx.Client(
        headers={
            "User-Agent": "DomainHunter-CoProbe/1.0",
            "Accept": "application/rdap+json, application/json",
        },
        follow_redirects=False,
    )

    all_results: list[dict[str, Any]] = []

    for idx, domain in enumerate(DOMAINS):
        assert idx < MAX_DOMAINS
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[{idx+1}/{len(DOMAINS)}] Probing {domain}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        probes: list[dict[str, Any]] = []

        # Probe 1: RDAP generic
        print(f"  [1/4] RDAP generic (rdap.org)...", file=sys.stderr, end=" ")
        p1 = probe_rdap_generic(domain, client)
        probes.append(p1)
        print(f"{p1.get('signal', '?')}", file=sys.stderr)
        time.sleep(RATE_LIMIT_S)

        # Probe 2: RDAP nic.co
        print(f"  [2/4] RDAP .co registry (rdap.nic.co)...", file=sys.stderr, end=" ")
        p2 = probe_rdap_nic_co(domain, client)
        probes.append(p2)
        print(f"{p2.get('signal', '?')}", file=sys.stderr)
        time.sleep(RATE_LIMIT_S)

        # Probe 3: HTTP HEAD
        print(f"  [3/4] HTTP HEAD...", file=sys.stderr, end=" ")
        p3 = probe_http_head(domain, client)
        probes.append(p3)
        print(f"{p3.get('signal', '?')}", file=sys.stderr)
        time.sleep(RATE_LIMIT_S)

        # Probe 4: Dynadot search
        print(f"  [4/4] Dynadot search API...", file=sys.stderr, end=" ")
        p4 = probe_dynadot_search(domain, api_key, client)
        probes.append(p4)
        print(f"{p4.get('signal', '?')}", file=sys.stderr)

        verdict = conclude_availability(probes)
        entry = {
            "domain": domain,
            "verdict": verdict,
            "probes": probes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        all_results.append(entry)

        if idx < len(DOMAINS) - 1:
            time.sleep(RATE_LIMIT_S)

    client.close()
    return all_results


def print_conclusions(results: list[dict[str, Any]]) -> None:
    """Print final availability conclusions."""
    assert isinstance(results, list)
    print(f"\n{'='*60}", file=sys.stderr)
    print("FINAL CONCLUSIONS", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    for r in results:
        domain = r["domain"]
        verdict = r["verdict"]
        signals = [p.get("signal", "?") for p in r["probes"]]
        sources = [p.get("source", "?") for p in r["probes"]]
        print(f"\n  {domain}: ** {verdict} **", file=sys.stderr)
        for src, sig in zip(sources, signals):
            note = ""
            for p in r["probes"]:
                if p.get("source") == src:
                    note = p.get("note", "")
                    break
            print(f"    {src:20s} -> {sig:12s}  {note}", file=sys.stderr)
    print(f"\n{'='*60}", file=sys.stderr)


def main() -> None:
    """Entrypoint: load env, run probes, save output."""
    assert ENV_PATH.exists(), f".env not found at {ENV_PATH}"
    load_dotenv(ENV_PATH)

    api_key = os.environ.get("DYNADOT_API_KEY", "")
    assert len(api_key) > 10, "DYNADOT_API_KEY not set or too short in .env"

    print(f"[Sprint 25] .co availability deep probe", file=sys.stderr)
    print(f"[Sprint 25] Targets: {', '.join(DOMAINS)}", file=sys.stderr)
    print(f"[Sprint 25] Dynadot API key: {api_key[:8]}...{api_key[-4:]}", file=sys.stderr)

    results = run_probes(api_key)
    print_conclusions(results)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_type": "co_availability_deep",
        "domains_checked": list(DOMAINS),
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n[Sprint 25] Results saved to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()

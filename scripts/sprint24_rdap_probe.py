#!/usr/bin/env python3
"""Sprint 24 — Live RDAP probe for 38 sweet_spot domains.

Queries rdap.org for each domain, extracts EPP status, registrar,
dates, and drop signals. Falls back to python-whois on 403.

NASA P10: functions <60 lines, 2+ assertions, bounded loops (max 50).
No global mutable state.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
RDAP_BASE = "https://rdap.org/domain"
TIMEOUT_S = 15
RATE_LIMIT_S = 0.5
MAX_DOMAINS = 50  # bounded-loop guard
DROP_STATUSES = frozenset({
    "client renew prohibited",
    "clientrenewprohibited",
    "pending delete",
    "pendingdelete",
    "redemption period",
    "redemptionperiod",
    "auto renew period",
    "autorenewperiod",
    "client hold",
    "clienthold",
    "server hold",
    "serverhold",
})
INPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "startup_reaper_2026-05-15.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sprint24_rdap_probe_2026-05-15.json"


def load_sweet_spot_domains(path: Path) -> list[str]:
    """Load sweet_spot domain names from the reaper JSON."""
    assert path.exists(), f"Input file missing: {path}"
    with open(path, "r") as fh:
        data = json.load(fh)
    assert "results" in data, "Expected 'results' key in JSON"
    domains = [
        r["domain"]
        for r in data["results"]
        if r.get("competition_tier") == "sweet_spot"
    ]
    assert len(domains) > 0, "No sweet_spot domains found"
    assert len(domains) <= MAX_DOMAINS, f"Too many domains: {len(domains)}"
    return domains


def extract_epp_statuses(rdap_json: dict[str, Any]) -> list[str]:
    """Pull EPP status strings from RDAP response."""
    assert isinstance(rdap_json, dict), "RDAP response must be dict"
    statuses: list[str] = []
    for entry in rdap_json.get("status", []):
        assert isinstance(entry, str), "Status entry must be string"
        statuses.append(entry)
    return statuses


def extract_registrar(rdap_json: dict[str, Any]) -> str:
    """Extract registrar name from RDAP entities."""
    assert isinstance(rdap_json, dict)
    for entity in rdap_json.get("entities", []):
        roles = entity.get("roles", [])
        if "registrar" in roles:
            # Try vcardArray first
            vcard = entity.get("vcardArray", [])
            if len(vcard) >= 2:
                for field in vcard[1]:
                    if len(field) >= 4 and field[0] == "fn":
                        return str(field[3])
            # Fallback to handle
            handle = entity.get("handle", "")
            if handle:
                return handle
    return "unknown"


def extract_dates(rdap_json: dict[str, Any]) -> tuple[str, str]:
    """Extract creation and expiry dates from RDAP events."""
    assert isinstance(rdap_json, dict)
    creation = ""
    expiry = ""
    for event in rdap_json.get("events", []):
        action = event.get("eventAction", "")
        date_val = event.get("eventDate", "")
        if action == "registration":
            creation = date_val
        elif action == "expiration":
            expiry = date_val
    return creation, expiry


def has_drop_signal(statuses: list[str]) -> bool:
    """Check if any EPP status indicates a drop signal."""
    assert isinstance(statuses, list)
    for s in statuses:
        normalized = s.lower().strip()
        if normalized in DROP_STATUSES:
            return True
    return False


def query_rdap(domain: str, session: requests.Session) -> dict[str, Any]:
    """Query RDAP for a single domain. Returns structured result."""
    assert isinstance(domain, str) and len(domain) > 0
    assert "." in domain, f"Invalid domain: {domain}"
    url = f"{RDAP_BASE}/{domain}"
    result: dict[str, Any] = {
        "domain": domain,
        "source": "rdap",
        "http_status": 0,
        "epp_statuses": [],
        "registrar": "unknown",
        "creation_date": "",
        "expiry_date": "",
        "drop_signal": False,
        "availability": "unknown",
        "error": None,
    }
    try:
        resp = session.get(url, timeout=TIMEOUT_S)
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            result["epp_statuses"] = extract_epp_statuses(data)
            result["registrar"] = extract_registrar(data)
            creation, expiry = extract_dates(data)
            result["creation_date"] = creation
            result["expiry_date"] = expiry
            result["drop_signal"] = has_drop_signal(result["epp_statuses"])
            result["availability"] = "registered"
        elif resp.status_code == 404:
            result["availability"] = "likely_available_or_pendingDelete"
            result["drop_signal"] = True
        elif resp.status_code == 403:
            result["error"] = "403_forbidden"
            result = _fallback_whois(domain, result)
        else:
            result["error"] = f"http_{resp.status_code}"
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_error"
    except Exception as exc:
        result["error"] = str(exc)[:200]
    return result


def _fallback_whois(domain: str, result: dict[str, Any]) -> dict[str, Any]:
    """Fallback to python-whois when RDAP returns 403."""
    assert isinstance(domain, str) and len(domain) > 0
    assert isinstance(result, dict)
    try:
        import whois
        w = whois.whois(domain)
        result["source"] = "whois_fallback"
        if w.status:
            if isinstance(w.status, list):
                result["epp_statuses"] = [str(s) for s in w.status]
            else:
                result["epp_statuses"] = [str(w.status)]
        if w.registrar:
            result["registrar"] = str(w.registrar)
        if w.creation_date:
            cd = w.creation_date
            if isinstance(cd, list):
                cd = cd[0]
            result["creation_date"] = cd.isoformat() if hasattr(cd, "isoformat") else str(cd)
        if w.expiration_date:
            ed = w.expiration_date
            if isinstance(ed, list):
                ed = ed[0]
            result["expiry_date"] = ed.isoformat() if hasattr(ed, "isoformat") else str(ed)
        result["drop_signal"] = has_drop_signal(result["epp_statuses"])
        result["availability"] = "registered"
        result["error"] = None  # whois succeeded
    except Exception as exc:
        result["error"] = f"whois_fallback_failed: {str(exc)[:150]}"
    return result


def print_status_table(results: list[dict[str, Any]]) -> None:
    """Print formatted status table to stderr."""
    assert isinstance(results, list)
    header = f"{'#':>3} {'Domain':30s} {'HTTP':>4} {'Source':8s} {'Drop?':5s} {'Availability':30s} {'Registrar':30s} {'EPP Statuses'}"
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)
    for i, r in enumerate(results[:MAX_DOMAINS], 1):
        epp_str = ", ".join(r["epp_statuses"][:5]) if r["epp_statuses"] else (r.get("error") or "n/a")
        drop_mark = "DROP" if r["drop_signal"] else "  -"
        registrar = (r.get("registrar") or "unknown")[:30]
        availability = r.get("availability") or "unknown"
        print(
            f"{i:3d} {r['domain']:30s} {r['http_status']:4d} {r['source']:8s} {drop_mark:5s} "
            f"{availability:30s} {registrar:30s} {epp_str[:60]}",
            file=sys.stderr,
        )


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics."""
    assert isinstance(results, list) and len(results) > 0
    drop_count = sum(1 for r in results if r["drop_signal"])
    active_count = sum(1 for r in results if r["availability"] == "registered" and not r["drop_signal"])
    available_count = sum(1 for r in results if "available" in r["availability"])
    error_count = sum(1 for r in results if r["error"] is not None)
    return {
        "total": len(results),
        "drop_signals": drop_count,
        "active_registered": active_count,
        "likely_available": available_count,
        "errors": error_count,
    }


def run_probe() -> None:
    """Main probe entrypoint. Queries all sweet_spot domains."""
    domains = load_sweet_spot_domains(INPUT_PATH)
    assert len(domains) <= MAX_DOMAINS

    print(f"[RDAP PROBE] Starting live probe of {len(domains)} sweet_spot domains", file=sys.stderr)
    print(f"[RDAP PROBE] Rate limit: {RATE_LIMIT_S}s between requests", file=sys.stderr)
    print(f"[RDAP PROBE] Timeout: {TIMEOUT_S}s per request", file=sys.stderr)
    print(file=sys.stderr)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "DomainHunter-RDAP-Probe/1.0",
        "Accept": "application/rdap+json, application/json",
    })

    results: list[dict[str, Any]] = []
    for idx, domain in enumerate(domains[:MAX_DOMAINS]):
        print(f"[{idx+1:2d}/{len(domains)}] Querying {domain}...", file=sys.stderr, end=" ")
        result = query_rdap(domain, session)
        results.append(result)
        status_label = "DROP" if result["drop_signal"] else result["availability"]
        print(f"{result['http_status']} -> {status_label}", file=sys.stderr)
        if idx < len(domains) - 1:
            time.sleep(RATE_LIMIT_S)

    print(file=sys.stderr)
    print_status_table(results)

    summary = summarize(results)
    print(file=sys.stderr)
    print(f"[SUMMARY] Total: {summary['total']}", file=sys.stderr)
    print(f"[SUMMARY] Drop signals: {summary['drop_signals']}", file=sys.stderr)
    print(f"[SUMMARY] Active registered: {summary['active_registered']}", file=sys.stderr)
    print(f"[SUMMARY] Likely available: {summary['likely_available']}", file=sys.stderr)
    print(f"[SUMMARY] Errors: {summary['errors']}", file=sys.stderr)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_type": "live_rdap",
        "total_queried": len(results),
        "summary": summary,
        "results": results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n[RDAP PROBE] Results saved to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    run_probe()

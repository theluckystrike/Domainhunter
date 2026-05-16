#!/usr/bin/env python3
"""Sprint 25 -- Live RDAP reprobe of all 19 backorder queue domains.

Checks if any domains have transitioned to pendingDelete, redemptionPeriod,
or any new drop phase since the last probe on 2026-05-15.

Uses httpx for HTTP requests. Rate limited to 2 requests/second.
Timeout 15s per request.

NASA P10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import httpx

# ---------------------------------------------------------------------------
# Constants (immutable -- NASA Rule 2: no global mutable state)
# ---------------------------------------------------------------------------
RDAP_BASE: Final[str] = "https://rdap.org/domain"
TIMEOUT_S: Final[float] = 15.0
RATE_LIMIT_INTERVAL: Final[float] = 0.5  # 2 requests/second = 500ms gap
MAX_DOMAINS: Final[int] = 50  # bounded-loop guard
MAX_STATUSES: Final[int] = 50  # bounded-loop guard for status parsing
MAX_EVENTS: Final[int] = 50  # bounded-loop guard for event parsing
MAX_ENTITIES: Final[int] = 50  # bounded-loop guard for entity parsing

DROP_PHASE_STATUSES: Final[frozenset[str]] = frozenset({
    "pending delete",
    "pendingdelete",
    "redemption period",
    "redemptionperiod",
})

ALL_DROP_SIGNAL_STATUSES: Final[frozenset[str]] = frozenset({
    "pending delete",
    "pendingdelete",
    "redemption period",
    "redemptionperiod",
    "auto renew period",
    "autorenewperiod",
    "client renew prohibited",
    "clientrenewprohibited",
    "client hold",
    "clienthold",
    "server hold",
    "serverhold",
})

QUEUE_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "data" / "backorder_queue.json"
)
OUTPUT_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / "data" / "sprint25_rdap_reprobe_2026-05-15.json"
)


# ---------------------------------------------------------------------------
# Queue loader
# ---------------------------------------------------------------------------

def load_queue_domains(path: Path) -> list[dict[str, Any]]:
    """Load domain entries from the backorder queue JSON.

    Returns list of dicts with at least 'domain' and 'epp_status' keys.
    """
    assert path.exists(), f"Queue file missing: {path}"
    assert path.suffix == ".json", f"Expected JSON file: {path}"
    with open(path, "r") as fh:
        data: dict[str, Any] = json.load(fh)
    assert "queue" in data, "Expected 'queue' key in backorder JSON"
    queue: list[dict[str, Any]] = data["queue"]
    assert 1 <= len(queue) <= MAX_DOMAINS, f"Queue size out of range: {len(queue)}"
    return queue


# ---------------------------------------------------------------------------
# RDAP parsing helpers
# ---------------------------------------------------------------------------

def extract_epp_statuses(rdap_json: dict[str, Any]) -> list[str]:
    """Pull EPP status strings from RDAP response 'status' array."""
    assert isinstance(rdap_json, dict), "RDAP response must be dict"
    raw: list[Any] = rdap_json.get("status", [])
    assert isinstance(raw, list), "status field must be a list"
    statuses: list[str] = []
    for idx, entry in enumerate(raw):
        if idx >= MAX_STATUSES:
            break
        if isinstance(entry, str):
            statuses.append(entry)
    return statuses


def extract_dates(rdap_json: dict[str, Any]) -> dict[str, str]:
    """Extract event dates (registration, expiration, last changed) from RDAP."""
    assert isinstance(rdap_json, dict), "RDAP response must be dict"
    events: list[Any] = rdap_json.get("events", [])
    assert isinstance(events, list), "events field must be a list"
    result: dict[str, str] = {}
    for idx, event in enumerate(events):
        if idx >= MAX_EVENTS:
            break
        action: str = event.get("eventAction", "")
        date_val: str = event.get("eventDate", "")
        if action and date_val:
            result[action] = date_val
    return result


def extract_registrar(rdap_json: dict[str, Any]) -> str:
    """Extract registrar name from RDAP entities array."""
    assert isinstance(rdap_json, dict), "RDAP response must be dict"
    entities: list[Any] = rdap_json.get("entities", [])
    assert isinstance(entities, list), "entities field must be a list"
    for idx, entity in enumerate(entities):
        if idx >= MAX_ENTITIES:
            break
        roles: list[str] = entity.get("roles", [])
        if "registrar" not in roles:
            continue
        vcard: list[Any] = entity.get("vcardArray", [None, []])
        if len(vcard) >= 2 and isinstance(vcard[1], list):
            for fidx, field in enumerate(vcard[1]):
                if fidx >= MAX_ENTITIES:
                    break
                if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                    return str(field[3])
        handle: str = entity.get("handle", "")
        if handle:
            return handle
    return "unknown"


# ---------------------------------------------------------------------------
# Drop-phase detection
# ---------------------------------------------------------------------------

def classify_drop_phase(statuses: list[str]) -> str:
    """Classify the domain's current drop lifecycle phase from EPP statuses.

    Returns one of: 'pendingDelete', 'redemptionPeriod', 'autoRenewPeriod',
    'clientHold', 'clientRenewProhibited', 'active', or 'unknown'.
    """
    assert isinstance(statuses, list), "statuses must be a list"
    normalized: list[str] = [s.lower().strip() for s in statuses[:MAX_STATUSES]]
    assert len(normalized) <= MAX_STATUSES, "status list too long"
    # Priority order: most advanced drop phase first
    if any(s in ("pending delete", "pendingdelete") for s in normalized):
        return "pendingDelete"
    if any(s in ("redemption period", "redemptionperiod") for s in normalized):
        return "redemptionPeriod"
    if any(s in ("auto renew period", "autorenewperiod") for s in normalized):
        return "autoRenewPeriod"
    if any(s in ("client hold", "clienthold", "server hold", "serverhold") for s in normalized):
        return "clientHold"
    if any(s in ("client renew prohibited", "clientrenewprohibited") for s in normalized):
        return "clientRenewProhibited"
    if any(s in ("active",) for s in normalized):
        return "active"
    return "unknown"


def is_new_drop_phase(old_epp: str, new_phase: str) -> bool:
    """Determine if the domain has advanced in the drop lifecycle."""
    assert isinstance(old_epp, str), "old_epp must be string"
    assert isinstance(new_phase, str), "new_phase must be string"
    phase_order: dict[str, int] = {
        "active": 0,
        "dry_run": 0,
        "clientRenewProhibited": 1,
        "clientHold": 2,
        "autoRenewPeriod": 3,
        "redemptionPeriod": 4,
        "pendingDelete": 5,
        "unknown": -1,
    }
    old_rank: int = phase_order.get(old_epp, 0)
    new_rank: int = phase_order.get(new_phase, -1)
    return new_rank > old_rank


# ---------------------------------------------------------------------------
# Single domain RDAP query
# ---------------------------------------------------------------------------

def query_single_domain(
    domain: str, old_epp: str, client: httpx.Client
) -> dict[str, Any]:
    """Query RDAP for one domain, compare against old EPP status."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert "." in domain, f"Invalid domain: {domain}"
    url: str = f"{RDAP_BASE}/{domain}"
    result: dict[str, Any] = {
        "domain": domain,
        "old_epp_status": old_epp,
        "http_status": 0,
        "new_epp_statuses": [],
        "new_phase": "unknown",
        "phase_changed": False,
        "registrar": "unknown",
        "expiry_date": "",
        "creation_date": "",
        "last_changed": "",
        "error": None,
    }
    try:
        resp: httpx.Response = client.get(url, timeout=TIMEOUT_S)
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            result["new_epp_statuses"] = extract_epp_statuses(data)
            result["new_phase"] = classify_drop_phase(result["new_epp_statuses"])
            result["phase_changed"] = is_new_drop_phase(old_epp, result["new_phase"])
            result["registrar"] = extract_registrar(data)
            dates: dict[str, str] = extract_dates(data)
            result["expiry_date"] = dates.get("expiration", "")
            result["creation_date"] = dates.get("registration", "")
            result["last_changed"] = dates.get("last changed", "")
        elif resp.status_code == 404:
            result["new_phase"] = "not_found_possible_drop"
            result["phase_changed"] = True
        else:
            result["error"] = f"http_{resp.status_code}"
    except httpx.TimeoutException:
        result["error"] = "timeout"
    except httpx.ConnectError:
        result["error"] = "connection_error"
    except Exception as exc:
        result["error"] = str(exc)[:200]
    return result


# ---------------------------------------------------------------------------
# Summary and output
# ---------------------------------------------------------------------------

def print_summary_table(results: list[dict[str, Any]]) -> None:
    """Print a formatted summary table to stderr."""
    assert isinstance(results, list), "results must be a list"
    assert len(results) > 0, "results must not be empty"
    header: str = (
        f"{'#':>3} {'Domain':30s} {'HTTP':>4} {'Old EPP':25s} "
        f"{'New Phase':22s} {'Changed':7s} {'Expiry':12s}"
    )
    print(header, file=sys.stderr)
    print("-" * len(header), file=sys.stderr)
    for i, r in enumerate(results[:MAX_DOMAINS], 1):
        changed_mark: str = ">>> YES" if r["phase_changed"] else "   no"
        expiry: str = r.get("expiry_date", "")[:10] if r.get("expiry_date") else "n/a"
        epp_display: str = r["new_phase"]
        if r.get("error"):
            epp_display = f"ERR: {r['error'][:15]}"
        print(
            f"{i:3d} {r['domain']:30s} {r['http_status']:4d} "
            f"{r['old_epp_status']:25s} {epp_display:22s} "
            f"{changed_mark:7s} {expiry:12s}",
            file=sys.stderr,
        )


def compute_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate summary statistics."""
    assert isinstance(results, list), "results must be a list"
    assert len(results) > 0, "results must not be empty"
    changed: list[str] = [r["domain"] for r in results if r["phase_changed"]]
    pending_delete: list[str] = [
        r["domain"] for r in results if r["new_phase"] == "pendingDelete"
    ]
    redemption: list[str] = [
        r["domain"] for r in results if r["new_phase"] == "redemptionPeriod"
    ]
    errors: list[str] = [r["domain"] for r in results if r.get("error")]
    return {
        "total_probed": len(results),
        "phase_changed_count": len(changed),
        "phase_changed_domains": changed,
        "pending_delete_domains": pending_delete,
        "redemption_period_domains": redemption,
        "error_count": len(errors),
        "error_domains": errors,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_reprobe() -> None:
    """Main reprobe entrypoint. Queries all backorder queue domains."""
    queue_entries: list[dict[str, Any]] = load_queue_domains(QUEUE_PATH)
    domain_count: int = len(queue_entries)
    assert 1 <= domain_count <= MAX_DOMAINS, f"Domain count out of range: {domain_count}"

    print(f"[REPROBE] Sprint 25 live RDAP reprobe of {domain_count} queue domains", file=sys.stderr)
    print(f"[REPROBE] Rate limit: {1/RATE_LIMIT_INTERVAL:.0f} req/s ({RATE_LIMIT_INTERVAL}s gap)", file=sys.stderr)
    print(f"[REPROBE] Timeout: {TIMEOUT_S}s per request", file=sys.stderr)
    print(f"[REPROBE] Endpoint: {RDAP_BASE}", file=sys.stderr)
    print(file=sys.stderr)

    client: httpx.Client = httpx.Client(
        headers={
            "User-Agent": "DomainHunter-RDAP-Reprobe/2.0",
            "Accept": "application/rdap+json, application/json",
        },
        follow_redirects=True,
    )

    results: list[dict[str, Any]] = []
    try:
        for idx, entry in enumerate(queue_entries[:MAX_DOMAINS]):
            domain: str = entry["domain"]
            old_epp: str = entry.get("epp_status", "unknown")
            print(
                f"  [{idx+1:2d}/{domain_count}] {domain:30s} ...",
                file=sys.stderr, end=" ", flush=True,
            )
            result: dict[str, Any] = query_single_domain(domain, old_epp, client)
            results.append(result)
            status_label: str = result["new_phase"]
            if result["phase_changed"]:
                status_label += " *** CHANGED ***"
            elif result.get("error"):
                status_label = f"ERR: {result['error']}"
            print(f"{result['http_status']} -> {status_label}", file=sys.stderr, flush=True)
            # Rate limit: 2 req/s
            if idx < domain_count - 1:
                time.sleep(RATE_LIMIT_INTERVAL)
    finally:
        client.close()

    assert len(results) > 0, "No results collected"

    print(file=sys.stderr)
    print_summary_table(results)

    summary: dict[str, Any] = compute_summary(results)

    print(file=sys.stderr)
    print(f"[SUMMARY] Total probed: {summary['total_probed']}", file=sys.stderr)
    print(f"[SUMMARY] Phase changed: {summary['phase_changed_count']}", file=sys.stderr)
    if summary["pending_delete_domains"]:
        print(f"[SUMMARY] *** PENDING DELETE: {summary['pending_delete_domains']}", file=sys.stderr)
    if summary["redemption_period_domains"]:
        print(f"[SUMMARY] *** REDEMPTION PERIOD: {summary['redemption_period_domains']}", file=sys.stderr)
    if summary["phase_changed_domains"]:
        print(f"[SUMMARY] Changed domains: {summary['phase_changed_domains']}", file=sys.stderr)
    else:
        print("[SUMMARY] No domains have advanced to a new drop phase.", file=sys.stderr)
    if summary["error_count"] > 0:
        print(f"[SUMMARY] Errors ({summary['error_count']}): {summary['error_domains']}", file=sys.stderr)

    # Save output
    output: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_type": "sprint25_rdap_reprobe",
        "source_file": str(QUEUE_PATH),
        "endpoint": RDAP_BASE,
        "total_queried": len(results),
        "summary": summary,
        "results": results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n[REPROBE] Results saved to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    run_reprobe()

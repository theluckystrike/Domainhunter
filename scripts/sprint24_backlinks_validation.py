#!/usr/bin/env python3
"""
Sprint 24 — DataForSEO Backlinks validation via WHOIS overview endpoint.

The Backlinks API (/v3/backlinks/*) requires a separate subscription (40204).
The WHOIS overview endpoint (/v3/domain_analytics/whois/overview/live) returns
backlinks_info with real backlink data and is available on our plan.

Backlink data persists after a site dies because external sites still link to it.

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable state.
"""

import base64
import json
import os
import sys
import time
from typing import Final, Any

# ── Constants (immutable) ──────────────────────────────────────────────
DATA_DIR: Final[str] = os.path.join(os.path.dirname(__file__), "..", "data")
INPUT_FILE: Final[str] = os.path.join(DATA_DIR, "startup_reaper_2026-05-15.json")
OUTPUT_FILE: Final[str] = os.path.join(DATA_DIR, "sprint24_backlinks_2026-05-15.json")
ENV_FILE: Final[str] = os.path.join(os.path.dirname(__file__), "..", ".env")

WHOIS_URL: Final[str] = "https://api.dataforseo.com/v3/domain_analytics/whois/overview/live"
BACKLINKS_SUMMARY_URL: Final[str] = "https://api.dataforseo.com/v3/backlinks/summary/live"

MAX_DOMAINS: Final[int] = 50
BATCH_SIZE: Final[int] = 8  # WHOIS OR-filter limit is 8 (9 returns 40501)
RATE_LIMIT_SEC: Final[float] = 0.3
MAX_BATCHES: Final[int] = 10


def load_env(env_path: str) -> dict[str, str]:
    """Load .env file into a dict. NASA: 2 assertions, <60 lines."""
    assert os.path.isfile(env_path), f".env not found: {env_path}"
    env: dict[str, str] = {}
    with open(env_path) as f:
        lines = f.readlines()
    assert len(lines) > 0, ".env file is empty"
    for line in lines[:100]:  # bounded loop
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def build_auth_header(login: str, password: str) -> dict[str, str]:
    """Build HTTP Basic Auth header. NASA: 2 assertions."""
    assert len(login) > 0, "Login is empty"
    assert len(password) > 0, "Password is empty"
    creds = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
    }


def load_sweet_spot_domains(input_path: str) -> list[str]:
    """Extract sweet_spot domains from reaper JSON. NASA: 2 assertions."""
    assert os.path.isfile(input_path), f"Input file not found: {input_path}"
    with open(input_path) as f:
        data = json.load(f)
    assert "results" in data, "No 'results' key in JSON"
    domains: list[str] = []
    for item in data["results"][:500]:  # bounded loop
        if item.get("competition_tier") == "sweet_spot":
            domains.append(item["domain"])
    assert len(domains) > 0, "No sweet_spot domains found"
    assert len(domains) <= MAX_DOMAINS, f"Too many domains: {len(domains)}"
    return domains


def post_api(url: str, body: list[dict], headers: dict[str, str]) -> dict[str, Any]:
    """POST to DataForSEO API. Returns parsed JSON. NASA: 2 assertions."""
    import urllib.request
    import urllib.error
    assert len(body) > 0, "Empty request body"
    assert "Authorization" in headers, "Missing auth header"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8") if e.fp else ""
        return {"error": str(e), "status_code": e.code, "body": body_text}
    except Exception as e:
        return {"error": str(e), "status_code": -1, "body": ""}


def build_or_filter(domains: list[str]) -> list:
    """Build OR-chained filter for WHOIS endpoint. NASA: 2 assertions, bounded."""
    assert len(domains) > 0, "No domains for filter"
    assert len(domains) <= BATCH_SIZE, f"Batch too large: {len(domains)}"
    filters: list = []
    for i, domain in enumerate(domains[:BATCH_SIZE]):  # bounded loop
        if i > 0:
            filters.append("or")
        filters.append(["domain", "=", domain])
    return filters


def chunk_list(items: list[str], size: int) -> list[list[str]]:
    """Split list into chunks. NASA: 2 assertions, bounded."""
    assert len(items) > 0, "Nothing to chunk"
    assert size > 0, "Chunk size must be positive"
    chunks: list[list[str]] = []
    for i in range(0, min(len(items), MAX_DOMAINS), size):  # bounded
        chunks.append(items[i : i + size])
    return chunks


def query_whois_batch(
    domains: list[str], headers: dict[str, str]
) -> tuple[list[dict], float]:
    """Query WHOIS for a batch of domains via OR filters. NASA: 2 assertions."""
    assert len(domains) > 0, "Empty batch"
    assert len(domains) <= BATCH_SIZE, f"Batch too large: {len(domains)}"
    filters = build_or_filter(domains)
    body = [{"limit": len(domains), "filters": filters}]
    resp = post_api(WHOIS_URL, body, headers)
    return parse_whois_response(resp, domains)


def parse_whois_response(
    resp: dict, expected_domains: list[str]
) -> tuple[list[dict], float]:
    """Parse WHOIS response, extract backlinks_info. NASA: 2 assertions, bounded."""
    assert isinstance(resp, dict), "Response must be dict"
    assert len(expected_domains) > 0, "Expected domains list empty"
    results: list[dict] = []
    cost = 0.0

    # Check for HTTP-level errors
    if "error" in resp and resp.get("status_code", 200) not in (200, 20000):
        for d in expected_domains[:MAX_DOMAINS]:  # bounded
            results.append({"domain": d, "error": resp["error"], "status_code": resp.get("status_code", -1)})
        return results, 0.0

    tasks = resp.get("tasks", [])
    if not tasks:
        for d in expected_domains[:MAX_DOMAINS]:  # bounded
            results.append({"domain": d, "error": "No tasks in response"})
        return results, 0.0

    task = tasks[0]
    cost = task.get("cost", 0.0)
    task_status = task.get("status_code", -1)

    if task_status != 20000:
        for d in expected_domains[:MAX_DOMAINS]:  # bounded
            results.append({
                "domain": d,
                "error": task.get("status_message", "unknown"),
                "status_code": task_status,
            })
        return results, cost

    # Parse items
    found_domains: set[str] = set()
    result_data = task.get("result", [])
    if result_data and len(result_data) > 0:
        items = result_data[0].get("items", [])
        for item in items[:MAX_DOMAINS]:  # bounded
            entry = extract_backlinks_from_whois(item)
            results.append(entry)
            found_domains.add(entry["domain"])

    # Add missing domains (not found in WHOIS)
    for d in expected_domains[:MAX_DOMAINS]:  # bounded
        if d not in found_domains:
            results.append({"domain": d, "error": "not found in WHOIS", "status_code": 0})

    return results, cost


def extract_backlinks_from_whois(item: dict) -> dict:
    """Extract backlinks_info from a WHOIS item. NASA: 2 assertions."""
    assert isinstance(item, dict), "Item must be dict"
    assert "domain" in item, "No domain key"
    bi = item.get("backlinks_info", {}) or {}
    return {
        "domain": item["domain"],
        "backlinks": bi.get("backlinks", 0),
        "referring_domains": bi.get("referring_domains", 0),
        "referring_main_domains": bi.get("referring_main_domains", 0),
        "referring_pages": bi.get("referring_pages", 0),
        "dofollow": bi.get("dofollow", 0),
        "backlinks_time_update": bi.get("time_update", ""),
        "registrar": item.get("registrar", ""),
        "registered": item.get("registered", None),
        "expiration_datetime": item.get("expiration_datetime", ""),
        "status_code": 20000,
    }


def eprint(msg: str) -> None:
    """Print to stderr. NASA: 2 assertions."""
    assert isinstance(msg, str), "msg must be str"
    assert len(msg) < 10000, "msg too long"
    print(msg, file=sys.stderr)


def query_all_domains(
    domains: list[str], headers: dict[str, str]
) -> tuple[list[dict], float]:
    """Query all domains in batches. NASA: 2 assertions, bounded loop."""
    assert len(domains) > 0, "No domains"
    assert len(domains) <= MAX_DOMAINS, f"Too many: {len(domains)}"
    batches = chunk_list(domains, BATCH_SIZE)
    all_results: list[dict] = []
    total_cost = 0.0
    for i, batch in enumerate(batches[:MAX_BATCHES]):  # bounded
        eprint(f"  Batch {i+1}/{len(batches)}: {len(batch)} domains "
               f"({batch[0]}...{batch[-1]})")
        batch_results, batch_cost = query_whois_batch(batch, headers)
        all_results.extend(batch_results)
        total_cost += batch_cost
        eprint(f"    -> {len(batch_results)} results, cost=${batch_cost:.4f}")
        for r in batch_results[:BATCH_SIZE]:  # bounded
            bl = r.get("backlinks", "-")
            rd = r.get("referring_domains", "-")
            err = r.get("error", "")
            status = "OK" if not err else err[:40]
            eprint(f"      {r['domain']:<30} bl={str(bl):>8} rd={str(rd):>6} [{status}]")
        if i < len(batches) - 1:
            time.sleep(RATE_LIMIT_SEC)
    return all_results, total_cost


def print_results_table(results: list[dict]) -> None:
    """Print formatted table to stderr. NASA: 2 assertions, bounded loop."""
    assert isinstance(results, list), "results must be a list"
    assert len(results) <= MAX_DOMAINS, f"Too many results: {len(results)}"
    eprint("")
    eprint(f"{'Domain':<30} {'Backlinks':>10} {'Ref Doms':>10} {'Main Doms':>10} "
           f"{'Dofollow':>10} {'Ref Pages':>10} {'Registrar':<20}")
    eprint("-" * 115)
    for entry in results[:MAX_DOMAINS]:  # bounded
        domain = entry.get("domain", "?")[:29]
        bl = entry.get("backlinks", "-")
        rd = entry.get("referring_domains", "-")
        md = entry.get("referring_main_domains", "-")
        df = entry.get("dofollow", "-")
        rp = entry.get("referring_pages", "-")
        reg = (entry.get("registrar", "-") or "-")[:19]
        err = entry.get("error", "")
        if err:
            eprint(f"{domain:<30} {'ERROR':>10} {err[:60]}")
        else:
            eprint(f"{domain:<30} {str(bl):>10} {str(rd):>10} {str(md):>10} "
                   f"{str(df):>10} {str(rp):>10} {reg:<20}")
    eprint("-" * 115)


def save_results(
    results: list[dict], total_cost: float, endpoint_used: str
) -> None:
    """Save results to JSON. NASA: 2 assertions."""
    assert isinstance(results, list), "results must be a list"
    assert len(OUTPUT_FILE) > 0, "Output file path is empty"

    # Sort by backlinks descending
    sorted_results = sorted(
        results, key=lambda x: x.get("backlinks", 0), reverse=True
    )

    # Compute summary stats
    with_data = [r for r in results if r.get("backlinks", 0) > 0]
    total_bl = sum(r.get("backlinks", 0) for r in results)
    total_rd = sum(r.get("referring_domains", 0) for r in results)

    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint_used": endpoint_used,
        "total_cost_usd": round(total_cost, 4),
        "domain_count": len(results),
        "domains_with_backlinks": len(with_data),
        "total_backlinks": total_bl,
        "total_referring_domains": total_rd,
        "note": "Backlinks API returned 40204 (not subscribed). "
                "Used WHOIS overview endpoint which includes backlinks_info.",
        "results": sorted_results,
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    eprint(f"\nSaved to {OUTPUT_FILE}")


def main() -> None:
    """Main entry point. NASA: 2 assertions."""
    assert os.path.isfile(ENV_FILE), f".env not found: {ENV_FILE}"
    assert os.path.isfile(INPUT_FILE), f"Input not found: {INPUT_FILE}"

    # Load credentials
    env = load_env(ENV_FILE)
    login = env.get("DATAFORSEO_LOGIN", "")
    password = env.get("DATAFORSEO_PASSWORD", "")
    assert len(login) > 0, "DATAFORSEO_LOGIN not set"
    assert len(password) > 0, "DATAFORSEO_PASSWORD not set"
    headers = build_auth_header(login, password)

    # Load domains
    domains = load_sweet_spot_domains(INPUT_FILE)
    eprint(f"Loaded {len(domains)} sweet_spot domains")

    # Step 1: Test Backlinks API (expected to fail with 40204)
    eprint(f"\n=== Testing /v3/backlinks/summary/live (expects 40204) ===")
    test_body = [{"target": domains[0]}]
    test_resp = post_api(BACKLINKS_SUMMARY_URL, test_body, headers)
    tasks = test_resp.get("tasks", [])
    task_status = tasks[0].get("status_code", -1) if tasks else -1
    eprint(f"  Backlinks API: task_status={task_status}")
    if task_status == 40204:
        eprint("  Confirmed: Backlinks subscription not active.")
    eprint(f"  Falling back to WHOIS overview (includes backlinks_info)")

    # Step 2: Query all via WHOIS overview with OR filters
    eprint(f"\n=== Querying WHOIS overview for {len(domains)} domains ===")
    results, total_cost = query_all_domains(domains, headers)

    # Step 3: Output
    print_results_table(results)
    with_data = [r for r in results if r.get("backlinks", 0) > 0]
    eprint(f"\nTotal API cost: ${total_cost:.4f}")
    eprint(f"Endpoint used: domain_analytics/whois/overview/live")
    eprint(f"Domains queried: {len(results)}")
    eprint(f"Domains with backlink data: {len(with_data)}/{len(results)}")
    if with_data:
        total_bl = sum(r.get("backlinks", 0) for r in results)
        max_bl = max(results, key=lambda x: x.get("backlinks", 0))
        eprint(f"Total backlinks across all: {total_bl:,}")
        eprint(f"Highest backlinks: {max_bl['domain']} ({max_bl.get('backlinks', 0):,})")

    save_results(results, total_cost, "domain_analytics/whois/overview/live")


if __name__ == "__main__":
    main()

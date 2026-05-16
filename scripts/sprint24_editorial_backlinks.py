#!/usr/bin/env python3
"""
Sprint 24 — Editorial Backlink Detection via DataForSEO SERP API.

Backlinks API returns 40204 (not subscribed), so we use SERP API instead:
  Strategy A: SERP query '"domain.com" site:ed1 OR site:ed2 ...' (editorial-focused)
  Strategy B: SERP query '"domain.com" -site:domain.com' depth=100 (broad scan)

Cross-references SERP results against a curated editorial domain list to identify
high-authority press coverage for top 10 sweet_spot domains.

NASA P10: functions <60 lines, 2+ assertions, bounded loops (max 15), no global mutable state.
"""

import base64
import json
import os
import sys
import time
from typing import Final, Any, Optional

# ── Constants (immutable) ──────────────────────────────────────────────
DATA_DIR: Final[str] = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_FILE: Final[str] = os.path.join(DATA_DIR, "sprint24_editorial_results.json")
ENV_FILE: Final[str] = os.path.join(os.path.dirname(__file__), "..", ".env")

SERP_URL: Final[str] = "https://api.dataforseo.com/v3/serp/google/organic/live/regular"

MAX_DOMAINS: Final[int] = 15
RATE_LIMIT_SEC: Final[float] = 0.5
SERP_DEPTH: Final[int] = 100

SWEET_SPOT_TOP10: Final[tuple[str, ...]] = (
    "humane.com", "arrival.com", "irl.com", "olive.com", "boweryfarming.com",
    "ghostautonomy.com", "convoy.com", "stenn.com", "veev.com", "infarm.com",
)

EDITORIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "techcrunch.com", "bloomberg.com", "forbes.com", "wsj.com", "nytimes.com",
    "cnbc.com", "reuters.com", "wired.com", "theverge.com", "bbc.com",
    "venturebeat.com", "crunchbase.com", "businessinsider.com", "arstechnica.com",
    "thenextweb.com", "zdnet.com", "engadget.com", "mashable.com",
})

# Split editorial domains into 2 groups for site: OR queries (Google limits ~32 terms)
EDITORIAL_GROUP_A: Final[tuple[str, ...]] = (
    "techcrunch.com", "bloomberg.com", "forbes.com", "wsj.com", "nytimes.com",
    "cnbc.com", "reuters.com", "wired.com", "theverge.com",
)
EDITORIAL_GROUP_B: Final[tuple[str, ...]] = (
    "bbc.com", "venturebeat.com", "crunchbase.com", "businessinsider.com",
    "arstechnica.com", "thenextweb.com", "zdnet.com", "engadget.com", "mashable.com",
)


def eprint(msg: str) -> None:
    """Print to stderr. NASA: 2 assertions."""
    assert isinstance(msg, str), "msg must be str"
    assert len(msg) < 10000, "msg too long"
    print(msg, file=sys.stderr)


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


def post_api(url: str, body: list[dict], headers: dict[str, str]) -> dict[str, Any]:
    """POST to DataForSEO API. Returns parsed JSON. NASA: 2 assertions."""
    import urllib.request
    import urllib.error
    assert len(body) > 0, "Empty request body"
    assert "Authorization" in headers, "Missing auth header"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8") if e.fp else ""
        return {"error": str(e), "status_code": e.code, "body": body_text}
    except Exception as e:
        return {"error": str(e), "status_code": -1, "body": ""}


def extract_serp_items(resp: dict) -> tuple[list[dict], float]:
    """Extract organic items from SERP response. NASA: 2 assertions."""
    assert isinstance(resp, dict), "Response must be dict"
    tasks = resp.get("tasks", [])
    assert isinstance(tasks, list), "Tasks must be list"
    if not tasks:
        return [], 0.0
    task = tasks[0]
    cost = task.get("cost", 0.0)
    if task.get("status_code") != 20000:
        return [], cost
    result_items = task.get("result", [])
    if not result_items:
        return [], cost
    items = result_items[0].get("items", [])
    organic = []
    for item in items[:200]:  # bounded
        if item.get("type") == "organic":
            organic.append(item)
    return organic, cost


def build_editorial_query(domain: str, group: tuple[str, ...]) -> str:
    """Build SERP query to find domain mentions on editorial sites. NASA: 2 assertions."""
    assert len(domain) > 0, "Domain is empty"
    assert len(group) > 0, "Group is empty"
    site_clauses = " OR ".join(f"site:{s}" for s in group[:15])  # bounded
    return f'"{domain}" {site_clauses}'


def build_broad_query(domain: str) -> str:
    """Build broad SERP query for domain mentions. NASA: 2 assertions."""
    assert len(domain) > 0, "Domain is empty"
    assert "." in domain, "Invalid domain format"
    return f'"{domain}" -site:{domain}'


def match_editorial(serp_domain: str) -> Optional[str]:
    """Check if a SERP result domain matches an editorial domain. NASA: 2 assertions."""
    assert isinstance(serp_domain, str), "serp_domain must be str"
    assert len(serp_domain) < 500, "Domain too long"
    for ed in EDITORIAL_DOMAINS:  # bounded by frozenset size (18)
        if serp_domain == ed or serp_domain.endswith(f".{ed}"):
            return ed
    return None


def process_serp_results(items: list[dict], target: str) -> dict[str, list[dict]]:
    """Group SERP items by domain, tracking editorial matches. NASA: 2 assertions."""
    assert isinstance(items, list), "items must be list"
    assert len(target) > 0, "target is empty"
    seen: dict[str, list[dict]] = {}
    for item in items[:300]:  # bounded
        dom = item.get("domain", "")
        if not dom:
            continue
        if dom not in seen:
            seen[dom] = []
        seen[dom].append({
            "title": item.get("title", "")[:120],
            "url": item.get("url", "")[:200],
            "position": item.get("rank_absolute", 0),
        })
    return seen


def query_editorial_for_domain(
    domain: str, headers: dict[str, str]
) -> tuple[dict[str, Any], float]:
    """
    Run editorial detection for a single domain using 3 SERP queries:
      1. Editorial group A (site: OR query)
      2. Editorial group B (site: OR query)
      3. Broad scan (all external mentions, depth=100)
    NASA: 2 assertions, bounded loop.
    """
    assert len(domain) > 0, "Domain is empty"
    assert "Authorization" in headers, "Missing auth"

    all_editorial: dict[str, list[dict]] = {}
    all_domains: dict[str, list[dict]] = {}
    total_cost = 0.0

    queries = [
        ("editorial_A", build_editorial_query(domain, EDITORIAL_GROUP_A), 30),
        ("editorial_B", build_editorial_query(domain, EDITORIAL_GROUP_B), 30),
        ("broad", build_broad_query(domain), SERP_DEPTH),
    ]

    for label, keyword, depth in queries[:5]:  # bounded
        body = [{
            "keyword": keyword,
            "location_code": 2840,
            "language_code": "en",
            "depth": depth,
        }]
        resp = post_api(SERP_URL, body, headers)
        items, cost = extract_serp_items(resp)
        total_cost += cost

        grouped = process_serp_results(items, domain)
        for dom, entries in grouped.items():
            ed_match = match_editorial(dom)
            if ed_match and ed_match not in all_editorial:
                all_editorial[ed_match] = entries
            if dom not in all_domains:
                all_domains[dom] = entries

        time.sleep(RATE_LIMIT_SEC)

    return build_domain_entry(domain, all_editorial, all_domains, total_cost)


def build_domain_entry(
    domain: str,
    editorial: dict[str, list[dict]],
    all_doms: dict[str, list[dict]],
    cost: float,
) -> tuple[dict[str, Any], float]:
    """Build result entry for a domain. NASA: 2 assertions."""
    assert len(domain) > 0, "Domain is empty"
    assert isinstance(editorial, dict), "editorial must be dict"

    # Top 10 external domains by number of mentions
    dom_counts = sorted(all_doms.items(), key=lambda x: -len(x[1]))[:10]
    top10 = []
    for dom, entries in dom_counts[:10]:  # bounded
        top10.append({
            "domain": dom,
            "mentions": len(entries),
            "sample_title": entries[0]["title"] if entries else "",
        })

    editorial_details = []
    for ed_dom, entries in sorted(editorial.items()):
        editorial_details.append({
            "domain": ed_dom,
            "articles": len(entries),
            "samples": entries[:3],  # bounded
        })

    entry = {
        "domain": domain,
        "endpoint": "serp/google/organic/live (editorial + broad)",
        "total_external_domains_found": len(all_doms),
        "editorial_domains_found": sorted(editorial.keys()),
        "editorial_count": len(editorial),
        "editorial_details": editorial_details,
        "top10_external_domains": top10,
        "cost": round(cost, 4),
    }
    return entry, cost


def print_domain_result(entry: dict, idx: int, total: int) -> None:
    """Print a single domain result to stderr. NASA: 2 assertions."""
    assert isinstance(entry, dict), "entry must be dict"
    assert idx > 0, "idx must be positive"
    domain = entry.get("domain", "?")
    ed_count = entry.get("editorial_count", 0)
    ed_list = entry.get("editorial_domains_found", [])
    ext_total = entry.get("total_external_domains_found", "?")
    cost = entry.get("cost", 0.0)
    eprint(f"  [{idx}/{total}] {domain} -- {ext_total} ext domains, "
           f"{ed_count} editorial, cost=${cost:.4f}")
    if ed_list:
        for ed in ed_list[:20]:  # bounded
            eprint(f"           -> {ed}")


def print_summary_table(results: list[dict]) -> None:
    """Print summary table to stderr. NASA: 2 assertions, bounded loop."""
    assert isinstance(results, list), "results must be list"
    assert len(results) <= MAX_DOMAINS, f"Too many results: {len(results)}"
    eprint("")
    eprint(f"{'Domain':<25} {'ExtDoms':>8} {'Editorial':>10} {'Editorial Domains':<55}")
    eprint("-" * 100)
    for entry in results[:MAX_DOMAINS]:  # bounded
        domain = entry.get("domain", "?")[:24]
        ext = entry.get("total_external_domains_found", "?")
        ed_count = entry.get("editorial_count", 0)
        ed_list = ", ".join(entry.get("editorial_domains_found", []))[:54]
        eprint(f"{domain:<25} {str(ext):>8} {str(ed_count):>10} {ed_list:<55}")
    eprint("-" * 100)


def print_top_domains(results: list[dict]) -> None:
    """Print top external domains per target. NASA: 2 assertions, bounded loop."""
    assert isinstance(results, list), "results must be list"
    assert len(results) <= MAX_DOMAINS, "Too many results"
    eprint("\n=== Top External Domains Per Target ===")
    for entry in results[:MAX_DOMAINS]:  # bounded
        domain = entry.get("domain", "?")
        top10 = entry.get("top10_external_domains", [])
        if top10:
            eprint(f"\n  {domain}:")
            for ref in top10[:10]:  # bounded
                eprint(f"    {ref.get('mentions',0):>3}x  {ref.get('domain','?')}")


def save_results(results: list[dict], total_cost: float, endpoint: str) -> None:
    """Save results to JSON. NASA: 2 assertions."""
    assert isinstance(results, list), "results must be list"
    assert len(OUTPUT_FILE) > 0, "Output path empty"
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint_used": endpoint,
        "total_cost_usd": round(total_cost, 4),
        "domain_count": len(results),
        "editorial_domain_list": sorted(EDITORIAL_DOMAINS),
        "note": "Backlinks API returned 40204 (not subscribed). Used SERP API fallback.",
        "methodology": (
            "3 SERP queries per target: "
            "(1) editorial group A site: OR query, "
            "(2) editorial group B site: OR query, "
            "(3) broad '\"domain\" -site:domain' depth=100. "
            "Results cross-referenced against 18 editorial domains."
        ),
        "results": results,
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    eprint(f"\nSaved to {OUTPUT_FILE}")


def main() -> None:
    """Main entry point. NASA: 2 assertions."""
    assert os.path.isfile(ENV_FILE), f".env not found: {ENV_FILE}"
    env = load_env(ENV_FILE)
    login = env.get("DATAFORSEO_LOGIN", "")
    password = env.get("DATAFORSEO_PASSWORD", "")
    assert len(login) > 0, "DATAFORSEO_LOGIN not set"
    assert len(password) > 0, "DATAFORSEO_PASSWORD not set"
    headers = build_auth_header(login, password)

    eprint("=== Sprint 24: Editorial Backlink Detection (SERP Fallback) ===")
    eprint(f"Targets: {len(SWEET_SPOT_TOP10)} sweet_spot domains")
    eprint(f"Editorial list: {len(EDITORIAL_DOMAINS)} domains")
    eprint("Strategy: 3 SERP queries per domain (2 editorial-focused + 1 broad)")
    eprint(f"Expected queries: {len(SWEET_SPOT_TOP10) * 3}")

    results: list[dict] = []
    total_cost = 0.0
    domains = list(SWEET_SPOT_TOP10)

    for i, domain in enumerate(domains[:MAX_DOMAINS], start=1):  # bounded
        eprint(f"\n--- [{i}/{len(domains)}] Processing {domain} ---")
        entry, cost = query_editorial_for_domain(domain, headers)
        results.append(entry)
        total_cost += cost
        print_domain_result(entry, i, len(domains))

    # Summary output
    print_summary_table(results)
    print_top_domains(results)

    eprint(f"\nTotal API cost: ${total_cost:.4f}")

    # Aggregate editorial stats
    all_editorial: dict[str, int] = {}
    for entry in results[:MAX_DOMAINS]:  # bounded
        for ed in entry.get("editorial_domains_found", []):
            all_editorial[ed] = all_editorial.get(ed, 0) + 1
    eprint(f"\n=== Editorial Coverage Summary ===")
    with_ed = sum(1 for r in results if r.get("editorial_count", 0) > 0)
    eprint(f"Domains with editorial coverage: {with_ed}/{len(results)}")
    if all_editorial:
        eprint("Most common editorial sources:")
        for ed, count in sorted(all_editorial.items(), key=lambda x: -x[1])[:15]:  # bounded
            eprint(f"  {ed}: covers {count}/{len(results)} targets")
    else:
        eprint("No editorial coverage found for any target.")

    save_results(results, total_cost, "serp/google/organic/live/regular")


if __name__ == "__main__":
    main()

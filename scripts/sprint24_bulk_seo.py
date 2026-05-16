#!/usr/bin/env python3
"""Sprint 24: Bulk SEO metrics via DataForSEO Backlinks API.

Two bulk API calls (bulk_ranks + bulk_pages_summary) for all 38 sweet_spot domains.
NASA P10: Functions <60 lines, 2+ assertions, bounded loops, no global mutable state.
"""

import json
import os
import sys
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ENV_PATH = ROOT / ".env"
OUTPUT_PATH = DATA_DIR / "sprint24_bulk_seo_2026-05-15.json"
INPUT_PATH = DATA_DIR / "startup_reaper_2026-05-15.json"

BULK_RANKS_URL = "https://api.dataforseo.com/v3/backlinks/bulk_ranks/live"
BULK_PAGES_URL = "https://api.dataforseo.com/v3/backlinks/bulk_pages_summary/live"

MAX_DOMAINS = 1000  # API limit per call
MAX_RETRIES = 2


def load_env(env_path: Path) -> dict:
    """Parse .env file into dict. Returns {key: value}."""
    assert env_path.exists(), f".env not found: {env_path}"
    result = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
    assert "DATAFORSEO_LOGIN" in result, "DATAFORSEO_LOGIN missing from .env"
    assert "DATAFORSEO_PASSWORD" in result, "DATAFORSEO_PASSWORD missing from .env"
    return result


def load_sweet_spot_domains(path: Path) -> list:
    """Load sweet_spot domains from reaper JSON."""
    assert path.exists(), f"Input file not found: {path}"
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", [])
    assert isinstance(results, list), "results must be a list"
    domains = [
        r["domain"]
        for r in results
        if isinstance(r, dict) and r.get("competition_tier") == "sweet_spot"
    ]
    assert len(domains) > 0, "No sweet_spot domains found"
    assert len(domains) <= MAX_DOMAINS, f"Too many domains: {len(domains)}"
    return domains


def build_auth_header(login: str, password: str) -> str:
    """Build HTTP Basic auth header value."""
    assert login and password, "Empty credentials"
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return f"Basic {token}"


def call_bulk_api(url: str, targets: list, auth_header: str) -> dict:
    """POST to a DataForSEO bulk endpoint. Returns parsed JSON response."""
    assert len(targets) > 0, "Empty targets list"
    assert len(targets) <= MAX_DOMAINS, f"Exceeds max: {len(targets)}"

    payload = json.dumps([{"targets": targets}]).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return {
            "http_error": e.code,
            "reason": str(e.reason),
            "body": body,
        }
    except urllib.error.URLError as e:
        return {"url_error": str(e.reason)}


def get_task_error(response: dict) -> tuple:
    """Check for task-level errors (top-level may be 20000 while tasks fail).
    Returns (error_code, error_message) or (None, None) if no error."""
    tasks = response.get("tasks", [])
    for task in tasks[:100]:  # bounded loop
        task_sc = task.get("status_code", 0)
        if task_sc != 20000 and task_sc != 0:
            return task_sc, task.get("status_message", "unknown")
    return None, None


def parse_bulk_ranks(response: dict) -> dict:
    """Extract {domain: rank} from bulk_ranks response."""
    result = {}
    status_code = response.get("status_code")
    if status_code and status_code != 20000:
        print(f"  [WARN] bulk_ranks top-level: {status_code} — {response.get('status_message')}")
        return result

    # Check task-level errors (API returns 20000 top-level even when tasks fail)
    task_err, task_msg = get_task_error(response)
    if task_err:
        print(f"  [ERROR] bulk_ranks task-level: {task_err} — {task_msg}")
        return result

    tasks = response.get("tasks", [])
    for task in tasks[:100]:  # bounded loop
        task_result = task.get("result") or []
        for item in task_result[:MAX_DOMAINS]:  # bounded loop
            domain = item.get("target", "")
            rank = item.get("rank", 0)
            if domain:
                result[domain] = rank
    return result


def parse_bulk_pages_summary(response: dict) -> dict:
    """Extract {domain: {rank, backlinks, referring_domains, broken_backlinks, spam_score}}."""
    result = {}
    status_code = response.get("status_code")
    if status_code and status_code != 20000:
        print(f"  [WARN] bulk_pages_summary top-level: {status_code} — {response.get('status_message')}")
        return result

    # Check task-level errors
    task_err, task_msg = get_task_error(response)
    if task_err:
        print(f"  [ERROR] bulk_pages_summary task-level: {task_err} — {task_msg}")
        return result

    tasks = response.get("tasks", [])
    for task in tasks[:100]:  # bounded loop
        task_result = task.get("result") or []
        for item in task_result[:MAX_DOMAINS]:  # bounded loop
            domain = item.get("target", "")
            if domain:
                result[domain] = {
                    "rank": item.get("rank", 0),
                    "backlinks": item.get("backlinks", 0),
                    "referring_domains": item.get("referring_domains", 0),
                    "broken_backlinks": item.get("broken_backlinks", 0),
                    "spam_score": item.get("spam_score", 0),
                }
    return result


def print_table(domains: list, ranks: dict, pages: dict) -> None:
    """Print aligned results table."""
    header = f"{'Domain':<30} {'Rank':>8} {'Backlinks':>12} {'Ref.Domains':>12} {'SpamScore':>10}"
    print(header)
    print("-" * len(header))
    for d in sorted(domains):
        r = ranks.get(d, 0)
        p = pages.get(d, {})
        bl = p.get("backlinks", 0)
        rd = p.get("referring_domains", 0)
        ss = p.get("spam_score", 0)
        print(f"{d:<30} {r:>8} {bl:>12} {rd:>12} {ss:>10}")


def save_output(domains: list, ranks: dict, pages: dict, raw_ranks: dict, raw_pages: dict) -> None:
    """Save combined results to JSON."""
    combined = {}
    for d in domains:
        p = pages.get(d, {})
        combined[d] = {
            "rank": ranks.get(d, p.get("rank", 0)),
            "backlinks": p.get("backlinks", 0),
            "referring_domains": p.get("referring_domains", 0),
            "broken_backlinks": p.get("broken_backlinks", 0),
            "spam_score": p.get("spam_score", 0),
        }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain_count": len(domains),
        "api_calls": 2,
        "api_cost_note": "bulk_ranks ~$0.002 + bulk_pages_summary ~$0.002 = ~$0.004 total",
        "bulk_ranks_meta": {
            "status_code": raw_ranks.get("status_code"),
            "status_message": raw_ranks.get("status_message"),
            "cost": raw_ranks.get("cost"),
            "tasks_count": raw_ranks.get("tasks_count"),
        },
        "bulk_pages_summary_meta": {
            "status_code": raw_pages.get("status_code"),
            "status_message": raw_pages.get("status_message"),
            "cost": raw_pages.get("cost"),
            "tasks_count": raw_pages.get("tasks_count"),
        },
        "results": combined,
    }

    # Check for top-level AND task-level errors
    for label, raw in [("bulk_ranks_raw_error", raw_ranks), ("bulk_pages_raw_error", raw_pages)]:
        sc = raw.get("status_code")
        if sc and sc != 20000:
            output[label] = {
                "status_code": sc,
                "status_message": raw.get("status_message"),
                "tasks": raw.get("tasks", []),
            }
        elif "http_error" in raw:
            output[label] = raw
        else:
            # Check task-level errors (top-level 20000 but tasks fail with 40204)
            task_err, task_msg = get_task_error(raw)
            if task_err:
                output[label] = {
                    "task_status_code": task_err,
                    "task_status_message": task_msg,
                    "top_level_status": sc,
                    "tasks": raw.get("tasks", []),
                }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to: {OUTPUT_PATH}")


def main() -> None:
    """Orchestrate bulk SEO data collection."""
    print("=" * 60)
    print("Sprint 24: Bulk SEO Metrics (DataForSEO)")
    print("=" * 60)

    # Load config
    env = load_env(ENV_PATH)
    domains = load_sweet_spot_domains(INPUT_PATH)
    auth = build_auth_header(env["DATAFORSEO_LOGIN"], env["DATAFORSEO_PASSWORD"])
    print(f"\nLoaded {len(domains)} sweet_spot domains")

    # Call 1: bulk_ranks
    print(f"\n[1/2] POST {BULK_RANKS_URL}")
    print(f"  Targets: {len(domains)} domains")
    raw_ranks = call_bulk_api(BULK_RANKS_URL, domains, auth)
    ranks = parse_bulk_ranks(raw_ranks)
    sc1 = raw_ranks.get("status_code", raw_ranks.get("http_error", "unknown"))
    task_err1, task_msg1 = get_task_error(raw_ranks)
    print(f"  Top-level status: {sc1}")
    print(f"  Task-level status: {task_err1 or 'OK'}")
    print(f"  Cost: {raw_ranks.get('cost', 'N/A')}")
    print(f"  Parsed ranks: {len(ranks)}")

    if task_err1 == 40204:
        print(f"\n  *** SUBSCRIPTION ERROR (40204) ***")
        print(f"  Message: {task_msg1}")
        print(f"  The Backlinks API subscription is NOT active.")
        print(f"  Activate at: https://app.dataforseo.com/backlinks-subscription")

    # Call 2: bulk_pages_summary
    print(f"\n[2/2] POST {BULK_PAGES_URL}")
    print(f"  Targets: {len(domains)} domains")
    raw_pages = call_bulk_api(BULK_PAGES_URL, domains, auth)
    pages = parse_bulk_pages_summary(raw_pages)
    sc2 = raw_pages.get("status_code", raw_pages.get("http_error", "unknown"))
    task_err2, task_msg2 = get_task_error(raw_pages)
    print(f"  Top-level status: {sc2}")
    print(f"  Task-level status: {task_err2 or 'OK'}")
    print(f"  Cost: {raw_pages.get('cost', 'N/A')}")
    print(f"  Parsed pages: {len(pages)}")

    if task_err2 == 40204:
        print(f"\n  *** SUBSCRIPTION ERROR (40204) ***")
        print(f"  Message: {task_msg2}")
        print(f"  The Backlinks API subscription is NOT active.")
        print(f"  Activate at: https://app.dataforseo.com/backlinks-subscription")

    # Output
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}\n")
    print_table(domains, ranks, pages)

    # Save
    save_output(domains, ranks, pages, raw_ranks, raw_pages)

    # Summary
    total_cost = 0.0
    for raw in [raw_ranks, raw_pages]:
        c = raw.get("cost")
        if c is not None:
            total_cost += float(c)
    print(f"\nTotal API cost: ${total_cost:.4f}")
    print("Done.")


if __name__ == "__main__":
    main()

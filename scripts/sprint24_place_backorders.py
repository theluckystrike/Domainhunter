#!/usr/bin/env python3
"""Sprint 24: Place Dynadot backorders for all 7 domains in the queue.

NASA P10 compliant: functions <60 lines, 2+ assertions, bounded loops,
all API responses checked, no global mutable state.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Constants
MAX_DOMAINS = 10  # bounded loop limit
RATE_LIMIT_SECONDS = 6  # 10 req/min = 6s gap
API_BASE = "https://api.dynadot.com/api3.json"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
QUEUE_FILE = DATA_DIR / "backorder_queue.json"
OUTPUT_FILE = DATA_DIR / "sprint24_backorder_results_2026-05-15.json"


def load_env(env_path: str) -> dict:
    """Load .env file into a dict. No global state mutation."""
    assert os.path.isfile(env_path), f".env not found: {env_path}"
    env = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    assert "DYNADOT_API_KEY" in env, "DYNADOT_API_KEY missing from .env"
    return env


def load_queue(queue_path: str) -> list:
    """Load backorder queue JSON and return domain list."""
    assert os.path.isfile(queue_path), f"Queue file not found: {queue_path}"
    with open(queue_path, "r") as f:
        data = json.load(f)
    domains = [item["domain"] for item in data.get("queue", [])]
    assert len(domains) > 0, "Queue is empty"
    assert len(domains) <= MAX_DOMAINS, f"Queue exceeds {MAX_DOMAINS} domains"
    return domains


def api_call(api_key: str, params: dict) -> dict:
    """Make a GET request to Dynadot API and return parsed JSON."""
    assert "command" in params, "API call requires 'command' parameter"
    assert len(api_key) > 10, "API key looks invalid (too short)"

    query_parts = [f"key={api_key}"]
    for k, v in params.items():
        query_parts.append(f"{k}={v}")
    url = f"{API_BASE}?{'&'.join(query_parts)}"

    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "DomainHunter/1.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.getcode()
            assert status_code == 200, f"HTTP {status_code}"
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"URL error: {e.reason}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"error": str(e)}


def get_account_balance(api_key: str) -> dict:
    """Fetch Dynadot account balance."""
    assert len(api_key) > 10, "API key invalid"
    result = api_call(api_key, {"command": "get_account_balance"})
    assert isinstance(result, dict), "Balance response must be dict"
    return result


def place_backorder(api_key: str, domain: str) -> dict:
    """Place a single backorder request for a domain."""
    assert len(domain) > 0, "Domain cannot be empty"
    assert "." in domain, f"Invalid domain format: {domain}"
    result = api_call(api_key, {
        "command": "add_backorder_request",
        "domain": domain,
    })
    assert isinstance(result, dict), "Backorder response must be dict"
    return result


def get_backorder_list(api_key: str) -> dict:
    """Get current backorder request list."""
    assert len(api_key) > 10, "API key invalid"
    result = api_call(api_key, {
        "command": "backorder_request_list",
        "startDate": "2020-01-01",
        "endDate": "2030-12-31",
    })
    assert isinstance(result, dict), "List response must be dict"
    return result


def process_all_backorders(api_key: str, domains: list) -> list:
    """Place backorders for all domains with rate limiting.

    Returns list of result dicts.
    """
    assert len(domains) <= MAX_DOMAINS, f"Too many domains: {len(domains)}"
    assert len(api_key) > 10, "API key invalid"

    results = []
    for i, domain in enumerate(domains):
        if i >= MAX_DOMAINS:
            break  # bounded loop guard

        print(f"\n[{i+1}/{len(domains)}] Placing backorder: {domain}")
        resp = place_backorder(api_key, domain)

        # Extract status from response
        status = "unknown"
        error_msg = None

        if "error" in resp:
            status = "api_error"
            error_msg = resp["error"]
        elif "AddBackorderRequestResponse" in resp:
            inner = resp["AddBackorderRequestResponse"]
            resp_code = inner.get("ResponseCode", -1)
            if resp_code == 0:
                status = "success"
            else:
                status = "failed"
                error_msg = inner.get("Error", f"ResponseCode={resp_code}")
        elif "ErrorResponse" in resp:
            status = "failed"
            error_msg = resp["ErrorResponse"].get("Error", "Unknown error")
        else:
            status = "unexpected_response"
            error_msg = json.dumps(resp)[:200]

        result = {
            "domain": domain,
            "status": status,
            "error": error_msg,
            "raw_response": resp,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        results.append(result)

        icon = "OK" if status == "success" else "FAIL"
        msg = error_msg or "Backorder placed"
        print(f"  [{icon}] {msg}")

        # Rate limit: wait before next request (skip after last)
        if i < len(domains) - 1:
            print(f"  Waiting {RATE_LIMIT_SECONDS}s (rate limit)...")
            time.sleep(RATE_LIMIT_SECONDS)

    return results


def print_results_table(results: list, balance_before: dict,
                        balance_after: dict, backorder_list: dict) -> None:
    """Print a formatted results table to stdout."""
    assert isinstance(results, list), "Results must be a list"
    assert len(results) > 0, "No results to display"

    print("\n" + "=" * 72)
    print("SPRINT 24 - DYNADOT BACKORDER RESULTS")
    print("=" * 72)

    # Balance
    print(f"\nBalance (before): {json.dumps(balance_before, indent=2)[:200]}")
    print(f"Balance (after):  {json.dumps(balance_after, indent=2)[:200]}")

    # Results table
    print(f"\n{'Domain':<30} {'Status':<12} {'Error/Note':<30}")
    print("-" * 72)
    success_count = 0
    fail_count = 0
    for r in results:
        if len(r) == 0:
            continue
        s = r["status"]
        if s == "success":
            success_count += 1
        else:
            fail_count += 1
        err = (r.get("error") or "OK")[:30]
        print(f"{r['domain']:<30} {s:<12} {err:<30}")

    print("-" * 72)
    print(f"Success: {success_count}  |  Failed: {fail_count}  |  "
          f"Total: {len(results)}")

    # Active backorders
    print(f"\nCurrent backorder list response:")
    print(json.dumps(backorder_list, indent=2)[:500])
    print("=" * 72)


def save_results(results: list, balance_before: dict,
                 balance_after: dict, backorder_list: dict,
                 output_path: str) -> None:
    """Save all results to JSON file."""
    assert len(results) > 0, "No results to save"
    assert output_path.endswith(".json"), "Output must be .json"

    success_count = sum(1 for r in results if r["status"] == "success")
    fail_count = len(results) - success_count

    output = {
        "sprint": "24",
        "task": "place_backorders",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "balance_before": balance_before,
        "balance_after": balance_after,
        "backorder_list": backorder_list,
        "summary": {
            "total_domains": len(results),
            "success_count": success_count,
            "fail_count": fail_count,
        },
        "results": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


def main() -> None:
    """Main entry point. Orchestrates backorder placement."""
    env_path = str(PROJECT_DIR / ".env")
    env = load_env(env_path)
    api_key = env["DYNADOT_API_KEY"]

    domains = load_queue(str(QUEUE_FILE))
    print(f"Loaded {len(domains)} domains from queue:")
    for d in domains:
        print(f"  - {d}")

    # Step 1: Check balance before
    print("\n--- Checking account balance (before) ---")
    balance_before = get_account_balance(api_key)
    print(json.dumps(balance_before, indent=2)[:300])
    time.sleep(RATE_LIMIT_SECONDS)

    # Step 2: Place all backorders
    print("\n--- Placing backorders ---")
    results = process_all_backorders(api_key, domains)

    # Step 3: Rate limit pause before next calls
    time.sleep(RATE_LIMIT_SECONDS)

    # Step 4: Check backorder list
    print("\n--- Checking current backorder list ---")
    backorder_list = get_backorder_list(api_key)
    time.sleep(RATE_LIMIT_SECONDS)

    # Step 5: Check balance after
    print("\n--- Checking account balance (after) ---")
    balance_after = get_account_balance(api_key)

    # Step 6: Print and save
    print_results_table(results, balance_before, balance_after, backorder_list)
    save_results(results, balance_before, balance_after, backorder_list,
                 str(OUTPUT_FILE))


if __name__ == "__main__":
    main()

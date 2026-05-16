#!/usr/bin/env python3
"""Sprint 25: Retry backorder placement for all 19 domains in the queue.

Calls Dynadot API add_backorder_request for each domain with 8s delay.
Checks balance before/after. Saves results to data/.

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable state.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# --- Constants ---

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_QUEUE_PATH: Path = _PROJECT_ROOT / "data" / "backorder_queue.json"
_OUTPUT_PATH: Path = _PROJECT_ROOT / "data" / "sprint25_backorder_retry_2026-05-15.json"
_ENV_PATH: Path = _PROJECT_ROOT / ".env"
_API_BASE: str = "https://api.dynadot.com/api3.json"
_TIMEOUT_S: int = 30
_DELAY_BETWEEN_REQUESTS_S: int = 8
_MAX_DOMAINS: int = 50  # bounded loop guard


def load_env(env_path: Path) -> dict[str, str]:
    """Load .env file into a dict of key=value pairs."""
    assert env_path.exists(), f".env not found at {env_path}"
    assert env_path.is_file(), f"{env_path} is not a file"
    result: dict[str, str] = {}
    with open(env_path, "r") as f:
        for idx, line in enumerate(f):
            if idx >= 100:  # bounded
                break
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
    assert isinstance(result, dict), "result must be a dict"
    assert len(result) > 0, ".env must contain at least one key"
    return result


def load_queue(queue_path: Path) -> list[dict[str, Any]]:
    """Load backorder queue JSON and return the domain list."""
    assert queue_path.exists(), f"Queue file not found: {queue_path}"
    assert queue_path.is_file(), f"{queue_path} is not a file"
    with open(queue_path, "r") as f:
        data: dict[str, Any] = json.load(f)
    queue: list[dict[str, Any]] = data.get("queue", [])
    assert isinstance(queue, list), "queue must be a list"
    assert len(queue) > 0, "queue must not be empty"
    return queue


def extract_domains(queue: list[dict[str, Any]]) -> list[str]:
    """Extract domain names from queue entries."""
    assert isinstance(queue, list), "queue must be a list"
    assert len(queue) > 0, "queue must not be empty"
    domains: list[str] = []
    for idx, entry in enumerate(queue):
        if idx >= _MAX_DOMAINS:
            break
        domain: str = entry.get("domain", "")
        assert isinstance(domain, str) and "." in domain, f"invalid domain: {domain}"
        domains.append(domain)
    assert len(domains) == len(queue), f"expected {len(queue)} domains, got {len(domains)}"
    return domains


def check_balance(api_key: str) -> dict[str, Any]:
    """Query Dynadot account balance."""
    assert isinstance(api_key, str) and len(api_key) > 10, "valid API key required"
    assert api_key.strip() == api_key, "API key must not have leading/trailing spaces"
    params: dict[str, str] = {"key": api_key, "command": "my_account_info"}
    with httpx.Client(timeout=_TIMEOUT_S) as client:
        resp: httpx.Response = client.get(_API_BASE, params=params)
    assert resp.status_code == 200, f"balance check failed: HTTP {resp.status_code}"
    data: dict[str, Any] = resp.json()
    assert isinstance(data, dict), "response must be a JSON object"
    return data


def place_backorder(api_key: str, domain: str) -> dict[str, Any]:
    """Place a single backorder request via Dynadot API."""
    assert isinstance(api_key, str) and len(api_key) > 10, "valid API key required"
    assert isinstance(domain, str) and "." in domain, f"invalid domain: {domain}"
    params: dict[str, str] = {
        "key": api_key,
        "command": "add_backorder_request",
        "domain": domain,
    }
    with httpx.Client(timeout=_TIMEOUT_S) as client:
        resp: httpx.Response = client.get(_API_BASE, params=params)
    data: dict[str, Any] = resp.json()
    assert isinstance(data, dict), "response must be a JSON object"
    assert resp.status_code == 200, f"HTTP {resp.status_code} for {domain}"
    return data


def parse_backorder_response(data: dict[str, Any], domain: str) -> dict[str, Any]:
    """Parse Dynadot backorder response into a result dict."""
    assert isinstance(data, dict), "data must be a dict"
    assert isinstance(domain, str), "domain must be a string"
    # Check multiple possible response wrappers
    resp_wrapper: dict[str, Any] | None = None
    for key in ("AddBackorderRequestResponse", "StatusHeader"):
        if key in data:
            resp_wrapper = data[key]
            break
    if resp_wrapper is None:
        resp_wrapper = data
    status: str = str(resp_wrapper.get("Status", resp_wrapper.get("status", "unknown")))
    error: str = str(resp_wrapper.get("Error", ""))
    success: bool = status.lower() == "success"
    message: str = error if error else status
    return {
        "domain": domain,
        "success": success,
        "status": status,
        "message": message,
        "raw_response": data,
    }


def extract_balance_amount(data: dict[str, Any]) -> str:
    """Extract balance string from account info response."""
    assert isinstance(data, dict), "data must be a dict"
    # Dynadot nests balance in various places
    for key in ("MyAccountInfoResponse", "AccountInfoResponse", "StatusHeader"):
        wrapper: Any = data.get(key)
        if isinstance(wrapper, dict):
            for bkey in ("Balance", "balance", "AccountBalance"):
                if bkey in wrapper:
                    return str(wrapper[bkey])
    # Fallback: return the full response summary
    assert isinstance(data, dict), "data invariant"
    return json.dumps(data, indent=2)[:500]


def run_backorder_sweep(api_key: str, domains: list[str]) -> list[dict[str, Any]]:
    """Place backorders for all domains with 8s delay between each."""
    assert isinstance(domains, list) and len(domains) > 0, "domains list required"
    assert len(domains) <= _MAX_DOMAINS, f"too many domains: {len(domains)}"
    results: list[dict[str, Any]] = []
    total: int = len(domains)
    for idx, domain in enumerate(domains):
        if idx >= _MAX_DOMAINS:
            break
        print(f"[{idx + 1}/{total}] Placing backorder for {domain} ...")
        try:
            raw: dict[str, Any] = place_backorder(api_key, domain)
            result: dict[str, Any] = parse_backorder_response(raw, domain)
            status_str: str = "OK" if result["success"] else "FAIL"
            print(f"  -> {status_str}: {result['message']}")
        except Exception as exc:
            result = {
                "domain": domain,
                "success": False,
                "status": "error",
                "message": str(exc),
                "raw_response": None,
            }
            print(f"  -> ERROR: {exc}")
        results.append(result)
        # Delay between requests (skip after last)
        if idx < total - 1:
            print(f"  Waiting {_DELAY_BETWEEN_REQUESTS_S}s (rate limit) ...")
            time.sleep(_DELAY_BETWEEN_REQUESTS_S)
    assert len(results) == len(domains), "result count must match domain count"
    return results


def save_results(results: list[dict[str, Any]], balance_before: str,
                 balance_after: str, output_path: Path) -> None:
    """Save sweep results to JSON file."""
    assert isinstance(results, list), "results must be a list"
    assert output_path.parent.exists(), f"output dir missing: {output_path.parent}"
    succeeded: int = sum(1 for r in results if r["success"])
    failed: int = len(results) - succeeded
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sprint": "25",
        "action": "retry_backorder_placement",
        "total_domains": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "results": results,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    assert output_path.exists(), "output file must exist after write"
    print(f"\nResults saved to {output_path}")
    print(f"Summary: {succeeded} succeeded, {failed} failed out of {len(results)}")


def main() -> None:
    """Main entry point: load queue, check balance, sweep backorders, save."""
    print("=" * 60)
    print("Sprint 25: Dynadot Backorder Retry Sweep")
    print("=" * 60)

    # Load config
    env: dict[str, str] = load_env(_ENV_PATH)
    api_key: str = env.get("DYNADOT_API_KEY", "")
    assert len(api_key) > 10, "DYNADOT_API_KEY not found or too short"

    # Load queue
    queue: list[dict[str, Any]] = load_queue(_QUEUE_PATH)
    domains: list[str] = extract_domains(queue)
    print(f"\nLoaded {len(domains)} domains from backorder queue")

    # Check balance before
    print("\nChecking Dynadot balance (before) ...")
    balance_before_raw: dict[str, Any] = check_balance(api_key)
    balance_before: str = extract_balance_amount(balance_before_raw)
    print(f"Balance before: {balance_before}")

    # Rate limit pause after balance check
    print(f"\nWaiting {_DELAY_BETWEEN_REQUESTS_S}s before starting sweep ...")
    time.sleep(_DELAY_BETWEEN_REQUESTS_S)

    # Run sweep
    print("\n--- Starting Backorder Sweep ---\n")
    results: list[dict[str, Any]] = run_backorder_sweep(api_key, domains)

    # Check balance after
    print(f"\nWaiting {_DELAY_BETWEEN_REQUESTS_S}s before balance check ...")
    time.sleep(_DELAY_BETWEEN_REQUESTS_S)
    print("Checking Dynadot balance (after) ...")
    balance_after_raw: dict[str, Any] = check_balance(api_key)
    balance_after: str = extract_balance_amount(balance_after_raw)
    print(f"Balance after: {balance_after}")

    # Save
    save_results(results, balance_before, balance_after, _OUTPUT_PATH)

    # Final summary
    print("\n" + "=" * 60)
    print("SWEEP COMPLETE")
    print("=" * 60)
    for r in results:
        tag: str = "OK" if r["success"] else "FAIL"
        print(f"  [{tag}] {r['domain']}: {r['message']}")


if __name__ == "__main__":
    main()

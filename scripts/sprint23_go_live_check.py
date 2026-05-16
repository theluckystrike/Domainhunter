#!/usr/bin/env python3
"""Sprint 23 -- Go-Live Checklist for Auto-Backorder Activation.

Verifies ALL prerequisites before enabling --auto-backorder in the cron wrapper.
Prints a checklist with PASS/FAIL for each item. If all pass, prints
GO-LIVE APPROVED and the exact command to flip from dry-run to live.

Usage:
  python scripts/sprint23_go_live_check.py

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_ENV_PATH: Final[str] = os.path.join(_ROOT, ".env")
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_SCRIPTS_DIR: Final[str] = os.path.join(_ROOT, "scripts")
_LOGS_DIR: Final[str] = os.path.join(_ROOT, "logs")
_MIN_BALANCE_USD: Final[float] = 25.0
_MAX_CHECKS: Final[int] = 20


# ── Result container ─────────────────────────────────────────────────


class CheckResult:
    """Immutable result of a single verification check."""

    __slots__ = ("name", "passed", "detail")

    def __init__(self, name: str, passed: bool, detail: str) -> None:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(passed, bool)
        self.name = name
        self.passed = passed
        self.detail = detail

    def __repr__(self) -> str:
        assert isinstance(self.name, str)
        assert isinstance(self.passed, bool)
        tag = "PASS" if self.passed else "FAIL"
        return f"[{tag}] {self.name}: {self.detail}"


# ── Individual check functions ───────────────────────────────────────


def _load_env_vars() -> dict[str, str]:
    """Parse .env file into a dict. Does NOT export to os.environ."""
    assert os.path.isdir(_ROOT)
    result: dict[str, str] = {}
    if not os.path.isfile(_ENV_PATH):
        return result
    with open(_ENV_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    assert isinstance(result, dict)
    return result


def _check_env_exists() -> CheckResult:
    """Verify .env file exists."""
    assert isinstance(_ENV_PATH, str) and len(_ENV_PATH) > 0
    exists = os.path.isfile(_ENV_PATH)
    assert isinstance(exists, bool)
    return CheckResult(
        ".env file exists",
        exists,
        _ENV_PATH if exists else "MISSING",
    )


def _check_env_key(env: dict[str, str], key: str, label: str) -> CheckResult:
    """Verify a specific key exists and is non-empty in .env."""
    assert isinstance(env, dict)
    assert isinstance(key, str) and len(key) > 0
    val = env.get(key, "")
    present = len(val) > 0
    masked = f"{val[:4]}...{val[-4:]}" if len(val) >= 8 else ("SET" if present else "EMPTY")
    return CheckResult(
        f".env has {label}",
        present,
        masked,
    )


def _extract_dynadot_balance(data: dict[str, Any]) -> float:
    """Extract USD balance from Dynadot API response. Returns -1 on failure."""
    assert isinstance(data, dict)
    assert len(data) > 0, "empty API response"
    bal_resp = data.get("GetAccountBalanceResponse", {})
    # Format 1: flat "Balance" field
    if "Balance" in bal_resp:
        return float(bal_resp["Balance"])
    # Format 2: "BalanceList" array with Currency/Amount pairs
    bal_list = bal_resp.get("BalanceList", [])
    for entry in bal_list[:10]:  # bounded
        if isinstance(entry, dict) and entry.get("Currency") == "USD":
            return float(entry.get("Amount", -1))
    # Fallback: first entry in BalanceList
    if bal_list and isinstance(bal_list[0], dict):
        return float(bal_list[0].get("Amount", -1))
    return -1.0


def _check_dynadot_api(env: dict[str, str]) -> CheckResult:
    """Make a real Dynadot API call to get account balance."""
    assert isinstance(env, dict)
    assert isinstance(env.get("DYNADOT_API_KEY", ""), str)
    api_key = env.get("DYNADOT_API_KEY", "")
    if not api_key:
        return CheckResult("Dynadot API responds", False, "No API key")
    try:
        import httpx
        params = {"key": api_key, "command": "get_account_balance"}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.dynadot.com/api3.json", params=params)
        data = resp.json()
        balance = _extract_dynadot_balance(data)
        if balance < 0:
            return CheckResult("Dynadot API responds", False, f"Bad response: {data}")
        return CheckResult("Dynadot API responds", True, f"Balance: ${balance:.2f}")
    except Exception as exc:
        return CheckResult("Dynadot API responds", False, str(exc))


def _check_dynadot_balance(env: dict[str, str]) -> CheckResult:
    """Verify Dynadot balance >= $25 (minimum for 2 catches)."""
    assert isinstance(env, dict)
    assert _MIN_BALANCE_USD > 0
    api_key = env.get("DYNADOT_API_KEY", "")
    if not api_key:
        return CheckResult(f"Dynadot balance >= ${_MIN_BALANCE_USD:.0f}", False, "No API key")
    try:
        import httpx
        params = {"key": api_key, "command": "get_account_balance"}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.dynadot.com/api3.json", params=params)
        data = resp.json()
        balance = _extract_dynadot_balance(data)
        ok = balance >= _MIN_BALANCE_USD
        return CheckResult(
            f"Dynadot balance >= ${_MIN_BALANCE_USD:.0f}",
            ok,
            f"${balance:.2f}" if balance >= 0 else "Could not read balance",
        )
    except Exception as exc:
        return CheckResult(f"Dynadot balance >= ${_MIN_BALANCE_USD:.0f}", False, str(exc))


def _check_json_file(path: str, label: str, key: str | None = None) -> CheckResult:
    """Verify a JSON file exists and optionally has entries under a key."""
    assert isinstance(path, str) and len(path) > 0
    assert isinstance(label, str)
    if not os.path.isfile(path):
        return CheckResult(label, False, f"MISSING: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if key is not None:
            entries = data.get(key, [])
            if isinstance(entries, dict):
                count = sum(len(v) for v in entries.values() if isinstance(v, list))
            elif isinstance(entries, list):
                count = len(entries)
            else:
                count = 0
            return CheckResult(label, count > 0, f"{count} entries under '{key}'")
        return CheckResult(label, True, os.path.basename(path))
    except Exception as exc:
        return CheckResult(label, False, str(exc))


def _check_file_exists(path: str, label: str) -> CheckResult:
    """Verify a file exists on disk."""
    assert isinstance(path, str) and len(path) > 0
    assert isinstance(label, str) and len(label) > 0
    exists = os.path.isfile(path)
    return CheckResult(label, exists, path if exists else "MISSING")


def _check_dir_exists(path: str, label: str) -> CheckResult:
    """Verify a directory exists."""
    assert isinstance(path, str) and len(path) > 0
    assert isinstance(label, str) and len(label) > 0
    exists = os.path.isdir(path)
    return CheckResult(label, exists, path if exists else "MISSING")


def _check_cron_entries() -> CheckResult:
    """Verify cron entries exist for drop_monitor and startup_reaper."""
    assert os.path.isdir(_ROOT)
    assert isinstance(_ROOT, str)
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        crontab = result.stdout
    except Exception as exc:
        return CheckResult("Cron entries installed", False, str(exc))

    has_monitor = "drop_monitor" in crontab
    has_reaper = "startup_reaper" in crontab
    if has_monitor and has_reaper:
        return CheckResult("Cron entries installed", True, "drop_monitor + startup_reaper found")
    missing = []
    if not has_monitor:
        missing.append("drop_monitor")
    if not has_reaper:
        missing.append("startup_reaper")
    return CheckResult("Cron entries installed", False, f"Missing: {', '.join(missing)}")


def _check_reaper_output() -> CheckResult:
    """Verify at least one startup_reaper_*.json exists in data/."""
    assert os.path.isdir(_ROOT)
    assert isinstance(_DATA_DIR, str)
    if not os.path.isdir(_DATA_DIR):
        return CheckResult("Reaper output exists", False, "data/ directory missing")
    matches = [
        f for f in os.listdir(_DATA_DIR)
        if f.startswith("startup_reaper_") and f.endswith(".json")
    ]
    if not matches:
        return CheckResult("Reaper output exists", False, "No startup_reaper_*.json found")
    latest = sorted(matches)[-1]
    return CheckResult("Reaper output exists", True, latest)


# ── Main orchestrator ────────────────────────────────────────────────


def _run_all_checks() -> list[CheckResult]:
    """Execute all go-live verification checks. Returns list of results."""
    assert os.path.isdir(_ROOT)
    env = _load_env_vars()
    results: list[CheckResult] = []

    # 1. Environment file and keys
    results.append(_check_env_exists())
    results.append(_check_env_key(env, "DYNADOT_API_KEY", "DYNADOT_API_KEY"))
    results.append(_check_env_key(env, "DATAFORSEO_LOGIN", "DATAFORSEO_LOGIN"))
    results.append(_check_env_key(env, "DATAFORSEO_PASSWORD", "DATAFORSEO_PASSWORD"))
    results.append(_check_env_key(env, "DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"))

    # 2. Dynadot API connectivity and balance
    results.append(_check_dynadot_api(env))
    results.append(_check_dynadot_balance(env))

    # 3. Data files
    results.append(_check_json_file(
        os.path.join(_SCRIPTS_DIR, "monitored_domains.json"),
        "monitored_domains.json has domains",
        "domains",
    ))
    results.append(_check_json_file(
        os.path.join(_DATA_DIR, "backorder_queue.json"),
        "backorder_queue.json has entries",
        "queue",
    ))

    # 4. Script files
    results.append(_check_file_exists(
        os.path.join(_SCRIPTS_DIR, "run_startup_reaper.sh"),
        "run_startup_reaper.sh exists",
    ))
    results.append(_check_file_exists(
        os.path.join(_SCRIPTS_DIR, "run_drop_monitor.sh"),
        "run_drop_monitor.sh exists",
    ))
    results.append(_check_file_exists(
        os.path.join(_SCRIPTS_DIR, "post_catch_executor.py"),
        "post_catch_executor.py exists",
    ))

    # 5. Cron and infrastructure
    results.append(_check_cron_entries())
    results.append(_check_dir_exists(_LOGS_DIR, "logs/ directory exists"))
    results.append(_check_dir_exists(_DATA_DIR, "data/ directory exists"))
    results.append(_check_reaper_output())

    assert len(results) <= _MAX_CHECKS, f"Too many checks: {len(results)}"
    return results


def _print_report(results: list[CheckResult]) -> int:
    """Print the go-live checklist and return exit code (0=approved, 1=blocked)."""
    assert isinstance(results, list) and len(results) > 0
    assert all(isinstance(r, CheckResult) for r in results[:10])

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print()
    print("=" * 70)
    print("  SPRINT 23 -- AUTO-BACKORDER GO-LIVE CHECKLIST")
    print("=" * 70)
    print()

    for i, r in enumerate(results, 1):
        tag = " PASS " if r.passed else " FAIL "
        print(f"  {i:2d}. [{tag}] {r.name}")
        print(f"             {r.detail}")
    print()
    print("-" * 70)
    print(f"  Score: {passed}/{total}")
    print()

    if passed == total:
        print("  >>> GO-LIVE APPROVED <<<")
        print()
        print("  Backorder activation progression:")
        print()
        print("  STEP 1 (current): dry-run-backorder (already in cron wrapper)")
        print("    - Verify dry-run output in logs/ for 1-2 cycles")
        print()
        print("  STEP 2 (when ready): Enable live auto-backorder:")
        print("    Edit scripts/run_startup_reaper.sh, line with --dry-run-backorder")
        print("    Change: --dry-run-backorder")
        print("    To:     --auto-backorder")
        print()
        print("  Or run this sed command:")
        print("    sed -i '' 's/--dry-run-backorder/--auto-backorder/' \\")
        print("      scripts/run_startup_reaper.sh")
        print()
        return 0
    else:
        failed = [r for r in results if not r.passed]
        print("  >>> GO-LIVE BLOCKED <<<")
        print()
        print(f"  {len(failed)} check(s) failed. Fix these before enabling auto-backorder:")
        for r in failed:
            print(f"    - {r.name}: {r.detail}")
        print()
        return 1


def main() -> None:
    """Entry point. Run checks and print report."""
    assert os.path.isdir(_ROOT)
    assert isinstance(_MAX_CHECKS, int)
    results = _run_all_checks()
    exit_code = _print_report(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

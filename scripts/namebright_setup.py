#!/usr/bin/env python3
"""NameBright / DropCatch API connectivity test.

Verifies OAuth2 authentication, account balance, domain listing, and
DropCatch API reachability. Run this before enabling production backorders.

Usage:
    python scripts/namebright_setup.py              # Full connectivity test
    python scripts/namebright_setup.py --check-only  # Just verify auth works
    python scripts/namebright_setup.py --balance     # Show account balance only

NASA Power of 10: functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import httpx

# ---------------------------------------------------------------------------
# Resolve project root so config.settings is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import Settings  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
_AUTH_URL: Final[str] = "https://api.namebright.com/auth/token"
_ACCOUNT_URL: Final[str] = "https://api.namebright.com/rest/account"
_DOMAINS_URL: Final[str] = "https://api.namebright.com/rest/account/domains"
_BACKORDERS_URL: Final[str] = "https://api.dropcatch.com/v2/backorders"
_TIMEOUT_SECONDS: Final[int] = 30
_MAX_CHECKS: Final[int] = 10
_HEADER_LINE: Final[str] = "=" * 40

# Status labels
_OK: Final[str] = "\033[32m[OK]\033[0m"
_FAIL: Final[str] = "\033[31m[FAIL]\033[0m"
_SKIP: Final[str] = "\033[33m[SKIP]\033[0m"


# ---------------------------------------------------------------------------
# Result container (frozen)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single connectivity check."""

    label: str
    passed: bool
    detail: str
    skipped: bool = False

    def __post_init__(self) -> None:
        assert isinstance(self.label, str) and len(self.label) > 0
        assert isinstance(self.passed, bool)

    def format(self) -> str:
        """Render as a single status line."""
        assert isinstance(self.label, str)
        assert isinstance(self.detail, str)
        if self.skipped:
            return f"{_SKIP} {self.label}: {self.detail}"
        tag = _OK if self.passed else _FAIL
        return f"{tag} {self.label}: {self.detail}"


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------
def load_credentials() -> tuple[str, str]:
    """Load DropCatch/NameBright credentials from .env via Settings.

    Returns:
        (client_id, client_secret) tuple. Both may be empty strings.
    """
    settings = Settings()
    client_id = settings.dropcatch_client_id or ""
    client_secret = settings.dropcatch_client_secret or ""
    assert isinstance(client_id, str), "client_id must be string"
    assert isinstance(client_secret, str), "client_secret must be string"
    return client_id, client_secret


def check_credentials(client_id: str, client_secret: str) -> CheckResult:
    """Verify that credentials are present and well-formed."""
    assert isinstance(client_id, str), "client_id type check"
    assert isinstance(client_secret, str), "client_secret type check"

    if not client_id or not client_secret:
        missing = []
        if not client_id:
            missing.append("DROPCATCH_CLIENT_ID")
        if not client_secret:
            missing.append("DROPCATCH_CLIENT_SECRET")
        return CheckResult(
            label="Credentials loaded",
            passed=False,
            detail=f"Missing: {', '.join(missing)} in .env",
        )

    # Validate format: client_id should be "accountname:appname"
    has_colon = ":" in client_id
    masked_id = f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) >= 8 else client_id
    if not has_colon:
        return CheckResult(
            label="Credentials loaded",
            passed=False,
            detail=f"client_id format invalid (expected 'account:app', got '{masked_id}')",
        )

    return CheckResult(
        label="Credentials loaded",
        passed=True,
        detail=f"client_id={masked_id}",
    )


# ---------------------------------------------------------------------------
# OAuth2 authentication
# ---------------------------------------------------------------------------
def authenticate(
    http: httpx.Client,
    client_id: str,
    client_secret: str,
) -> tuple[CheckResult, str]:
    """Acquire an OAuth2 bearer token from NameBright.

    Returns:
        (CheckResult, token_string). Token is empty on failure.
    """
    assert len(client_id) > 0, "client_id required"
    assert len(client_secret) > 0, "client_secret required"

    try:
        response = http.post(
            _AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    except httpx.RequestError as exc:
        return CheckResult(
            label="OAuth2 authentication",
            passed=False,
            detail=f"Connection error: {exc}",
        ), ""

    if response.status_code not in (200, 201):
        return CheckResult(
            label="OAuth2 authentication",
            passed=False,
            detail=f"{response.status_code} {response.reason_phrase} - Check client_id and client_secret",
        ), ""

    data: dict[str, Any] = response.json()
    token = data.get("access_token", "")
    expires_in = int(data.get("expires_in", 0))

    if not token:
        return CheckResult(
            label="OAuth2 authentication",
            passed=False,
            detail="No access_token in response",
        ), ""

    return CheckResult(
        label="OAuth2 authentication",
        passed=True,
        detail=f"Token acquired (expires in {expires_in}s)",
    ), token


# ---------------------------------------------------------------------------
# Account balance
# ---------------------------------------------------------------------------
def check_account_balance(
    http: httpx.Client,
    token: str,
) -> CheckResult:
    """Fetch account balance from NameBright REST API."""
    assert len(token) > 0, "token required"
    assert isinstance(http, httpx.Client), "http client required"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = http.get(_ACCOUNT_URL, headers=headers)
    except httpx.RequestError as exc:
        return CheckResult(
            label="Account balance",
            passed=False,
            detail=f"Connection error: {exc}",
        )

    if response.status_code != 200:
        return CheckResult(
            label="Account balance",
            passed=False,
            detail=f"{response.status_code} {response.reason_phrase}",
        )

    data: dict[str, Any] = response.json()
    balance = _extract_balance(data)

    return CheckResult(
        label="Account balance",
        passed=True,
        detail=f"${balance:,.2f}",
    )


def _extract_balance(data: dict[str, Any]) -> float:
    """Extract USD balance from account response.

    Tries common field names: Balance, AccountBalance, balance, amount.
    Returns 0.0 if not found.
    """
    assert isinstance(data, dict), "data must be dict"
    assert data is not None, "data must not be None"

    for key in ("Balance", "AccountBalance", "balance", "amount", "AvailableBalance"):
        if key in data:
            return float(data[key])
    # Nested under account object
    account = data.get("Account", data.get("account", {}))
    if isinstance(account, dict):
        for key in ("Balance", "AccountBalance", "balance", "AvailableBalance"):
            if key in account:
                return float(account[key])
    return 0.0


# ---------------------------------------------------------------------------
# Domain listing
# ---------------------------------------------------------------------------
def check_domains(
    http: httpx.Client,
    token: str,
) -> CheckResult:
    """List domains in the NameBright account."""
    assert len(token) > 0, "token required"
    assert isinstance(http, httpx.Client), "http client required"

    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": 1, "domainsPerPage": 10}

    try:
        response = http.get(_DOMAINS_URL, headers=headers, params=params)
    except httpx.RequestError as exc:
        return CheckResult(
            label="Domains in account",
            passed=False,
            detail=f"Connection error: {exc}",
        )

    if response.status_code != 200:
        return CheckResult(
            label="Domains in account",
            passed=False,
            detail=f"{response.status_code} {response.reason_phrase}",
        )

    data = response.json()
    count = _extract_domain_count(data)

    return CheckResult(
        label="Domains in account",
        passed=True,
        detail=str(count),
    )


def _extract_domain_count(data: Any) -> int:
    """Extract domain count from domains response.

    Handles list response, dict with TotalCount, or dict with domains key.
    """
    assert data is not None, "data must not be None"

    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        if "TotalCount" in data:
            return int(data["TotalCount"])
        if "totalCount" in data:
            return int(data["totalCount"])
        for key in ("Domains", "domains", "Results", "results"):
            if key in data and isinstance(data[key], list):
                return len(data[key])
    return 0


# ---------------------------------------------------------------------------
# DropCatch API connectivity
# ---------------------------------------------------------------------------
def check_dropcatch_api(
    http: httpx.Client,
    token: str,
) -> CheckResult:
    """Test DropCatch v2 API with its own auth endpoint."""
    assert isinstance(http, httpx.Client), "http client required"
    assert isinstance(token, str), "token must be string"

    settings = Settings()
    dc_id = settings.dropcatch_client_id or ""
    dc_secret = settings.dropcatch_api_secret or ""

    if not dc_id or not dc_secret:
        return CheckResult(label="DropCatch API", passed=False, detail="Missing DROPCATCH_API_SECRET in .env")

    try:
        auth_resp = http.post(
            "https://api.dropcatch.com/Authorize",
            json={"ClientId": dc_id, "ClientSecret": dc_secret},
            headers={"Content-Type": "application/json"},
        )
    except httpx.RequestError as exc:
        return CheckResult(label="DropCatch API", passed=False, detail=f"Auth error: {exc}")

    if auth_resp.status_code != 200:
        return CheckResult(label="DropCatch API", passed=False, detail=f"Auth: {auth_resp.status_code}")

    dc_token = auth_resp.json().get("token", "")
    assert len(dc_token) > 0, "No token in DropCatch auth response"

    try:
        response = http.get(
            _BACKORDERS_URL,
            headers={"Authorization": f"Bearer {dc_token}", "Content-Type": "application/json"},
            params={"size": 1},
        )
    except httpx.RequestError as exc:
        return CheckResult(label="DropCatch API", passed=False, detail=f"Connection error: {exc}")

    if response.status_code != 200:
        return CheckResult(label="DropCatch API", passed=False, detail=f"{response.status_code}")

    data = response.json()
    count = _extract_backorder_count(data)
    return CheckResult(label="DropCatch API", passed=True, detail=f"Accessible ({count} active backorders)")


def _extract_backorder_count(data: Any) -> int:
    """Extract active backorder count from response."""
    assert data is not None, "data must not be None"

    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("TotalCount", "totalCount", "Total", "total"):
            if key in data:
                return int(data[key])
        for key in ("Results", "results", "Backorders", "backorders"):
            if key in data and isinstance(data[key], list):
                return len(data[key])
    return 0


# ---------------------------------------------------------------------------
# IP whitelist check (inferred from successful API call)
# ---------------------------------------------------------------------------
def check_ip_whitelist(auth_passed: bool, dropcatch_passed: bool) -> CheckResult:
    """Infer IP whitelist status from successful API calls.

    If both auth and DropCatch API succeed, IP is whitelisted.
    NameBright blocks non-whitelisted IPs at the auth level.
    """
    assert isinstance(auth_passed, bool), "auth_passed must be bool"
    assert isinstance(dropcatch_passed, bool), "dropcatch_passed must be bool"

    if auth_passed and dropcatch_passed:
        return CheckResult(
            label="IP whitelist",
            passed=True,
            detail="Verified (auth + API both succeeded)",
        )
    if auth_passed:
        return CheckResult(
            label="IP whitelist",
            passed=True,
            detail="Verified (auth succeeded)",
        )
    return CheckResult(
        label="IP whitelist",
        passed=False,
        detail="Cannot verify (auth failed — may be IP block or bad credentials)",
    )


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------
def print_report(results: list[CheckResult]) -> int:
    """Print status report to stdout. Returns 0 if all passed, 1 otherwise."""
    assert isinstance(results, list), "results must be list"
    assert len(results) > 0, "at least one result required"

    print()
    print(f"NAMEBRIGHT API CONNECTIVITY TEST")
    print(_HEADER_LINE)

    for r in results:
        print(r.format())

    print()
    all_passed = all(r.passed or r.skipped for r in results)
    any_failed = any(not r.passed and not r.skipped for r in results)

    if not any_failed:
        print("\033[32mREADY FOR PRODUCTION\033[0m")
    else:
        failed_count = sum(1 for r in results if not r.passed and not r.skipped)
        print(f"\033[31m{failed_count} CHECK(S) FAILED\033[0m")

    print()
    return 0 if not any_failed else 1


def make_skip_result(label: str) -> CheckResult:
    """Create a skipped result for when auth fails."""
    assert isinstance(label, str) and len(label) > 0
    assert label is not None
    return CheckResult(
        label=label,
        passed=False,
        detail="Skipped (auth required)",
        skipped=True,
    )


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------
def run_full_test(
    http: httpx.Client,
    client_id: str,
    client_secret: str,
) -> list[CheckResult]:
    """Run all connectivity checks. Returns list of results."""
    assert isinstance(http, httpx.Client), "http client required"
    assert isinstance(client_id, str), "client_id type check"

    results: list[CheckResult] = []

    # 1. Credential check
    cred_result = check_credentials(client_id, client_secret)
    results.append(cred_result)
    if not cred_result.passed:
        results.append(make_skip_result("OAuth2 authentication"))
        results.append(make_skip_result("Account balance"))
        results.append(make_skip_result("Domains in account"))
        results.append(make_skip_result("DropCatch API"))
        results.append(make_skip_result("IP whitelist"))
        return results

    # 2. OAuth2 authentication
    auth_result, token = authenticate(http, client_id, client_secret)
    results.append(auth_result)
    if not auth_result.passed:
        results.append(make_skip_result("Account balance"))
        results.append(make_skip_result("Domains in account"))
        results.append(make_skip_result("DropCatch API"))
        results.append(check_ip_whitelist(False, False))
        return results

    # 3. Account balance
    results.append(check_account_balance(http, token))

    # 4. Domain listing
    results.append(check_domains(http, token))

    # 5. DropCatch API
    dc_result = check_dropcatch_api(http, token)
    results.append(dc_result)

    # 6. IP whitelist (inferred)
    results.append(check_ip_whitelist(True, dc_result.passed))

    assert len(results) <= _MAX_CHECKS, f"Too many checks: {len(results)}"
    return results


def run_check_only(
    http: httpx.Client,
    client_id: str,
    client_secret: str,
) -> list[CheckResult]:
    """Verify auth only -- minimal API calls."""
    assert isinstance(http, httpx.Client), "http client required"
    assert isinstance(client_id, str), "client_id type check"

    results: list[CheckResult] = []

    cred_result = check_credentials(client_id, client_secret)
    results.append(cred_result)
    if not cred_result.passed:
        results.append(make_skip_result("OAuth2 authentication"))
        return results

    auth_result, _token = authenticate(http, client_id, client_secret)
    results.append(auth_result)

    assert len(results) <= _MAX_CHECKS, f"Too many checks: {len(results)}"
    return results


def run_balance_only(
    http: httpx.Client,
    client_id: str,
    client_secret: str,
) -> list[CheckResult]:
    """Show account balance only."""
    assert isinstance(http, httpx.Client), "http client required"
    assert isinstance(client_id, str), "client_id type check"

    results: list[CheckResult] = []

    cred_result = check_credentials(client_id, client_secret)
    results.append(cred_result)
    if not cred_result.passed:
        results.append(make_skip_result("OAuth2 authentication"))
        results.append(make_skip_result("Account balance"))
        return results

    auth_result, token = authenticate(http, client_id, client_secret)
    results.append(auth_result)
    if not auth_result.passed:
        results.append(make_skip_result("Account balance"))
        return results

    results.append(check_account_balance(http, token))

    assert len(results) <= _MAX_CHECKS, f"Too many checks: {len(results)}"
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="NameBright / DropCatch API connectivity test.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/namebright_setup.py              # Full test\n"
            "  python scripts/namebright_setup.py --check-only # Auth only\n"
            "  python scripts/namebright_setup.py --balance    # Balance only\n"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Just verify authentication works",
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        help="Show account balance only",
    )

    args = parser.parse_args(argv)
    assert isinstance(args.check_only, bool), "check_only parse error"
    assert isinstance(args.balance, bool), "balance parse error"
    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on failure."""
    args = parse_args(argv)

    # Load credentials
    try:
        client_id, client_secret = load_credentials()
    except Exception as exc:
        print(f"\n{_FAIL} Failed to load settings: {exc}")
        print("  Ensure .env exists in project root with DROPCATCH_CLIENT_ID and DROPCATCH_CLIENT_SECRET")
        return 1

    # Run requested check mode
    with httpx.Client(timeout=_TIMEOUT_SECONDS) as http:
        if args.check_only:
            results = run_check_only(http, client_id, client_secret)
        elif args.balance:
            results = run_balance_only(http, client_id, client_secret)
        else:
            results = run_full_test(http, client_id, client_secret)

    return print_report(results)


if __name__ == "__main__":
    raise SystemExit(main())

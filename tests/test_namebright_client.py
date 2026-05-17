"""Tests for NameBright API client — OAuth2 auth, domain management, DNS, push transfers.

Mocks all HTTP calls via unittest.mock.patch on httpx.Client.request.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No mutable global state.
NASA Rule 6: All assertions explicit — min 2 per test.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clients.namebright_client import (
    AccountInfo,
    AvailabilityResult,
    DnsRecord,
    DomainDetail,
    DomainSummary,
    NameBrightAuthError,
    NameBrightClient,
    NameBrightError,
    NameBrightNotFoundError,
    NameBrightRateLimitError,
    RegistrationResult,
    _RateLimiter,
)

# ---------------------------------------------------------------------------
# Constants (immutable — NASA Rule 2)
# ---------------------------------------------------------------------------
_CLIENT_ID: str = "testaccount:testapp"
_CLIENT_SECRET: str = "test-secret-abc123"

_AUTH_SUCCESS_RESPONSE: dict[str, Any] = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test_token",
    "token_type": "bearer",
    "expires_in": 1800,
}

_AUTH_REFRESHED_RESPONSE: dict[str, Any] = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.refreshed_token",
    "token_type": "bearer",
    "expires_in": 1800,
}

_ACCOUNT_BALANCE_RESPONSE: dict[str, Any] = {
    "Balance": 1250.75,
}

_LIST_DOMAINS_RESPONSE: list[dict[str, Any]] = [
    {
        "DomainName": "devtoolshub.com",
        "Status": "Active",
        "ExpireDate": "2027-06-15T00:00:00Z",
    },
    {
        "DomainName": "aicode.dev",
        "Status": "Active",
        "ExpireDate": "2027-03-22T00:00:00Z",
    },
]

_DOMAIN_DETAIL_RESPONSE: dict[str, Any] = {
    "DomainName": "devtoolshub.com",
    "Status": "Active",
    "ExpireDate": "2027-06-15T00:00:00Z",
    "Locked": True,
    "AutoRenew": True,
    "Privacy": True,
    "Category": "Technology",
    "AuthCode": "abc123XYZ",
}

_AVAILABILITY_AVAILABLE_RESPONSE: dict[str, Any] = {
    "DomainName": "freshstartup.dev",
    "Available": True,
    "Price": 12.99,
    "PromotionPrice": 9.99,
}

_AVAILABILITY_TAKEN_RESPONSE: dict[str, Any] = {
    "DomainName": "google.com",
    "Available": False,
    "Price": 0.0,
    "PromotionPrice": 0.0,
}

_REGISTRATION_RESPONSE: dict[str, Any] = {
    "OrderId": 12345,
    "TotalPrice": 12.99,
}

_DNS_RECORDS_RESPONSE: list[dict[str, Any]] = [
    {
        "Id": 1001,
        "Type": "A",
        "Name": "@",
        "Content": "93.184.216.34",
        "Ttl": 3600,
    },
    {
        "Id": 1002,
        "Type": "CNAME",
        "Name": "www",
        "Content": "devtoolshub.com",
        "Ttl": 3600,
    },
    {
        "Id": 1003,
        "Type": "MX",
        "Name": "@",
        "Content": "mail.devtoolshub.com",
        "Ttl": 3600,
    },
]

_ADD_DNS_RECORD_RESPONSE: dict[str, Any] = {
    "Id": 1004,
    "Type": "TXT",
    "Name": "@",
    "Content": "v=spf1 include:_spf.google.com ~all",
    "Ttl": 3600,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_mock_response(
    status_code: int,
    json_data: Any = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response with the given status and body."""
    resp = MagicMock()
    resp.status_code = status_code
    if text:
        resp.text = text
    else:
        resp.text = json.dumps(json_data if json_data is not None else {})
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = json.JSONDecodeError("", "", 0)
    return resp


def _make_client() -> NameBrightClient:
    """Create a NameBrightClient with test credentials and no rate-limit delay."""
    client = NameBrightClient(
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
    )
    # Override rate limiter to avoid real sleeps in tests
    client._rate_limiter = _RateLimiter(
        max_requests=100, window_seconds=1, min_interval=0.0,
    )
    return client


def _auth_then_api(api_response: MagicMock) -> list[MagicMock]:
    """Build a side_effect list: first call returns auth token, second returns API data."""
    auth_resp = _make_mock_response(200, _AUTH_SUCCESS_RESPONSE)
    return [auth_resp, api_response]


def _auth_then_multi(*api_responses: MagicMock) -> list[MagicMock]:
    """Build a side_effect list: auth token first, then multiple API responses."""
    auth_resp = _make_mock_response(200, _AUTH_SUCCESS_RESPONSE)
    return [auth_resp, *api_responses]


# ---------------------------------------------------------------------------
# 1. Auth success — token acquired, cached, used in subsequent calls
# ---------------------------------------------------------------------------
def test_auth_success() -> None:
    """Successful OAuth2 token acquisition caches the token for reuse."""
    client = _make_client()
    auth_resp = _make_mock_response(200, _AUTH_SUCCESS_RESPONSE)
    api_resp_1 = _make_mock_response(200, _ACCOUNT_BALANCE_RESPONSE)
    api_resp_2 = _make_mock_response(200, _ACCOUNT_BALANCE_RESPONSE)

    with patch.object(
        client._http, "request", side_effect=[auth_resp, api_resp_1, api_resp_2],
    ) as mock_request:
        # First call triggers auth + API
        _ = client.get_account_balance()
        # Second call should reuse cached token (no new auth call)
        _ = client.get_account_balance()
        # Auth was called once (first request), then 2 API calls = 3 total
        assert mock_request.call_count == 3

    assert client._access_token == _AUTH_SUCCESS_RESPONSE["access_token"]


# ---------------------------------------------------------------------------
# 2. Auth failure — raises NameBrightAuthError on 401
# ---------------------------------------------------------------------------
def test_auth_failure() -> None:
    """Non-200 response during token acquisition raises NameBrightAuthError."""
    client = _make_client()
    auth_resp = _make_mock_response(401, text="Unauthorized")

    with patch.object(client._http, "request", return_value=auth_resp):
        with pytest.raises(NameBrightAuthError) as exc_info:
            client.get_account_balance()

    assert "401" in str(exc_info.value)
    assert isinstance(exc_info.value, NameBrightError)


# ---------------------------------------------------------------------------
# 3. Auth token refresh — expired token triggers re-auth
# ---------------------------------------------------------------------------
def test_auth_token_refresh() -> None:
    """Expired token is refreshed automatically before the next API call."""
    client = _make_client()

    # Simulate an already-expired token
    client._access_token = "old_expired_token"
    client._token_expiry = time.time() - 100  # expired 100s ago

    auth_resp = _make_mock_response(200, _AUTH_REFRESHED_RESPONSE)
    api_resp = _make_mock_response(200, _ACCOUNT_BALANCE_RESPONSE)

    with patch.object(client._http, "request", side_effect=[auth_resp, api_resp]):
        _ = client.get_account_balance()

    assert client._access_token == _AUTH_REFRESHED_RESPONSE["access_token"]
    assert client._token_expiry > time.time()


# ---------------------------------------------------------------------------
# 4. get_account_balance — returns AccountInfo
# ---------------------------------------------------------------------------
def test_get_account_balance() -> None:
    """get_account_balance returns a properly populated AccountInfo."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _ACCOUNT_BALANCE_RESPONSE)),
    ):
        result = client.get_account_balance()

    assert isinstance(result, AccountInfo)
    assert result.balance == pytest.approx(1250.75)
    assert dataclasses.is_dataclass(result)


# ---------------------------------------------------------------------------
# 5. list_domains — returns list of DomainSummary
# ---------------------------------------------------------------------------
def test_list_domains() -> None:
    """list_domains returns a list of DomainSummary objects."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _LIST_DOMAINS_RESPONSE)),
    ):
        result = client.list_domains()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(d, DomainSummary) for d in result)
    assert result[0].domain == "devtoolshub.com"
    assert result[1].domain == "aicode.dev"


# ---------------------------------------------------------------------------
# 6. get_domain — returns DomainDetail
# ---------------------------------------------------------------------------
def test_get_domain() -> None:
    """get_domain returns a DomainDetail with full domain info."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _DOMAIN_DETAIL_RESPONSE)),
    ):
        result = client.get_domain("devtoolshub.com")

    assert isinstance(result, DomainDetail)
    assert result.domain == "devtoolshub.com"
    assert result.locked is True
    assert result.auto_renew is True
    assert result.privacy is True
    assert dataclasses.is_dataclass(result)


# ---------------------------------------------------------------------------
# 7. check_availability — domain available
# ---------------------------------------------------------------------------
def test_check_availability_available() -> None:
    """Available domain returns AvailabilityResult with available=True."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(
            _make_mock_response(200, _AVAILABILITY_AVAILABLE_RESPONSE),
        ),
    ):
        result = client.check_availability("freshstartup.dev")

    assert isinstance(result, AvailabilityResult)
    assert result.available is True
    assert result.price == pytest.approx(12.99)
    assert result.domain == "freshstartup.dev"


# ---------------------------------------------------------------------------
# 8. check_availability — domain taken
# ---------------------------------------------------------------------------
def test_check_availability_taken() -> None:
    """Taken domain returns AvailabilityResult with available=False."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(
            _make_mock_response(200, _AVAILABILITY_TAKEN_RESPONSE),
        ),
    ):
        result = client.check_availability("google.com")

    assert isinstance(result, AvailabilityResult)
    assert result.available is False
    assert result.domain == "google.com"


# ---------------------------------------------------------------------------
# 9. register_domain — returns RegistrationResult
# ---------------------------------------------------------------------------
def test_register_domain() -> None:
    """Successful registration returns RegistrationResult."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _REGISTRATION_RESPONSE)),
    ):
        result = client.register_domain("freshstartup.dev")

    assert isinstance(result, RegistrationResult)
    assert result.order_id == 12345
    assert result.total_price == pytest.approx(12.99)


# ---------------------------------------------------------------------------
# 10. set_nameservers — clears then sets new NS
# ---------------------------------------------------------------------------
def test_set_nameservers() -> None:
    """set_nameservers clears existing NS and adds new ones."""
    client = _make_client()
    new_ns = ["ns1.cloudflare.com", "ns2.cloudflare.com"]

    # Build empty-body responses (clear + put(ns1) + put(ns2))
    # _handle_response returns None when text is empty/whitespace
    def _empty_response() -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        return resp

    # Auth + clear + put(ns1) + put(ns2) = 4 API responses
    with patch.object(
        client._http, "request",
        side_effect=[
            _make_mock_response(200, _AUTH_SUCCESS_RESPONSE),
            _empty_response(),
            _empty_response(),
            _empty_response(),
        ],
    ) as mock_request:
        result = client.set_nameservers("devtoolshub.com", new_ns)

    assert result is True
    # auth(1) + clear(1) + put(2) = 4
    assert mock_request.call_count == 4


# ---------------------------------------------------------------------------
# 11. get_dns_records — returns list of DnsRecord
# ---------------------------------------------------------------------------
def test_get_dns_records() -> None:
    """get_dns_records returns a list of DnsRecord objects."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _DNS_RECORDS_RESPONSE)),
    ):
        result = client.get_dns_records("devtoolshub.com")

    assert isinstance(result, list)
    assert len(result) == 3
    assert all(isinstance(r, DnsRecord) for r in result)
    assert result[0].record_type == "A"
    assert result[0].value == "93.184.216.34"
    assert result[1].record_type == "CNAME"


# ---------------------------------------------------------------------------
# 12. add_dns_record — returns DnsRecord
# ---------------------------------------------------------------------------
def test_add_dns_record() -> None:
    """add_dns_record returns the newly created DnsRecord."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _ADD_DNS_RECORD_RESPONSE)),
    ):
        result = client.add_dns_record(
            domain="devtoolshub.com",
            record_type="TXT",
            name="@",
            value="v=spf1 include:_spf.google.com ~all",
            ttl=3600,
        )

    assert isinstance(result, DnsRecord)
    assert result.record_type == "TXT"
    assert "spf1" in result.value
    assert dataclasses.is_dataclass(result)


# ---------------------------------------------------------------------------
# 13. Rate limiter — timestamps recorded
# ---------------------------------------------------------------------------
def test_rate_limiter_basic() -> None:
    """Rate limiter records timestamps on each acquire call."""
    limiter = _RateLimiter(max_requests=30, window_seconds=30, min_interval=0.0)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert len(limiter._timestamps) == 3
    assert all(isinstance(ts, float) for ts in limiter._timestamps)


# ---------------------------------------------------------------------------
# 14. Rate limiter — 30-request window enforcement
# ---------------------------------------------------------------------------
def test_rate_limiter_window_enforcement() -> None:
    """Rate limiter enforces the sliding window of max N requests."""
    max_req = 5
    limiter = _RateLimiter(max_requests=max_req, window_seconds=30, min_interval=0.0)

    # Fill the window completely
    for _ in range(max_req):
        limiter.acquire()

    assert len(limiter._timestamps) == max_req

    # The deque should be at capacity; next acquire would need to wait
    # Verify the window is full by checking timestamp count
    now = time.monotonic()
    limiter._evict_expired(now)
    assert len(limiter._timestamps) == max_req


# ---------------------------------------------------------------------------
# 15. Exception hierarchy
# ---------------------------------------------------------------------------
def test_exception_hierarchy() -> None:
    """All specific exceptions inherit from NameBrightError."""
    assert issubclass(NameBrightAuthError, NameBrightError)
    assert issubclass(NameBrightRateLimitError, NameBrightError)
    assert issubclass(NameBrightNotFoundError, NameBrightError)
    assert issubclass(NameBrightError, Exception)


# ---------------------------------------------------------------------------
# 16. Result dataclasses are frozen (immutable)
# ---------------------------------------------------------------------------
def test_result_dataclasses_frozen() -> None:
    """All result dataclasses must be frozen (reject attribute mutation)."""
    account = AccountInfo(balance=100.0)
    summary = DomainSummary(domain="test.com", status="Active", expiry="2027-01-01")
    availability = AvailabilityResult(
        domain="test.com", available=True, price=9.99, promotion_price=7.99,
    )
    dns = DnsRecord(record_id=1, record_type="A", name="@", value="1.2.3.4", ttl=3600)

    for obj in (account, summary, availability, dns):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.balance = 0  # type: ignore[misc,attr-defined]

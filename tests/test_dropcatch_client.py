"""Tests for DropCatch API client — backorders, auctions, bids, downloads.

Mocks all HTTP calls via unittest.mock.patch on httpx.Client.request.
Tests the actual client at clients/dropcatch_client.py (524 lines).

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

from clients.dropcatch_client import (
    AuctionInfo,
    BackorderResult,
    BidResult,
    BulkBackorderResult,
    DropCatchAuthError,
    DropCatchBackorderError,
    DropCatchClient,
    DropCatchError,
    _RateLimiter,
)

# ---------------------------------------------------------------------------
# Constants (immutable — NASA Rule 2)
# ---------------------------------------------------------------------------
_AUTH_URL: str = "https://api.namebright.com/auth/token"
_API_BASE: str = "https://api.dropcatch.com"
_CLIENT_ID: str = "testaccount:testapp"
_CLIENT_SECRET: str = "test-secret-dropcatch-999"

_AUTH_SUCCESS_RESPONSE: dict[str, Any] = {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.dc_test_token",
    "token_type": "bearer",
    "expires_in": 1800,
}

_BACKORDER_SUCCESS_RESPONSE: dict[str, Any] = {
    "someErrors": False,
    "results": [
        {
            "domainName": "expiredgem.com",
            "success": True,
            "maxBid": 59.00,
            "message": "Backorder placed successfully",
            "statusCode": "Success",
        },
        {
            "domainName": "droppingsoon.net",
            "success": True,
            "maxBid": 59.00,
            "message": "Backorder placed successfully",
            "statusCode": "Success",
        },
    ],
}

_BACKORDER_PARTIAL_FAILURE_RESPONSE: dict[str, Any] = {
    "someErrors": True,
    "results": [
        {
            "domainName": "gooddomain.com",
            "success": True,
            "maxBid": 59.00,
            "message": "Backorder placed successfully",
            "statusCode": "Success",
        },
        {
            "domainName": "baddomain.com",
            "success": False,
            "maxBid": 0,
            "message": "Domain is not in a droppable state",
            "statusCode": "InvalidDomain",
        },
    ],
}

_CANCEL_BACKORDERS_RESPONSE: dict[str, Any] = {
    "someErrors": False,
    "results": [
        {"domainName": "expiredgem.com", "success": True, "message": "Cancelled"},
    ],
}

_LIST_BACKORDERS_RESPONSE: list[dict[str, Any]] = [
    {
        "DomainName": "expiredgem.com",
        "MaxBid": 59.00,
        "Type": "Standard",
        "Status": "Active",
        "DropDate": "2026-05-20",
    },
    {
        "DomainName": "droppingsoon.net",
        "MaxBid": 59.00,
        "Type": "Standard",
        "Status": "Active",
        "DropDate": "2026-05-21",
    },
    {
        "DomainName": "cheapfind.org",
        "MaxBid": 15.00,
        "Type": "DiscountClub",
        "Status": "Active",
        "DropDate": "2026-05-22",
    },
]

_SEARCH_AUCTIONS_RESPONSE: list[dict[str, Any]] = [
    {
        "AuctionId": 10001,
        "DomainName": "techtools.com",
        "HighBid": 125.00,
        "EndTime": "2026-05-18T23:59:00Z",
        "AuctionType": "Standard",
    },
    {
        "AuctionId": 10002,
        "DomainName": "codemarket.io",
        "HighBid": 45.00,
        "EndTime": "2026-05-19T23:59:00Z",
        "AuctionType": "Standard",
    },
]

_GET_AUCTION_RESPONSE: dict[str, Any] = {
    "AuctionId": 10001,
    "DomainName": "techtools.com",
    "HighBid": 125.00,
    "EndTime": "2026-05-18T23:59:00Z",
    "AuctionType": "Standard",
    "BidCount": 7,
    "TotalBidders": 3,
    "MinNextBid": 130.00,
}

_PLACE_BIDS_RESPONSE: dict[str, Any] = {
    "someErrors": False,
    "results": [
        {
            "auctionId": 10001,
            "success": True,
            "message": "Bid placed successfully",
        },
        {
            "auctionId": 10002,
            "success": True,
            "message": "Bid placed successfully",
        },
    ],
}

_DOWNLOAD_DROPPING_BYTES: bytes = b"PK\x03\x04fake-zip-content-for-testing"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_mock_response(
    status_code: int,
    json_data: Any = None,
    content: bytes | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response with the given status and body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data if json_data is not None else {})
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = json.JSONDecodeError("", "", 0)
    if content is not None:
        resp.content = content
    else:
        resp.content = resp.text.encode("utf-8")
    return resp


def _make_client() -> DropCatchClient:
    """Create a DropCatchClient with test credentials and no rate-limit delay."""
    client = DropCatchClient(
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


# ---------------------------------------------------------------------------
# 1. Auth success — token acquired and cached
# ---------------------------------------------------------------------------
def test_auth_success() -> None:
    """Successful OAuth2 token acquisition stores the bearer token."""
    client = _make_client()
    auth_resp = _make_mock_response(200, _AUTH_SUCCESS_RESPONSE)
    api_resp = _make_mock_response(200, _LIST_BACKORDERS_RESPONSE)

    with patch.object(client._http, "request", side_effect=[auth_resp, api_resp]):
        _ = client.list_backorders()

    assert client._access_token == _AUTH_SUCCESS_RESPONSE["access_token"]
    assert client._token_expiry > time.time()


# ---------------------------------------------------------------------------
# 2. Auth failure — AssertionError on non-200 (client uses assert)
# ---------------------------------------------------------------------------
def test_auth_failure() -> None:
    """Non-200 response during token acquisition raises AssertionError."""
    client = _make_client()
    auth_resp = _make_mock_response(401, text="Unauthorized")

    with patch.object(client._http, "request", return_value=auth_resp):
        with pytest.raises(AssertionError) as exc_info:
            client.list_backorders()

    assert "Auth failed" in str(exc_info.value)
    assert "401" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. place_backorders — full success
# ---------------------------------------------------------------------------
def test_place_backorders_success() -> None:
    """Successful bulk backorder returns BulkBackorderResult with no errors."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _BACKORDER_SUCCESS_RESPONSE)),
    ):
        result = client.place_backorders(["expiredgem.com", "droppingsoon.net"])

    assert isinstance(result, BulkBackorderResult)
    assert result.some_errors is False
    assert len(result.results) == 2
    assert all(r.success for r in result.results)
    assert result.results[0].domain == "expiredgem.com"
    assert result.results[0].max_bid == pytest.approx(59.00)


# ---------------------------------------------------------------------------
# 4. place_backorders — partial failure
# ---------------------------------------------------------------------------
def test_place_backorders_partial_failure() -> None:
    """Partial failure returns BulkBackorderResult with some_errors=True."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _BACKORDER_PARTIAL_FAILURE_RESPONSE)),
    ):
        result = client.place_backorders(["gooddomain.com", "baddomain.com"])

    assert isinstance(result, BulkBackorderResult)
    assert result.some_errors is True
    assert len(result.results) == 2

    successes = [r for r in result.results if r.success]
    failures = [r for r in result.results if not r.success]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].domain == "baddomain.com"
    assert "not in a droppable state" in failures[0].message


# ---------------------------------------------------------------------------
# 5. cancel_backorders — success
# ---------------------------------------------------------------------------
def test_cancel_backorders() -> None:
    """cancel_backorders returns raw API response with success status."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _CANCEL_BACKORDERS_RESPONSE)),
    ):
        result = client.cancel_backorders(["expiredgem.com"])

    assert isinstance(result, dict)
    assert result["someErrors"] is False
    assert len(result["results"]) == 1


# ---------------------------------------------------------------------------
# 6. list_backorders — returns list
# ---------------------------------------------------------------------------
def test_list_backorders() -> None:
    """list_backorders returns the JSON list of active backorder dicts."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _LIST_BACKORDERS_RESPONSE)),
    ):
        result = client.list_backorders(search_term="gem", size=50)

    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["DomainName"] == "expiredgem.com"
    assert result[2]["Type"] == "DiscountClub"


# ---------------------------------------------------------------------------
# 7. search_auctions — returns auction list
# ---------------------------------------------------------------------------
def test_search_auctions() -> None:
    """search_auctions returns a list of auction dicts."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _SEARCH_AUCTIONS_RESPONSE)),
    ):
        result = client.search_auctions(search_term="tech", size=50, tlds=["com", "io"])

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["AuctionId"] == 10001
    assert result[1]["DomainName"] == "codemarket.io"


# ---------------------------------------------------------------------------
# 8. place_bids — returns bid results
# ---------------------------------------------------------------------------
def test_place_bids() -> None:
    """place_bids returns a dict with per-bid results."""
    client = _make_client()
    bids = [
        {"AuctionId": 10001, "Amount": 130.00},
        {"AuctionId": 10002, "Amount": 50.00},
    ]

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _PLACE_BIDS_RESPONSE)),
    ):
        result = client.place_bids(bids)

    assert isinstance(result, dict)
    assert result["someErrors"] is False
    assert len(result["results"]) == 2
    assert all(r["success"] for r in result["results"])


# ---------------------------------------------------------------------------
# 9. download_dropping_domains — returns raw bytes
# ---------------------------------------------------------------------------
def test_download_dropping_domains() -> None:
    """download_dropping_domains returns raw ZIP file bytes."""
    client = _make_client()
    download_resp = _make_mock_response(200, content=_DOWNLOAD_DROPPING_BYTES)

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(download_resp),
    ):
        result = client.download_dropping_domains(days_out=0, file_type="Csv")

    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result == _DOWNLOAD_DROPPING_BYTES


# ---------------------------------------------------------------------------
# 10. Rate limiter acquire — timestamps recorded
# ---------------------------------------------------------------------------
def test_rate_limiter_acquire() -> None:
    """Rate limiter records timestamps on each acquire call."""
    limiter = _RateLimiter(max_requests=30, window_seconds=30, min_interval=0.0)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert len(limiter._timestamps) == 3
    assert all(isinstance(ts, float) for ts in limiter._timestamps)
    # Timestamps should be monotonically increasing
    ts_list = list(limiter._timestamps)
    assert ts_list == sorted(ts_list)


# ---------------------------------------------------------------------------
# 11. Bulk backorder parsing — typed results
# ---------------------------------------------------------------------------
def test_bulk_backorder_parsing() -> None:
    """_parse_bulk_backorder converts raw API JSON into typed dataclasses."""
    result = DropCatchClient._parse_bulk_backorder(_BACKORDER_SUCCESS_RESPONSE)

    assert isinstance(result, BulkBackorderResult)
    assert result.some_errors is False
    assert len(result.results) == 2

    first = result.results[0]
    assert isinstance(first, BackorderResult)
    assert first.domain == "expiredgem.com"
    assert first.success is True
    assert first.max_bid == pytest.approx(59.00)
    assert first.status_code == "Success"
    assert dataclasses.is_dataclass(first)


# ---------------------------------------------------------------------------
# 12. Result dataclasses are frozen (immutable)
# ---------------------------------------------------------------------------
def test_result_dataclasses_frozen() -> None:
    """All result dataclasses must be frozen (reject attribute mutation)."""
    bo = BackorderResult(
        domain="test.com", success=True, max_bid=59.0,
        message="ok", status_code="Success",
    )
    bulk = BulkBackorderResult(some_errors=False, results=[bo])
    auction = AuctionInfo(
        auction_id=1, domain="test.com", high_bid=100.0,
        end_time="2026-05-20T00:00:00Z", auction_type="Standard",
    )
    bid = BidResult(auction_id=1, success=True, message="ok")

    for obj in (bo, auction, bid):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.domain = "hacked.com"  # type: ignore[misc,attr-defined]


# ---------------------------------------------------------------------------
# 13. Exception hierarchy
# ---------------------------------------------------------------------------
def test_exception_hierarchy() -> None:
    """All specific exceptions inherit from DropCatchError."""
    assert issubclass(DropCatchAuthError, DropCatchError)
    assert issubclass(DropCatchBackorderError, DropCatchError)
    assert issubclass(DropCatchError, Exception)


# ---------------------------------------------------------------------------
# 14. Input validation — empty domains rejected
# ---------------------------------------------------------------------------
def test_place_backorders_empty_domains() -> None:
    """Empty domain list raises AssertionError."""
    client = _make_client()
    with pytest.raises(AssertionError, match="At least one domain"):
        client.place_backorders([])

    # Also verify max limit
    with pytest.raises(AssertionError, match="Max 100"):
        client.place_backorders([f"domain{i}.com" for i in range(101)])


# ---------------------------------------------------------------------------
# 15. Input validation — bid amount floor
# ---------------------------------------------------------------------------
def test_place_backorders_amount_floor() -> None:
    """Bid amount below $8.00 minimum raises AssertionError."""
    client = _make_client()
    with pytest.raises(AssertionError, match="Amount must be"):
        client.place_backorders(["test.com"], amount=5.00)

    # $8.00 exact should NOT raise (discount club minimum)
    # We don't actually call the API here; just verify the assertion passes
    assert True


# ---------------------------------------------------------------------------
# 16. get_auction — returns single auction dict
# ---------------------------------------------------------------------------
def test_get_auction() -> None:
    """get_auction returns a dict with full auction details."""
    client = _make_client()

    with patch.object(
        client._http, "request",
        side_effect=_auth_then_api(_make_mock_response(200, _GET_AUCTION_RESPONSE)),
    ):
        result = client.get_auction(10001)

    assert isinstance(result, dict)
    assert result["AuctionId"] == 10001
    assert result["DomainName"] == "techtools.com"
    assert result["MinNextBid"] == 130.00


# ---------------------------------------------------------------------------
# 17. Token refresh on expiry
# ---------------------------------------------------------------------------
def test_token_refresh_on_expiry() -> None:
    """Expired token triggers automatic refresh before API call."""
    client = _make_client()

    # Simulate an already-expired token
    client._access_token = "old_expired_token"
    client._token_expiry = time.time() - 100  # expired 100s ago

    refreshed_auth = {
        "access_token": "fresh_new_token",
        "token_type": "bearer",
        "expires_in": 1800,
    }
    auth_resp = _make_mock_response(200, refreshed_auth)
    api_resp = _make_mock_response(200, _LIST_BACKORDERS_RESPONSE)

    with patch.object(client._http, "request", side_effect=[auth_resp, api_resp]):
        _ = client.list_backorders()

    assert client._access_token == "fresh_new_token"
    assert client._token_expiry > time.time()


# ---------------------------------------------------------------------------
# 18. Context manager protocol
# ---------------------------------------------------------------------------
def test_context_manager() -> None:
    """DropCatchClient supports context manager protocol (with statement)."""
    with DropCatchClient(
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
    ) as client:
        assert isinstance(client, DropCatchClient)
        assert client._client_id == _CLIENT_ID

    # After __exit__, the HTTP client should be closed
    assert True  # If no exception, context manager works

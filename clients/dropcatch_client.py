"""DropCatch REST API client — backorder, auction, and bid management.

MAJOR FINDING: DropCatch DOES have a public REST API (v1 + v2).
Authentication is via NameBright OAuth2 (client_credentials grant).

Setup requirements:
  1. Create NameBright.com account: https://www.namebright.com/NewAccount
  2. Enable API access: https://www.namebright.com/Settings#Api
  3. Grant "Register Domains" permission
  4. Configure IP whitelist for your API account
  5. Log into DropCatch.com with NameBright credentials at least once
  6. Set DROPCATCH_CLIENT_ID and DROPCATCH_API_SECRET in .env
     Format: client_id = "accountname:appname"

API docs:
  - Swagger UI:  https://api.dropcatch.com/documentation
  - v2 spec:     https://api.dropcatch.com/documentation/v2/doc.json
  - v1 spec:     https://api.dropcatch.com/documentation/v1/doc.json
  - Examples:    https://github.com/NameBright/DropCatchBackorderExamples

Auth endpoint:
  - POST https://api.namebright.com/auth/token (30-min tokens)

API endpoints (v2):
  - PUT    /v2/backorders          — Place/update backorders (bulk)
  - DELETE /v2/backorders          — Cancel backorders (bulk)
  - GET    /v2/backorders          — List active backorders
  - GET    /v2/auctions            — Search auctions
  - GET    /v2/auctions/{id}       — Get single auction
  - GET    /v2/auctions/{id}/bids  — Get bids on auction
  - POST   /v2/bids                — Place bids (bulk)
  - GET    /v2/bids                — List your bids
  - GET    /v2/downloads/dropping/{type} — Download dropping domains CSV

Legacy endpoints (v1):
  - POST https://www.dropcatch.com/api/BackorderDomainsApi/BackOrderDomains
  - POST https://www.dropcatch.com/api/BackorderDomainsApi/CancelBackOrders

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_AUTH_URL: str = "https://api.dropcatch.com/Authorize"
_AUTH_URL_LEGACY: str = "https://api.namebright.com/auth/token"
_API_BASE_URL: str = "https://api.dropcatch.com"
_LEGACY_BASE_URL: str = "https://www.dropcatch.com"
_TIMEOUT_SECONDS: int = 30
_TOKEN_LIFETIME_SECONDS: int = 1800  # 30 minutes
_TOKEN_REFRESH_BUFFER: int = 60  # Refresh 1 min early
_STANDARD_BACKORDER_PRICE: float = 59.00
_DISCOUNT_CLUB_MIN_PRICE: float = 8.00

# NameBright rate limit: 30 requests per 30 seconds (hard limit, revokes access)
_MAX_REQUESTS_PER_WINDOW: int = 30
_WINDOW_SECONDS: int = 30
_MIN_REQUEST_INTERVAL: float = 1.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class DropCatchError(Exception):
    """Base error for DropCatch API failures."""


class DropCatchAuthError(DropCatchError):
    """Raised when authentication fails."""


class DropCatchBackorderError(DropCatchError):
    """Raised when a backorder request fails."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BackorderResult:
    """Result for a single domain backorder attempt."""
    domain: str
    success: bool
    max_bid: float
    message: str
    status_code: str


@dataclass(frozen=True)
class BulkBackorderResult:
    """Result for a bulk backorder request."""
    some_errors: bool
    results: list[BackorderResult]


@dataclass(frozen=True)
class AuctionInfo:
    """Summary of a DropCatch auction."""
    auction_id: int
    domain: str
    high_bid: float
    end_time: str
    auction_type: str


@dataclass(frozen=True)
class BidResult:
    """Result for a single bid attempt."""
    auction_id: int
    success: bool
    message: str


# ---------------------------------------------------------------------------
# Rate limiter (thread-safe, stdlib only)
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Sliding-window rate limiter enforcing both per-second and per-window caps.

    Uses a deque of timestamps to track the sliding window and a monotonic
    clock for the minimum interval between consecutive requests.
    """

    def __init__(
        self,
        max_requests: int = _MAX_REQUESTS_PER_WINDOW,
        window_seconds: int = _WINDOW_SECONDS,
        min_interval: float = _MIN_REQUEST_INTERVAL,
    ) -> None:
        assert max_requests > 0, f"max_requests must be positive, got {max_requests}"
        assert window_seconds > 0, f"window_seconds must be positive, got {window_seconds}"
        assert min_interval >= 0, f"min_interval must be non-negative, got {min_interval}"
        self._max_requests = max_requests
        self._window_seconds = float(window_seconds)
        self._min_interval = min_interval
        self._timestamps: deque[float] = deque(maxlen=max_requests)
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a request slot is available, then record the request.

        Enforces two constraints:
          1. Minimum interval since last request (_MIN_REQUEST_INTERVAL).
          2. Sliding window of max N requests per window (_MAX_REQUESTS_PER_WINDOW).
        """
        with self._lock:
            now = time.monotonic()
            self._evict_expired(now)

            # Enforce minimum interval since last request
            if self._timestamps:
                elapsed = now - self._timestamps[-1]
                if elapsed < self._min_interval:
                    wait = self._min_interval - elapsed
                    logger.debug("rate_limit_interval", wait_seconds=round(wait, 3))
                    time.sleep(wait)
                    now = time.monotonic()

            # Enforce sliding window cap
            self._evict_expired(now)
            if len(self._timestamps) >= self._max_requests:
                oldest = self._timestamps[0]
                wait = self._window_seconds - (now - oldest)
                if wait > 0:
                    logger.info(
                        "rate_limit_window",
                        wait_seconds=round(wait, 3),
                        window_size=len(self._timestamps),
                    )
                    time.sleep(wait)
                    now = time.monotonic()
                    self._evict_expired(now)

            self._timestamps.append(now)

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class DropCatchClient:
    """DropCatch REST API client with automatic token management.

    Args:
        client_id: NameBright API client ID (format: "account:app")
        client_secret: NameBright API client secret
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        assert len(client_id) > 0, "client_id must not be empty"
        assert len(client_secret) > 0, "client_secret must not be empty"
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expiry: float = 0.0
        self._http = httpx.Client(timeout=_TIMEOUT_SECONDS)
        self._rate_limiter = _RateLimiter()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> DropCatchClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ----- Rate-limited HTTP -----

    def _rate_limited_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request after acquiring a rate-limit slot.

        All API calls MUST go through this method to respect the
        NameBright hard limit of 30 requests per 30 seconds.
        """
        assert len(method) > 0, "HTTP method must not be empty"
        assert len(url) > 0, "URL must not be empty"
        self._rate_limiter.acquire()
        return self._http.request(method, url, **kwargs)

    # ----- Authentication -----

    def _ensure_token(self) -> str:
        """Get a valid bearer token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        """Request a new bearer token from DropCatch API."""
        response = self._rate_limited_request(
            "POST",
            _AUTH_URL,
            json={
                "ClientId": self._client_id,
                "ClientSecret": self._client_secret,
            },
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in (200, 201), (
            f"Auth failed: HTTP {response.status_code} — {response.text}"
        )

        data = response.json()
        # DropCatch returns "token", NameBright returns "access_token"
        token = data.get("token") or data.get("access_token")
        assert token, f"No token in auth response: {list(data.keys())}"

        self._access_token = token
        expires_in = int(data.get("expiresIn", data.get("expires_in", _TOKEN_LIFETIME_SECONDS)))
        self._token_expiry = time.time() + expires_in - _TOKEN_REFRESH_BUFFER

        logger.info("dropcatch_token_refreshed", expires_in=expires_in)
        return token

    def _auth_headers(self) -> dict[str, str]:
        """Build headers with current bearer token."""
        token = self._ensure_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ----- Backorders (v2 API) -----

    def place_backorders(
        self,
        domains: list[str],
        amount: float = _STANDARD_BACKORDER_PRICE,
        backorder_type: str = "Standard",
    ) -> BulkBackorderResult:
        """Place backorders for one or more domains.

        Args:
            domains: List of domain names to backorder.
            amount: Bid amount per domain (59.00 for standard, 8-58 for discount).
            backorder_type: "Standard" or "DiscountClub".

        Returns:
            BulkBackorderResult with per-domain results.
        """
        assert len(domains) > 0, "At least one domain required"
        assert len(domains) <= 100, f"Max 100 domains per request, got {len(domains)}"
        assert amount >= _DISCOUNT_CLUB_MIN_PRICE, (
            f"Amount must be >= ${_DISCOUNT_CLUB_MIN_PRICE}"
        )

        payload = [
            {"Domain": d, "Amount": amount, "Type": backorder_type}
            for d in domains
        ]

        response = self._rate_limited_request(
            "PUT",
            f"{_API_BASE_URL}/v2/backorders",
            headers=self._auth_headers(),
            json=payload,
        )
        assert response.status_code == 200, (
            f"Backorder failed: HTTP {response.status_code} — {response.text}"
        )

        raw_data = response.json()
        logger.debug("place_backorders_raw_response", data=str(raw_data)[:500])
        return self._parse_bulk_backorder(raw_data)

    def place_backorders_legacy(
        self,
        domains: list[str],
        routing_code: str = "standard",
    ) -> dict[str, Any]:
        """Place backorders via the legacy v1 endpoint.

        Args:
            domains: Domain names. For discount club, format as "domain.com,15".
            routing_code: "standard" or "discount".

        Returns:
            Raw API response dict.
        """
        assert len(domains) > 0, "At least one domain required"
        assert routing_code in ("standard", "discount"), (
            f"routing_code must be 'standard' or 'discount', got '{routing_code}'"
        )

        response = self._rate_limited_request(
            "POST",
            f"{_LEGACY_BASE_URL}/api/BackorderDomainsApi/BackOrderDomains",
            headers=self._auth_headers(),
            json={"domains": domains, "routingCode": routing_code},
        )
        assert response.status_code == 200, (
            f"Legacy backorder failed: HTTP {response.status_code} — {response.text}"
        )
        return response.json()

    def cancel_backorders(self, domains: list[str]) -> dict[str, Any]:
        """Cancel active backorders for the given domains.

        Returns:
            CancelBackordersResult with per-domain status.
        """
        assert len(domains) > 0, "At least one domain required"
        assert len(domains) <= 100, f"Max 100 per request, got {len(domains)}"

        response = self._rate_limited_request(
            "DELETE",
            f"{_API_BASE_URL}/v2/backorders",
            headers=self._auth_headers(),
            json=domains,
        )
        assert response.status_code == 200, (
            f"Cancel failed: HTTP {response.status_code} — {response.text}"
        )
        return response.json()

    def list_backorders(
        self,
        search_term: str | None = None,
        size: int = 50,
    ) -> list[dict[str, Any]]:
        """List active backorders, optionally filtered by search term."""
        assert 1 <= size <= 200, f"size must be 1-200, got {size}"

        params: dict[str, Any] = {"size": size}
        if search_term:
            params["searchTerm"] = search_term

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/backorders",
            headers=self._auth_headers(),
            params=params,
        )
        assert response.status_code == 200, (
            f"List backorders failed: HTTP {response.status_code} — {response.text}"
        )

        data: Any = response.json()

        # API may return a dict wrapper (e.g. {"Results": [...]}) instead of
        # a bare list.  Unwrap it so callers always get list[dict].
        if isinstance(data, dict):
            for key in ("Results", "results", "Backorders", "backorders", "items"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                # Dict has no recognisable list value — return empty list
                logger.warning(
                    "list_backorders_unexpected_dict",
                    keys=list(data.keys()),
                )
                data = []

        assert isinstance(data, list), (
            f"Expected list from list_backorders, got {type(data).__name__}"
        )
        return data

    # ----- Auctions (v2 API) -----

    def search_auctions(
        self,
        search_term: str | None = None,
        size: int = 50,
        tlds: list[str] | None = None,
        high_bid_max: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search active auctions.

        Returns:
            List of auction dicts. The API returns a wrapper dict with
            "items", "totalRecords", and "cursor" keys; this method
            unwraps it to return the items list directly.
        """
        assert 1 <= size <= 200, f"size must be 1-200, got {size}"

        params: dict[str, Any] = {"size": size, "showAllActive": True}
        if search_term:
            params["searchTerm"] = search_term
        if tlds:
            for i, tld in enumerate(tlds):
                params[f"Tlds[{i}]"] = tld
        if high_bid_max is not None:
            params["HighBid.Max"] = high_bid_max

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/auctions",
            headers=self._auth_headers(),
            params=params,
        )
        assert response.status_code == 200, (
            f"Search auctions failed: HTTP {response.status_code}"
        )

        data: Any = response.json()

        # API returns {"items": [...], "totalRecords": N, "cursor": {...}}
        # Unwrap to return the list directly, matching the type hint.
        if isinstance(data, dict):
            for key in ("items", "Items", "results", "Results", "auctions", "Auctions"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            logger.warning(
                "search_auctions_unexpected_dict",
                keys=list(data.keys()),
            )
            return []

        assert isinstance(data, list), (
            f"Expected list from search_auctions, got {type(data).__name__}"
        )
        return data

    def get_auction(self, auction_id: int) -> dict[str, Any]:
        """Get details for a specific auction."""
        assert auction_id > 0, f"Invalid auction_id: {auction_id}"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/auctions/{auction_id}",
            headers=self._auth_headers(),
        )
        assert response.status_code == 200, (
            f"Get auction failed: HTTP {response.status_code}"
        )
        return response.json()

    def get_auction_bids(
        self, auction_id: int, size: int = 50,
    ) -> list[dict[str, Any]]:
        """Get bid history for a specific auction.

        Returns:
            List of bid dicts with Alias, AccountId, Amount, IsProxy,
            IsHighBid, BidOrder, Created fields.
        """
        assert auction_id > 0, f"Invalid auction_id: {auction_id}"
        assert 1 <= size <= 200, f"size must be 1-200, got {size}"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/auctions/{auction_id}/bids",
            headers=self._auth_headers(),
            params={"size": size},
        )
        assert response.status_code == 200, (
            f"Get auction bids failed: HTTP {response.status_code}"
        )

        data: Any = response.json()
        if isinstance(data, dict):
            bids = data.get("bids") or data.get("Bids") or []
            assert isinstance(bids, list), f"Expected list, got {type(bids)}"
            return bids
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        return data

    def list_my_bids(
        self,
        size: int = 50,
        winning: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List auctions you are bidding on.

        Args:
            size: Number of results (1-200).
            winning: Filter to only winning (True) or losing (False) bids.

        Returns:
            List of bid dicts with AuctionId, Domain, IsWinning,
            HighBid, MaxBid fields.
        """
        assert 1 <= size <= 200, f"size must be 1-200, got {size}"

        params: dict[str, Any] = {"size": size}
        if winning is not None:
            params["winning"] = winning

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/bids",
            headers=self._auth_headers(),
            params=params,
        )
        assert response.status_code == 200, (
            f"List bids failed: HTTP {response.status_code}"
        )

        data: Any = response.json()
        if isinstance(data, dict):
            for key in ("items", "Items", "bids", "Bids"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return []
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        return data

    def place_bids(
        self, bids: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Place bids on one or more auctions.

        Args:
            bids: List of {"AuctionId": int, "Amount": float} dicts.

        Returns:
            BulkBidResult with per-bid status.
        """
        assert len(bids) > 0, "At least one bid required"
        assert all("AuctionId" in b and "Amount" in b for b in bids), (
            "Each bid must have 'AuctionId' and 'Amount'"
        )

        response = self._rate_limited_request(
            "POST",
            f"{_API_BASE_URL}/v2/bids",
            headers=self._auth_headers(),
            json=bids,
        )
        assert response.status_code == 200, (
            f"Place bids failed: HTTP {response.status_code}"
        )
        return response.json()

    # ----- Downloads -----

    def download_dropping_domains(
        self, days_out: int = 0, file_type: str = "Csv"
    ) -> bytes:
        """Download the dropping domains list as a ZIP file.

        Args:
            days_out: 0-4 for specific day, or 5 for AllDays.
            file_type: "Csv" or "Xlsx".

        Returns:
            Raw ZIP file bytes.
        """
        assert 0 <= days_out <= 5, f"days_out must be 0-5, got {days_out}"
        type_map = {0: "DaysOut0", 1: "DaysOut1", 2: "DaysOut2",
                    3: "DaysOut3", 4: "DaysOut4", 5: "AllDays"}
        drop_type = type_map[days_out]

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/v2/downloads/dropping/{drop_type}",
            headers=self._auth_headers(),
            params={"fileType": file_type},
        )
        assert response.status_code == 200, (
            f"Download failed: HTTP {response.status_code}"
        )
        return response.content

    # ----- Parsing helpers -----

    @staticmethod
    def _parse_bulk_backorder(data: dict[str, Any]) -> BulkBackorderResult:
        """Parse a bulk backorder API response into typed result.

        Handles TWO response formats:
          - v2 Swagger spec (live API): {"Successes": [...], "Failures": [...]}
            Successes items: {Domain, Amount, MaxBid, Type, DropDate}
            Failures items:  {Domain, Error: {ErrorCode, Description}}
          - Legacy/examples (camelCase): {"someErrors": bool, "results": [...]}
            Results items: {domainName, success, maxBid, message, statusCode}
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        results: list[BackorderResult] = []

        # --- Format 1: v2 API with Successes/Failures (any casing) ---
        successes = data.get("Successes") or data.get("successes") or []
        failures = data.get("Failures") or data.get("failures") or []

        if successes or failures:
            for s in successes:
                domain = s.get("Domain") or s.get("domain") or ""
                max_bid = float(s.get("MaxBid") or s.get("maxBid") or s.get("Amount") or s.get("amount") or 0)
                results.append(BackorderResult(
                    domain=domain,
                    success=True,
                    max_bid=max_bid,
                    message="Backorder placed successfully",
                    status_code="Success",
                ))
            for f in failures:
                domain = f.get("Domain") or f.get("domain") or ""
                error_obj = f.get("Error") or f.get("error") or {}
                err_desc = error_obj.get("Description") or error_obj.get("description") or "" if isinstance(error_obj, dict) else str(error_obj)
                err_code = error_obj.get("ErrorCode") or error_obj.get("errorCode") or "" if isinstance(error_obj, dict) else ""
                results.append(BackorderResult(
                    domain=domain,
                    success=False,
                    max_bid=0.0,
                    message=err_desc or f"Backorder failed: {err_code}" if err_code else err_desc or "Backorder failed",
                    status_code=str(err_code),
                ))
            some_errors = len(failures) > 0
        else:
            # --- Format 2: Legacy camelCase with results array ---
            for r in data.get("results", []):
                results.append(BackorderResult(
                    domain=r.get("domainName", ""),
                    success=r.get("success", False),
                    max_bid=float(r.get("maxBid", 0)),
                    message=r.get("message", ""),
                    status_code=str(r.get("statusCode", "")),
                ))
            some_errors = data.get("someErrors", False)

        return BulkBackorderResult(
            some_errors=some_errors,
            results=results,
        )

"""GoDaddy Aftermarket API client — listing search, details, and bidding.

Provides sync access to GoDaddy's Aftermarket (auction) endpoints via
httpx.Client. Thread-safe rate limiting prevents 429 responses.

Auth: GoDaddy API keys (sso-key scheme).
  - Create API key at: https://developer.godaddy.com/keys
  - Set GODADDY_API_KEY and GODADDY_API_SECRET in .env

API endpoints used:
  - GET  /v1/aftermarket/listings              — Search listings by domain
  - GET  /v1/aftermarket/listings/{listing_id}  — Get single listing details
  - POST /v1/aftermarket/listings/{listing_id}/bids — Place a bid

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
_GODADDY_API_BASE: str = "https://api.godaddy.com"
_TIMEOUT_SECONDS: int = 15
_MAX_REQUESTS_PER_MINUTE: int = 60
_WINDOW_SECONDS: int = 60
_MIN_REQUEST_INTERVAL: float = 1.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class GoDaddyAuctionError(Exception):
    """Base error for GoDaddy Aftermarket API failures."""


class GoDaddyAuthError(GoDaddyAuctionError):
    """Raised when authentication fails (401/403 on non-bid endpoints)."""


class GoDaddyRateLimitError(GoDaddyAuctionError):
    """Raised when GoDaddy returns HTTP 429 (Too Many Requests)."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ListingInfo:
    """Summary of a GoDaddy aftermarket listing."""
    listing_id: int
    domain: str
    price: float
    bid_count: int
    auction_end: str
    listing_type: str


@dataclass(frozen=True)
class BidResult:
    """Result for a single bid attempt."""
    listing_id: int
    success: bool
    status_code: int
    message: str
    api_blocked: bool


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
        max_requests: int = _MAX_REQUESTS_PER_MINUTE,
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
          2. Sliding window of max N requests per window (_MAX_REQUESTS_PER_MINUTE).
        """
        assert self._max_requests > 0, "max_requests invariant violated"
        assert self._window_seconds > 0, "window_seconds invariant violated"
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
        assert isinstance(now, float), f"now must be float, got {type(now).__name__}"
        assert now >= 0.0, f"now must be non-negative, got {now}"
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class GoDaddyAuctionClient:
    """GoDaddy Aftermarket REST API client with rate limiting.

    Uses sso-key authentication (no OAuth token refresh needed).

    Args:
        api_key: GoDaddy API key.
        api_secret: GoDaddy API secret.
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        assert len(api_key) > 0, "api_key must not be empty"
        assert len(api_secret) > 0, "api_secret must not be empty"
        self._api_key = api_key
        self._api_secret = api_secret
        self._http = httpx.Client(timeout=_TIMEOUT_SECONDS)
        self._rate_limiter = _RateLimiter()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        assert self._http is not None, "HTTP client must exist"
        assert self._rate_limiter is not None, "Rate limiter must exist"
        self._http.close()

    def __enter__(self) -> GoDaddyAuctionClient:
        assert self._http is not None, "HTTP client must exist"
        assert self._rate_limiter is not None, "Rate limiter must exist"
        return self

    def __exit__(self, *args: Any) -> None:
        assert self._http is not None, "HTTP client must exist"
        assert self._rate_limiter is not None, "Rate limiter must exist"
        self.close()

    # ----- Auth headers -----

    def _auth_headers(self) -> dict[str, str]:
        """Build headers with sso-key authorization."""
        assert len(self._api_key) > 0, "api_key must not be empty"
        assert len(self._api_secret) > 0, "api_secret must not be empty"
        return {
            "Authorization": f"sso-key {self._api_key}:{self._api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ----- Rate-limited HTTP -----

    def _rate_limited_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request after acquiring a rate-limit slot.

        All API calls MUST go through this method to respect GoDaddy's
        rate limit of 60 requests per 60 seconds.
        """
        assert len(method) > 0, "HTTP method must not be empty"
        assert len(url) > 0, "URL must not be empty"
        self._rate_limiter.acquire()
        return self._http.request(method, url, **kwargs)

    # ----- Listing search -----

    def search_listing(self, domain: str) -> ListingInfo | None:
        """Search for a domain in GoDaddy aftermarket listings.

        Args:
            domain: The domain name to search for.

        Returns:
            ListingInfo if found, None if 404 or empty result.
        """
        assert isinstance(domain, str), f"domain must be str, got {type(domain).__name__}"
        assert len(domain) > 0, "domain must not be empty"

        response = self._rate_limited_request(
            "GET",
            f"{_GODADDY_API_BASE}/v1/aftermarket/listings",
            headers=self._auth_headers(),
            params={"domain": domain},
        )

        if response.status_code == 404:
            logger.debug("search_listing_not_found", domain=domain)
            return None

        if response.status_code in (401, 403):
            raise GoDaddyAuthError(
                f"Auth failed searching listings: HTTP {response.status_code} — {response.text}"
            )

        if response.status_code == 429:
            raise GoDaddyRateLimitError(
                f"Rate limited searching listings: {response.text}"
            )

        if response.status_code != 200:
            raise GoDaddyAuctionError(
                f"Search listing failed: HTTP {response.status_code} — {response.text}"
            )

        data: Any = response.json()
        return self._parse_listing_response(data, domain)

    # ----- Listing details -----

    def get_listing_details(self, listing_id: int) -> ListingInfo:
        """Get detailed info for a specific aftermarket listing.

        Args:
            listing_id: The GoDaddy listing ID.

        Returns:
            ListingInfo with full listing data.

        Raises:
            GoDaddyAuctionError: On any non-200 response.
            GoDaddyAuthError: On 401/403.
            GoDaddyRateLimitError: On 429.
        """
        assert isinstance(listing_id, int), f"listing_id must be int, got {type(listing_id).__name__}"
        assert listing_id > 0, f"listing_id must be positive, got {listing_id}"

        response = self._rate_limited_request(
            "GET",
            f"{_GODADDY_API_BASE}/v1/aftermarket/listings/{listing_id}",
            headers=self._auth_headers(),
        )

        if response.status_code in (401, 403):
            raise GoDaddyAuthError(
                f"Auth failed getting listing {listing_id}: HTTP {response.status_code}"
            )

        if response.status_code == 429:
            raise GoDaddyRateLimitError(
                f"Rate limited getting listing {listing_id}: {response.text}"
            )

        if response.status_code != 200:
            raise GoDaddyAuctionError(
                f"Get listing failed: HTTP {response.status_code} — {response.text}"
            )

        data: Any = response.json()
        listing = self._parse_single_listing(data)
        assert listing is not None, f"Failed to parse listing data for ID {listing_id}"
        return listing

    # ----- Place bid -----

    def place_bid(self, listing_id: int, amount: float) -> BidResult:
        """Place a bid on a GoDaddy aftermarket listing.

        Args:
            listing_id: The listing to bid on.
            amount: Bid amount in USD.

        Returns:
            BidResult. On 403 with USER_NOT_ALLOWED, returns api_blocked=True
            instead of raising.

        Raises:
            GoDaddyRateLimitError: On 429.
            GoDaddyAuctionError: On other non-success responses.
        """
        assert isinstance(listing_id, int) and listing_id > 0, (
            f"listing_id must be positive int, got {listing_id}"
        )
        assert isinstance(amount, (int, float)) and amount > 0, (
            f"amount must be positive, got {amount}"
        )

        response = self._rate_limited_request(
            "POST",
            f"{_GODADDY_API_BASE}/v1/aftermarket/listings/{listing_id}/bids",
            headers=self._auth_headers(),
            json={"amount": amount},
        )

        logger.info(
            "godaddy_place_bid",
            listing_id=listing_id,
            amount=amount,
            status_code=response.status_code,
        )

        return self._handle_bid_response(response, listing_id)

    # ----- Test API access -----

    def test_api_access(self) -> bool:
        """Test whether the API credentials have valid access.

        Tries a dummy listing search. Returns True if 200, False if 401/403.

        Returns:
            True if API access works, False if auth is rejected.
        """
        assert len(self._api_key) > 0, "api_key must not be empty for access test"
        assert len(self._api_secret) > 0, "api_secret must not be empty for access test"

        try:
            response = self._rate_limited_request(
                "GET",
                f"{_GODADDY_API_BASE}/v1/aftermarket/listings",
                headers=self._auth_headers(),
                params={"domain": "example.com"},
            )
        except httpx.HTTPError as exc:
            logger.warning("godaddy_access_test_failed", error=str(exc))
            return False

        is_ok = response.status_code == 200
        logger.info(
            "godaddy_access_test",
            status_code=response.status_code,
            success=is_ok,
        )
        return is_ok

    # ----- Parsing helpers -----

    @staticmethod
    def _parse_listing_response(data: Any, domain: str) -> ListingInfo | None:
        """Parse a search listing response into ListingInfo.

        Handles both list and dict response formats from GoDaddy's
        inconsistent API.

        Args:
            data: Raw JSON response (could be list or dict).
            domain: The domain that was searched for.

        Returns:
            ListingInfo if a matching listing is found, None otherwise.
        """
        assert data is not None, "Response data must not be None"
        assert isinstance(domain, str), f"domain must be str, got {type(domain).__name__}"

        # GoDaddy may return a list of listings or a single dict
        listings: list[dict[str, Any]] = []

        if isinstance(data, list):
            listings = data
        elif isinstance(data, dict):
            # Could be a single listing or a wrapper with a results key
            for key in ("listings", "results", "items", "Listings", "Results"):
                if key in data and isinstance(data[key], list):
                    listings = data[key]
                    break
            else:
                # Treat the dict itself as a single listing
                listings = [data]
        else:
            logger.warning("search_listing_unexpected_type", data_type=type(data).__name__)
            return None

        if len(listings) == 0:
            return None

        # Return the first matching listing
        item = listings[0]
        return GoDaddyAuctionClient._parse_single_listing(item)

    @staticmethod
    def _extract_field(item: dict[str, Any], keys: tuple[str, ...], default: Any) -> Any:
        """Extract a value from a dict trying multiple key names.

        Args:
            item: Source dictionary.
            keys: Key names to try in order.
            default: Fallback if no key matches.

        Returns:
            First truthy value found, or default.
        """
        assert isinstance(item, dict), f"item must be dict, got {type(item).__name__}"
        assert len(keys) > 0, "keys tuple must not be empty"
        for key in keys:
            val = item.get(key)
            if val is not None and val != "" and val != 0:
                return val
        return default

    @staticmethod
    def _parse_single_listing(item: dict[str, Any]) -> ListingInfo | None:
        """Parse a single listing dict into a ListingInfo dataclass.

        Handles multiple field-naming conventions (camelCase, PascalCase,
        snake_case) since GoDaddy responses vary by endpoint version.

        Args:
            item: A single listing dict from the API.

        Returns:
            ListingInfo if parseable, None if critical fields are missing.
        """
        assert isinstance(item, dict), f"item must be dict, got {type(item).__name__}"
        assert len(item) > 0, "listing item must not be empty"

        _ef = GoDaddyAuctionClient._extract_field
        listing_id = _ef(item, ("listingId", "ListingId", "listing_id", "auctionId", "id"), 0)
        domain = _ef(item, ("domain", "Domain", "domainName", "DomainName"), "")
        price = float(_ef(item, ("price", "Price", "currentPrice", "CurrentPrice", "bidAmount"), 0.0))
        bid_count = int(_ef(item, ("bidCount", "BidCount", "bid_count", "numberOfBids"), 0))
        auction_end = str(_ef(item, ("auctionEndTime", "AuctionEndTime", "auction_end", "endTime", "expiresAt"), ""))
        listing_type = str(_ef(item, ("listingType", "ListingType", "listing_type", "type", "Type"), "unknown"))

        if not listing_id and not domain:
            logger.warning("parse_listing_no_id_or_domain", keys=list(item.keys()))
            return None

        return ListingInfo(
            listing_id=int(listing_id),
            domain=str(domain),
            price=price,
            bid_count=bid_count,
            auction_end=auction_end,
            listing_type=listing_type,
        )

    @staticmethod
    def _handle_bid_response(response: httpx.Response, listing_id: int) -> BidResult:
        """Parse a bid placement response into BidResult.

        403 with USER_NOT_ALLOWED returns api_blocked=True (no raise).
        429 raises GoDaddyRateLimitError. Other errors raise GoDaddyAuctionError.
        """
        assert isinstance(response, httpx.Response), "response must be httpx.Response"
        assert isinstance(listing_id, int) and listing_id > 0, (
            f"listing_id must be positive int, got {listing_id}"
        )

        status = response.status_code
        body_text = response.text

        if status == 429:
            raise GoDaddyRateLimitError(f"Rate limited on listing {listing_id}: {body_text}")

        if status == 403:
            is_blocked = "USER_NOT_ALLOWED" in body_text.upper()
            logger.warning("godaddy_bid_forbidden", listing_id=listing_id, api_blocked=is_blocked)
            return BidResult(
                listing_id=listing_id, success=False, status_code=status,
                message=body_text[:500], api_blocked=is_blocked,
            )

        if status == 401:
            raise GoDaddyAuthError(f"Auth failed on listing {listing_id}: {body_text}")

        if status in (200, 201):
            logger.info("godaddy_bid_success", listing_id=listing_id)
            return BidResult(
                listing_id=listing_id, success=True, status_code=status,
                message="Bid placed successfully", api_blocked=False,
            )

        raise GoDaddyAuctionError(f"Bid failed on listing {listing_id}: HTTP {status} — {body_text}")

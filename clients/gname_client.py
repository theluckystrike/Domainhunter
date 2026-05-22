"""Gname REST API client — backorder, auction, and dropcatch management.

Gname (gname.com) has 500+ ICANN registrar slots, second only to DropCatch.
Adding Gname to the stacked backorder increases catch probability from ~55%
(DropCatch alone) to ~65-70% (DropCatch + Dynadot + Gname).

Authentication: MD5-signed requests (appid + appkey + gntime → gntoken).
  1. Create account at gname.com
  2. Upgrade to Reseller account
  3. Navigate to Platform → User Center → Reseller → API Settings
  4. Copy APPID and APPKEY
  5. Set GNAME_APP_ID and GNAME_APP_KEY in .env

API base URL: https://www.gname.com
API docs: https://www.gname.com/domain/api

Key backorder endpoints:
  - POST /api/backorder/channel   — List available channels + pricing
  - POST /api/backorder/add       — Place single backorder
  - POST /api/backorder/bulk      — Place bulk backorders (max 100)
  - POST /api/backorder/list      — List backorders with status filtering
  - POST /api/backorder/info      — Get backorder details by domain
  - POST /api/backorder/budget    — Set budget for a backorder
  - POST /api/dropcatch/list      — Search dropping/expired domains
  - POST /api/user/balance        — Check account balance

Signature method:
  1. Sort all params by key (ASCII dict order), URL-encode values
  2. Concatenate as key1=value1&key2=value2...
  3. Append APPKEY to the end (no & separator — just concatenation)
  4. MD5 hash the string, uppercase the hex digest → gntoken

Channel pricing (as of 2026-05):
  Ch 1:  $65.00 (deposit $8.00, 12 TLDs, highest catch rate)
  Ch 10: $43.00 (deposit $5.00, 11 TLDs)
  Ch 2:  $26.00 (deposit $3.00, 11 TLDs)
  Ch 3:  $16.00 (deposit $2.00, 11 TLDs)
  Ch 4:  $15.00 (deposit $2.00, 8 TLDs)
  Ch 5:  $13.00 (deposit $2.00, 7 TLDs)
  Ch 6:  $11.50 (deposit $1.00, 7 TLDs)
  Ch 8:  $9.50  (deposit $1.00, 7 TLDs)
  Ch 9:  $6.00  (deposit $1.00, 3 TLDs)

IMPORTANT: Backorders cannot be cancelled once placed.
Deposits are frozen during the backorder and refunded if unsuccessful.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import hashlib
import threading
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_API_BASE_URL: str = "https://www.gname.com"
_TIMEOUT_SECONDS: int = 30
_MAX_DOMAINS_PER_BULK: int = 100

# Gname does not publish explicit rate limits, but we enforce conservative
# limits to avoid triggering IP bans.  60 requests per 60 seconds.
_MAX_REQUESTS_PER_WINDOW: int = 60
_WINDOW_SECONDS: int = 60
_MIN_REQUEST_INTERVAL: float = 1.0

# Channel IDs and their costs (USD) for .com domains
_DEFAULT_CHANNEL: int = 2  # $26.00, good balance of cost/catch rate

# Backorder status codes from the API
_STATUS_IN_BACKORDER: int = 0
_STATUS_DIRECTLY_WON: int = 1
_STATUS_AUCTION_WON: int = 2
_STATUS_IN_AUCTION: int = 3
_STATUS_OTHERS_WON: int = 4
_STATUS_AUCTION_LOST: int = 5
_STATUS_REDEEMED: int = 6
_STATUS_DROPCATCH_LOST: int = 7


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GnameDropDomain:
    """A dropping domain from Gname dropcatch search with authority metrics."""
    domain: str
    da: int
    pa: int
    tf: int
    cf: int
    bl: int
    rd: int
    drop_date: str = ""

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) > 0, (
            "domain must be non-empty string"
        )
        assert self.da >= 0, f"da must be >= 0, got: {self.da}"
        assert self.tf >= 0, f"tf must be >= 0, got: {self.tf}"


class GnameError(Exception):
    """Base error for Gname API failures."""


class GnameAuthError(GnameError):
    """Raised when authentication or signature verification fails."""


class GnameBackorderError(GnameError):
    """Raised when a backorder request fails."""


# ---------------------------------------------------------------------------
# Result dataclasses (frozen — immutable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BackorderResult:
    """Result of a single domain backorder attempt."""
    domain: str
    success: bool
    frozen_amount: str
    message: str


@dataclass(frozen=True)
class BulkBackorderResult:
    """Result of a bulk backorder request."""
    success_count: int
    error_count: int
    successes: list[BackorderResult]
    errors: list[BackorderResult]


@dataclass(frozen=True)
class BackorderInfo:
    """Detailed backorder information for a domain."""
    backorder_id: str
    domain: str
    status: int
    status_label: str
    channel: str
    amount: str
    frozen_amount: str
    backorder_time: str
    deletion_date: str


@dataclass(frozen=True)
class ChannelInfo:
    """Information about a backorder channel."""
    channel_id: int
    name: str
    price: str
    deposit: str
    tld_count: int
    tlds: tuple[str, ...]
    status: int
    channel_type: int


@dataclass(frozen=True)
class BalanceInfo:
    """Account balance information."""
    total_balance: str
    available_balance: str
    frozen_amount: str
    recharge_amount: str
    consumption_amount: str


# ---------------------------------------------------------------------------
# Rate limiter (thread-safe, stdlib only)
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Sliding-window rate limiter enforcing both per-second and per-window caps."""

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
        """Block until a request slot is available, then record the request."""
        with self._lock:
            now = time.monotonic()
            self._evict_expired(now)

            if self._timestamps:
                elapsed = now - self._timestamps[-1]
                if elapsed < self._min_interval:
                    wait = self._min_interval - elapsed
                    logger.debug("gname_rate_limit_interval", wait_seconds=round(wait, 3))
                    time.sleep(wait)
                    now = time.monotonic()

            self._evict_expired(now)
            if len(self._timestamps) >= self._max_requests:
                oldest = self._timestamps[0]
                wait = self._window_seconds - (now - oldest)
                if wait > 0:
                    logger.info(
                        "gname_rate_limit_window",
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
# Signature generation
# ---------------------------------------------------------------------------
def _generate_signature(params: dict[str, str], app_key: str) -> str:
    """Generate MD5 signature for Gname API request.

    Steps:
      1. Sort params by key (ASCII dictionary order)
      2. Build URL-encoded key=value pairs joined by &
      3. Append app_key directly (no & separator)
      4. MD5 hash, uppercase hex digest

    Returns:
        Uppercase MD5 hex digest string (32 chars).
    """
    assert isinstance(params, dict), "params must be a dict"
    assert len(app_key) > 0, "app_key must not be empty"

    sorted_items = sorted(params.items(), key=lambda kv: kv[0])
    parts: list[str] = []
    for key, value in sorted_items:
        encoded_value = urllib.parse.quote(str(value), safe="")
        parts.append(f"{key}={encoded_value}")

    string_a = "&".join(parts)
    string_sign_temp = string_a + app_key

    md5_hash = hashlib.md5(string_sign_temp.encode("utf-8")).hexdigest()
    assert len(md5_hash) == 32, f"MD5 hash has wrong length: {len(md5_hash)}"
    return md5_hash.upper()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class GnameClient:
    """Gname REST API client with MD5 signature authentication.

    Args:
        app_id: Gname API application ID (from Reseller API Settings).
        app_key: Gname API application key (secret, used for signing).
    """

    def __init__(self, app_id: str, app_key: str) -> None:
        assert len(app_id) > 0, "app_id must not be empty"
        assert len(app_key) > 0, "app_key must not be empty"
        self._app_id = app_id
        self._app_key = app_key
        self._http = httpx.Client(timeout=_TIMEOUT_SECONDS)
        self._rate_limiter = _RateLimiter()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> GnameClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ----- Internal helpers -----

    def _build_params(self, **kwargs: Any) -> dict[str, str]:
        """Build request params with appid, gntime, and gntoken."""
        assert self._app_id, "app_id must be set"
        assert self._app_key, "app_key must be set"

        params: dict[str, str] = {
            "appid": self._app_id,
            "gntime": str(int(time.time())),
        }
        for key, value in kwargs.items():
            if value is not None:
                params[key] = str(value)

        gntoken = _generate_signature(params, self._app_key)
        params["gntoken"] = gntoken
        return params

    def _rate_limited_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request after acquiring a rate-limit slot."""
        assert len(method) > 0, "HTTP method must not be empty"
        assert len(url) > 0, "URL must not be empty"
        self._rate_limiter.acquire()
        return self._http.request(method, url, **kwargs)

    def _post_api(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a POST request to a Gname API endpoint.

        Args:
            endpoint: API path (e.g. '/api/backorder/add').
            **kwargs: Additional parameters to include in the request.

        Returns:
            Parsed JSON response dict.

        Raises:
            GnameAuthError: If signature verification fails.
            GnameError: If the API returns an error.
        """
        assert endpoint.startswith("/"), f"endpoint must start with /, got {endpoint!r}"
        assert len(endpoint) > 1, "endpoint must not be just /"

        params = self._build_params(**kwargs)
        url = f"{_API_BASE_URL}{endpoint}"

        response = self._rate_limited_request("POST", url, data=params)
        assert response.status_code == 200, (
            f"Gname API HTTP {response.status_code}: {response.text[:300]}"
        )

        data: dict[str, Any] = response.json()
        assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"

        code = data.get("code", -1)
        if code == -1:
            msg = data.get("msg", "Unknown error")
            if "verification error" in str(msg).lower():
                raise GnameAuthError(f"Gname signature verification failed: {msg}")
            raise GnameError(f"Gname API error: {msg}")

        return data

    # ----- Backorder operations -----

    def place_backorder(
        self,
        domain: str,
        channel: int = _DEFAULT_CHANNEL,
        budget: float | None = None,
        remark: str = "",
    ) -> BackorderResult:
        """Place a backorder on a single domain.

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').
            channel: Channel ID (1-10, default 2 = $26.00).
            budget: Maximum budget amount (optional).
            remark: Optional note/comment.

        Returns:
            BackorderResult with success status and frozen deposit amount.
        """
        assert isinstance(domain, str) and "." in domain, "valid domain required"
        assert isinstance(channel, int) and channel > 0, f"channel must be positive int, got {channel}"

        extra_params: dict[str, Any] = {"ym": domain, "td": channel}
        if budget is not None:
            assert budget > 0, f"budget must be positive, got {budget}"
            extra_params["qian"] = budget
        if remark:
            extra_params["bz"] = remark

        try:
            data = self._post_api("/api/backorder/add", **extra_params)
            frozen = str(data.get("data", "0"))
            return BackorderResult(
                domain=domain,
                success=True,
                frozen_amount=frozen,
                message=data.get("msg", "backorder success"),
            )
        except GnameError as exc:
            return BackorderResult(
                domain=domain,
                success=False,
                frozen_amount="0",
                message=str(exc),
            )

    def place_backorders_bulk(
        self,
        domains: list[str],
        channel: int = _DEFAULT_CHANNEL,
    ) -> BulkBackorderResult:
        """Place backorders for multiple domains (max 100 per call).

        Args:
            domains: List of FQDNs to backorder.
            channel: Channel ID for all domains.

        Returns:
            BulkBackorderResult with per-domain success/failure.
        """
        assert len(domains) > 0, "At least one domain required"
        assert len(domains) <= _MAX_DOMAINS_PER_BULK, (
            f"Max {_MAX_DOMAINS_PER_BULK} domains per request, got {len(domains)}"
        )
        assert all("." in d for d in domains), "All entries must be valid domains"

        ym_str = "\n".join(domains)
        try:
            data = self._post_api("/api/backorder/bulk", ym=ym_str, td=channel)
        except GnameError as exc:
            return BulkBackorderResult(
                success_count=0,
                error_count=len(domains),
                successes=[],
                errors=[
                    BackorderResult(domain=d, success=False, frozen_amount="0", message=str(exc))
                    for d in domains
                ],
            )

        return self._parse_bulk_response(data, domains)

    def check_backorder_status(self, domain: str) -> BackorderInfo:
        """Get the status and details of a backorder for a domain.

        Args:
            domain: FQDN to check.

        Returns:
            BackorderInfo with current status.
        """
        assert isinstance(domain, str) and "." in domain, "valid domain required"

        data = self._post_api("/api/backorder/info", ym=domain)
        info = data.get("data", {})
        assert isinstance(info, dict), f"Expected dict in data field, got {type(info).__name__}"

        return BackorderInfo(
            backorder_id=str(info.get("id", "")),
            domain=str(info.get("ym", domain)),
            status=int(info.get("zt", -1)),
            status_label=str(info.get("ztstr", "unknown")),
            channel=str(info.get("td", "")),
            amount=str(info.get("qian", "0")),
            frozen_amount=str(info.get("dqian", "0")),
            backorder_time=str(info.get("sj", "")),
            deletion_date=str(info.get("scsj", "")),
        )

    def list_backorders(
        self,
        status: int | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List backorders with optional status filtering.

        Status codes:
          0 = in backorder, 1 = directly won, 2 = auction won,
          3 = in auction, 4 = others won, 5 = auction lost,
          6 = redeemed, 7 = dropcatch lost

        Args:
            status: Filter by backorder status (optional).
            page: Page number (default 1).
            limit: Items per page (default 50, max 2000).

        Returns:
            List of backorder record dicts.
        """
        assert isinstance(page, int) and page >= 1, f"page must be >= 1, got {page}"
        assert isinstance(limit, int) and 1 <= limit <= 2000, f"limit must be 1-2000, got {limit}"

        extra: dict[str, Any] = {"page": page, "limit": limit}
        if status is not None:
            assert 0 <= status <= 7, f"status must be 0-7, got {status}"
            extra["ydzt"] = status

        data = self._post_api("/api/backorder/list", **extra)
        result = data.get("data", [])
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("list", result.get("data", []))
        return []

    def get_channels(self) -> list[ChannelInfo]:
        """Retrieve available backorder channels with pricing.

        Returns:
            List of ChannelInfo with pricing and TLD support.
        """
        data = self._post_api("/api/backorder/channel")
        raw_channels = data.get("data", [])
        assert isinstance(raw_channels, list), "channels data must be a list"

        channels: list[ChannelInfo] = []
        for idx, ch in enumerate(raw_channels):
            if idx >= 50:  # bounded loop
                break
            if not isinstance(ch, dict):
                continue
            tlds_raw = ch.get("tlds", [])
            tlds = tuple(str(t) for t in tlds_raw) if isinstance(tlds_raw, list) else ()
            channels.append(ChannelInfo(
                channel_id=int(ch.get("id", ch.get("channel_id", 0))),
                name=str(ch.get("name", f"Channel {ch.get('id', '?')}")),
                price=str(ch.get("price", "0")),
                deposit=str(ch.get("deposit", ch.get("dqian", "0"))),
                tld_count=len(tlds),
                tlds=tlds,
                status=int(ch.get("status", 0)),
                channel_type=int(ch.get("channel_type", 0)),
            ))
        return channels

    def get_balance(self) -> BalanceInfo:
        """Check account balance.

        Returns:
            BalanceInfo with total, available, frozen, recharge, consumption amounts.
        """
        data = self._post_api("/api/user/balance")
        info = data.get("data", {})
        assert isinstance(info, dict), f"Expected dict in data, got {type(info).__name__}"

        return BalanceInfo(
            total_balance=str(info.get("zqian", "0")),
            available_balance=str(info.get("kqian", "0")),
            frozen_amount=str(info.get("dqian", "0")),
            recharge_amount=str(info.get("czqian", "0")),
            consumption_amount=str(info.get("xfqian", "0")),
        )

    # ----- Dropcatch search -----

    def search_dropping_domains(
        self,
        *,
        tf_min: int | None = None,
        da_min: int | None = None,
        rd_min: int | None = None,
        tld: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[GnameDropDomain]:
        """Search dropping/expired domains with authority filters.

        Uses POST /api/dropcatch/list which returns native DA/PA/TF/CF/BL/RD.

        Args:
            tf_min: Minimum Trust Flow filter.
            da_min: Minimum Domain Authority filter.
            rd_min: Minimum Referring Domains filter.
            tld: TLD filter (e.g. 'com').
            page: Page number (default 1).
            limit: Items per page (default 50, max 2000).

        Returns:
            List of GnameDropDomain with authority metrics.
        """
        assert isinstance(page, int) and page >= 1, f"page must be >= 1, got {page}"
        assert isinstance(limit, int) and 1 <= limit <= 2000, (
            f"limit must be 1-2000, got {limit}"
        )

        extra: dict[str, Any] = {"page": page, "limit": limit}
        if tf_min is not None:
            extra["tf_min"] = tf_min
        if da_min is not None:
            extra["da_min"] = da_min
        if rd_min is not None:
            extra["rd_min"] = rd_min
        if tld is not None:
            extra["tld"] = tld

        data = self._post_api("/api/dropcatch/list", **extra)
        raw_list = data.get("data", [])
        if isinstance(raw_list, dict):
            raw_list = raw_list.get("list", raw_list.get("data", []))
        if not isinstance(raw_list, list):
            raw_list = []

        results: list[GnameDropDomain] = []
        for idx, item in enumerate(raw_list):
            if idx >= 2000:  # bounded loop
                break
            if not isinstance(item, dict):
                continue
            results.append(GnameDropDomain(
                domain=str(item.get("ym", item.get("domain", ""))),
                da=int(item.get("da", 0)),
                pa=int(item.get("pa", 0)),
                tf=int(item.get("tf", 0)),
                cf=int(item.get("cf", 0)),
                bl=int(item.get("bl", 0)),
                rd=int(item.get("rd", 0)),
                drop_date=str(item.get("scsj", item.get("drop_date", ""))),
            ))

        assert isinstance(results, list), "results must be a list"
        logger.info("gname_dropcatch_search", count=len(results))
        return results

    # ----- Parsing helpers -----

    @staticmethod
    def _parse_bulk_response(
        data: dict[str, Any],
        domains: list[str],
    ) -> BulkBackorderResult:
        """Parse a bulk backorder API response into typed result.

        Response format:
          {
            "code": 1,
            "data": {
              "oksl": 3,
              "errsl": 1,
              "ok": [{"ym": "...", "qian": "3.00", ...}],
              "err": [{"ym": "...", "msg": "...", ...}]
            }
          }
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert isinstance(domains, list), "domains must be a list"

        result_data = data.get("data", {})
        if not isinstance(result_data, dict):
            result_data = {}

        ok_count = int(result_data.get("oksl", 0))
        err_count = int(result_data.get("errsl", 0))

        successes: list[BackorderResult] = []
        for item in result_data.get("ok", []):
            if not isinstance(item, dict):
                continue
            successes.append(BackorderResult(
                domain=str(item.get("ym", "")),
                success=True,
                frozen_amount=str(item.get("qian", item.get("dqian", "0"))),
                message="backorder success",
            ))

        errors: list[BackorderResult] = []
        for item in result_data.get("err", []):
            if not isinstance(item, dict):
                continue
            errors.append(BackorderResult(
                domain=str(item.get("ym", "")),
                success=False,
                frozen_amount="0",
                message=str(item.get("msg", item.get("error", "unknown error"))),
            ))

        return BulkBackorderResult(
            success_count=ok_count,
            error_count=err_count,
            successes=successes,
            errors=errors,
        )

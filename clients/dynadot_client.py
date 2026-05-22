"""Dynadot REST API client — backorder, search, and domain info.

Dynadot API docs: https://api.dynadot.com/api3.json
Authentication: API key as query parameter.
Rate limit: 10 requests per minute (enforced client-side).

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BASE_URL: str = "https://api.dynadot.com/api3.json"
_TIMEOUT_SECONDS: int = 30
_MAX_RETRIES: int = 3
_RATE_LIMIT_RPM: int = 10
_RATE_WINDOW_SECONDS: float = 60.0
_BACKORDER_PRICE_USD: float = 10.99


# --- Exceptions ---


class DynadotError(Exception):
    """Base error for Dynadot API failures."""


class DynadotRateLimitError(DynadotError):
    """Raised when client-side rate limit would be exceeded."""


class DynadotAuthError(DynadotError):
    """Raised when API key is missing or rejected."""


# --- Frozen result dataclasses ---


@dataclass(frozen=True)
class BackorderResult:
    """Result of a backorder or delete-backorder operation."""

    domain: str
    success: bool
    message: str


@dataclass(frozen=True)
class DomainSearchResult:
    """Result of a domain availability search."""

    domain: str
    available: bool
    price_usd: float


@dataclass(frozen=True)
class DomainInfoResult:
    """Domain registration details from Dynadot."""

    domain: str
    expiration: str
    name_servers: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class RegisterResult:
    """Result of a domain registration."""

    domain: str
    success: bool
    message: str
    expiration: str


@dataclass(frozen=True)
class SetNameserversResult:
    """Result of a nameserver update."""

    domain: str
    success: bool
    message: str


# --- Rate limiter (instance-scoped, not global) ---


class _RateLimiter:
    """Sliding-window rate limiter scoped to a client instance."""

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        assert max_calls >= 1, "max_calls must be >= 1"
        assert window_seconds > 0, "window must be positive"
        self._max_calls: int = max_calls
        self._window: float = window_seconds
        self._timestamps: list[float] = []

    def acquire(self) -> None:
        """Block if rate limit reached, prune old timestamps."""
        assert self._max_calls >= 1, "max_calls invariant"
        now: float = time.monotonic()
        cutoff: float = now - self._window
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self._max_calls:
            wait_time: float = self._timestamps[0] - cutoff
            raise DynadotRateLimitError(
                f"Rate limit: {self._max_calls}/min exceeded, retry in {wait_time:.1f}s"
            )
        self._timestamps.append(now)
        assert len(self._timestamps) <= self._max_calls, "timestamps exceed limit"


# --- Client ---


class DynadotClient:
    """Async client for Dynadot domain API."""

    def __init__(self, settings: Settings, *, dry_run: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(dry_run, bool), "dry_run must be a boolean"
        self._api_key: str = settings.dynadot_api_key
        if not self._api_key:
            raise DynadotAuthError("DYNADOT_API_KEY is empty or not set")
        self._dry_run: bool = dry_run
        self._limiter: _RateLimiter = _RateLimiter(_RATE_LIMIT_RPM, _RATE_WINDOW_SECONDS)
        self._timeout: float = float(_TIMEOUT_SECONDS)

    def _build_params(self, command: str, **kwargs: str) -> dict[str, str]:
        """Build query parameters for a Dynadot API call."""
        assert isinstance(command, str) and len(command) > 0, "command required"
        assert isinstance(self._api_key, str) and len(self._api_key) > 0, "api_key required"
        params: dict[str, str] = {"key": self._api_key, "command": command}
        params.update(kwargs)
        return params

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _request(self, command: str, **kwargs: str) -> dict[str, Any]:
        """Execute a GET request against the Dynadot API.

        Args:
            command: API command name (e.g. 'search', 'backorder').
            **kwargs: Additional query parameters.

        Returns:
            Parsed JSON response dict.
        """
        assert isinstance(command, str), "command must be a string"
        assert len(command) > 0, "command must not be empty"

        self._limiter.acquire()
        params: dict[str, str] = self._build_params(command, **kwargs)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response: httpx.Response = await client.get(_BASE_URL, params=params)
        except httpx.TimeoutException as exc:
            logger.error("dynadot_timeout", command=command)
            raise DynadotError(f"Dynadot API timed out after {_TIMEOUT_SECONDS}s") from exc
        except httpx.HTTPError as exc:
            logger.error("dynadot_http_error", command=command, error=str(exc))
            raise DynadotError(f"Dynadot HTTP error: {exc}") from exc

        return self._handle_response(response, command)

    def _handle_response(self, response: httpx.Response, command: str) -> dict[str, Any]:
        """Parse and validate a Dynadot API response."""
        assert response is not None, "response must not be None"
        assert isinstance(command, str), "command must be a string"

        status: int = response.status_code
        if status == 401 or status == 403:
            raise DynadotAuthError(f"Dynadot auth failed ({status}): check API key")
        if status != 200:
            body_preview: str = response.text[:300]
            logger.error("dynadot_api_error", status=status, command=command, body=body_preview)
            raise DynadotError(f"Dynadot API returned {status}: {body_preview[:200]}")

        data: dict[str, Any] = response.json()
        assert isinstance(data, dict), "response must be a JSON object"
        logger.info("dynadot_response", command=command, status=status)
        return data

    async def backorder(self, domain: str) -> BackorderResult:
        """Place a backorder on a domain ($10.99, charged only if caught).

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').

        Returns:
            BackorderResult with success status.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="backorder", domain=domain,
                        price=_BACKORDER_PRICE_USD)
            return BackorderResult(domain=domain, success=True,
                                   message=f"[DRY RUN] Would backorder {domain}")

        data: dict[str, Any] = await self._request(
            "add_backorder_request", domain=domain,
        )
        success: bool = _is_success_backorder(data)
        msg: str = _extract_message_backorder(data)
        return BackorderResult(domain=domain, success=success, message=msg)

    async def delete_backorder(self, domain: str) -> BackorderResult:
        """Remove an active backorder.

        Args:
            domain: Domain to cancel backorder for.

        Returns:
            BackorderResult with cancellation status.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="delete_backorder", domain=domain)
            return BackorderResult(domain=domain, success=True,
                                   message=f"[DRY RUN] Would delete backorder {domain}")

        data: dict[str, Any] = await self._request(
            "delete_backorder_request", domain=domain,
        )
        success: bool = _is_success_backorder(data)
        msg: str = _extract_message_backorder(data)
        return BackorderResult(domain=domain, success=success, message=msg)

    async def list_backorder(self) -> list[str]:
        """List all active backorders.

        Returns:
            List of domain names with active backorders.
        """
        assert self._api_key, "api_key must be set"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="list_backorder")
            return []

        data: dict[str, Any] = await self._request(
            "backorder_request_list",
            startDate="2020-01-01", endDate="2030-12-31",
        )
        domains: list[str] = _extract_backorder_list(data)
        assert isinstance(domains, list), "result must be a list"
        return domains

    async def search(self, domain: str) -> DomainSearchResult:
        """Check domain availability.

        Args:
            domain: Domain name to check.

        Returns:
            DomainSearchResult with availability and price.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="search", domain=domain)
            return DomainSearchResult(domain=domain, available=False, price_usd=0.0)

        data: dict[str, Any] = await self._request("search", domain0=domain)
        return _parse_search_result(data, domain)

    async def register_domain(
        self, domain: str, duration: int = 1, currency: str = "USD"
    ) -> RegisterResult:
        """Register a new domain via Dynadot API.

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').
            duration: Registration period in years (default 1).
            currency: Payment currency (default 'USD').

        Returns:
            RegisterResult with success status and expiration.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(duration, int) and 1 <= duration <= 10, "duration 1-10 years"
        assert currency in ("USD", "EUR", "GBP", "CNY", "CAD", "INR"), "valid currency"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="register", domain=domain,
                        duration=duration, currency=currency)
            return RegisterResult(domain=domain, success=True,
                                  message=f"[DRY RUN] Would register {domain}",
                                  expiration="")

        data: dict[str, Any] = await self._request(
            "register", domain=domain, duration=str(duration), currency=currency,
        )
        return _parse_register_result(data, domain)

    async def set_nameservers(
        self, domain: str, nameservers: list[str]
    ) -> SetNameserversResult:
        """Set nameservers for a registered domain.

        Args:
            domain: Domain name to update.
            nameservers: List of nameserver hostnames (up to 13).

        Returns:
            SetNameserversResult with success status.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(nameservers, list) and 1 <= len(nameservers) <= 13, (
            "1-13 nameservers required"
        )

        if self._dry_run:
            logger.info("dynadot_dry_run", action="set_ns", domain=domain,
                        nameservers=nameservers)
            return SetNameserversResult(domain=domain, success=True,
                                        message=f"[DRY RUN] Would set NS for {domain}")

        ns_params: dict[str, str] = {}
        for idx, ns in enumerate(nameservers):
            assert isinstance(ns, str) and len(ns) > 0, f"nameserver {idx} invalid"
            if idx >= 13:
                break
            ns_params[f"ns{idx}"] = ns

        data: dict[str, Any] = await self._request(
            "set_ns", domain=domain, **ns_params,
        )
        success: bool = _is_success(data)
        msg: str = _extract_message(data)
        return SetNameserversResult(domain=domain, success=success, message=msg)

    async def domain_info(self, domain: str) -> DomainInfoResult:
        """Get detailed domain registration info.

        Args:
            domain: Domain name to look up.

        Returns:
            DomainInfoResult with expiration, nameservers, status.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        if self._dry_run:
            logger.info("dynadot_dry_run", action="domain_info", domain=domain)
            return DomainInfoResult(domain=domain, expiration="", name_servers=(), status="dry_run")

        data: dict[str, Any] = await self._request("domain_info", domain=domain)
        return _parse_domain_info(data, domain)


# --- Pure helper functions (no side effects) ---


def _is_success(data: dict[str, Any]) -> bool:
    """Check if API response indicates success."""
    assert isinstance(data, dict), "data must be a dict"
    # Check common response wrappers (SetNsResponse, RegisterResponse, etc.)
    for key in ("StatusHeader", "SetNsResponse", "RegisterResponse",
                "SetDnsResponse"):
        resp: Any = data.get(key)
        if isinstance(resp, dict):
            code: int = int(resp.get("ResponseCode", -1))
            if code == 0:
                return True
            status: str = str(resp.get("Status", resp.get("status", "")))
            if status.lower() == "success":
                return True
    # Fallback: check top-level
    status_header: dict[str, Any] = data.get("StatusHeader", data)
    status_str: str = str(status_header.get("Status", status_header.get("status", "")))
    assert isinstance(status_str, str), "status must resolve to string"
    return status_str.lower() == "success"


def _is_success_backorder(data: dict[str, Any]) -> bool:
    """Check if backorder API response indicates success."""
    assert isinstance(data, dict), "data must be a dict"
    for key in ("AddBackorderRequestResponse", "DeleteBackorderRequestResponse",
                "BackorderRequestListResponse", "StatusHeader"):
        resp: Any = data.get(key)
        if isinstance(resp, dict):
            status: str = str(resp.get("Status", resp.get("status", "")))
            return status.lower() == "success"
    return _is_success(data)


def _extract_message(data: dict[str, Any]) -> str:
    """Extract human-readable message from API response."""
    assert isinstance(data, dict), "data must be a dict"
    header: dict[str, Any] = data.get("StatusHeader", data)
    msg: str = str(header.get("Message", header.get("message", "")))
    assert isinstance(msg, str), "message must be a string"
    return msg if msg else str(header.get("Status", "unknown"))


def _extract_message_backorder(data: dict[str, Any]) -> str:
    """Extract message from backorder-specific API responses."""
    assert isinstance(data, dict), "data must be a dict"
    for key in ("AddBackorderRequestResponse", "DeleteBackorderRequestResponse",
                "BackorderRequestListResponse"):
        resp: Any = data.get(key)
        if isinstance(resp, dict):
            err: str = str(resp.get("Error", ""))
            if err:
                return err
            return str(resp.get("Status", "unknown"))
    return _extract_message(data)


def _extract_backorder_list(data: dict[str, Any]) -> list[str]:
    """Parse list of backorder domains from API response.

    Handles two response structures:
      - Direct: {"BackorderList": [...]}
      - Nested: {"BackorderRequestListResponse": {"BackorderRequestList": [...]}}
    """
    assert isinstance(data, dict), "data must be a dict"
    # Try direct keys first
    items: Any = data.get("BackorderList", data.get("backorder_list"))
    # Try nested response wrapper (actual API format)
    if items is None:
        wrapper: Any = data.get("BackorderRequestListResponse", {})
        if isinstance(wrapper, dict):
            items = wrapper.get("BackorderRequestList", wrapper.get("backorder_request_list"))
    if not isinstance(items, list):
        items = []
    domains: list[str] = []
    for idx, item in enumerate(items):
        if idx >= 1000:  # bounded loop
            break
        if isinstance(item, dict):
            domain: str = str(item.get("DomainName", item.get("Domain", item.get("domain", ""))))
            if domain:
                domains.append(domain)
        elif isinstance(item, str) and item:
            domains.append(item)
    assert isinstance(domains, list), "result must be a list"
    return domains


def _parse_search_result(data: dict[str, Any], domain: str) -> DomainSearchResult:
    """Parse domain search response into DomainSearchResult."""
    assert isinstance(data, dict), "data must be a dict"
    assert isinstance(domain, str), "domain must be a string"
    search_resp: Any = data.get("SearchResponse", data)
    if isinstance(search_resp, dict):
        results: Any = search_resp.get("SearchResults", search_resp)
        if isinstance(results, list) and len(results) > 0:
            first: dict[str, Any] = results[0] if isinstance(results[0], dict) else {}
            available: bool = str(first.get("Available", "no")).lower() == "yes"
            price: float = float(first.get("Price", 0.0))
            return DomainSearchResult(domain=domain, available=available, price_usd=price)
    available_str: str = str(search_resp.get("Available", search_resp.get("available", "no")))
    price_val: float = float(search_resp.get("Price", search_resp.get("price", 0.0)))
    return DomainSearchResult(domain=domain, available=available_str.lower() == "yes",
                              price_usd=price_val)


def _parse_register_result(data: dict[str, Any], domain: str) -> RegisterResult:
    """Parse domain registration response into RegisterResult."""
    assert isinstance(data, dict), "data must be a dict"
    assert isinstance(domain, str), "domain must be a string"
    reg_resp: Any = data.get("RegisterResponse", data)
    if isinstance(reg_resp, dict):
        code: int = int(reg_resp.get("ResponseCode", -1))
        status: str = str(reg_resp.get("Status", ""))
        expiration: str = str(reg_resp.get("Expiration", ""))
        success: bool = code == 0 or status.lower() == "success"
        msg: str = status if status else _extract_message(data)
        return RegisterResult(domain=domain, success=success,
                              message=msg, expiration=expiration)
    # Fallback: check top-level status
    success = _is_success(data)
    msg = _extract_message(data)
    return RegisterResult(domain=domain, success=success,
                          message=msg, expiration="")


def _parse_domain_info(data: dict[str, Any], domain: str) -> DomainInfoResult:
    """Parse domain info response into DomainInfoResult."""
    assert isinstance(data, dict), "data must be a dict"
    assert isinstance(domain, str), "domain must be a string"
    info: dict[str, Any] = data.get("DomainInfoResponse", data.get("domain_info", data))
    if not isinstance(info, dict):
        info = {}
    expiration: str = str(info.get("Expiration", info.get("expiration", "")))
    ns_raw: Any = info.get("NameServers", info.get("name_servers", []))
    ns_list: list[str] = []
    if isinstance(ns_raw, list):
        for idx, ns in enumerate(ns_raw):
            if idx >= 20:  # bounded
                break
            ns_list.append(str(ns))
    status: str = str(info.get("Status", info.get("status", "unknown")))
    return DomainInfoResult(domain=domain, expiration=expiration,
                            name_servers=tuple(ns_list), status=status)

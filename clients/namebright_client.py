"""NameBright REST API client — domain management, DNS, registration, transfers.

SEPARATE from dropcatch_client.py (which handles backorders/auctions).
This client manages domains via the NameBright Domain Management API.

Setup requirements:
  1. Create NameBright.com account: https://www.namebright.com/NewAccount
  2. Enable API access: https://www.namebright.com/Settings#Api
  3. Grant appropriate permissions (domain management, DNS, registration)
  4. Configure IP whitelist for your API account
  5. Set NAMEBRIGHT_CLIENT_ID and NAMEBRIGHT_CLIENT_SECRET in .env
     Format: client_id = "accountname:appname"

API docs:
  - Base URL: https://api.namebright.com/rest/

Auth endpoint:
  - POST https://api.namebright.com/auth/token (30-min tokens)

Rate limit:
  - 30 requests per 30 seconds (HARD limit, revokes API access on violation)

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
# Constants (immutable module-level — NASA Rule 2)
# ---------------------------------------------------------------------------
_AUTH_URL: str = "https://api.namebright.com/auth/token"
_API_BASE_URL: str = "https://api.namebright.com/rest"
_TIMEOUT_SECONDS: int = 30
_TOKEN_LIFETIME_SECONDS: int = 1800  # 30 minutes
_TOKEN_REFRESH_BUFFER: int = 60  # Refresh 1 min early

# NameBright rate limit: 30 requests per 30 seconds (hard limit, revokes access)
_MAX_REQUESTS_PER_WINDOW: int = 30
_WINDOW_SECONDS: int = 30
_MIN_REQUEST_INTERVAL: float = 1.0

# Pagination bounds
_MAX_DOMAINS_PER_PAGE: int = 200
_MAX_NAMESERVERS: int = 13
_MAX_DNS_RECORDS: int = 500


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class NameBrightError(Exception):
    """Base error for NameBright API failures."""


class NameBrightAuthError(NameBrightError):
    """Raised when authentication fails (invalid credentials, expired token)."""


class NameBrightRateLimitError(NameBrightError):
    """Raised when rate limit is exceeded (30 req / 30 sec)."""


class NameBrightNotFoundError(NameBrightError):
    """Raised when a requested resource (domain, record) is not found."""


# ---------------------------------------------------------------------------
# Result dataclasses (frozen — NASA Rule 2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AccountInfo:
    """Account balance information."""
    balance: float

    def __post_init__(self) -> None:
        assert isinstance(self.balance, (int, float)), "balance must be numeric"
        assert self.balance >= 0, f"balance must be non-negative, got {self.balance}"


@dataclass(frozen=True)
class DomainSummary:
    """Compact domain listing entry."""
    domain: str
    status: str
    expiry: str

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) > 0, "domain required"
        assert isinstance(self.status, str), "status must be a string"


@dataclass(frozen=True)
class DomainDetail:
    """Full domain details including lock, privacy, and auth code."""
    domain: str
    status: str
    expiry: str
    locked: bool
    auto_renew: bool
    privacy: bool
    category: str
    auth_code: str

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) > 0, "domain required"
        assert isinstance(self.locked, bool), "locked must be bool"


@dataclass(frozen=True)
class AvailabilityResult:
    """Domain availability check result."""
    domain: str
    available: bool
    price: float
    promotion_price: float

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) > 0, "domain required"
        assert isinstance(self.available, bool), "available must be bool"


@dataclass(frozen=True)
class RegistrationResult:
    """Domain registration confirmation."""
    order_id: int
    total_price: float

    def __post_init__(self) -> None:
        assert isinstance(self.order_id, int), "order_id must be int"
        assert self.total_price >= 0, f"total_price must be non-negative, got {self.total_price}"


@dataclass(frozen=True)
class DnsRecord:
    """Single DNS host record."""
    record_id: int
    record_type: str
    name: str
    value: str
    ttl: int

    def __post_init__(self) -> None:
        assert isinstance(self.record_id, int), "record_id must be int"
        assert isinstance(self.record_type, str) and len(self.record_type) > 0, "type required"


# ---------------------------------------------------------------------------
# Rate limiter (thread-safe, stdlib only — copied from dropcatch_client.py)
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
class NameBrightClient:
    """NameBright Domain Management API client with automatic token management.

    Handles OAuth2 authentication, rate limiting (30 req / 30 sec),
    and provides typed methods for domain management, DNS, registration,
    and transfer operations.

    Args:
        client_id: NameBright API client ID (format: "account:app").
        client_secret: NameBright API client secret.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        assert isinstance(client_id, str) and len(client_id) > 0, "client_id must not be empty"
        assert isinstance(client_secret, str) and len(client_secret) > 0, (
            "client_secret must not be empty"
        )
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expiry: float = 0.0
        self._http = httpx.Client(timeout=_TIMEOUT_SECONDS)
        self._rate_limiter = _RateLimiter()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> NameBrightClient:
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
        """Request a new OAuth2 bearer token from NameBright."""
        response = self._rate_limited_request(
            "POST",
            _AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code not in (200, 201):
            raise NameBrightAuthError(
                f"Auth failed: HTTP {response.status_code} — {response.text[:300]}"
            )

        data = response.json()
        token = data.get("access_token")
        assert token, f"No access_token in auth response: {list(data.keys())}"

        self._access_token = token
        expires_in = int(data.get("expires_in", _TOKEN_LIFETIME_SECONDS))
        self._token_expiry = time.time() + expires_in - _TOKEN_REFRESH_BUFFER

        logger.info("namebright_token_refreshed", expires_in=expires_in)
        return token

    def _auth_headers(self) -> dict[str, str]:
        """Build headers with current bearer token."""
        token = self._ensure_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ----- Response handling -----

    def _handle_response(self, response: httpx.Response, context: str) -> Any:
        """Check response status and return parsed JSON.

        Raises typed exceptions for auth, rate limit, and not-found errors.
        """
        assert response is not None, "response must not be None"
        assert isinstance(context, str) and len(context) > 0, "context required"

        status = response.status_code
        if status == 401 or status == 403:
            self._access_token = None  # Force re-auth on next call
            raise NameBrightAuthError(
                f"{context}: HTTP {status} — {response.text[:300]}"
            )
        if status == 404:
            raise NameBrightNotFoundError(
                f"{context}: HTTP 404 — {response.text[:300]}"
            )
        if status == 429:
            raise NameBrightRateLimitError(
                f"{context}: rate limit exceeded — {response.text[:300]}"
            )
        if status < 200 or status >= 300:
            raise NameBrightError(
                f"{context}: HTTP {status} — {response.text[:300]}"
            )

        # Some endpoints return empty body on success (PUT/DELETE)
        if not response.text or not response.text.strip():
            return None
        return response.json()

    # ----- Account -----

    def get_account_balance(self) -> AccountInfo:
        """Get the current account balance.

        Returns:
            AccountInfo with the account balance.
        """
        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/account",
            headers=self._auth_headers(),
        )
        data = self._handle_response(response, "get_account_balance")
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        balance = float(data.get("Balance", data.get("balance", 0.0)))
        return AccountInfo(balance=balance)

    # ----- Domain listing -----

    def list_domains(self, page: int = 1, per_page: int = 50) -> list[DomainSummary]:
        """List domains in the account with pagination.

        Args:
            page: Page number (1-indexed).
            per_page: Domains per page (1-200).

        Returns:
            List of DomainSummary entries for the requested page.
        """
        assert isinstance(page, int) and page >= 1, f"page must be >= 1, got {page}"
        assert isinstance(per_page, int) and 1 <= per_page <= _MAX_DOMAINS_PER_PAGE, (
            f"per_page must be 1-{_MAX_DOMAINS_PER_PAGE}, got {per_page}"
        )

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/account/domains",
            headers=self._auth_headers(),
            params={"page": page, "domainsPerPage": per_page},
        )
        data = self._handle_response(response, "list_domains")
        # API returns {"ResultsTotal": N, "CurrentPage": N, "Domains": [...]}
        if isinstance(data, dict):
            domain_list = data.get("Domains", data.get("domains", []))
        else:
            domain_list = data
        assert isinstance(domain_list, list), f"Expected list, got {type(domain_list)}"

        results: list[DomainSummary] = []
        for idx, item in enumerate(domain_list):
            if idx >= _MAX_DOMAINS_PER_PAGE:
                break
            assert isinstance(item, dict), f"Expected dict at index {idx}"
            results.append(DomainSummary(
                domain=str(item.get("DomainName", item.get("domainName", ""))),
                status=str(item.get("Status", item.get("status", ""))),
                expiry=str(item.get("ExpirationDate", item.get("ExpireDate", item.get("expireDate", "")))),
            ))
        return results

    # ----- Domain detail -----

    def get_domain(self, domain: str) -> DomainDetail:
        """Get full details for a specific domain.

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').

        Returns:
            DomainDetail with lock status, privacy, auth code, etc.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/account/domains/{domain}",
            headers=self._auth_headers(),
        )
        data = self._handle_response(response, f"get_domain({domain})")
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        return DomainDetail(
            domain=str(data.get("DomainName", data.get("domainName", domain))),
            status=str(data.get("Status", data.get("status", ""))),
            expiry=str(data.get("ExpireDate", data.get("expireDate", ""))),
            locked=bool(data.get("Locked", data.get("locked", False))),
            auto_renew=bool(data.get("AutoRenew", data.get("autoRenew", False))),
            privacy=bool(data.get("Privacy", data.get("privacy", False))),
            category=str(data.get("Category", data.get("category", ""))),
            auth_code=str(data.get("AuthCode", data.get("authCode", ""))),
        )

    # ----- Availability -----

    def check_availability(self, domain: str) -> AvailabilityResult:
        """Check if a domain is available for registration.

        Args:
            domain: Domain name to check (e.g. 'example.com').

        Returns:
            AvailabilityResult with availability status and pricing.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/purchase/availability/{domain}",
            headers=self._auth_headers(),
        )
        data = self._handle_response(response, f"check_availability({domain})")
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        return AvailabilityResult(
            domain=str(data.get("DomainName", data.get("domainName", domain))),
            available=bool(data.get("Available", data.get("available", False))),
            price=float(data.get("Price", data.get("price", 0.0))),
            promotion_price=float(
                data.get("PromotionPrice", data.get("promotionPrice", 0.0))
            ),
        )

    # ----- Registration -----

    def register_domain(
        self, domain: str, years: int = 1
    ) -> RegistrationResult:
        """Register a new domain.

        Args:
            domain: Domain name to register (e.g. 'example.com').
            years: Registration period in years (1-10).

        Returns:
            RegistrationResult with order ID and total price.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(years, int) and 1 <= years <= 10, (
            f"years must be 1-10, got {years}"
        )

        payload = {
            "DomainName": domain,
            "Years": years,
        }

        response = self._rate_limited_request(
            "POST",
            f"{_API_BASE_URL}/purchase/register",
            headers=self._auth_headers(),
            json=payload,
        )
        data = self._handle_response(response, f"register_domain({domain})")
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        return RegistrationResult(
            order_id=int(data.get("OrderId", data.get("orderId", 0))),
            total_price=float(data.get("TotalPrice", data.get("totalPrice", 0.0))),
        )

    # ----- Nameservers -----

    def get_nameservers(self, domain: str) -> list[str]:
        """Get the current nameservers for a domain.

        Args:
            domain: Domain name to query.

        Returns:
            List of nameserver hostnames.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/account/domains/{domain}/nameservers",
            headers=self._auth_headers(),
        )
        data = self._handle_response(response, f"get_nameservers({domain})")
        assert isinstance(data, list), f"Expected list, got {type(data)}"

        nameservers: list[str] = []
        for idx, ns in enumerate(data):
            if idx >= _MAX_NAMESERVERS:
                break
            nameservers.append(str(ns))
        return nameservers

    def set_nameservers(self, domain: str, nameservers: list[str]) -> bool:
        """Replace all nameservers for a domain.

        Clears existing nameservers first, then sets the new ones.

        Args:
            domain: Domain name to update.
            nameservers: List of nameserver hostnames (1-13).

        Returns:
            True if all nameservers were set successfully.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(nameservers, list) and 1 <= len(nameservers) <= _MAX_NAMESERVERS, (
            f"1-{_MAX_NAMESERVERS} nameservers required, got {len(nameservers)}"
        )

        # Step 1: Clear existing nameservers
        self._clear_nameservers(domain)

        # Step 2: Set each nameserver (bounded loop)
        for idx, ns in enumerate(nameservers):
            if idx >= _MAX_NAMESERVERS:
                break
            assert isinstance(ns, str) and len(ns) > 0, f"nameserver {idx} is empty"
            self._put_nameserver(domain, ns)

        logger.info(
            "namebright_nameservers_set",
            domain=domain,
            count=len(nameservers),
        )
        return True

    def _clear_nameservers(self, domain: str) -> None:
        """Delete all nameservers for a domain."""
        assert isinstance(domain, str) and len(domain) > 0, "domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "DELETE",
            f"{_API_BASE_URL}/account/domains/{domain}/nameservers",
            headers=self._auth_headers(),
        )
        self._handle_response(response, f"clear_nameservers({domain})")
        logger.debug("namebright_nameservers_cleared", domain=domain)

    def _put_nameserver(self, domain: str, ns: str) -> None:
        """Add a single nameserver to a domain."""
        assert isinstance(domain, str) and len(domain) > 0, "domain required"
        assert isinstance(ns, str) and len(ns) > 0, "nameserver required"

        response = self._rate_limited_request(
            "PUT",
            f"{_API_BASE_URL}/account/domains/{domain}/nameservers/{ns}",
            headers=self._auth_headers(),
        )
        self._handle_response(response, f"put_nameserver({domain}, {ns})")
        logger.debug("namebright_nameserver_added", domain=domain, ns=ns)

    # ----- DNS records -----

    def get_dns_records(self, domain: str) -> list[DnsRecord]:
        """Get all DNS host records for a domain.

        Args:
            domain: Domain name to query.

        Returns:
            List of DnsRecord entries.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "GET",
            f"{_API_BASE_URL}/account/domains/{domain}/hostrecords/all",
            headers=self._auth_headers(),
        )
        data = self._handle_response(response, f"get_dns_records({domain})")
        assert isinstance(data, list), f"Expected list, got {type(data)}"

        records: list[DnsRecord] = []
        for idx, item in enumerate(data):
            if idx >= _MAX_DNS_RECORDS:
                break
            assert isinstance(item, dict), f"Expected dict at index {idx}"
            records.append(DnsRecord(
                record_id=int(item.get("Id", item.get("id", 0))),
                record_type=str(item.get("Type", item.get("type", ""))),
                name=str(item.get("Name", item.get("name", ""))),
                value=str(item.get("Content", item.get("content", ""))),
                ttl=int(item.get("Ttl", item.get("ttl", 3600))),
            ))
        return records

    def add_dns_record(
        self,
        domain: str,
        record_type: str,
        name: str,
        value: str,
        ttl: int = 3600,
    ) -> DnsRecord:
        """Add a DNS host record to a domain.

        Args:
            domain: Domain name to update.
            record_type: Record type (A, AAAA, CNAME, MX, TXT, etc.).
            name: Record name (e.g. '@', 'www', 'mail').
            value: Record value (e.g. IP address, hostname).
            ttl: Time-to-live in seconds (default 3600).

        Returns:
            The created DnsRecord.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(record_type, str) and len(record_type) > 0, "record_type required"
        assert isinstance(name, str), "name must be a string"
        assert isinstance(value, str) and len(value) > 0, "value required"
        assert isinstance(ttl, int) and ttl > 0, f"ttl must be positive, got {ttl}"

        payload = {
            "Name": name,
            "Content": value,
            "Ttl": ttl,
        }

        response = self._rate_limited_request(
            "POST",
            f"{_API_BASE_URL}/account/domains/{domain}/hostrecords/{record_type}",
            headers=self._auth_headers(),
            json=payload,
        )
        data = self._handle_response(response, f"add_dns_record({domain}, {record_type})")
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

        logger.info(
            "namebright_dns_record_added",
            domain=domain,
            type=record_type,
            name=name,
        )
        return DnsRecord(
            record_id=int(data.get("Id", data.get("id", 0))),
            record_type=str(data.get("Type", data.get("type", record_type))),
            name=str(data.get("Name", data.get("name", name))),
            value=str(data.get("Content", data.get("content", value))),
            ttl=int(data.get("Ttl", data.get("ttl", ttl))),
        )

    def delete_dns_record(
        self,
        domain: str,
        record_type: str,
        record_id: int,
    ) -> bool:
        """Delete a specific DNS host record.

        Args:
            domain: Domain name owning the record.
            record_type: Record type (A, AAAA, CNAME, etc.).
            record_id: ID of the record to delete.

        Returns:
            True if the record was deleted successfully.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(record_type, str) and len(record_type) > 0, "record_type required"
        assert isinstance(record_id, int) and record_id >= 0, (
            f"record_id must be non-negative, got {record_id}"
        )

        response = self._rate_limited_request(
            "DELETE",
            f"{_API_BASE_URL}/account/domains/{domain}/hostrecords/{record_type}/{record_id}",
            headers=self._auth_headers(),
        )
        self._handle_response(response, f"delete_dns_record({domain}, {record_type}, {record_id})")
        logger.info(
            "namebright_dns_record_deleted",
            domain=domain,
            type=record_type,
            record_id=record_id,
        )
        return True

    # ----- Transfers (push) -----

    def accept_inbound_push(self, domain: str) -> bool:
        """Accept an inbound domain push (transfer in).

        Args:
            domain: Domain name being pushed to this account.

        Returns:
            True if the push was accepted successfully.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"

        response = self._rate_limited_request(
            "PUT",
            f"{_API_BASE_URL}/account/inboundpush/{domain}/Accept",
            headers=self._auth_headers(),
        )
        self._handle_response(response, f"accept_inbound_push({domain})")
        logger.info("namebright_inbound_push_accepted", domain=domain)
        return True

    def initiate_outbound_push(self, domain: str, email: str) -> bool:
        """Initiate an outbound domain push (transfer out to another account).

        Args:
            domain: Domain name to push out.
            email: Email address of the receiving NameBright account.

        Returns:
            True if the push was initiated successfully.
        """
        assert isinstance(domain, str) and len(domain) > 3, "valid domain required"
        assert "." in domain, "domain must contain a TLD"
        assert isinstance(email, str) and "@" in email, "valid email required"

        response = self._rate_limited_request(
            "POST",
            f"{_API_BASE_URL}/account/outboundpush/{domain}/Initiate",
            headers=self._auth_headers(),
            params={"emailAddress": email},
        )
        self._handle_response(response, f"initiate_outbound_push({domain}, {email})")
        logger.info(
            "namebright_outbound_push_initiated",
            domain=domain,
            recipient=email,
        )
        return True

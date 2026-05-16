"""Async RDAP client for structured domain WHOIS lookups.

RDAP (Registration Data Access Protocol) returns structured JSON instead of
legacy WHOIS plaintext. Uses TLD-specific RDAP servers for accurate routing.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants (immutable — NASA Rule 2)
# ---------------------------------------------------------------------------
_TIMEOUT_SECONDS: Final[int] = 30
_MAX_CONCURRENT: Final[int] = 20
_TLD_DELAY_SECONDS: Final[float] = 3.0
_MAX_RETRIES: Final[int] = 3
_MAX_NAMESERVERS: Final[int] = 20
_MAX_STATUS_CODES: Final[int] = 50
_MAX_EVENTS: Final[int] = 50
_MAX_DOMAINS_PER_BATCH: Final[int] = 500
_USER_AGENT: Final[str] = "DomainHunter/1.0 (+https://github.com/domain-hunter)"

RDAP_SERVERS: Final[MappingProxyType[str, str]] = MappingProxyType({
    ".com": "https://rdap.verisign.com/com/v1/domain/",
    ".net": "https://rdap.verisign.com/net/v1/domain/",
    ".org": "https://rdap.publicinterestregistry.org/rdap/domain/",
    ".io": "https://rdap.nic.io/domain/",
    ".ai": "https://rdap.nic.ai/domain/",
    ".co": "https://rdap.nic.co/domain/",
    ".dev": "https://rdap.nic.google/domain/",
})

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RDAPError(Exception):
    """Base error for RDAP client operations."""


class RDAPNotFoundError(RDAPError):
    """Raised when domain is not found in RDAP (404)."""


class RDAPRateLimitError(RDAPError):
    """Raised when RDAP server returns 429 rate limit."""


# ---------------------------------------------------------------------------
# Result dataclass (frozen — NASA Rule 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RDAPResult:
    """Immutable RDAP lookup result for a single domain."""

    domain: str
    status_codes: tuple[str, ...]
    registry_expiry: str
    registrar_expiry: str
    registrar_name: str
    nameservers: tuple[str, ...]
    creation_date: str
    last_updated: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class RDAPClient:
    """Async RDAP client with TLD-specific routing and rate limiting."""

    def __init__(self) -> None:
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        self._tld_last_request: dict[str, float] = {}

    @staticmethod
    def _extract_tld(domain: str) -> str:
        """Extract the TLD suffix from a domain name.

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').

        Returns:
            TLD with leading dot (e.g. '.com').
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) > 0, "domain must not be empty"
        dot_idx: int = domain.rfind(".")
        assert dot_idx > 0, f"invalid domain format: {domain}"
        return domain[dot_idx:].lower()

    @staticmethod
    def _resolve_rdap_url(domain: str, tld: str) -> str:
        """Build the full RDAP query URL for a domain.

        Args:
            domain: Fully qualified domain name.
            tld: TLD suffix with leading dot.

        Returns:
            Full RDAP URL for the domain query.
        """
        assert isinstance(tld, str), "tld must be a string"
        assert tld in RDAP_SERVERS, f"unsupported TLD: {tld}"
        base_url: str = RDAP_SERVERS[tld]
        return f"{base_url}{domain}"

    async def _enforce_tld_delay(self, tld: str) -> None:
        """Enforce per-TLD rate limiting with a minimum delay between requests.

        Args:
            tld: TLD suffix to rate-limit against.
        """
        assert isinstance(tld, str), "tld must be a string"
        assert tld.startswith("."), "tld must start with a dot"
        last: float = self._tld_last_request.get(tld, 0.0)
        elapsed: float = time.monotonic() - last
        if elapsed < _TLD_DELAY_SECONDS:
            await asyncio.sleep(_TLD_DELAY_SECONDS - elapsed)
        self._tld_last_request[tld] = time.monotonic()

    @staticmethod
    def _parse_events(data: dict[str, Any]) -> dict[str, str]:
        """Extract date fields from RDAP events array.

        Args:
            data: Raw RDAP JSON response dict.

        Returns:
            Dict mapping event action to date string.
        """
        assert isinstance(data, dict), "data must be a dict"
        events: list[dict[str, Any]] = data.get("events", [])
        assert isinstance(events, list), "events must be a list"
        result: dict[str, str] = {}
        for idx, event in enumerate(events):
            if idx >= _MAX_EVENTS:
                break
            action: str = event.get("eventAction", "")
            date: str = event.get("eventDate", "")
            if action and date:
                result[action] = date
        return result

    @staticmethod
    def _parse_nameservers(data: dict[str, Any]) -> tuple[str, ...]:
        """Extract nameserver hostnames from RDAP response.

        Args:
            data: Raw RDAP JSON response dict.

        Returns:
            Tuple of nameserver hostname strings.
        """
        assert isinstance(data, dict), "data must be a dict"
        ns_list: list[dict[str, Any]] = data.get("nameservers", [])
        assert isinstance(ns_list, list), "nameservers must be a list"
        servers: list[str] = []
        for idx, ns in enumerate(ns_list):
            if idx >= _MAX_NAMESERVERS:
                break
            hostname: str = ns.get("ldhName", "")
            if hostname:
                servers.append(hostname.lower())
        return tuple(servers)

    @staticmethod
    def _parse_registrar(data: dict[str, Any]) -> str:
        """Extract registrar name from RDAP entities.

        Args:
            data: Raw RDAP JSON response dict.

        Returns:
            Registrar name string, or empty string if not found.
        """
        assert isinstance(data, dict), "data must be a dict"
        entities: list[dict[str, Any]] = data.get("entities", [])
        assert isinstance(entities, list), "entities must be a list"
        for idx, entity in enumerate(entities):
            if idx >= _MAX_STATUS_CODES:
                break
            roles: list[str] = entity.get("roles", [])
            if "registrar" in roles:
                vcards: list[Any] = entity.get("vcardArray", [None, []])[1]
                for vcard_idx, entry in enumerate(vcards):
                    if vcard_idx >= _MAX_STATUS_CODES:
                        break
                    if isinstance(entry, list) and len(entry) >= 4 and entry[0] == "fn":
                        return str(entry[3])
        return ""

    def _build_result(self, domain: str, data: dict[str, Any]) -> RDAPResult:
        """Parse raw RDAP JSON into a frozen RDAPResult dataclass.

        Args:
            domain: The queried domain name.
            data: Raw RDAP JSON response dict.

        Returns:
            Populated RDAPResult instance.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert isinstance(data, dict), "data must be a dict"

        events: dict[str, str] = self._parse_events(data)
        raw_status: list[str] = data.get("status", [])
        status_codes: tuple[str, ...] = tuple(
            raw_status[:_MAX_STATUS_CODES]
        )

        return RDAPResult(
            domain=data.get("ldhName", domain).lower(),
            status_codes=status_codes,
            registry_expiry=events.get("expiration", ""),
            registrar_expiry=data.get("registrarExpiry", ""),
            registrar_name=self._parse_registrar(data),
            nameservers=self._parse_nameservers(data),
            creation_date=events.get("registration", ""),
            last_updated=events.get("last changed", ""),
        )

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def lookup(self, domain: str) -> RDAPResult:
        """Look up a single domain via RDAP.

        Args:
            domain: Fully qualified domain name (e.g. 'example.com').

        Returns:
            RDAPResult with parsed registration data.

        Raises:
            RDAPNotFoundError: Domain not found (404).
            RDAPRateLimitError: Server returned 429.
            RDAPError: Any other RDAP failure.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) > 0, "domain must not be empty"

        tld: str = self._extract_tld(domain)
        url: str = self._resolve_rdap_url(domain, tld)
        headers: dict[str, str] = {
            "Accept": "application/rdap+json",
            "User-Agent": _USER_AGENT,
        }

        async with self._semaphore:
            await self._enforce_tld_delay(tld)
            try:
                async with httpx.AsyncClient(timeout=float(_TIMEOUT_SECONDS)) as client:
                    response: httpx.Response = await client.get(url, headers=headers)
            except httpx.TimeoutException as exc:
                logger.error("rdap_timeout", domain=domain, url=url)
                raise RDAPError(f"RDAP timeout for {domain}") from exc
            except httpx.HTTPError as exc:
                logger.error("rdap_http_error", domain=domain, error=str(exc))
                raise RDAPError(f"RDAP HTTP error for {domain}: {exc}") from exc

        return self._handle_response(response, domain)

    def _handle_response(self, response: httpx.Response, domain: str) -> RDAPResult:
        """Process RDAP HTTP response into a result or raise appropriate error.

        Args:
            response: httpx Response from the RDAP server.
            domain: The queried domain name.

        Returns:
            Parsed RDAPResult on success.
        """
        assert response is not None, "response must not be None"
        assert isinstance(domain, str), "domain must be a string"

        status: int = response.status_code

        if status == 404:
            logger.info("rdap_not_found", domain=domain)
            raise RDAPNotFoundError(f"Domain not found in RDAP: {domain}")

        if status == 429:
            logger.warning("rdap_rate_limited", domain=domain)
            raise RDAPRateLimitError(f"RDAP rate limited for {domain}")

        if status != 200:
            body_text: str = response.text[:500]
            logger.error("rdap_error", domain=domain, status=status, body=body_text)
            raise RDAPError(f"RDAP returned {status} for {domain}: {body_text[:200]}")

        data: dict[str, Any] = response.json()
        result: RDAPResult = self._build_result(domain, data)
        logger.info("rdap_lookup_ok", domain=result.domain, status_codes=result.status_codes)
        return result

    async def lookup_batch(self, domains: list[str]) -> list[RDAPResult | RDAPError]:
        """Look up multiple domains concurrently with rate limiting.

        Args:
            domains: List of domain names to query.

        Returns:
            List of RDAPResult on success or RDAPError subclass on failure,
            preserving input order.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert 1 <= len(domains) <= _MAX_DOMAINS_PER_BATCH, (
            f"batch size must be 1-{_MAX_DOMAINS_PER_BATCH}, got {len(domains)}"
        )

        tasks: list[asyncio.Task[RDAPResult]] = []
        for idx, domain in enumerate(domains):
            if idx >= _MAX_DOMAINS_PER_BATCH:
                break
            tasks.append(asyncio.create_task(self._safe_lookup(domain)))

        raw_results: list[RDAPResult | RDAPError] = await asyncio.gather(*tasks)
        assert len(raw_results) == len(tasks), "gather must return same count as tasks"

        ok_count: int = sum(1 for r in raw_results if isinstance(r, RDAPResult))
        logger.info(
            "rdap_batch_complete",
            total=len(domains), success=ok_count, failed=len(domains) - ok_count,
        )
        return raw_results

    async def _safe_lookup(self, domain: str) -> RDAPResult | RDAPError:
        """Wrap lookup to catch errors for batch processing.

        Args:
            domain: Domain name to look up.

        Returns:
            RDAPResult on success, or RDAPError subclass on failure.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) > 0, "domain must not be empty"
        try:
            return await self.lookup(domain)
        except RDAPError as exc:
            return exc

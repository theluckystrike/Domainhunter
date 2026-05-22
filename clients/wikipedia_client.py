"""Wikipedia external link checker — FREE authority signal.

Uses MediaWiki exturlusage API to check if any Wikipedia article
links to a domain. A Wikipedia backlink = guaranteed DR 30+.

Endpoint: GET https://en.wikipedia.org/w/api.php
No auth required. Rate limit: ~200/min (be polite).

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

from typing import Any, Final

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_API_URL: Final[str] = "https://en.wikipedia.org/w/api.php"
_TIMEOUT_SECONDS: Final[int] = 15
_MAX_BATCH_SIZE: Final[int] = 50
_USER_AGENT: Final[str] = "DomainHunter/1.0 (authority-gate; contact@example.com)"


class WikipediaError(Exception):
    """Raised when Wikipedia API returns an error."""


class WikipediaClient:
    """Client for checking Wikipedia external links to domains.

    No API key required. Uses the MediaWiki exturlusage query.
    """

    def __init__(self, *, mock: bool = False) -> None:
        assert isinstance(mock, bool), "mock must be a boolean"
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def has_wikipedia_links(self, domain: str) -> bool:
        """Check if any Wikipedia article links to this domain.

        Args:
            domain: Target domain (e.g. 'example.com').

        Returns:
            True if at least one Wikipedia article links to the domain.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert "." in domain, f"invalid domain: {domain}"

        if self._mock:
            return domain in (
                "github.com", "wikipedia.org", "python.org",
                "mozilla.org", "w3.org",
            )

        return await self._fetch_live(domain)

    async def _fetch_live(self, domain: str) -> bool:
        """Query Wikipedia exturlusage API."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        params: dict[str, str] = {
            "action": "query",
            "list": "exturlusage",
            "euquery": domain,
            "eulimit": "1",
            "format": "json",
        }
        headers: dict[str, str] = {"User-Agent": _USER_AGENT}

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(
                _API_URL, params=params, headers=headers
            ) as response:
                status: int = response.status
                if status != 200:
                    body: str = await response.text()
                    logger.warning(
                        "wikipedia_api_error",
                        status=status, body=body[:300],
                    )
                    raise WikipediaError(
                        f"Wikipedia API returned {status}: {body[:200]}"
                    )
                raw: dict[str, Any] = await response.json()

        has_links: bool = self._parse_response(raw)
        logger.info(
            "wikipedia_checked",
            domain=domain, has_links=has_links,
        )
        return has_links

    @staticmethod
    def _parse_response(raw: dict[str, Any]) -> bool:
        """Parse Wikipedia exturlusage response."""
        assert isinstance(raw, dict), "response must be a dict"

        query: dict[str, Any] = raw.get("query", {})
        assert isinstance(query, dict), "query must be a dict"

        ext_usage: list[dict[str, Any]] = query.get("exturlusage", [])
        assert isinstance(ext_usage, list), "exturlusage must be a list"

        return len(ext_usage) > 0

    async def check_batch(
        self, domains: list[str],
    ) -> dict[str, bool]:
        """Check Wikipedia links for multiple domains.

        Sequential to respect rate limits. Max 50 per call.

        Args:
            domains: List of domains to check.

        Returns:
            Dict mapping domain -> has_wikipedia_links.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert len(domains) <= _MAX_BATCH_SIZE, (
            f"batch too large: {len(domains)} > {_MAX_BATCH_SIZE}"
        )

        results: dict[str, bool] = {}
        for domain in domains:
            try:
                results[domain] = await self.has_wikipedia_links(domain)
            except WikipediaError:
                results[domain] = False
                logger.warning("wikipedia_batch_error", domain=domain)

        assert isinstance(results, dict), "results must be a dict"
        return results

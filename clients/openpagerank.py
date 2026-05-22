"""Open PageRank API client — FREE bulk domain authority lookups.

Endpoint: GET https://openpagerank.com/api/v1.0/getPageRank
Auth: API-OPR header (free key from domcop.com)
Batch: Up to 100 domains per request
Rate limit: 10K requests/hour (4.3M domains/day)
Data: Common Crawl + Common Search, updated quarterly.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_API_URL: Final[str] = "https://openpagerank.com/api/v1.0/getPageRank"
_TIMEOUT_SECONDS: Final[int] = 20
_MAX_BATCH_SIZE: Final[int] = 100


class OpenPageRankError(Exception):
    """Raised when Open PageRank API returns an error."""


@dataclass(frozen=True)
class PageRankResult:
    """PageRank result for a single domain.

    Attributes:
        domain: The queried domain.
        page_rank_integer: Integer PageRank (0-10).
        page_rank_decimal: Decimal PageRank (0.0-10.0).
        rank: Global rank position (0 = unranked).
        status_code: HTTP status from OPR for this domain (200 = found).
    """

    domain: str
    page_rank_integer: int
    page_rank_decimal: float
    rank: int
    status_code: int

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) > 0, (
            "domain must be non-empty string"
        )
        assert 0 <= self.page_rank_integer <= 10, (
            f"page_rank_integer must be 0-10, got: {self.page_rank_integer}"
        )


class OpenPageRankClient:
    """Client for Open PageRank bulk domain lookups.

    Args:
        settings: Pipeline settings (needs openpagerank_api_key).
        mock: If True, return synthetic data for testing.
    """

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_key: str = settings.openpagerank_api_key
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_pagerank(
        self, domains: list[str],
    ) -> list[PageRankResult]:
        """Get PageRank for up to 100 domains in a single batch.

        Args:
            domains: List of domain names (max 100).

        Returns:
            List of PageRankResult, one per domain.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert 0 < len(domains) <= _MAX_BATCH_SIZE, (
            f"batch size must be 1-{_MAX_BATCH_SIZE}, got {len(domains)}"
        )
        assert all(isinstance(d, str) and "." in d for d in domains), (
            "all entries must be valid domain strings"
        )

        if self._mock:
            return self._mock_results(domains)

        return await self._fetch_live(domains)

    async def _fetch_live(
        self, domains: list[str],
    ) -> list[PageRankResult]:
        """Execute live API request to Open PageRank."""
        assert len(self._api_key) > 0, (
            "openpagerank_api_key must be set in .env"
        )
        assert len(domains) > 0, "domains must not be empty"

        headers: dict[str, str] = {"API-OPR": self._api_key}
        params: list[tuple[str, str]] = [
            ("domains[]", d) for d in domains
        ]

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(
                _API_URL, headers=headers, params=params
            ) as response:
                status: int = response.status
                if status != 200:
                    body: str = await response.text()
                    logger.error(
                        "openpagerank_api_error",
                        status=status, body=body[:500],
                    )
                    raise OpenPageRankError(
                        f"Open PageRank returned {status}: {body[:200]}"
                    )
                raw: dict[str, Any] = await response.json()

        results: list[PageRankResult] = self._parse_response(raw)
        assert isinstance(results, list), "results must be a list"
        logger.info(
            "openpagerank_fetched",
            count=len(results),
            nonzero=sum(1 for r in results if r.page_rank_integer > 0),
        )
        return results

    @staticmethod
    def _parse_response(raw: dict[str, Any]) -> list[PageRankResult]:
        """Parse OPR JSON response into typed results."""
        assert isinstance(raw, dict), "response must be a dict"
        assert "response" in raw, "response must contain 'response' key"

        items: list[dict[str, Any]] = raw["response"]
        assert isinstance(items, list), "response items must be a list"

        results: list[PageRankResult] = []
        for i, item in enumerate(items):
            if i >= _MAX_BATCH_SIZE:
                break
            domain: str = item.get("domain", "")
            if not domain:
                continue
            results.append(PageRankResult(
                domain=domain,
                page_rank_integer=int(item.get("page_rank_integer", 0) or 0),
                page_rank_decimal=float(item.get("page_rank_decimal", 0.0) or 0.0),
                rank=int(item.get("rank", 0) or 0),
                status_code=int(item.get("status_code", 0) or 0),
            ))

        return results

    @staticmethod
    def _mock_results(domains: list[str]) -> list[PageRankResult]:
        """Generate synthetic PageRank results for testing."""
        assert isinstance(domains, list), "domains must be a list"
        results: list[PageRankResult] = []
        for domain in domains:
            # Known high-authority domains get realistic scores
            if domain in ("github.com", "wikipedia.org", "google.com"):
                pr = 8
            elif domain in ("reddit.com", "medium.com", "bbc.com"):
                pr = 7
            else:
                pr = 0
            results.append(PageRankResult(
                domain=domain,
                page_rank_integer=pr,
                page_rank_decimal=float(pr),
                rank=1000 if pr > 0 else 0,
                status_code=200,
            ))
        return results

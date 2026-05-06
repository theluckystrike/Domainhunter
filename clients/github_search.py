"""GitHub Code Search API client for domain mention discovery.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FIXTURE_PATH: str = str(
    Path(__file__).parent.parent / "tests" / "fixtures" / "github_search_sample.json"
)
_BASE_URL: str = "https://api.github.com/search/code"
_TIMEOUT_SECONDS: int = 10
_PER_PAGE: int = 10


class GitHubSearchError(Exception):
    """Raised when GitHub Search API returns an error."""


class GitHubSearchClient:
    """Client for GitHub code search to find domain mentions."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._token: str = settings.github_token
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def search_domain_mentions(self, domain: str) -> int:
        """Search GitHub code for mentions of a domain.

        Args:
            domain: Target domain name to search for.

        Returns:
            Total count of code files mentioning the domain.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return await self._load_mock_data(domain)

        return await self._fetch_live(domain)

    async def _fetch_live(self, domain: str) -> int:
        """Execute live GitHub code search."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        params: dict[str, str | int] = {
            "q": f"{domain}+in:file",
            "per_page": _PER_PAGE,
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(
                _BASE_URL, headers=headers, params=params
            ) as response:
                status: int = response.status
                if status == 403:
                    logger.warning(
                        "github_search_rate_limited", domain=domain,
                    )
                    raise GitHubSearchError(
                        "GitHub search rate limited"
                    )
                if status != 200:
                    body: str = await response.text()
                    logger.error(
                        "github_search_error",
                        status=status, body=body[:500],
                    )
                    raise GitHubSearchError(
                        f"GitHub search returned {status}: {body[:200]}"
                    )
                raw_data: dict[str, Any] = await response.json()

        total_count: int = self._extract_count(raw_data)
        assert isinstance(total_count, int), "total_count must be an int"
        assert total_count >= 0, "total_count must be non-negative"
        logger.info(
            "github_search_fetched",
            domain=domain, total_count=total_count,
        )
        return total_count

    @staticmethod
    def _extract_count(raw_data: dict[str, Any]) -> int:
        """Extract total_count from GitHub search response."""
        assert isinstance(raw_data, dict), "raw_data must be a dict"
        assert "total_count" in raw_data, (
            "response must contain total_count"
        )

        total: int = raw_data["total_count"]
        assert isinstance(total, int), "total_count must be an integer"
        return total

    async def _load_mock_data(self, domain: str) -> int:
        """Load fixture data or return 0 for unknown domains."""
        assert isinstance(domain, str), "domain must be a string"

        fixture_path: Path = Path(_FIXTURE_PATH)
        if not fixture_path.exists():
            return 0

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: dict[str, Any] = json.loads(raw_text)
        total: int = self._extract_count(raw_data)
        assert isinstance(total, int), "mock total must be an int"
        return total

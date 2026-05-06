"""Google Custom Search Engine client for indexed page counts.

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
    Path(__file__).parent.parent / "tests" / "fixtures" / "google_cse_sample.json"
)
_BASE_URL: str = "https://customsearch.googleapis.com/customsearch/v1"
_TIMEOUT_SECONDS: int = 10
_DAILY_HARD_CAP: int = 95


class GoogleCSEError(Exception):
    """Raised when Google CSE API returns an error."""


class GoogleCSEQuotaExhausted(GoogleCSEError):
    """Raised when daily quota is exhausted."""


class GoogleCSEClient:
    """Client for Google Custom Search Engine API with daily quota tracking."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_key: str = settings.google_cse_api_key
        self._cx: str = settings.google_cse_cx
        self._mock: bool = mock
        self._daily_usage: int = 0
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @property
    def daily_usage(self) -> int:
        """Current daily API usage count."""
        assert isinstance(self._daily_usage, int), "usage must be int"
        assert self._daily_usage >= 0, "usage must be non-negative"
        return self._daily_usage

    def reset_daily_usage(self) -> None:
        """Reset daily usage counter (call at midnight)."""
        assert isinstance(self._daily_usage, int), "usage must be int before reset"
        self._daily_usage = 0
        assert self._daily_usage == 0, "usage must be reset to 0"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_indexed_pages(self, domain: str) -> int:
        """Get approximate count of indexed pages for a domain.

        Args:
            domain: Target domain name (e.g., 'example.com').

        Returns:
            Approximate number of indexed pages.

        Raises:
            GoogleCSEQuotaExhausted: If daily quota cap is reached.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._daily_usage >= _DAILY_HARD_CAP:
            raise GoogleCSEQuotaExhausted(
                f"Daily quota cap reached: {self._daily_usage}/{_DAILY_HARD_CAP}"
            )

        if self._mock:
            return await self._load_mock_data()

        return await self._fetch_live(domain)

    async def _fetch_live(self, domain: str) -> int:
        """Execute live Google CSE search."""
        assert isinstance(domain, str), "domain must be a string"
        assert self._daily_usage < _DAILY_HARD_CAP, "quota must not be exhausted"

        params: dict[str, str] = {
            "key": self._api_key,
            "cx": self._cx,
            "q": f"site:{domain}",
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(_BASE_URL, params=params) as response:
                self._daily_usage += 1
                status: int = response.status
                if status != 200:
                    body: str = await response.text()
                    logger.error(
                        "google_cse_api_error",
                        status=status, body=body[:500],
                    )
                    raise GoogleCSEError(
                        f"Google CSE API returned {status}: {body[:200]}"
                    )
                raw_data: dict[str, Any] = await response.json()

        total: int = self._extract_total(raw_data)
        assert isinstance(total, int), "total must be an int"
        assert total >= 0, "total must be non-negative"
        logger.info(
            "google_cse_fetched",
            domain=domain, total=total, usage=self._daily_usage,
        )
        return total

    @staticmethod
    def _extract_total(raw_data: dict[str, Any]) -> int:
        """Extract total results count from CSE response."""
        assert isinstance(raw_data, dict), "raw_data must be a dict"
        assert "searchInformation" in raw_data or "queries" in raw_data, (
            "response must contain search info"
        )

        search_info: dict[str, Any] = raw_data.get("searchInformation", {})
        total_str: str = search_info.get("totalResults", "0")
        total: int = int(total_str)

        assert isinstance(total, int), "total must be an int"
        return total

    async def _load_mock_data(self) -> int:
        """Load fixture data for testing."""
        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), f"Fixture not found: {_FIXTURE_PATH}"

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: dict[str, Any] = json.loads(raw_text)
        total: int = self._extract_total(raw_data)

        self._daily_usage += 1
        assert isinstance(total, int), "mock total must be an int"
        return total

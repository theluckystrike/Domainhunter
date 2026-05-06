"""CatchDoms API client for expired domain discovery with scoring.

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
    Path(__file__).parent.parent / "tests" / "fixtures" / "catchdoms_sample.json"
)
_BASE_URL: str = "https://catchdoms.com/api/domains"
_TIMEOUT_SECONDS: int = 15
_MAX_PAGES: int = 10
_PER_PAGE: int = 100


class CatchDomsError(Exception):
    """Raised when CatchDoms API returns an error."""


class CatchDomsClient:
    """Client for CatchDoms expired domain marketplace API."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_key: str = settings.catchdoms_api_key
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def fetch_domains(self, score_min: int = 40) -> list[dict[str, Any]]:
        """Fetch scored expired domains from CatchDoms.

        Args:
            score_min: Minimum domain score filter (0-100).

        Returns:
            List of domain dicts with score, DA, backlinks, etc.
        """
        assert isinstance(score_min, int), "score_min must be an int"
        assert 0 <= score_min <= 100, f"score_min must be 0-100, got {score_min}"

        if self._mock:
            return await self._load_mock_data(score_min)

        return await self._fetch_all_pages(score_min)

    async def _fetch_all_pages(self, score_min: int) -> list[dict[str, Any]]:
        """Paginate through all available domain pages."""
        assert isinstance(score_min, int), "score_min must be an int"
        assert 0 <= score_min <= 100, "score_min must be 0-100"

        all_domains: list[dict[str, Any]] = []
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            for page_num in range(1, _MAX_PAGES + 1):
                params: dict[str, str | int] = {
                    "score_min": score_min,
                    "has_backlinks": 1,
                    "per_page": _PER_PAGE,
                    "page": page_num,
                }
                async with session.get(
                    _BASE_URL, headers=headers, params=params
                ) as response:
                    status: int = response.status
                    if status != 200:
                        body: str = await response.text()
                        logger.error(
                            "catchdoms_api_error",
                            status=status, body=body[:500], page=page_num,
                        )
                        raise CatchDomsError(
                            f"CatchDoms API returned {status}: {body[:200]}"
                        )
                    raw_data: dict[str, Any] = await response.json()

                page_domains, has_next = self._parse_page(raw_data)
                all_domains.extend(page_domains)

                if not has_next:
                    break

        assert isinstance(all_domains, list), "result must be a list"
        assert all(isinstance(d, dict) for d in all_domains[:100]), (
            "all entries must be dicts"
        )
        logger.info("catchdoms_fetched", total=len(all_domains))
        return all_domains

    def _parse_page(
        self, response: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Parse a single page response from CatchDoms.

        Args:
            response: Raw JSON response dict for one page.

        Returns:
            Tuple of (domain_list, has_next_page).
        """
        assert isinstance(response, dict), "response must be a dict"
        assert "data" in response, "response must contain 'data' key"

        data: list[dict[str, Any]] = response["data"]
        assert isinstance(data, list), "data must be a list"

        # Support both old format (page/last_page) and new format (meta/links)
        meta: dict[str, Any] = response.get("meta", {})
        links: dict[str, Any] = response.get("links", {})
        current_page: int = meta.get("page", response.get("page", 1))
        last_page: int = meta.get("last_page", response.get("last_page", 1))
        has_next_link: bool = links.get("next") is not None if links else False
        has_next: bool = has_next_link or current_page < last_page

        return data, has_next

    async def _load_mock_data(self, score_min: int) -> list[dict[str, Any]]:
        """Load fixture data for testing."""
        assert isinstance(score_min, int), "score_min must be an int"

        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), f"Fixture not found: {_FIXTURE_PATH}"

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: dict[str, Any] = json.loads(raw_text)

        page_domains, _ = self._parse_page(raw_data)
        filtered: list[dict[str, Any]] = [
            d for d in page_domains if d.get("score", 0) >= score_min
        ]
        assert isinstance(filtered, list), "filtered result must be a list"
        return filtered

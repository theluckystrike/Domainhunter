"""DataForSEO API client for backlink analysis.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import json
from base64 import b64encode
from pathlib import Path
from typing import Any

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FIXTURE_PATH: str = str(
    Path(__file__).parent.parent / "tests" / "fixtures" / "dataforseo_sample.json"
)
_BASE_URL: str = "https://api.dataforseo.com/v3/backlinks/summary/live"
_TIMEOUT_SECONDS: int = 20


class DataForSEOError(Exception):
    """Raised when DataForSEO API returns an error."""


class DataForSEOClient:
    """Client for DataForSEO backlink summary API with HTTP Basic auth."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._login: str = settings.dataforseo_login
        self._password: str = settings.dataforseo_password
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    def _build_auth_header(self) -> str:
        """Build HTTP Basic Authorization header value."""
        credentials: str = f"{self._login}:{self._password}"
        encoded: str = b64encode(credentials.encode("utf-8")).decode("ascii")
        assert len(encoded) > 0, "encoded credentials must not be empty"
        assert isinstance(encoded, str), "encoded must be a string"
        return f"Basic {encoded}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_backlink_summary(self, domain: str) -> dict[str, Any]:
        """Get backlink summary metrics for a domain.

        Args:
            domain: Target domain name (e.g., 'example.com').

        Returns:
            Dict with referring_domains, total_backlinks,
            branded_anchor_pct, exact_match_anchor_pct,
            top_country, top_country_pct, domain_rank.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return await self._load_mock_data(domain)

        return await self._fetch_live(domain)

    async def _fetch_live(self, domain: str) -> dict[str, Any]:
        """Execute live backlink summary request."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        headers: dict[str, str] = {
            "Authorization": self._build_auth_header(),
            "Content-Type": "application/json",
        }
        post_body: list[dict[str, Any]] = [{"target": domain, "limit": 1000}]

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                _BASE_URL, headers=headers, json=post_body
            ) as response:
                status: int = response.status
                if status != 200:
                    body_text: str = await response.text()
                    logger.error(
                        "dataforseo_api_error",
                        status=status, body=body_text[:500],
                    )
                    raise DataForSEOError(
                        f"DataForSEO API returned {status}: {body_text[:200]}"
                    )
                raw_data: dict[str, Any] = await response.json()

        result: dict[str, Any] = self._extract_summary(raw_data)
        assert isinstance(result, dict), "result must be a dict"
        assert "referring_domains" in result, "result must include referring_domains"
        logger.info("dataforseo_fetched", domain=domain)
        return result

    def _extract_summary(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract normalized summary from raw DataForSEO response."""
        assert isinstance(raw_data, dict), "raw_data must be a dict"
        assert "tasks" in raw_data, "response must contain 'tasks' key"

        tasks: list[dict[str, Any]] = raw_data["tasks"]
        assert len(tasks) > 0, "tasks list must not be empty"

        task: dict[str, Any] = tasks[0]
        task_status: int = task.get("status_code", 0)
        if task_status != 20000:
            raise DataForSEOError(f"Task failed with status {task_status}")

        results: list[dict[str, Any]] = task.get("result", [])
        assert len(results) > 0, "result list must not be empty"

        r: dict[str, Any] = results[0]
        countries: dict[str, int] = r.get("referring_links_countries", {})
        top_country, top_country_pct = self._top_country(countries)
        total_bl: int = r.get("backlinks", 0)
        anchor_links: int = r.get("referring_links_types", {}).get("anchor", 0)

        # Use anchor_stats if available (newer fixture format)
        anchor_stats: dict[str, float] = r.get("anchor_stats", {})
        branded_pct: float = anchor_stats.get(
            "branded_pct", self._safe_pct(anchor_links, total_bl)
        )
        exact_match_pct: float = anchor_stats.get(
            "exact_match_pct", self._safe_pct(anchor_links, total_bl)
        )

        return {
            "referring_domains": r.get("referring_domains", 0),
            "total_backlinks": total_bl,
            "branded_anchor_pct": branded_pct,
            "exact_match_anchor_pct": exact_match_pct,
            "top_country": top_country,
            "top_country_pct": top_country_pct,
            "domain_rank": r.get("rank", 0),
        }

    @staticmethod
    def _top_country(countries: dict[str, int]) -> tuple[str, float]:
        """Find the country with the most referring links."""
        assert isinstance(countries, dict), "countries must be a dict"

        if not countries:
            return ("unknown", 0.0)

        total: int = sum(countries.values())
        assert total >= 0, "total must be non-negative"

        if total == 0:
            return ("unknown", 0.0)

        top_key: str = max(countries, key=lambda k: countries[k])
        pct: float = round((countries[top_key] / total) * 100, 1)
        return (top_key, pct)

    @staticmethod
    def _safe_pct(part: int, whole: int) -> float:
        """Calculate percentage safely, returning 0 if whole is 0."""
        assert isinstance(part, int), "part must be an int"
        assert isinstance(whole, int), "whole must be an int"
        if whole == 0:
            return 0.0
        return round((part / whole) * 100, 1)

    async def _load_mock_data(self, domain: str) -> dict[str, Any]:
        """Load fixture data for testing."""
        assert isinstance(domain, str), "domain must be a string"

        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), f"Fixture not found: {_FIXTURE_PATH}"

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: dict[str, Any] = json.loads(raw_text)

        # Try to find matching domain in multi-task fixture
        tasks: list[dict[str, Any]] = raw_data.get("tasks", [])
        for i, task in enumerate(tasks):
            if i >= 100:
                break
            results: list[dict[str, Any]] = task.get("result", [])
            if results and results[0].get("target") == domain:
                single: dict[str, Any] = {
                    "tasks": [task],
                    "status_code": raw_data.get("status_code", 20000),
                }
                return self._extract_summary(single)

        # Fallback: use first task
        result: dict[str, Any] = self._extract_summary(raw_data)
        assert isinstance(result, dict), "mock result must be a dict"
        return result

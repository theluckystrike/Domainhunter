"""Wayback Machine CDX and Availability API client.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_FIXTURE_PATH: str = str(
    Path(__file__).parent.parent / "tests" / "fixtures" / "wayback_cdx_sample.json"
)
_CDX_URL: str = "https://web.archive.org/cdx/search/cdx"
_AVAILABILITY_URL: str = "https://archive.org/wayback/available"
_TIMEOUT_SECONDS: int = 30
_RATE_LIMIT_DELAY: float = 1.0
_MAX_SNAPSHOTS: int = 500
_MAX_CONTENT_LENGTH: int = 500_000


class WaybackError(Exception):
    """Raised when Wayback Machine API returns an error."""


class WaybackClient:
    """Client for Internet Archive Wayback Machine CDX and availability APIs."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
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
    async def get_snapshot_history(
        self, domain: str
    ) -> list[dict[str, str]]:
        """Get CDX snapshot history for a domain.

        Args:
            domain: Target domain name.

        Returns:
            List of snapshot dicts with timestamp, original, statuscode,
            mimetype.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return await self._load_mock_history()

        return await self._fetch_cdx(domain)

    async def _fetch_cdx(self, domain: str) -> list[dict[str, str]]:
        """Fetch CDX data from Wayback Machine."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        params: dict[str, str | int] = {
            "url": domain,
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype",
            "filter": "statuscode:200",
            "collapse": "urlkey",
            "limit": _MAX_SNAPSHOTS,
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(_CDX_URL, params=params) as response:
                status: int = response.status
                if status != 200:
                    body: str = await response.text()
                    logger.error(
                        "wayback_cdx_error",
                        status=status, body=body[:500],
                    )
                    raise WaybackError(
                        f"Wayback CDX returned {status}: {body[:200]}"
                    )
                raw_data: list[list[str]] = await response.json()

        snapshots: list[dict[str, str]] = self._parse_cdx(raw_data)
        assert isinstance(snapshots, list), "snapshots must be a list"
        await asyncio.sleep(_RATE_LIMIT_DELAY)
        logger.info(
            "wayback_cdx_fetched",
            domain=domain, count=len(snapshots),
        )
        return snapshots

    @staticmethod
    def _parse_cdx(raw_data: list[list[str]]) -> list[dict[str, str]]:
        """Parse CDX JSON array into list of dicts."""
        assert isinstance(raw_data, list), "raw_data must be a list"
        assert len(raw_data) >= 1, (
            "CDX response must have at least header row"
        )

        headers: list[str] = raw_data[0]
        assert isinstance(headers, list), "first row must be headers"

        snapshots: list[dict[str, str]] = []
        for i, row in enumerate(raw_data[1:]):
            if i >= _MAX_SNAPSHOTS:
                break
            if len(row) == len(headers):
                snapshot: dict[str, str] = dict(zip(headers, row))
                snapshots.append(snapshot)

        return snapshots

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_availability(
        self, domain: str
    ) -> dict[str, Any] | None:
        """Check if a domain has Wayback snapshots available.

        Args:
            domain: Target domain name.

        Returns:
            Availability dict or None if not archived.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return {
                "url": domain,
                "archived_snapshots": {
                    "closest": {
                        "status": "200",
                        "available": True,
                        "url": (
                            "https://web.archive.org/web/20230101/"
                            + domain
                        ),
                        "timestamp": "20230101000000",
                    }
                },
            }

        return await self._fetch_availability(domain)

    async def _fetch_availability(
        self, domain: str
    ) -> dict[str, Any] | None:
        """Fetch availability data from Wayback."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        params: dict[str, str] = {"url": domain}

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(
                _AVAILABILITY_URL, params=params
            ) as response:
                status: int = response.status
                if status != 200:
                    logger.warning(
                        "wayback_availability_error", status=status,
                    )
                    return None
                raw_data: dict[str, Any] = await response.json()

        await asyncio.sleep(_RATE_LIMIT_DELAY)
        snapshots: dict[str, Any] = raw_data.get(
            "archived_snapshots", {}
        )
        if not snapshots or not snapshots.get("closest"):
            return None

        assert isinstance(raw_data, dict), "data must be a dict"
        return raw_data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def fetch_snapshot_content(self, url: str) -> str:
        """Fetch the HTML content of an archived snapshot.

        Args:
            url: Full Wayback Machine snapshot URL.

        Returns:
            HTML content string (truncated to max length).
        """
        assert isinstance(url, str), "url must be a string"
        assert url.startswith("http"), (
            f"url must be http(s), got: {url[:50]}"
        )

        if self._mock:
            return "<html><body>Mock archived content</body></html>"

        return await self._fetch_content(url)

    async def _fetch_content(self, url: str) -> str:
        """Fetch raw snapshot content from Wayback."""
        assert isinstance(url, str), "url must be a string"
        assert len(url) > 10, "url must be a valid URL"

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url) as response:
                status: int = response.status
                if status != 200:
                    logger.warning(
                        "wayback_content_error",
                        status=status, url=url[:100],
                    )
                    raise WaybackError(
                        f"Wayback content fetch returned {status}"
                    )
                content: str = await response.text()

        await asyncio.sleep(_RATE_LIMIT_DELAY)
        truncated: str = content[:_MAX_CONTENT_LENGTH]
        assert isinstance(truncated, str), "content must be a string"
        assert len(truncated) >= 0, "content length must be non-negative"
        return truncated

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_snapshot_count(self, domain: str) -> int:
        """Get total number of Wayback snapshots for a domain.

        Uses the lightweight showNumPages=true CDX parameter that returns
        a single integer instead of full snapshot data. Zero snapshots
        means the domain was never a real website = guaranteed DR 0.

        Args:
            domain: Target domain name.

        Returns:
            Number of CDX pages (proxy for snapshot count). 0 = dead domain.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            # Known domains get realistic counts
            if domain in ("github.com", "wikipedia.org", "google.com"):
                return 500
            return 0

        return await self._fetch_snapshot_count(domain)

    async def _fetch_snapshot_count(self, domain: str) -> int:
        """Fetch snapshot page count from Wayback CDX."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        params: dict[str, str] = {
            "url": domain,
            "matchType": "domain",
            "showNumPages": "true",
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(_CDX_URL, params=params) as response:
                status: int = response.status
                if status != 200:
                    logger.warning(
                        "wayback_count_error",
                        domain=domain, status=status,
                    )
                    return 0
                body: str = await response.text()

        await asyncio.sleep(_RATE_LIMIT_DELAY)

        try:
            count: int = int(body.strip())
        except ValueError:
            logger.warning(
                "wayback_count_parse_error",
                domain=domain, body=body[:100],
            )
            return 0

        assert count >= 0, f"count must be non-negative, got: {count}"
        logger.info(
            "wayback_snapshot_count",
            domain=domain, count=count,
        )
        return count

    async def _load_mock_history(self) -> list[dict[str, str]]:
        """Load fixture CDX data for testing."""
        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), (
            f"Fixture not found: {_FIXTURE_PATH}"
        )

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: list[list[str]] = json.loads(raw_text)
        assert isinstance(raw_data, list), "fixture data must be a list"

        snapshots: list[dict[str, str]] = self._parse_cdx(raw_data)
        assert isinstance(snapshots, list), (
            "parsed mock snapshots must be a list"
        )
        return snapshots

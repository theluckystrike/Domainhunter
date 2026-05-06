"""WhoisFreaks API client for expired domain discovery.

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
    Path(__file__).parent.parent / "tests" / "fixtures" / "whoisfreaks_sample.json"
)
_BASE_URL: str = "https://api.whoisfreaks.com/v1.0/whois"
_TIMEOUT_SECONDS: int = 30
_MAX_DOMAINS: int = 10_000


class WhoisFreaksError(Exception):
    """Raised when WhoisFreaks API returns an error."""


class WhoisFreaksClient:
    """Client for WhoisFreaks expired domain feed and WHOIS lookups."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_key: str = settings.whoisfreaks_api_key
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def fetch_expired_domains(self, date: str) -> list[str]:
        """Fetch expired domains for a given date.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            List of expired domain name strings.
        """
        assert isinstance(date, str), "date must be a string"
        assert len(date) == 10 and date[4] == "-" and date[7] == "-", (
            f"date must be YYYY-MM-DD format, got: {date}"
        )

        if self._mock:
            return await self._load_mock_data()

        return await self._fetch_live(date)

    async def _fetch_live(self, date: str) -> list[str]:
        """Execute live API request to WhoisFreaks."""
        assert isinstance(date, str), "date must be a non-empty string"
        assert len(date) > 0, "date must not be empty"

        params: dict[str, str] = {
            "apiKey": self._api_key,
            "whois": "live",
            "date": date,
        }

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(_BASE_URL, params=params) as response:
                status: int = response.status
                if status != 200:
                    body: str = await response.text()
                    logger.error(
                        "whoisfreaks_api_error", status=status, body=body[:500],
                    )
                    raise WhoisFreaksError(
                        f"WhoisFreaks API returned status {status}: {body[:200]}"
                    )
                raw_data: dict[str, Any] = await response.json()

        domains: list[str] = self._parse_domains(raw_data)
        assert isinstance(domains, list), "parsed domains must be a list"
        assert all(isinstance(d, str) for d in domains[:100]), (
            "all domain entries must be strings"
        )
        logger.info("whoisfreaks_fetched", count=len(domains), date=date)
        return domains

    async def _load_mock_data(self) -> list[str]:
        """Load fixture data for testing."""
        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), f"Fixture not found: {_FIXTURE_PATH}"

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        raw_data: dict[str, Any] = json.loads(raw_text)
        assert isinstance(raw_data, dict), "fixture data must be a dict"

        domains: list[str] = self._parse_domains(raw_data)
        assert isinstance(domains, list), "parsed mock domains must be a list"
        return domains

    def _parse_domains(self, raw_data: dict[str, Any]) -> list[str]:
        """Extract domain names from WhoisFreaks API response.

        Args:
            raw_data: Raw JSON response from the API.

        Returns:
            List of domain name strings.
        """
        assert isinstance(raw_data, dict), "raw_data must be a dict"
        has_data: bool = (
            "whois_data" in raw_data
            or "domainList" in raw_data
            or "domains" in raw_data
        )
        assert has_data, (
            "response must contain 'whois_data', 'domainList', or 'domains'"
        )

        domains: list[str] = []

        if "whois_data" in raw_data:
            entries: list[dict[str, Any]] = raw_data["whois_data"]
            for i, entry in enumerate(entries):
                if i >= _MAX_DOMAINS:
                    break
                domain_name: str | None = entry.get("domain_name")
                if domain_name and isinstance(domain_name, str):
                    domains.append(domain_name.lower().strip())
        elif "domains" in raw_data:
            raw_list: list[str] = raw_data["domains"]
            for i, domain in enumerate(raw_list):
                if i >= _MAX_DOMAINS:
                    break
                if isinstance(domain, str) and len(domain) > 0:
                    domains.append(domain.lower().strip())
        elif "domainList" in raw_data:
            raw_list2: list[str] = raw_data["domainList"]
            for i, domain in enumerate(raw_list2):
                if i >= _MAX_DOMAINS:
                    break
                if isinstance(domain, str) and len(domain) > 0:
                    domains.append(domain.lower().strip())

        assert isinstance(domains, list), "result must be a list"
        return domains

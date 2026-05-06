"""Moz Domain Authority checker via Apify actor.

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
    Path(__file__).parent.parent / "tests" / "fixtures" / "moz_sample.json"
)
_ACTOR_URL: str = (
    "https://api.apify.com/v2/acts/seo-scraper~moz-domain-authority-checker/runs"
)
_TIMEOUT_SECONDS: int = 120
_MAX_BATCH_SIZE: int = 10
_MAX_POLL_ITERATIONS: int = 60
_POLL_INTERVAL_SECONDS: float = 2.0


class MozApifyError(Exception):
    """Raised when Moz Apify actor fails."""


class MozApifyClient:
    """Client for Moz DA/PA/spam via Apify actor, with polling."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_token: str = settings.apify_api_token
        self._mock: bool = mock
        self._timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
            total=_TIMEOUT_SECONDS
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get_domain_authority(
        self, domains: list[str]
    ) -> list[dict[str, Any]]:
        """Get DA, PA, and spam score for a batch of domains.

        Args:
            domains: List of domain names (max 10 per batch).

        Returns:
            List of dicts with domain, da, pa, spam_score per domain.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert 0 < len(domains) <= _MAX_BATCH_SIZE, (
            f"batch must be 1-{_MAX_BATCH_SIZE} domains, got {len(domains)}"
        )

        if self._mock:
            return await self._load_mock_data(domains)

        return await self._run_actor(domains)

    async def _run_actor(self, domains: list[str]) -> list[dict[str, Any]]:
        """Start the Apify actor and poll for results."""
        assert isinstance(domains, list), "domains must be a list"
        assert len(domains) > 0, "domains must not be empty"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {"domains": domains}

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                _ACTOR_URL, headers=headers, json=body
            ) as response:
                status: int = response.status
                if status not in (200, 201):
                    err: str = await response.text()
                    logger.error(
                        "moz_apify_start_error",
                        status=status, body=err[:500],
                    )
                    raise MozApifyError(
                        f"Apify actor start failed {status}: {err[:200]}"
                    )
                run_data: dict[str, Any] = await response.json()

            run_id: str = run_data["data"]["id"]
            assert isinstance(run_id, str), "run_id must be a string"

            items: list[dict[str, Any]] = await self._poll_run(
                session, run_id, headers
            )

        results: list[dict[str, Any]] = self._normalize_results(items)
        assert isinstance(results, list), "results must be a list"
        assert len(results) > 0, "must have at least one result"
        logger.info("moz_apify_fetched", count=len(results))
        return results

    async def _poll_run(
        self,
        session: aiohttp.ClientSession,
        run_id: str,
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Poll Apify run until complete, with bounded iterations."""
        assert isinstance(run_id, str), "run_id must be a string"
        assert len(run_id) > 0, "run_id must not be empty"

        dataset_url: str = (
            f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"
        )

        for iteration in range(_MAX_POLL_ITERATIONS):
            run_url: str = f"https://api.apify.com/v2/actor-runs/{run_id}"
            async with session.get(run_url, headers=headers) as resp:
                if resp.status != 200:
                    raise MozApifyError(
                        f"Poll failed with status {resp.status}"
                    )
                run_info: dict[str, Any] = await resp.json()

            run_status: str = run_info.get("data", {}).get("status", "")
            if run_status == "SUCCEEDED":
                break
            if run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise MozApifyError(
                    f"Apify run {run_id} ended: {run_status}"
                )

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        else:
            raise MozApifyError(
                f"Apify run {run_id} did not complete in "
                f"{_MAX_POLL_ITERATIONS} polls"
            )

        async with session.get(dataset_url, headers=headers) as resp:
            if resp.status != 200:
                raise MozApifyError(
                    f"Dataset fetch failed: {resp.status}"
                )
            items: list[dict[str, Any]] = await resp.json()

        assert isinstance(items, list), "dataset items must be a list"
        return items

    @staticmethod
    def _normalize_results(
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Normalize raw Apify actor output to standard format."""
        assert isinstance(items, list), "items must be a list"

        results: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            if i >= _MAX_BATCH_SIZE:
                break
            results.append({
                "domain": item.get("domain", ""),
                "da": item.get("domainAuthority", item.get("da", 0)),
                "pa": item.get("pageAuthority", item.get("pa", 0)),
                "spam_score": item.get(
                    "spamScore", item.get("spam_score", 0)
                ),
            })

        assert isinstance(results, list), "normalized results must be a list"
        return results

    async def _load_mock_data(
        self, domains: list[str]
    ) -> list[dict[str, Any]]:
        """Load fixture data for testing."""
        assert isinstance(domains, list), "domains must be a list"

        fixture_path: Path = Path(_FIXTURE_PATH)
        assert fixture_path.exists(), f"Fixture not found: {_FIXTURE_PATH}"

        raw_text: str = fixture_path.read_text(encoding="utf-8")
        items: list[dict[str, Any]] = json.loads(raw_text)
        results: list[dict[str, Any]] = self._normalize_results(items)

        # Filter to only requested domains if possible
        requested_set: set[str] = set(domains)
        filtered: list[dict[str, Any]] = [
            r for r in results if r["domain"] in requested_set
        ]
        if not filtered:
            filtered = results[:len(domains)]

        assert isinstance(filtered, list), "filtered mock must be a list"
        return filtered

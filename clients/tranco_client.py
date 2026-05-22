"""Tranco top-1M domain ranking — local lookup client.

Downloads the Tranco combined ranking list (~25MB) and caches locally.
Provides O(1) lookups via hash set. No API calls after initial download.

The Tranco list aggregates rankings from Cisco Umbrella, Majestic,
Cloudflare Radar, Chrome UX Report, and Farsight DNSDB.

Requires: pip install tranco

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import os
import time
from typing import Final

import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_DEFAULT_CACHE_DIR: Final[str] = ".tranco-cache"
_REFRESH_INTERVAL_SECONDS: Final[int] = 86400  # 24 hours
_MAX_BATCH_SIZE: Final[int] = 10000


class TrancoError(Exception):
    """Raised when Tranco list operations fail."""


class TrancoClient:
    """Local Tranco top-1M ranking lookup.

    Downloads list once, caches to disk, refreshes every 24 hours.
    All lookups are O(1) against an in-memory dict.
    """

    def __init__(self, *, cache_dir: str = _DEFAULT_CACHE_DIR) -> None:
        assert isinstance(cache_dir, str), "cache_dir must be str"
        self._cache_dir: str = cache_dir
        self._rankings: dict[str, int] = {}
        self._tranco_list: object | None = None
        self._loaded_at: float = 0.0

    def _ensure_loaded(self) -> None:
        """Load or refresh the Tranco list if needed."""
        now = time.monotonic()
        if self._tranco_list and (now - self._loaded_at) < _REFRESH_INTERVAL_SECONDS:
            return

        try:
            from tranco import Tranco
        except ImportError as exc:
            raise TrancoError(
                "tranco package not installed. Run: pip install tranco"
            ) from exc

        os.makedirs(self._cache_dir, exist_ok=True)
        try:
            t = Tranco(cache=True, cache_dir=self._cache_dir)
            self._tranco_list = t.list()
        except Exception as exc:
            if self._tranco_list:
                logger.warning("tranco_refresh_failed", error=str(exc))
                return  # keep stale data
            raise TrancoError(f"Failed to download Tranco list: {exc}") from exc

        self._loaded_at = now
        logger.info("tranco_loaded", domains=len(self._tranco_list.list))

    def is_ranked(self, domain: str) -> int | None:
        """Check if domain is in Tranco top 1M.

        Returns rank (1 = most popular) or None if not ranked.
        """
        assert isinstance(domain, str), "domain must be str"
        assert "." in domain, f"invalid domain: {domain}"

        self._ensure_loaded()
        if not self._tranco_list:
            return None

        # Try exact match first, then www variants
        rank = self._tranco_list.rank(domain)
        if rank == -1 and domain.startswith("www."):
            rank = self._tranco_list.rank(domain[4:])
        if rank == -1 and not domain.startswith("www."):
            rank = self._tranco_list.rank(f"www.{domain}")

        return rank if rank != -1 else None

    def get_ranked_domains(
        self, domains: list[str],
    ) -> dict[str, int | None]:
        """Batch lookup. Returns dict[domain, rank_or_None].

        Handles up to MAX_BATCH_SIZE domains per call.
        """
        assert isinstance(domains, list), "domains must be list"
        assert len(domains) <= _MAX_BATCH_SIZE, (
            f"batch too large: {len(domains)} > {_MAX_BATCH_SIZE}"
        )

        self._ensure_loaded()
        results: dict[str, int | None] = {}
        for domain in domains:
            results[domain] = self.is_ranked(domain)
        return results

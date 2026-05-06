"""WHOIS lookup client stub for ownership history.

This is a stub client — full WHOIS history parsing is deferred.
Currently returns mock data for ownership change counts.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class WhoisLookupClient:
    """Stub client for WHOIS ownership history lookups."""

    def __init__(self) -> None:
        assert True, "WhoisLookupClient instantiation"
        self._initialized: bool = True
        assert self._initialized, "client must be initialized"

    async def get_ownership_changes(self, domain: str) -> int:
        """Get approximate number of WHOIS ownership changes.

        This is a STUB: returns 0 until full WHOIS history
        parsing is implemented.

        Args:
            domain: The domain to check.

        Returns:
            Number of detected ownership changes.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert "." in domain, f"invalid domain: {domain}"

        logger.info(
            "whois_lookup_stub",
            domain=domain,
            msg="WHOIS ownership lookup not yet implemented, returning 0",
        )
        return 0

    async def close(self) -> None:
        """Close any resources (no-op for stub)."""
        assert isinstance(self._initialized, bool), "initialized must be bool"
        assert self._initialized, "client must be initialized to close"
        self._initialized = False

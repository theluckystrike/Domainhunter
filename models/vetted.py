"""VettedDomain — frozen dataclass output from SENTINEL agent.

Represents a domain that has passed SEO quality vetting.
NASA Rule 2: frozen=True prevents mutation after creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VettedDomain:
    """Immutable domain that passed SENTINEL SEO vetting."""

    domain: str
    tld: str
    source: str
    discovered_at: datetime
    run_id: str

    # SEO metrics from Moz
    domain_authority: int
    page_authority: int
    spam_score: float

    # Backlink metrics from DataForSEO
    referring_domains: int
    backlinks_total: int
    dofollow_ratio: float

    # Google index status
    indexed_pages: int

    # Niche relevance carried from SCOUT
    niche_keyword_hits: tuple[str, ...] = ()
    niche_relevance_score: float = 0.0

    # Flags (warnings that don't kill, but inform)
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.domain, str), "domain must be a string"
        assert len(self.domain) >= 4, f"domain too short: {self.domain}"
        assert "." in self.domain, f"domain must contain a dot: {self.domain}"
        assert isinstance(self.domain_authority, int), "DA must be int"
        assert 0 <= self.domain_authority <= 100, (
            f"DA out of range: {self.domain_authority}"
        )
        assert 0 <= self.page_authority <= 100, (
            f"PA out of range: {self.page_authority}"
        )
        assert 0.0 <= self.spam_score <= 100.0, (
            f"spam_score out of range: {self.spam_score}"
        )
        assert self.referring_domains >= 0, "referring_domains must be >= 0"
        assert self.indexed_pages >= 0, "indexed_pages must be >= 0"

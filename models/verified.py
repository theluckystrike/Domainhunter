"""VerifiedDomain — frozen dataclass output from ARCHIVIST agent.

Represents a domain that has passed historical verification.
NASA Rule 2: frozen=True prevents mutation after creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VerifiedDomain:
    """Immutable domain that passed ARCHIVIST history verification."""

    domain: str
    tld: str
    source: str
    discovered_at: datetime
    run_id: str

    # SEO metrics carried from SENTINEL
    domain_authority: int
    page_authority: int
    spam_score: float
    referring_domains: int
    backlinks_total: int
    dofollow_ratio: float
    indexed_pages: int

    # Archive history from ARCHIVIST
    archive_age_years: float
    total_snapshots: int
    first_snapshot_date: datetime | None
    last_snapshot_date: datetime | None
    title_consistency: float
    max_content_gap_months: int
    language_change_detected: bool
    ownership_changes: int

    # Sample titles from Wayback
    sample_titles: tuple[str, ...] = ()

    # Red flags that were detected but below threshold
    red_flags: tuple[str, ...] = ()

    # Niche relevance carried through pipeline
    niche_keyword_hits: tuple[str, ...] = ()
    niche_relevance_score: float = 0.0

    # Flags from SENTINEL carried through
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.domain, str), "domain must be a string"
        assert len(self.domain) >= 4, f"domain too short: {self.domain}"
        assert "." in self.domain, f"domain must contain a dot: {self.domain}"
        assert isinstance(self.archive_age_years, float), "archive_age must be float"
        assert self.archive_age_years >= 0.0, (
            f"archive_age_years must be >= 0: {self.archive_age_years}"
        )
        assert 0.0 <= self.title_consistency <= 1.0, (
            f"title_consistency must be 0-1: {self.title_consistency}"
        )
        assert self.max_content_gap_months >= 0, "content gap must be >= 0"
        assert self.ownership_changes >= 0, "ownership_changes must be >= 0"
        assert self.total_snapshots >= 0, "total_snapshots must be >= 0"

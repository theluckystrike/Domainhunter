"""DomainCandidate — frozen dataclass output from SCOUT agent.

Represents a raw expired domain candidate discovered during scouting.
NASA Rule 2: frozen=True prevents mutation after creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainCandidate:
    """Immutable domain candidate discovered by SCOUT."""

    domain: str
    tld: str
    source: str  # "whoisfreaks" | "catchdoms" | "apify_expireddomains"
    discovered_at: datetime
    run_id: str

    # Optional metadata from discovery source
    expiry_date: datetime | None = None
    estimated_da: int | None = None  # rough DA from source, if available
    registrar: str | None = None
    drop_date: datetime | None = None

    # Niche relevance signal from domain name analysis
    niche_keyword_hits: tuple[str, ...] = ()
    niche_relevance_score: float = 0.0

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.domain, str), "domain must be a string"
        assert len(self.domain) >= 4, f"domain too short: {self.domain}"
        assert "." in self.domain, f"domain must contain a dot: {self.domain}"
        assert isinstance(self.tld, str), "tld must be a string"
        assert self.tld.startswith("."), f"tld must start with dot: {self.tld}"
        assert isinstance(self.source, str), "source must be a string"
        assert len(self.source) > 0, "source must not be empty"
        assert isinstance(self.run_id, str), "run_id must be a string"
        assert len(self.run_id) > 0, "run_id must not be empty"
        assert 0.0 <= self.niche_relevance_score <= 1.0, (
            f"niche_relevance_score must be 0.0-1.0, got {self.niche_relevance_score}"
        )

    @property
    def domain_name(self) -> str:
        """Return domain without TLD."""
        assert "." in self.domain, "domain must contain a dot"
        parts = self.domain.rsplit(".", 1)
        assert len(parts) == 2, f"unexpected domain format: {self.domain}"
        return parts[0]

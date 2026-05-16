"""Startup Reaper data models -- frozen dataclasses for the dead-startup pipeline.

Pipeline stages: DeadStartup -> ResolvedStartup -> ProbedStartup -> ReapedDomain

Each stage enriches the previous with new data from the corresponding agent.
All dataclasses are frozen (immutable) per NASA Power-of-Ten Rule 2.
__post_init__ assertions enforce invariants at construction time.

Sprint 20: Redesigned with explicit field typing, allowed-set validation,
and per-dimension score breakdowns on ReapedDomain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_SECTORS: frozenset[str] = frozenset({
    "ai", "fintech", "healthtech", "biotech", "cleantech",
    "edtech", "crypto", "ecommerce", "logistics", "other",
})

ALLOWED_TIERS: frozenset[str] = frozenset({
    "critical", "high", "medium", "low",
})


@dataclass(frozen=True)
class DeadStartup:
    """Stage 1: Raw harvest output from any dead-startup source.

    Represents a company identified as dead/shut-down before any domain
    resolution or RDAP probing has occurred.  The domain field may be None
    when the source only provides a company name without a known website.

    Fields
    ------
    name : str
        Company name (non-empty).
    domain : str | None
        Primary domain if already known, otherwise None.
    funding_usd : float
        Total funding raised in USD (>= 0).
    sector : str
        Industry vertical, must be in ALLOWED_SECTORS.
    source : str
        Provenance tag: ``existing_data``, ``deepseek``, or ``yc_dead``.
    death_year : int | None
        Calendar year the company shut down, if known.
    description : str
        One-line company description.
    """

    name: str
    domain: str | None
    funding_usd: float
    sector: str
    source: str
    death_year: int | None
    description: str

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.name, str) and len(self.name.strip()) > 0, (
            f"name must be a non-empty string, got {self.name!r}"
        )
        assert isinstance(self.funding_usd, (int, float)) and self.funding_usd >= 0, (
            f"funding_usd must be >= 0, got {self.funding_usd}"
        )
        assert self.sector in ALLOWED_SECTORS, (
            f"sector must be one of {sorted(ALLOWED_SECTORS)}, got {self.sector!r}"
        )
        assert isinstance(self.source, str) and len(self.source.strip()) > 0, (
            f"source must be a non-empty string, got {self.source!r}"
        )
        assert isinstance(self.description, str), (
            f"description must be a string, got {type(self.description).__name__}"
        )


@dataclass(frozen=True)
class ResolvedStartup:
    """Stage 2: Dead startup after domain resolution.

    All fields from DeadStartup are carried forward, with ``domain`` now
    required (non-None) and a ``resolution_method`` indicating how the
    domain was discovered or confirmed.

    Fields (additions over DeadStartup)
    ------------------------------------
    domain : str
        Confirmed primary domain (must contain a dot).
    resolution_method : str
        How the domain was resolved: ``field``, ``deepseek``, or ``web``.
    """

    name: str
    domain: str
    funding_usd: float
    sector: str
    source: str
    death_year: int | None
    description: str
    resolution_method: str

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.domain, str) and len(self.domain.strip()) > 0, (
            f"domain must be a non-empty string, got {self.domain!r}"
        )
        assert "." in self.domain, (
            f"domain must contain at least one dot, got {self.domain!r}"
        )
        assert isinstance(self.name, str) and len(self.name.strip()) > 0, (
            f"name must be a non-empty string, got {self.name!r}"
        )
        assert isinstance(self.resolution_method, str) and len(self.resolution_method.strip()) > 0, (
            f"resolution_method must be a non-empty string, got {self.resolution_method!r}"
        )
        assert self.sector in ALLOWED_SECTORS, (
            f"sector must be one of {sorted(ALLOWED_SECTORS)}, got {self.sector!r}"
        )


@dataclass(frozen=True)
class ProbedStartup:
    """Stage 3: Resolved startup after RDAP probe.

    Carries all ResolvedStartup fields plus RDAP results indicating the
    domain's current registration status and drop signals.

    Fields (additions over ResolvedStartup)
    ----------------------------------------
    epp_status : str
        EPP status code from RDAP, e.g. ``pendingDelete``,
        ``clientRenewProhibited``, ``active``, ``404``.
    drop_signal : bool
        True if the domain shows indicators of an imminent drop.
    registrar : str | None
        Current registrar name, if available from RDAP.
    expiry_date : str | None
        Domain expiry date in ISO 8601 format, if available.
    """

    name: str
    domain: str
    funding_usd: float
    sector: str
    source: str
    death_year: int | None
    description: str
    resolution_method: str
    epp_status: str
    drop_signal: bool
    registrar: str | None
    expiry_date: str | None

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.epp_status, str) and len(self.epp_status.strip()) > 0, (
            f"epp_status must be a non-empty string, got {self.epp_status!r}"
        )
        assert isinstance(self.domain, str) and "." in self.domain, (
            f"domain must contain a dot, got {self.domain!r}"
        )
        assert isinstance(self.drop_signal, bool), (
            f"drop_signal must be a bool, got {type(self.drop_signal).__name__}"
        )
        assert self.sector in ALLOWED_SECTORS, (
            f"sector must be one of {sorted(ALLOWED_SECTORS)}, got {self.sector!r}"
        )


@dataclass(frozen=True)
class ReapedDomain:
    """Stage 4: Final scored domain ready for acquisition decision.

    Contains all ProbedStartup fields plus a 9-dimension composite score,
    tier classification, SEO metrics from DataForSEO, and a recommended bid.

    Fields (additions over ProbedStartup)
    --------------------------------------
    reaper_score : float
        Composite score from 0 to 100.
    tier : str
        Priority tier: ``critical``, ``high``, ``medium``, or ``low``.
    funding_score : float
        Score component for startup funding magnitude.
    authority_score : float
        Score component for domain authority / backlink profile.
    drop_certainty_score : float
        Score component for confidence the domain will actually drop.
    editorial_score : float
        Score component for quality of referring editorial links.
    age_score : float
        Score component for domain age.
    niche_score : float
        Score component for niche/sector alignment.
    traffic_score : float
        Score component for estimated organic traffic.
    trademark_score : float
        Score component for trademark risk (higher = less risk).
    recommended_bid : float
        Suggested maximum bid in USD for acquiring the domain.
    domain_rank : int | None
        DataForSEO domain rank, if available.
    referring_domains : int | None
        Count of unique referring domains, if available.
    total_backlinks : int | None
        Total backlink count, if available.
    spam_score : float | None
        Spam score from 0 to 100, if available.
    """

    # -- Inherited from ProbedStartup --
    name: str
    domain: str
    funding_usd: float
    sector: str
    source: str
    death_year: int | None
    description: str
    resolution_method: str
    epp_status: str
    drop_signal: bool
    registrar: str | None
    expiry_date: str | None
    # -- Scoring dimensions --
    reaper_score: float
    tier: str
    funding_score: float
    authority_score: float
    drop_certainty_score: float
    editorial_score: float
    age_score: float
    niche_score: float
    traffic_score: float
    trademark_score: float
    recommended_bid: float
    # -- SEO metrics --
    domain_rank: int | None
    referring_domains: int | None
    total_backlinks: int | None
    spam_score: float | None

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        assert isinstance(self.reaper_score, (int, float)), (
            f"reaper_score must be numeric, got {type(self.reaper_score).__name__}"
        )
        assert 0.0 <= self.reaper_score <= 100.0, (
            f"reaper_score must be 0-100, got {self.reaper_score}"
        )
        assert self.tier in ALLOWED_TIERS, (
            f"tier must be one of {sorted(ALLOWED_TIERS)}, got {self.tier!r}"
        )
        assert isinstance(self.domain, str) and "." in self.domain, (
            f"domain must contain a dot, got {self.domain!r}"
        )
        assert isinstance(self.recommended_bid, (int, float)) and self.recommended_bid >= 0, (
            f"recommended_bid must be >= 0, got {self.recommended_bid}"
        )


def reaped_to_dict(r: ReapedDomain) -> dict[str, Any]:
    """Serialize a ReapedDomain to a JSON-safe dictionary.

    All float values are rounded to 1 decimal place for clean serialization.
    """
    assert isinstance(r, ReapedDomain), "must be ReapedDomain"
    return {
        "name": r.name,
        "domain": r.domain,
        "funding_usd": r.funding_usd,
        "sector": r.sector,
        "source": r.source,
        "death_year": r.death_year,
        "description": r.description,
        "resolution_method": r.resolution_method,
        "epp_status": r.epp_status,
        "drop_signal": r.drop_signal,
        "registrar": r.registrar,
        "expiry_date": r.expiry_date,
        "reaper_score": round(r.reaper_score, 1),
        "tier": r.tier,
        "funding_score": round(r.funding_score, 1),
        "authority_score": round(r.authority_score, 1),
        "drop_certainty_score": round(r.drop_certainty_score, 1),
        "editorial_score": round(r.editorial_score, 1),
        "age_score": round(r.age_score, 1),
        "niche_score": round(r.niche_score, 1),
        "traffic_score": round(r.traffic_score, 1),
        "trademark_score": round(r.trademark_score, 1),
        "recommended_bid": round(r.recommended_bid, 1),
        "domain_rank": r.domain_rank,
        "referring_domains": r.referring_domains,
        "total_backlinks": r.total_backlinks,
        "spam_score": round(r.spam_score, 1) if r.spam_score is not None else None,
    }

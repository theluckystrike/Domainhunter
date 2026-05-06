"""DomainVerdict — frozen dataclass output from ORACLE agent.

Final pipeline output with buy/watch/skip verdict and reasoning.
NASA Rule 2: frozen=True prevents mutation after creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VerdictType(Enum):
    """Possible oracle verdicts for a domain."""

    BUY_NOW = "BUY_NOW"
    WATCH = "WATCH"
    SKIP = "SKIP"


@dataclass(frozen=True)
class ScoreBreakdown:
    """Immutable breakdown of all scoring components."""

    domain_authority_score: float
    backlink_quality_score: float
    niche_relevance_score: float
    archive_integrity_score: float
    social_signal_score: float
    brand_value_score: float
    spam_safety_score: float
    registration_feasibility_score: float

    def __post_init__(self) -> None:
        fields = (
            "domain_authority_score",
            "backlink_quality_score",
            "niche_relevance_score",
            "archive_integrity_score",
            "social_signal_score",
            "brand_value_score",
            "spam_safety_score",
            "registration_feasibility_score",
        )
        assert len(fields) == 8, "ScoreBreakdown must have exactly 8 fields"
        for field_name in fields:
            val = getattr(self, field_name)
            assert 0.0 <= val <= 100.0, f"{field_name} must be 0-100, got {val}"


@dataclass(frozen=True)
class DomainVerdict:
    """Immutable final verdict from ORACLE agent."""

    domain: str
    tld: str
    run_id: str
    judged_at: datetime

    # Verdict
    verdict: VerdictType
    final_score: float  # 0.0-100.0
    confidence: float  # 0.0-1.0

    # Score breakdown
    score_breakdown: ScoreBreakdown

    # AI-generated reasoning
    reasoning: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    recommended_use_cases: tuple[str, ...]

    # Acquisition intel
    estimated_value_usd: float
    registrar_availability: str  # "available" | "backorder" | "auction" | "unknown"
    recommended_registrar: str

    # Key pass-through metrics
    domain_authority: int
    spam_score: float
    spectre_score: float
    years_active: float
    referring_domains: int

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) >= 4, "invalid domain"
        assert isinstance(self.run_id, str) and len(self.run_id) > 0, "invalid run_id"
        assert isinstance(self.verdict, VerdictType), "verdict must be VerdictType"
        assert 0.0 <= self.final_score <= 100.0, (
            f"final_score must be 0-100, got {self.final_score}"
        )
        assert 0.0 <= self.confidence <= 1.0, (
            f"confidence must be 0-1, got {self.confidence}"
        )
        assert isinstance(self.reasoning, str) and len(self.reasoning) > 0, (
            "reasoning must be non-empty string"
        )
        assert self.estimated_value_usd >= 0.0, "estimated_value_usd non-negative"
        assert 0 <= self.domain_authority <= 100, "DA must be 0-100"

    @property
    def is_actionable(self) -> bool:
        """Whether this verdict requires immediate action."""
        assert isinstance(self.verdict, VerdictType), "verdict must be VerdictType"
        result = self.verdict == VerdictType.BUY_NOW
        assert isinstance(result, bool), "is_actionable must return bool"
        return result

    @property
    def summary(self) -> str:
        """One-line verdict summary for reports and alerts."""
        assert isinstance(self.domain, str), "domain must be a string"
        line = (
            f"{self.domain} | {self.verdict.value} | "
            f"Score: {self.final_score:.1f} | "
            f"DA: {self.domain_authority} | "
            f"Value: ${self.estimated_value_usd:,.0f}"
        )
        assert len(line) > 0, "summary must be non-empty"
        return line

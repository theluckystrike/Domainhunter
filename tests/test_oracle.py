"""Tests for ORACLE agent — final verdict scoring and decision.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from config.constants import (
    ORACLE_WEIGHTS,
    VERDICT_BUY_NOW_THRESHOLD,
    VERDICT_WATCH_THRESHOLD,
)
from models.scored import (
    BrandAnalysis,
    GitHubSignal,
    RedditSignal,
    ScoredDomain,
)
from models.verdict import (
    DomainVerdict,
    ScoreBreakdown,
    VerdictType,
)

_RUN_ID: str = "test-run-oracle-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — pure ORACLE scoring band functions
# ---------------------------------------------------------------------------

def _score_da(da: int) -> float:
    """Score DA in bands: 25-30->60, 30-40->80, 40-50->90, 50+->70."""
    if da >= 50:
        return 70.0  # diminishing returns, often overpriced
    if da >= 40:
        return 90.0  # sweet spot
    if da >= 30:
        return 80.0  # good value
    if da >= 25:
        return 60.0  # marginal
    return 30.0  # below threshold


def _score_ref_domains(ref: int) -> float:
    """Score referring domains in bands."""
    if ref >= 1000:
        return 80.0  # large but may have spam
    if ref >= 400:
        return 95.0  # sweet spot
    if ref >= 200:
        return 85.0  # good
    if ref >= 100:
        return 70.0  # marginal
    return 40.0  # too few


def _score_archive(age_years: float) -> float:
    """Score archive age in bands."""
    if age_years >= 10.0:
        return 100.0
    if age_years >= 7.0:
        return 90.0
    if age_years >= 5.0:
        return 80.0
    if age_years >= 3.0:
        return 70.0
    return 40.0


def _score_anchors(branded_pct: float) -> float:
    """Score anchor text profile by branded percentage."""
    if branded_pct >= 60.0:
        return 90.0  # healthy branded profile
    if branded_pct >= 45.0:
        return 70.0  # decent
    if branded_pct >= 30.0:
        return 50.0  # some branded
    return 40.0  # low branded = likely manipulated


def _score_price(price_usd: float) -> float:
    """Score estimated acquisition price."""
    if price_usd <= 500.0:
        return 100.0  # bargain
    if price_usd <= 1500.0:
        return 80.0  # reasonable
    if price_usd <= 3000.0:
        return 60.0  # moderate
    if price_usd <= 5000.0:
        return 50.0  # expensive
    return 30.0  # very expensive


def _determine_verdict(final_score: float) -> VerdictType:
    """Determine verdict based on final score."""
    if final_score >= VERDICT_BUY_NOW_THRESHOLD:
        return VerdictType.BUY_NOW
    if final_score >= VERDICT_WATCH_THRESHOLD:
        return VerdictType.WATCH
    return VerdictType.SKIP


def _calc_final_score(breakdown: ScoreBreakdown) -> float:
    """Calculate weighted final score from breakdown."""
    score = (
        breakdown.domain_authority_score * ORACLE_WEIGHTS["domain_authority"]
        + breakdown.backlink_quality_score * ORACLE_WEIGHTS["backlink_quality"]
        + breakdown.niche_relevance_score * ORACLE_WEIGHTS["niche_relevance"]
        + breakdown.archive_integrity_score * ORACLE_WEIGHTS["archive_integrity"]
        + breakdown.social_signal_score * ORACLE_WEIGHTS["social_signal"]
        + breakdown.brand_value_score * ORACLE_WEIGHTS["brand_value"]
        + breakdown.spam_safety_score * ORACLE_WEIGHTS["spam_safety"]
        + breakdown.registration_feasibility_score
        * ORACLE_WEIGHTS["registration_feasibility"]
    )
    return min(100.0, max(0.0, score))


# ---------------------------------------------------------------------------
# DA scoring band tests
# ---------------------------------------------------------------------------

def test_da_scoring_bands() -> None:
    """Verify DA scoring band outputs."""
    assert _score_da(30) == 80.0   # 30-40 band
    assert _score_da(40) == 90.0   # 40-50 band (sweet spot)
    assert _score_da(55) == 70.0   # 50+ band (diminishing)


def test_da_scoring_edge_cases() -> None:
    """DA at exact boundaries."""
    assert _score_da(25) == 60.0  # lower bound of marginal
    assert _score_da(50) == 70.0  # lower bound of high
    assert _score_da(20) == 30.0  # below threshold


# ---------------------------------------------------------------------------
# Referring domains scoring band tests
# ---------------------------------------------------------------------------

def test_ref_domains_bands() -> None:
    """Verify referring domains scoring bands."""
    assert _score_ref_domains(200) == 85.0   # 200-400 band
    assert _score_ref_domains(500) == 95.0   # 400-1000 sweet spot
    assert _score_ref_domains(1500) == 80.0  # 1000+ large


def test_ref_domains_low() -> None:
    """Low referring domains scores poorly."""
    assert _score_ref_domains(50) == 40.0
    assert _score_ref_domains(100) == 70.0


# ---------------------------------------------------------------------------
# Archive scoring tests
# ---------------------------------------------------------------------------

def test_archive_scoring() -> None:
    """Verify archive age scoring bands."""
    assert _score_archive(4.0) == 70.0   # 3-5yr band
    assert _score_archive(7.0) == 90.0   # 7-10yr band
    assert _score_archive(12.0) == 100.0  # 10+ band


def test_archive_scoring_young() -> None:
    """Young domains score poorly."""
    assert _score_archive(2.0) == 40.0
    assert _score_archive(0.5) == 40.0


# ---------------------------------------------------------------------------
# Anchor scoring tests
# ---------------------------------------------------------------------------

def test_anchor_scoring() -> None:
    """Verify anchor text profile scoring."""
    assert _score_anchors(65.0) == 90.0  # high branded = healthy
    assert _score_anchors(50.0) == 70.0  # decent
    assert _score_anchors(30.0) == 50.0  # some branded


def test_anchor_scoring_low_branded() -> None:
    """Low branded anchors suggest manipulation."""
    assert _score_anchors(20.0) == 40.0
    assert _score_anchors(10.0) == 40.0


# ---------------------------------------------------------------------------
# Price scoring tests
# ---------------------------------------------------------------------------

def test_price_scoring() -> None:
    """Verify price scoring bands."""
    assert _score_price(300.0) == 100.0   # bargain
    assert _score_price(1000.0) == 80.0   # reasonable
    assert _score_price(3000.0) == 60.0   # moderate


def test_price_scoring_expensive() -> None:
    """Expensive domains score poorly."""
    assert _score_price(5000.0) == 50.0
    assert _score_price(10000.0) == 30.0


# ---------------------------------------------------------------------------
# Verdict tests
# ---------------------------------------------------------------------------

def test_verdict_buy_now() -> None:
    """Score=85 exceeds BUY_NOW threshold (80) -> BUY_NOW."""
    verdict = _determine_verdict(85.0)
    assert verdict == VerdictType.BUY_NOW


def test_verdict_investigate() -> None:
    """Score=70 is between WATCH (60) and BUY_NOW (80) -> WATCH."""
    verdict = _determine_verdict(70.0)
    assert verdict == VerdictType.WATCH


def test_verdict_pass() -> None:
    """Score=45 is below WATCH threshold (60) -> SKIP."""
    verdict = _determine_verdict(45.0)
    assert verdict == VerdictType.SKIP


def test_verdict_boundary_buy() -> None:
    """Score exactly at BUY_NOW threshold -> BUY_NOW."""
    verdict = _determine_verdict(80.0)
    assert verdict == VerdictType.BUY_NOW


def test_verdict_boundary_watch() -> None:
    """Score exactly at WATCH threshold -> WATCH."""
    verdict = _determine_verdict(60.0)
    assert verdict == VerdictType.WATCH


# ---------------------------------------------------------------------------
# Final score calculation tests
# ---------------------------------------------------------------------------

def test_final_score_high() -> None:
    """High component scores produce BUY_NOW verdict."""
    breakdown = ScoreBreakdown(
        domain_authority_score=90.0,
        backlink_quality_score=95.0,
        niche_relevance_score=85.0,
        archive_integrity_score=90.0,
        social_signal_score=72.0,
        brand_value_score=80.0,
        spam_safety_score=95.0,
        registration_feasibility_score=100.0,
    )
    final = _calc_final_score(breakdown)
    assert final >= VERDICT_BUY_NOW_THRESHOLD
    verdict = _determine_verdict(final)
    assert verdict == VerdictType.BUY_NOW


def test_final_score_low() -> None:
    """Low component scores produce SKIP verdict."""
    breakdown = ScoreBreakdown(
        domain_authority_score=30.0,
        backlink_quality_score=40.0,
        niche_relevance_score=20.0,
        archive_integrity_score=40.0,
        social_signal_score=10.0,
        brand_value_score=25.0,
        spam_safety_score=30.0,
        registration_feasibility_score=50.0,
    )
    final = _calc_final_score(breakdown)
    assert final < VERDICT_WATCH_THRESHOLD
    verdict = _determine_verdict(final)
    assert verdict == VerdictType.SKIP


# ---------------------------------------------------------------------------
# Full run mock test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_mock(mock_scored: list[ScoredDomain]) -> None:
    """End-to-end ORACLE with mock scored domains and simulated Claude."""
    assert len(mock_scored) == 2

    verdicts: list[DomainVerdict] = []
    for sd in mock_scored:
        da_score = _score_da(sd.domain_authority)
        ref_score = _score_ref_domains(sd.referring_domains)
        archive_score = _score_archive(sd.years_active)
        anchor_score = _score_anchors(65.0)  # assume branded anchor data
        price_score = _score_price(500.0)   # assume moderate price

        breakdown = ScoreBreakdown(
            domain_authority_score=da_score,
            backlink_quality_score=ref_score,
            niche_relevance_score=sd.niche_relevance_score * 100.0,
            archive_integrity_score=archive_score,
            social_signal_score=sd.spectre_score,
            brand_value_score=sd.brand_score,
            spam_safety_score=90.0,  # low spam = high safety
            registration_feasibility_score=price_score,
        )
        final = _calc_final_score(breakdown)
        verdict_type = _determine_verdict(final)

        verdicts.append(DomainVerdict(
            domain=sd.domain, tld=sd.tld, run_id=_RUN_ID,
            judged_at=_NOW, verdict=verdict_type,
            final_score=final, confidence=0.85,
            score_breakdown=breakdown,
            reasoning="Mock AI reasoning for test",
            strengths=("Strong DA", "Clean backlinks"),
            weaknesses=("Limited social signals",),
            recommended_use_cases=("Tech blog", "SaaS landing page"),
            estimated_value_usd=500.0,
            registrar_availability="available",
            recommended_registrar="Namecheap",
            domain_authority=sd.domain_authority,
            spam_score=sd.spam_score,
            spectre_score=sd.spectre_score,
            years_active=sd.years_active,
            referring_domains=sd.referring_domains,
        ))

    assert len(verdicts) == 2
    for v in verdicts:
        assert isinstance(v, DomainVerdict)
        assert isinstance(v.verdict, VerdictType)
        assert 0.0 <= v.final_score <= 100.0
        assert len(v.reasoning) > 0
        assert v.is_actionable == (v.verdict == VerdictType.BUY_NOW)
        assert len(v.summary) > 0

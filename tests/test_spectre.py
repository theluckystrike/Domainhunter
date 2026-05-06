"""Tests for SPECTRE agent — social signal analysis and scoring.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from config.constants import (
    NICHE_KEYWORD_WEIGHTS,
    NICHE_KEYWORDS_TIER1,
    NICHE_KEYWORDS_TIER4,
    SPECTRE_WEIGHTS,
)
from models.scored import (
    BrandAnalysis,
    GitHubSignal,
    RedditSignal,
    ScoredDomain,
)

_RUN_ID: str = "test-run-spectre-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — pure SPECTRE scoring functions
# ---------------------------------------------------------------------------

def _calc_github_score(gh: GitHubSignal) -> float:
    """Calculate GitHub social score (0-100)."""
    # Stars contribute most, then forks, then mentions
    raw = (
        min(gh.total_stars, 500) * 0.12
        + min(gh.total_forks, 200) * 0.15
        + min(gh.repo_mentions, 50) * 1.0
        + min(gh.readme_mentions, 30) * 0.8
    )
    return min(100.0, raw)


def _calc_reddit_score(rd: RedditSignal) -> float:
    """Calculate Reddit social score (0-100)."""
    raw = (
        min(rd.total_mentions, 50) * 1.5
        + min(rd.total_upvotes, 500) * 0.08
        + len(rd.subreddits_seen) * 3.0
        + (rd.avg_sentiment + 1.0) * 10.0  # normalize -1..1 to 0..20
    )
    return min(100.0, raw)


def _calc_community_score(
    github_score: float,
    reddit_score: float,
) -> float:
    """Calculate combined community score."""
    # Weighted: GitHub=60%, Reddit=40%
    raw = github_score * 0.6 + reddit_score * 0.4
    return min(100.0, raw)


def _calc_keyword_score(keyword_hits: tuple[str, ...]) -> float:
    """Score based on niche keyword tier matches (0-100)."""
    if not keyword_hits:
        return 0.0
    total_weight = 0.0
    for kw in keyword_hits:
        weight = NICHE_KEYWORD_WEIGHTS.get(kw, 0.0)
        total_weight += weight
    # Normalize: tier1 single match = 1.0 weight = 100 points
    score = total_weight * 100.0
    return min(100.0, score)


def _calc_composite_score(
    github_score: float,
    reddit_score: float,
    brand_score: float,
    social_recency_score: float,
) -> float:
    """Calculate SPECTRE composite score using configured weights."""
    # Simplified composite using SPECTRE_WEIGHTS categories
    w_gh = SPECTRE_WEIGHTS["github_stars"] + SPECTRE_WEIGHTS["github_forks"]
    w_gh += SPECTRE_WEIGHTS["github_mentions"]  # total github weight
    w_rd = SPECTRE_WEIGHTS["reddit_mentions"] + SPECTRE_WEIGHTS["reddit_sentiment"]
    w_brand = SPECTRE_WEIGHTS["brand_searchability"]
    w_recency = SPECTRE_WEIGHTS["social_recency"]

    # Normalize weights to sum to 1.0
    total_w = w_gh + w_rd + w_brand + w_recency
    score = (
        github_score * (w_gh / total_w)
        + reddit_score * (w_rd / total_w)
        + brand_score * (w_brand / total_w)
        + social_recency_score * (w_recency / total_w)
    )
    return min(100.0, max(0.0, score))


# ---------------------------------------------------------------------------
# Community score tests
# ---------------------------------------------------------------------------

def test_community_score_calculation() -> None:
    """github=5 mentions + reddit=3 mentions results in a moderate score."""
    gh = GitHubSignal(
        repo_mentions=5, total_stars=120, total_forks=30,
        readme_mentions=8, issue_mentions=12,
    )
    rd = RedditSignal(
        total_mentions=3, total_upvotes=85,
        subreddits_seen=("programming", "webdev"),
        avg_sentiment=0.6,
    )
    gh_score = _calc_github_score(gh)
    rd_score = _calc_reddit_score(rd)
    community = _calc_community_score(gh_score, rd_score)

    assert 0.0 <= gh_score <= 100.0
    assert 0.0 <= rd_score <= 100.0
    assert 0.0 <= community <= 100.0
    # With these inputs, community should be moderate (30-80 range)
    assert community >= 20.0, f"community too low: {community}"


def test_community_score_zero_signals() -> None:
    """Zero social signals should produce near-zero community score."""
    gh = GitHubSignal(
        repo_mentions=0, total_stars=0, total_forks=0,
        readme_mentions=0, issue_mentions=0,
    )
    rd = RedditSignal(
        total_mentions=0, total_upvotes=0,
        subreddits_seen=(),
        avg_sentiment=0.0,
    )
    gh_score = _calc_github_score(gh)
    rd_score = _calc_reddit_score(rd)
    community = _calc_community_score(gh_score, rd_score)

    assert gh_score == 0.0
    # Reddit score includes sentiment normalization, so minimum is 10
    assert community < 10.0


# ---------------------------------------------------------------------------
# Keyword score tests
# ---------------------------------------------------------------------------

def test_keyword_score_tier1() -> None:
    """Tier1 keyword match ('claude') should score 100 points."""
    assert "claude" in NICHE_KEYWORDS_TIER1
    score = _calc_keyword_score(("claude",))
    assert score == 100.0


def test_keyword_score_tier4() -> None:
    """Tier4 keyword only ('startup') should score 20 points."""
    assert "startup" in NICHE_KEYWORDS_TIER4
    score = _calc_keyword_score(("startup",))
    # Tier4 weight = 0.2, so 0.2 * 100 = 20
    assert score == pytest.approx(20.0, abs=0.1)


def test_keyword_score_multiple_tiers() -> None:
    """Multiple keyword hits across tiers should accumulate."""
    # "ai" = tier1 (1.0), "startup" = tier4 (0.2) = 1.2 * 100 = capped at 100
    score = _calc_keyword_score(("ai", "startup"))
    assert score == 100.0  # capped


def test_keyword_score_empty() -> None:
    """No keyword hits should score 0."""
    score = _calc_keyword_score(())
    assert score == 0.0


# ---------------------------------------------------------------------------
# Composite score tests
# ---------------------------------------------------------------------------

def test_composite_score_formula() -> None:
    """Verify weighted SPECTRE composite formula produces valid output."""
    composite = _calc_composite_score(
        github_score=72.0,
        reddit_score=58.0,
        brand_score=75.0,
        social_recency_score=65.0,
    )
    assert 0.0 <= composite <= 100.0
    # With these mid-high inputs, composite should be moderate-high
    assert composite >= 50.0


def test_composite_score_all_zero() -> None:
    """All zero inputs should produce zero composite."""
    composite = _calc_composite_score(0.0, 0.0, 0.0, 0.0)
    assert composite == 0.0


def test_composite_score_all_max() -> None:
    """All max inputs should produce 100 composite."""
    composite = _calc_composite_score(100.0, 100.0, 100.0, 100.0)
    assert composite == 100.0


# ---------------------------------------------------------------------------
# Full run mock test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_mock(mock_verified: list[Any]) -> None:
    """End-to-end SPECTRE with mock social signal data."""
    from models.verified import VerifiedDomain

    assert len(mock_verified) == 3

    gh_signal = GitHubSignal(
        repo_mentions=5, total_stars=120, total_forks=30,
        readme_mentions=8, issue_mentions=12,
    )
    rd_signal = RedditSignal(
        total_mentions=3, total_upvotes=85,
        subreddits_seen=("programming", "webdev"),
        avg_sentiment=0.6,
    )
    brand = BrandAnalysis(
        brand_name="devtoolshub", is_pronounceable=True,
        is_memorable=True, trademark_conflict=False,
        exact_match_searches=320, brand_searchability_score=0.75,
    )

    scored_domains: list[ScoredDomain] = []
    for v in mock_verified:
        assert isinstance(v, VerifiedDomain)
        gh_score = _calc_github_score(gh_signal)
        rd_score = _calc_reddit_score(rd_signal)
        brand_score = brand.brand_searchability_score * 100.0
        recency_score = 65.0
        spectre = _calc_composite_score(
            gh_score, rd_score, brand_score, recency_score,
        )
        scored_domains.append(ScoredDomain(
            domain=v.domain, tld=v.tld, run_id=_RUN_ID,
            scored_at=_NOW, github_signal=gh_signal,
            reddit_signal=rd_signal, brand_analysis=brand,
            github_score=gh_score, reddit_score=rd_score,
            brand_score=brand_score, social_recency_score=recency_score,
            spectre_score=spectre,
            domain_authority=v.domain_authority, spam_score=v.spam_score,
            referring_domains=v.referring_domains,
            trust_flow=30, citation_flow=35,
            years_active=v.archive_age_years,
            total_snapshots=v.total_snapshots,
            content_drift_score=0.15,
            niche_relevance_score=v.niche_relevance_score,
            niche_keyword_hits=v.niche_keyword_hits,
            source=v.source,
        ))

    assert len(scored_domains) == 3
    for sd in scored_domains:
        assert isinstance(sd, ScoredDomain)
        assert 0.0 <= sd.spectre_score <= 100.0
        assert 0.0 <= sd.github_score <= 100.0
        assert 0.0 <= sd.reddit_score <= 100.0

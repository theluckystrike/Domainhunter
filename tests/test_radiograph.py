"""Tests for RADIOGRAPH agent — deep backlink quality analysis.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

from typing import Any

import pytest

from agents.radiograph import (
    BacklinkProfile,
    _analyze_single_domain,
    _calculate_quality_score,
    _classify_referring_domain,
    _detect_red_flags,
    _extract_domain_from_url,
    _generate_mock_referring_urls,
    run,
)
from config.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> Settings:
    """Build a Settings instance for testing."""
    return Settings(
        database_url="sqlite:///test_domainhunter.db",
        max_scout_candidates=100,
        max_sentinel_survivors=20,
        max_archivist_verified=10,
        max_spectre_scored=5,
    )


# ---------------------------------------------------------------------------
# Test: Domain classification
# ---------------------------------------------------------------------------

def test_classify_tier1_github() -> None:
    """github.com must be classified as tier1."""
    assert _classify_referring_domain("github.com") == "tier1"


def test_classify_tier1_subdomain() -> None:
    """Subdomain of a tier1 domain must also be tier1."""
    assert _classify_referring_domain("docs.github.com") == "tier1"


def test_classify_tier1_various() -> None:
    """Multiple tier1 domains must all classify correctly."""
    tier1_domains: list[str] = [
        "reddit.com", "forbes.com", "techcrunch.com",
        "wikipedia.org", "medium.com",
    ]
    for domain in tier1_domains:
        result = _classify_referring_domain(domain)
        assert result == "tier1", f"{domain} should be tier1, got {result}"


def test_classify_tier2_stackoverflow() -> None:
    """stackoverflow.com must be classified as tier2."""
    assert _classify_referring_domain("stackoverflow.com") == "tier2"


def test_classify_tier2_various() -> None:
    """Multiple tier2 domains must all classify correctly."""
    tier2_domains: list[str] = [
        "dev.to", "hackernoon.com", "producthunt.com",
        "freecodecamp.org", "codepen.io",
    ]
    for domain in tier2_domains:
        result = _classify_referring_domain(domain)
        assert result == "tier2", f"{domain} should be tier2, got {result}"


def test_classify_tier3_unknown() -> None:
    """Unknown legitimate domain must be classified as tier3."""
    assert _classify_referring_domain("my-blog.com") == "tier3"
    assert _classify_referring_domain("randomsite.net") == "tier3"


def test_classify_spam_casino() -> None:
    """Casino-related domain must be classified as spam."""
    assert _classify_referring_domain("best-casino-online.xyz") == "spam"
    assert _classify_referring_domain("poker-stars-free.top") == "spam"


def test_classify_spam_tld() -> None:
    """Spam TLDs must be classified as spam regardless of name."""
    assert _classify_referring_domain("legitimate-sounding.xyz") == "spam"
    assert _classify_referring_domain("normal.buzz") == "spam"
    assert _classify_referring_domain("okay.click") == "spam"


def test_classify_spam_pharma() -> None:
    """Pharma spam domains must be caught."""
    assert _classify_referring_domain("buy-viagra-cheap.com") == "spam"
    assert _classify_referring_domain("pharma-pills.net") == "spam"


# ---------------------------------------------------------------------------
# Test: URL domain extraction
# ---------------------------------------------------------------------------

def test_extract_domain_from_full_url() -> None:
    """Full HTTPS URL must extract clean domain."""
    result = _extract_domain_from_url("https://github.com/user/repo")
    assert result == "github.com"


def test_extract_domain_from_bare_domain() -> None:
    """Bare domain without protocol must still extract correctly."""
    result = _extract_domain_from_url("stackoverflow.com")
    assert result == "stackoverflow.com"


def test_extract_domain_from_subdomain_url() -> None:
    """URL with subdomain must preserve full hostname."""
    result = _extract_domain_from_url("https://docs.python.org/3/tutorial/")
    assert result == "docs.python.org"


# ---------------------------------------------------------------------------
# Test: Quality score calculation
# ---------------------------------------------------------------------------

def test_quality_score_all_tier1() -> None:
    """10 tier1 backlinks with no spam should yield high score."""
    score = _calculate_quality_score(tier1=10, tier2=0, tier3=0, spam=0)
    assert score > 70.0
    assert score <= 100.0


def test_quality_score_all_spam() -> None:
    """All spam backlinks should yield zero score."""
    score = _calculate_quality_score(tier1=0, tier2=0, tier3=0, spam=20)
    assert score == 0.0


def test_quality_score_mixed() -> None:
    """Mixed backlinks should yield moderate score."""
    score = _calculate_quality_score(tier1=3, tier2=5, tier3=10, spam=2)
    # Raw = 3*15 + 5*5 + 10*1 + 2*(-10) = 45 + 25 + 10 - 20 = 60
    # Normalized = (60/200) * 100 = 30.0
    assert score == 30.0


def test_quality_score_floor_at_zero() -> None:
    """Heavy spam should not produce negative score."""
    score = _calculate_quality_score(tier1=0, tier2=0, tier3=1, spam=50)
    assert score == 0.0


def test_quality_score_cap_at_100() -> None:
    """Extremely high raw score should cap at 100."""
    score = _calculate_quality_score(tier1=50, tier2=50, tier3=50, spam=0)
    assert score == 100.0


# ---------------------------------------------------------------------------
# Test: Red flag detection
# ---------------------------------------------------------------------------

def test_red_flag_high_spam_ratio() -> None:
    """Spam ratio >30% must trigger red flag."""
    flags = _detect_red_flags(
        tier1=1, tier2=1, tier3=2, spam=5,
        total=9, unique_domains=5,
    )
    assert any("spam ratio" in f.lower() for f in flags)


def test_red_flag_zero_authority() -> None:
    """Zero tier1 and tier2 must trigger red flag."""
    flags = _detect_red_flags(
        tier1=0, tier2=0, tier3=10, spam=0,
        total=10, unique_domains=5,
    )
    assert any("zero authority" in f.lower() for f in flags)


def test_red_flag_low_diversity() -> None:
    """Many links from few domains must trigger red flag."""
    flags = _detect_red_flags(
        tier1=2, tier2=3, tier3=50, spam=0,
        total=55, unique_domains=3,
    )
    assert any("diversity" in f.lower() for f in flags)


def test_red_flag_link_concentration() -> None:
    """High links-per-domain must trigger concentration flag."""
    flags = _detect_red_flags(
        tier1=5, tier2=5, tier3=100, spam=0,
        total=110, unique_domains=5,
    )
    assert any("concentration" in f.lower() for f in flags)


def test_no_red_flags_healthy_profile() -> None:
    """Healthy profile should have zero flags."""
    flags = _detect_red_flags(
        tier1=5, tier2=10, tier3=20, spam=1,
        total=36, unique_domains=30,
    )
    # With these numbers: spam ratio 1/36 ~3%, has authority, good diversity
    assert len(flags) == 0


# ---------------------------------------------------------------------------
# Test: Single domain analysis
# ---------------------------------------------------------------------------

def test_analyze_single_domain_with_mock_urls() -> None:
    """Analysis with mock URLs should produce valid BacklinkProfile."""
    mock_urls: list[str] = [
        "https://github.com/repo1",
        "https://reddit.com/r/test",
        "https://forbes.com/article",
        "https://stackoverflow.com/q/1",
        "https://random-blog.com/post",
        "https://spam-casino.xyz/link",
    ]
    profile = _analyze_single_domain("testdomain.com", mock_urls)
    assert isinstance(profile, BacklinkProfile)
    assert profile.domain == "testdomain.com"
    assert profile.total_backlinks == 6
    assert profile.tier1_count >= 2  # github, reddit, forbes
    assert profile.tier2_count >= 1  # stackoverflow
    assert profile.spam_count >= 1   # spam-casino.xyz
    assert 0.0 <= profile.quality_score <= 100.0


def test_analyze_single_domain_empty_urls() -> None:
    """Analysis with no URLs should produce zero-score profile."""
    profile = _analyze_single_domain("empty.com", [])
    assert profile.total_backlinks == 0
    assert profile.quality_score == 0.0
    assert profile.tier1_count == 0


def test_backlink_profile_to_dict() -> None:
    """BacklinkProfile.to_dict() must include all required fields."""
    profile = BacklinkProfile(
        domain="test.com", tier1_count=3, tier2_count=5,
        tier3_count=10, spam_count=1, total_backlinks=19,
        quality_score=65.5, red_flags=("flag1",),
        tier1_sources=("github.com",),
        referring_domains_seen=15,
    )
    d = profile.to_dict()
    assert d["domain"] == "test.com"
    assert d["tier1_count"] == 3
    assert d["quality_score"] == 65.5
    assert isinstance(d["red_flags"], list)
    assert isinstance(d["tier1_sources"], list)


# ---------------------------------------------------------------------------
# Test: Mock data generation
# ---------------------------------------------------------------------------

def test_mock_referring_urls_count() -> None:
    """Mock data must generate a reasonable number of URLs."""
    urls = _generate_mock_referring_urls("example.com")
    assert isinstance(urls, list)
    assert len(urls) >= 5
    assert all(isinstance(u, str) for u in urls)


def test_mock_referring_urls_contain_known_domains() -> None:
    """Mock URLs must reference known authority domains."""
    urls = _generate_mock_referring_urls("example.com")
    url_text = " ".join(urls)
    assert "github.com" in url_text
    assert "reddit.com" in url_text


# ---------------------------------------------------------------------------
# Test: Full run (mock mode)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_mock() -> None:
    """End-to-end RADIOGRAPH run with mock data."""
    settings = _make_settings()
    domains = ["devtoolshub.com", "aicode.dev", "stackreview.io"]
    profiles = await run(settings, domains, mock=True)
    assert len(profiles) == 3
    assert all(isinstance(p, BacklinkProfile) for p in profiles)
    # Should be sorted by quality_score descending
    for i in range(len(profiles) - 1):
        assert profiles[i].quality_score >= profiles[i + 1].quality_score


@pytest.mark.asyncio
async def test_full_run_empty_input() -> None:
    """Empty domain list should return empty results."""
    settings = _make_settings()
    profiles = await run(settings, [], mock=True)
    assert profiles == []


@pytest.mark.asyncio
async def test_full_run_single_domain() -> None:
    """Single domain should produce exactly one profile."""
    settings = _make_settings()
    profiles = await run(settings, ["solo.com"], mock=True)
    assert len(profiles) == 1
    assert profiles[0].domain == "solo.com"


# ---------------------------------------------------------------------------
# Test: Budget tier classification (Sprint 3)
# ---------------------------------------------------------------------------

def test_budget_tier_cheap_domain() -> None:
    """Domain with mostly tier3 and some tier1 should be moderate."""
    profile = _analyze_single_domain("cheapdomain.com", [
        "https://github.com/mention",
        "https://random-blog-1.com/post",
        "https://random-blog-2.com/post",
        "https://random-blog-3.com/post",
        "https://random-blog-4.com/post",
    ])
    assert profile.quality_score > 0.0
    assert profile.tier1_count == 1
    assert profile.tier3_count == 4


def test_budget_tier_premium_domain() -> None:
    """Domain with many tier1 backlinks should score high."""
    premium_urls: list[str] = [
        "https://github.com/repo",
        "https://reddit.com/r/sub",
        "https://forbes.com/article",
        "https://techcrunch.com/post",
        "https://medium.com/story",
        "https://wired.com/article",
        "https://nature.com/paper",
        "https://bbc.com/news",
    ]
    profile = _analyze_single_domain("premium.com", premium_urls)
    assert profile.quality_score >= 50.0
    assert profile.tier1_count >= 7
    assert profile.spam_count == 0

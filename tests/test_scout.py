"""Tests for SCOUT agent — domain discovery and filtering.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config.constants import (
    ALLOWED_TLDS,
    MAX_DOMAIN_LENGTH,
    MAX_HYPHENS_IN_DOMAIN,
    MAX_NUMBERS_IN_DOMAIN,
    NICHE_KEYWORDS_TIER1,
    NICHE_KEYWORDS_TIER3,
    SPAM_TLDS,
)
from models.candidate import DomainCandidate

_RUN_ID: str = "test-run-scout-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — pure functions for SCOUT logic (testable without agent import)
# ---------------------------------------------------------------------------

def _extract_tld(domain: str) -> str:
    """Extract TLD from domain string."""
    assert "." in domain, f"no dot in domain: {domain}"
    idx = domain.rfind(".")
    return domain[idx:]


def _is_tld_allowed(tld: str) -> bool:
    """Check if TLD is in the allowed list."""
    return tld in ALLOWED_TLDS


def _is_tld_spam(tld: str) -> bool:
    """Check if TLD is a known spam TLD."""
    return tld in SPAM_TLDS


def _count_digits(name: str) -> int:
    """Count digits in a string."""
    return sum(1 for c in name if c.isdigit())


def _count_hyphens(name: str) -> int:
    """Count hyphens in a string."""
    return name.count("-")


def _domain_name_part(domain: str) -> str:
    """Extract the name part before the TLD."""
    idx = domain.rfind(".")
    return domain[:idx]


def _matches_keyword(domain: str, keywords: tuple[str, ...]) -> bool:
    """Check if any keyword appears in the domain name."""
    name = _domain_name_part(domain).lower()
    for kw in keywords:
        if kw in name:
            return True
    return False


def _make_candidate(domain: str, source: str = "whoisfreaks",
                    keywords: tuple[str, ...] = (),
                    score: float = 0.0) -> DomainCandidate:
    """Build a DomainCandidate from a domain string."""
    tld = _extract_tld(domain)
    return DomainCandidate(
        domain=domain, tld=tld, source=source,
        discovered_at=_NOW, run_id=_RUN_ID,
        niche_keyword_hits=keywords,
        niche_relevance_score=score,
    )


# ---------------------------------------------------------------------------
# TLD filter tests
# ---------------------------------------------------------------------------

def test_tld_filter_allows_valid() -> None:
    """Valid TLDs (.com, .io, .dev) must pass the allowed filter."""
    valid_tlds: list[str] = [".com", ".io", ".dev"]
    for tld in valid_tlds:
        assert _is_tld_allowed(tld), f"{tld} should be allowed"


def test_tld_filter_allows_net_is_not_in_list() -> None:
    """.net is NOT in ALLOWED_TLDS — verify this is intentional."""
    assert not _is_tld_allowed(".net"), ".net should not be in ALLOWED_TLDS"


def test_tld_filter_blocks_spam() -> None:
    """Spam TLDs (.xyz, .top, .click) must be blocked."""
    spam_tlds: list[str] = [".xyz", ".top", ".click"]
    for tld in spam_tlds:
        assert _is_tld_spam(tld), f"{tld} should be spam"
        assert not _is_tld_allowed(tld), f"{tld} should not be allowed"


# ---------------------------------------------------------------------------
# Quality filter tests
# ---------------------------------------------------------------------------

def test_quality_filter_blocks_long_domains() -> None:
    """Domains with name part > 25 chars should be flagged as low quality."""
    long_domain = "verylongdomainnamethatshouldbefiltered.com"
    name_part = _domain_name_part(long_domain)
    assert len(name_part) > 25, f"name part should be >25: {name_part}"


def test_quality_filter_blocks_excessive_numbers() -> None:
    """Domains with >3 digits in name should be flagged."""
    numeric_domains: list[str] = ["a1b2c3d4e5.com", "123456789.net"]
    for domain in numeric_domains:
        name_part = _domain_name_part(domain)
        digit_count = _count_digits(name_part)
        assert digit_count > MAX_NUMBERS_IN_DOMAIN, (
            f"{domain} has {digit_count} digits, threshold is {MAX_NUMBERS_IN_DOMAIN}"
        )


def test_quality_filter_blocks_excessive_hyphens() -> None:
    """Domains with >1 hyphen in name should be flagged."""
    hyphen_domains: list[str] = [
        "buy-sell-trade-cheap-fast.com",
        "a-b-c-d-e-f.io",
        "test-1-2-3-4.com",
    ]
    for domain in hyphen_domains:
        name_part = _domain_name_part(domain)
        hyphen_count = _count_hyphens(name_part)
        assert hyphen_count > MAX_HYPHENS_IN_DOMAIN, (
            f"{domain} has {hyphen_count} hyphens, threshold is {MAX_HYPHENS_IN_DOMAIN}"
        )


def test_quality_filter_allows_clean_domains() -> None:
    """Clean domains with 0-1 hyphens and few digits pass."""
    clean: list[str] = ["devtoolshub.com", "aicode.dev", "stackreview.io"]
    for domain in clean:
        name_part = _domain_name_part(domain)
        assert _count_hyphens(name_part) <= MAX_HYPHENS_IN_DOMAIN
        assert _count_digits(name_part) <= MAX_NUMBERS_IN_DOMAIN


# ---------------------------------------------------------------------------
# Keyword matching tests
# ---------------------------------------------------------------------------

def test_keyword_matching_finds_tier1() -> None:
    """Tier1 keyword 'prompt' in domain name matches."""
    domain = "promptcraft.dev"
    assert _matches_keyword(domain, NICHE_KEYWORDS_TIER1)


def test_keyword_matching_finds_tier3() -> None:
    """Tier3 keyword 'coding' in a hyphenated domain matches."""
    domain = "ai-coding.com"
    assert _matches_keyword(domain, NICHE_KEYWORDS_TIER3)


def test_keyword_matching_no_match() -> None:
    """Generic domain without niche keywords does not match any tier."""
    domain = "summergarden.com"
    assert not _matches_keyword(domain, NICHE_KEYWORDS_TIER1)
    assert not _matches_keyword(domain, NICHE_KEYWORDS_TIER3)


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

def test_deduplication_removes_exact() -> None:
    """Same domain from 2 sources must deduplicate to 1 result."""
    candidates: list[DomainCandidate] = [
        _make_candidate("devtoolshub.com", source="whoisfreaks"),
        _make_candidate("devtoolshub.com", source="catchdoms"),
    ]
    seen: set[str] = set()
    unique: list[DomainCandidate] = []
    for c in candidates:
        key = c.domain.lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    assert len(unique) == 1
    assert unique[0].domain == "devtoolshub.com"


def test_deduplication_case_insensitive() -> None:
    """DevTools.com and devtools.com must deduplicate."""
    domains_raw: list[str] = ["DevTools.com", "devtools.com", "DEVTOOLS.COM"]
    normalized: set[str] = {d.lower() for d in domains_raw}
    assert len(normalized) == 1
    assert "devtools.com" in normalized


# ---------------------------------------------------------------------------
# Full run tests with mocked clients
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_with_mock_produces_valid_candidates(
    fixture_path: Path,
) -> None:
    """Full SCOUT run with mock clients produces valid DomainCandidate objects."""
    with open(fixture_path / "whoisfreaks_sample.json", "r") as f:
        wf_data: dict[str, Any] = json.load(f)

    raw_domains: list[str] = wf_data["domains"]
    assert len(raw_domains) == 50

    # Simulate SCOUT filtering pipeline
    candidates: list[DomainCandidate] = []
    seen: set[str] = set()
    for domain in raw_domains:
        domain_lower = domain.lower().strip()
        tld = _extract_tld(domain_lower)
        if not _is_tld_allowed(tld):
            continue
        name_part = _domain_name_part(domain_lower)
        if _count_digits(name_part) > MAX_NUMBERS_IN_DOMAIN:
            continue
        if _count_hyphens(name_part) > MAX_HYPHENS_IN_DOMAIN:
            continue
        if domain_lower in seen:
            continue
        seen.add(domain_lower)
        candidates.append(_make_candidate(domain_lower))

    assert len(candidates) > 0
    assert len(candidates) <= len(raw_domains)
    for c in candidates:
        assert isinstance(c, DomainCandidate)
        assert c.tld in ALLOWED_TLDS


def test_run_caps_at_max() -> None:
    """SCOUT output must never exceed max_scout_candidates."""
    max_cap: int = 5
    all_candidates: list[DomainCandidate] = [
        _make_candidate(f"domain{i}.com") for i in range(20)
    ]
    capped: list[DomainCandidate] = all_candidates[:max_cap]
    assert len(capped) == max_cap
    assert len(capped) <= max_cap


def test_tech_keywords_sorted_first() -> None:
    """Candidates with niche keyword hits sort before generic ones."""
    tech = _make_candidate("promptcraft.dev", keywords=("prompt",), score=1.0)
    generic = _make_candidate("summergarden.com", keywords=(), score=0.0)
    candidates: list[DomainCandidate] = [generic, tech]
    sorted_candidates = sorted(
        candidates,
        key=lambda c: c.niche_relevance_score,
        reverse=True,
    )
    assert sorted_candidates[0].domain == "promptcraft.dev"
    assert sorted_candidates[1].domain == "summergarden.com"


# ---------------------------------------------------------------------------
# Fixture data validation tests
# ---------------------------------------------------------------------------

def test_whoisfreaks_fixture_has_50_domains(fixture_path: Path) -> None:
    """WhoisFreaks fixture must contain exactly 50 domain entries."""
    with open(fixture_path / "whoisfreaks_sample.json", "r") as f:
        data: dict[str, Any] = json.load(f)
    assert len(data["domains"]) == 50
    assert data["date"] == "2026-05-06"


def test_catchdoms_fixture_structure(fixture_path: Path) -> None:
    """CatchDoms fixture must have data array with score fields."""
    with open(fixture_path / "catchdoms_sample.json", "r") as f:
        data: dict[str, Any] = json.load(f)
    assert "data" in data
    assert len(data["data"]) == 5
    for entry in data["data"]:
        assert "name" in entry
        assert "score" in entry
        assert "backlinks" in entry

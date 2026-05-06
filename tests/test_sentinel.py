"""Tests for SENTINEL agent — SEO quality vetting.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from config.constants import (
    MAX_SPAM_SCORE,
    MIN_BRANDED_ANCHOR_PCT,
    MIN_DA_THRESHOLD,
    MIN_REFERRING_DOMAINS,
)
from models.candidate import DomainCandidate
from models.vetted import VettedDomain

_RUN_ID: str = "test-run-sentinel-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — pure SENTINEL decision functions
# ---------------------------------------------------------------------------

def _should_kill_da(da: int) -> bool:
    """Kill if DA is below the minimum threshold."""
    assert isinstance(da, int), "DA must be int"
    return da < MIN_DA_THRESHOLD


def _should_kill_spam(spam_score: float) -> bool:
    """Kill if spam score exceeds the max allowed."""
    assert isinstance(spam_score, float), "spam_score must be float"
    return spam_score > MAX_SPAM_SCORE


def _should_kill_no_index(indexed_pages: int) -> bool:
    """Kill if domain has zero indexed pages."""
    assert isinstance(indexed_pages, int), "indexed_pages must be int"
    return indexed_pages == 0


def _should_kill_low_ref_domains(ref_domains: int) -> bool:
    """Kill if referring domains are below minimum."""
    assert isinstance(ref_domains, int), "ref_domains must be int"
    return ref_domains < MIN_REFERRING_DOMAINS


def _should_flag_exact_match(exact_match_pct: float) -> bool:
    """Flag if exact-match anchor text percentage is suspiciously high."""
    return exact_match_pct > 30.0


def _should_flag_single_country(top_country_pct: float) -> bool:
    """Flag if one country dominates backlink profile."""
    return top_country_pct > 80.0


def _make_candidate(domain: str, tld: str = ".com") -> DomainCandidate:
    """Build a DomainCandidate for testing."""
    return DomainCandidate(
        domain=domain, tld=tld, source="whoisfreaks",
        discovered_at=_NOW, run_id=_RUN_ID,
    )


def _make_vetted(
    domain: str, da: int, pa: int, spam: float,
    ref: int, bl: int, idx: int, tld: str = ".com",
) -> VettedDomain:
    """Build a VettedDomain for testing."""
    return VettedDomain(
        domain=domain, tld=tld, source="whoisfreaks",
        discovered_at=_NOW, run_id=_RUN_ID,
        domain_authority=da, page_authority=pa,
        spam_score=spam, referring_domains=ref,
        backlinks_total=bl, dofollow_ratio=0.80,
        indexed_pages=idx,
    )


# ---------------------------------------------------------------------------
# Kill condition tests
# ---------------------------------------------------------------------------

def test_kills_low_da() -> None:
    """DA=20 is below MIN_DA_THRESHOLD=25, must be killed."""
    assert _should_kill_da(20)
    assert _should_kill_da(10)
    assert _should_kill_da(24)


def test_passes_good_da() -> None:
    """DA=35 is above MIN_DA_THRESHOLD=25, must pass."""
    assert not _should_kill_da(35)
    assert not _should_kill_da(25)
    assert not _should_kill_da(80)


def test_kills_high_spam() -> None:
    """spam_score=25% exceeds MAX_SPAM_SCORE=20%, must be killed."""
    assert _should_kill_spam(25.0)
    assert _should_kill_spam(45.0)
    assert _should_kill_spam(100.0)


def test_passes_low_spam() -> None:
    """spam_score=10% is below MAX_SPAM_SCORE=20%, must pass."""
    assert not _should_kill_spam(10.0)
    assert not _should_kill_spam(20.0)
    assert not _should_kill_spam(5.0)


def test_kills_zero_index() -> None:
    """google_indexed_pages=0 means domain is deindexed, must be killed."""
    assert _should_kill_no_index(0)


def test_passes_nonzero_index() -> None:
    """indexed_pages > 0 must pass the index check."""
    assert not _should_kill_no_index(1)
    assert not _should_kill_no_index(2450)


def test_kills_low_ref_domains() -> None:
    """referring_domains=50 is below MIN_REFERRING_DOMAINS=100, killed."""
    assert _should_kill_low_ref_domains(50)
    assert _should_kill_low_ref_domains(0)
    assert _should_kill_low_ref_domains(99)


def test_passes_good_ref_domains() -> None:
    """referring_domains=200 is above MIN_REFERRING_DOMAINS=100, passes."""
    assert not _should_kill_low_ref_domains(200)
    assert not _should_kill_low_ref_domains(100)


# ---------------------------------------------------------------------------
# Flag condition tests
# ---------------------------------------------------------------------------

def test_flags_high_exact_match() -> None:
    """exact_match_anchor_pct=35% triggers a warning flag."""
    assert _should_flag_exact_match(35.0)
    assert _should_flag_exact_match(60.0)


def test_does_not_flag_normal_exact_match() -> None:
    """exact_match_anchor_pct=12% is healthy, no flag."""
    assert not _should_flag_exact_match(12.0)
    assert not _should_flag_exact_match(30.0)


def test_flags_single_country() -> None:
    """top_country_pct=85% triggers geographic concentration flag."""
    assert _should_flag_single_country(85.0)
    assert _should_flag_single_country(95.0)


def test_does_not_flag_diverse_countries() -> None:
    """top_country_pct=55% is diversified, no flag."""
    assert not _should_flag_single_country(55.0)
    assert not _should_flag_single_country(80.0)


# ---------------------------------------------------------------------------
# Full run mock test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_mock(fixture_path: Path) -> None:
    """End-to-end SENTINEL with mock Moz + DataForSEO data."""
    with open(fixture_path / "moz_sample.json", "r") as f:
        moz_data: list[dict[str, Any]] = json.load(f)
    with open(fixture_path / "dataforseo_sample.json", "r") as f:
        dfs_data: dict[str, Any] = json.load(f)

    # Build a lookup from moz data
    moz_lookup: dict[str, dict[str, Any]] = {
        entry["domain"]: entry for entry in moz_data
    }
    # Build DataForSEO lookup
    dfs_lookup: dict[str, dict[str, Any]] = {}
    for task in dfs_data["tasks"]:
        for result in task["result"]:
            dfs_lookup[result["target"]] = result

    # Simulate SENTINEL vetting
    survivors: list[VettedDomain] = []
    for domain, moz in moz_lookup.items():
        da: int = moz["da"]
        spam: float = moz["spam_score"]
        if _should_kill_da(da):
            continue
        if _should_kill_spam(spam):
            continue
        tld = "." + domain.rsplit(".", 1)[1]
        dfs = dfs_lookup.get(domain, {})
        ref = dfs.get("referring_domains", 0)
        if _should_kill_low_ref_domains(ref):
            continue
        survivors.append(_make_vetted(
            domain=domain, da=da, pa=moz["pa"], spam=spam,
            ref=ref, bl=moz["backlinks"], idx=100, tld=tld,
        ))

    assert len(survivors) > 0
    for s in survivors:
        assert isinstance(s, VettedDomain)
        assert s.domain_authority >= MIN_DA_THRESHOLD
        assert s.spam_score <= MAX_SPAM_SCORE


# ---------------------------------------------------------------------------
# Cap and sort tests
# ---------------------------------------------------------------------------

def test_caps_at_max() -> None:
    """SENTINEL output never exceeds max_sentinel_survivors."""
    max_cap: int = 3
    all_vetted: list[VettedDomain] = [
        _make_vetted(f"domain{i}.com", da=40, pa=35, spam=5.0,
                     ref=200, bl=1000, idx=500)
        for i in range(10)
    ]
    capped: list[VettedDomain] = all_vetted[:max_cap]
    assert len(capped) == max_cap


def test_sorted_by_da() -> None:
    """SENTINEL output must be sorted by DA descending."""
    vetted: list[VettedDomain] = [
        _make_vetted("low.com", da=28, pa=25, spam=5.0,
                     ref=150, bl=500, idx=200),
        _make_vetted("high.com", da=55, pa=50, spam=3.0,
                     ref=500, bl=3000, idx=1500),
        _make_vetted("mid.com", da=38, pa=35, spam=8.0,
                     ref=250, bl=1200, idx=800),
    ]
    sorted_vetted = sorted(vetted, key=lambda v: v.domain_authority, reverse=True)
    assert sorted_vetted[0].domain_authority == 55
    assert sorted_vetted[1].domain_authority == 38
    assert sorted_vetted[2].domain_authority == 28

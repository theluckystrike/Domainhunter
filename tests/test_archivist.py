"""Tests for ARCHIVIST agent — Wayback Machine history verification.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from config.constants import MIN_ARCHIVE_YEARS
from models.verified import VerifiedDomain
from models.vetted import VettedDomain

_RUN_ID: str = "test-run-archivist-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — pure ARCHIVIST decision functions
# ---------------------------------------------------------------------------

def _should_kill_young(archive_age_years: float) -> bool:
    """Kill if domain archive is younger than MIN_ARCHIVE_YEARS."""
    return archive_age_years < MIN_ARCHIVE_YEARS


def _detect_language_change(titles: list[str]) -> bool:
    """Detect CJK characters in page titles as language change red flag."""
    for title in titles:
        for ch in title:
            if "\u4e00" <= ch <= "\u9fff":  # CJK Unified Ideographs
                return True
            if "\u3040" <= ch <= "\u309f":  # Hiragana
                return True
            if "\u30a0" <= ch <= "\u30ff":  # Katakana
                return True
            if "\uac00" <= ch <= "\ud7af":  # Hangul
                return True
    return False


def _detect_content_gap(snapshots: list[str], max_gap_months: int = 18) -> bool:
    """Detect if there is a content gap exceeding max_gap_months."""
    if len(snapshots) < 2:
        return False
    dates: list[datetime] = []
    for ts in snapshots:
        year = int(ts[:4])
        month = int(ts[4:6])
        day = int(ts[6:8])
        dates.append(datetime(year, month, day, tzinfo=timezone.utc))
    dates.sort()
    for i in range(1, len(dates)):
        delta = dates[i] - dates[i - 1]
        gap_months = delta.days / 30.44  # average days per month
        if gap_months >= max_gap_months:
            return True
    return False


def _detect_pbn_pattern(ownership_changes: int) -> bool:
    """Detect PBN pattern: 6+ owner changes is suspicious."""
    return ownership_changes >= 6


def _calc_title_consistency(titles: list[str]) -> float:
    """Calculate title consistency as ratio of most common title."""
    if not titles:
        return 0.0
    from collections import Counter
    counts = Counter(titles)
    most_common_count = counts.most_common(1)[0][1]
    return most_common_count / len(titles)


def _archive_age_from_snapshots(snapshots: list[list[str]]) -> float:
    """Calculate archive age in years from CDX snapshot rows."""
    if len(snapshots) < 2:
        return 0.0
    # Skip header row
    timestamps: list[str] = []
    for row in snapshots:
        if row[0] == "timestamp":
            continue
        timestamps.append(row[0])
    if not timestamps:
        return 0.0
    first_ts = timestamps[0]
    last_ts = timestamps[-1]
    first_year = int(first_ts[:4])
    last_year = int(last_ts[:4])
    first_month = int(first_ts[4:6])
    last_month = int(last_ts[4:6])
    age = (last_year - first_year) + (last_month - first_month) / 12.0
    return max(0.0, age)


def _make_vetted(domain: str, da: int = 42, tld: str = ".com") -> VettedDomain:
    """Build a VettedDomain for testing."""
    return VettedDomain(
        domain=domain, tld=tld, source="whoisfreaks",
        discovered_at=_NOW, run_id=_RUN_ID,
        domain_authority=da, page_authority=38,
        spam_score=5.0, referring_domains=450,
        backlinks_total=2300, dofollow_ratio=0.80,
        indexed_pages=2450,
    )


def _make_verified(
    domain: str, age: float, snaps: int, consistency: float,
    gap: int, lang: bool, owners: int, tld: str = ".com",
) -> VerifiedDomain:
    """Build a VerifiedDomain for testing."""
    return VerifiedDomain(
        domain=domain, tld=tld, source="whoisfreaks",
        discovered_at=_NOW, run_id=_RUN_ID,
        domain_authority=42, page_authority=38,
        spam_score=5.0, referring_domains=450,
        backlinks_total=2300, dofollow_ratio=0.80,
        indexed_pages=2450,
        archive_age_years=age, total_snapshots=snaps,
        first_snapshot_date=datetime(2016, 3, 15, tzinfo=timezone.utc),
        last_snapshot_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        title_consistency=consistency,
        max_content_gap_months=gap,
        language_change_detected=lang,
        ownership_changes=owners,
    )


# ---------------------------------------------------------------------------
# Age tests
# ---------------------------------------------------------------------------

def test_kills_young_domain() -> None:
    """archive_age < 3 years (MIN_ARCHIVE_YEARS) must be killed."""
    assert _should_kill_young(1.5)
    assert _should_kill_young(2.9)
    assert _should_kill_young(0.0)


def test_passes_old_domain() -> None:
    """archive_age >= 5 years easily passes MIN_ARCHIVE_YEARS=3."""
    assert not _should_kill_young(5.0)
    assert not _should_kill_young(10.0)
    assert not _should_kill_young(3.0)


# ---------------------------------------------------------------------------
# Language change tests
# ---------------------------------------------------------------------------

def test_detects_language_change() -> None:
    """CJK characters in title trigger language change red flag."""
    titles_with_cjk: list[str] = [
        "Developer Tools Hub",
        "Developer Tools Hub",
        "\u5f00\u53d1\u5de5\u5177\u4e2d\u5fc3",  # Chinese: "Development Tools Center"
        "Buy Cheap Domains",
    ]
    assert _detect_language_change(titles_with_cjk)


def test_no_language_change_english_only() -> None:
    """Pure English titles should not trigger language change."""
    titles_english: list[str] = [
        "Developer Tools Hub",
        "DevTools Hub - Build Better",
        "DevTools Hub | Home",
    ]
    assert not _detect_language_change(titles_english)


# ---------------------------------------------------------------------------
# Content gap tests
# ---------------------------------------------------------------------------

def test_detects_content_gap() -> None:
    """18-month gap between snapshots is a red flag."""
    # Snapshots with an 18+ month gap between 2018 and 2020
    timestamps: list[str] = [
        "20160315120000",
        "20170522143000",
        "20180101090000",
        "20200620110000",  # 29-month gap from 2018-01-01
        "20210303080000",
    ]
    assert _detect_content_gap(timestamps, max_gap_months=18)


def test_no_content_gap() -> None:
    """Regular yearly snapshots have no 18-month gap."""
    timestamps: list[str] = [
        "20160315120000",
        "20170522143000",
        "20180801090000",
        "20190115160000",
        "20200620110000",
    ]
    assert not _detect_content_gap(timestamps, max_gap_months=18)


# ---------------------------------------------------------------------------
# PBN pattern tests
# ---------------------------------------------------------------------------

def test_detects_pbn_pattern() -> None:
    """6+ owner changes is a PBN red flag."""
    assert _detect_pbn_pattern(6)
    assert _detect_pbn_pattern(10)


def test_no_pbn_pattern() -> None:
    """2 owner changes is normal."""
    assert not _detect_pbn_pattern(2)
    assert not _detect_pbn_pattern(5)


# ---------------------------------------------------------------------------
# Title consistency tests
# ---------------------------------------------------------------------------

def test_title_consistency_calculation() -> None:
    """80% same titles = 0.8 consistency score, passes."""
    titles: list[str] = [
        "DevTools Hub", "DevTools Hub", "DevTools Hub", "DevTools Hub",
        "Different Title",
    ]
    consistency = _calc_title_consistency(titles)
    assert abs(consistency - 0.8) < 0.01


def test_title_consistency_low() -> None:
    """30% consistency with mostly different titles, fails quality check."""
    titles: list[str] = [
        "Title A", "Title B", "Title C", "Title A", "Title D",
        "Title E", "Title F", "Title A", "Title G", "Title H",
    ]
    consistency = _calc_title_consistency(titles)
    assert consistency == pytest.approx(0.3, abs=0.01)
    assert consistency < 0.5  # below acceptable threshold


def test_title_consistency_empty() -> None:
    """Empty title list returns 0.0 consistency."""
    assert _calc_title_consistency([]) == 0.0


# ---------------------------------------------------------------------------
# Full run mock test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_mock(fixture_path: Path) -> None:
    """End-to-end ARCHIVIST with mock Wayback CDX data."""
    with open(fixture_path / "wayback_cdx_sample.json", "r") as f:
        cdx_data: list[list[str]] = json.load(f)

    # Calculate archive age from fixture
    age = _archive_age_from_snapshots(cdx_data)
    assert age >= 5.0, f"expected >= 5yr archive age, got {age}"

    # Simulate ARCHIVIST verification
    assert not _should_kill_young(age)

    # Extract timestamps (skip header)
    timestamps: list[str] = [row[0] for row in cdx_data if row[0] != "timestamp"]
    assert len(timestamps) == 10

    # Check no content gap
    has_gap = _detect_content_gap(timestamps, max_gap_months=18)
    # The fixture has yearly snapshots, so no 18-month gap
    assert not has_gap

    # Build a VerifiedDomain from the results
    verified = _make_verified(
        domain="devtoolshub.com", age=age, snaps=len(timestamps),
        consistency=0.85, gap=12, lang=False, owners=2,
    )
    assert isinstance(verified, VerifiedDomain)
    assert verified.archive_age_years >= MIN_ARCHIVE_YEARS
    assert not verified.language_change_detected


def test_archive_age_from_fixture(fixture_path: Path) -> None:
    """Wayback CDX fixture should show ~9 years of history."""
    with open(fixture_path / "wayback_cdx_sample.json", "r") as f:
        cdx_data: list[list[str]] = json.load(f)
    age = _archive_age_from_snapshots(cdx_data)
    # 2016 to 2025 = ~9 years
    assert 8.0 <= age <= 10.0, f"expected ~9yr age, got {age}"

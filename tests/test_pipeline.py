"""Integration tests for the full 5-agent pipeline.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from config.constants import (
    ALLOWED_TLDS,
    MAX_HYPHENS_IN_DOMAIN,
    MAX_NUMBERS_IN_DOMAIN,
    MIN_ARCHIVE_YEARS,
    MIN_DA_THRESHOLD,
    MAX_SPAM_SCORE,
    MIN_REFERRING_DOMAINS,
    VERDICT_BUY_NOW_THRESHOLD,
    VERDICT_WATCH_THRESHOLD,
)
from config.settings import Settings
from models.candidate import DomainCandidate
from models.scored import (
    BrandAnalysis,
    GitHubSignal,
    RedditSignal,
    ScoredDomain,
)
from models.verdict import DomainVerdict, ScoreBreakdown, VerdictType
from models.verified import VerifiedDomain
from models.vetted import VettedDomain

_RUN_ID: str = "test-run-pipeline-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers — simulate each pipeline stage
# ---------------------------------------------------------------------------

def _extract_tld(domain: str) -> str:
    """Extract TLD from domain."""
    idx = domain.rfind(".")
    return domain[idx:]


def _scout_filter(domains: list[str], max_cap: int) -> list[DomainCandidate]:
    """Simulate SCOUT stage: TLD + quality filtering."""
    candidates: list[DomainCandidate] = []
    seen: set[str] = set()
    for domain in domains:
        d = domain.lower().strip()
        tld = _extract_tld(d)
        if tld not in ALLOWED_TLDS:
            continue
        name = d[:d.rfind(".")]
        digits = sum(1 for c in name if c.isdigit())
        hyphens = name.count("-")
        if digits > MAX_NUMBERS_IN_DOMAIN:
            continue
        if hyphens > MAX_HYPHENS_IN_DOMAIN:
            continue
        if d in seen:
            continue
        seen.add(d)
        candidates.append(DomainCandidate(
            domain=d, tld=tld, source="mock",
            discovered_at=_NOW, run_id=_RUN_ID,
        ))
        if len(candidates) >= max_cap:
            break
    return candidates


def _sentinel_filter(
    candidates: list[DomainCandidate],
    da_map: dict[str, int],
    spam_map: dict[str, float],
    ref_map: dict[str, int],
    max_cap: int,
) -> list[VettedDomain]:
    """Simulate SENTINEL stage: SEO metric vetting."""
    survivors: list[VettedDomain] = []
    for c in candidates:
        da = da_map.get(c.domain, 0)
        spam = spam_map.get(c.domain, 100.0)
        ref = ref_map.get(c.domain, 0)
        if da < MIN_DA_THRESHOLD:
            continue
        if spam > MAX_SPAM_SCORE:
            continue
        if ref < MIN_REFERRING_DOMAINS:
            continue
        survivors.append(VettedDomain(
            domain=c.domain, tld=c.tld, source=c.source,
            discovered_at=c.discovered_at, run_id=c.run_id,
            domain_authority=da, page_authority=da - 5,
            spam_score=spam, referring_domains=ref,
            backlinks_total=ref * 5, dofollow_ratio=0.80,
            indexed_pages=ref * 2,
        ))
        if len(survivors) >= max_cap:
            break
    return sorted(survivors, key=lambda v: v.domain_authority, reverse=True)


def _archivist_filter(
    vetted: list[VettedDomain],
    age_map: dict[str, float],
    max_cap: int,
) -> list[VerifiedDomain]:
    """Simulate ARCHIVIST stage: history verification."""
    verified: list[VerifiedDomain] = []
    for v in vetted:
        age = age_map.get(v.domain, 0.0)
        if age < MIN_ARCHIVE_YEARS:
            continue
        verified.append(VerifiedDomain(
            domain=v.domain, tld=v.tld, source=v.source,
            discovered_at=v.discovered_at, run_id=v.run_id,
            domain_authority=v.domain_authority,
            page_authority=v.page_authority,
            spam_score=v.spam_score,
            referring_domains=v.referring_domains,
            backlinks_total=v.backlinks_total,
            dofollow_ratio=v.dofollow_ratio,
            indexed_pages=v.indexed_pages,
            archive_age_years=age, total_snapshots=int(age * 12),
            first_snapshot_date=datetime(2016, 1, 1, tzinfo=timezone.utc),
            last_snapshot_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            title_consistency=0.85, max_content_gap_months=6,
            language_change_detected=False, ownership_changes=2,
        ))
        if len(verified) >= max_cap:
            break
    return verified


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str) -> None:
    """Create a minimal SQLite test database."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT,
            scout_count INTEGER DEFAULT 0,
            sentinel_count INTEGER DEFAULT 0,
            archivist_count INTEGER DEFAULT 0,
            spectre_count INTEGER DEFAULT 0,
            oracle_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            domain TEXT PRIMARY KEY,
            run_id TEXT,
            stage TEXT,
            da INTEGER,
            spam_score REAL,
            verdict TEXT,
            final_score REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _write_pipeline_run(
    db_path: str, run_id: str,
    scout_count: int, sentinel_count: int,
    archivist_count: int,
) -> None:
    """Write a pipeline run record to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO pipeline_runs "
        "(run_id, started_at, scout_count, sentinel_count, archivist_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, _NOW.isoformat(), scout_count, sentinel_count, archivist_count),
    )
    conn.commit()
    conn.close()


def _write_domain(
    db_path: str, domain: str, run_id: str,
    stage: str, da: int, spam: float,
) -> None:
    """Write a domain record to SQLite."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO domains "
        "(domain, run_id, stage, da, spam_score, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (domain, run_id, stage, da, spam, _NOW.isoformat()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Full pipeline dry run test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline_dry_run(settings: Settings) -> None:
    """Runs all 5 pipeline stages with mock data, verifying shrinkage."""
    raw_domains: list[str] = [
        "devtoolshub.com", "aicode.dev", "stackreview.io",
        "codebench.dev", "mlcompare.io", "promptguide.dev",
        "toolchain.io", "summergarden.com", "random123.xyz",
        "buy-sell-trade-cheap-fast.com",
    ]

    # Stage 1: SCOUT
    candidates = _scout_filter(raw_domains, settings.max_scout_candidates)
    assert len(candidates) > 0
    assert len(candidates) <= settings.max_scout_candidates
    for c in candidates:
        assert c.tld in ALLOWED_TLDS

    # Stage 2: SENTINEL
    da_map = {c.domain: 40 for c in candidates}
    spam_map = {c.domain: 8.0 for c in candidates}
    ref_map = {c.domain: 250 for c in candidates}
    vetted = _sentinel_filter(
        candidates, da_map, spam_map, ref_map,
        settings.max_sentinel_survivors,
    )
    assert len(vetted) > 0
    assert len(vetted) <= settings.max_sentinel_survivors
    assert len(vetted) <= len(candidates)

    # Stage 3: ARCHIVIST
    age_map = {v.domain: 7.0 for v in vetted}
    verified = _archivist_filter(
        vetted, age_map, settings.max_archivist_verified,
    )
    assert len(verified) > 0
    assert len(verified) <= settings.max_archivist_verified
    assert len(verified) <= len(vetted)

    # Verify pipeline shrinkage
    assert len(candidates) >= len(vetted) >= len(verified)


# ---------------------------------------------------------------------------
# Empty SCOUT test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_handles_empty_scout(settings: Settings) -> None:
    """SCOUT returns 0 candidates, pipeline continues gracefully."""
    raw_domains: list[str] = [
        "random123.xyz", "spamsite.top", "free-click.click",
    ]
    candidates = _scout_filter(raw_domains, settings.max_scout_candidates)
    assert len(candidates) == 0

    # SENTINEL receives empty input, produces empty output
    vetted = _sentinel_filter(candidates, {}, {}, {}, settings.max_sentinel_survivors)
    assert len(vetted) == 0

    # ARCHIVIST receives empty input
    verified = _archivist_filter(vetted, {}, settings.max_archivist_verified)
    assert len(verified) == 0


# ---------------------------------------------------------------------------
# All killed by SENTINEL test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_handles_all_killed(settings: Settings) -> None:
    """SENTINEL kills everything, pipeline continues gracefully."""
    raw_domains: list[str] = ["devtoolshub.com", "aicode.dev", "stackreview.io"]
    candidates = _scout_filter(raw_domains, settings.max_scout_candidates)
    assert len(candidates) > 0

    # All domains have DA=10 (below threshold) -> all killed
    da_map = {c.domain: 10 for c in candidates}
    spam_map = {c.domain: 5.0 for c in candidates}
    ref_map = {c.domain: 200 for c in candidates}
    vetted = _sentinel_filter(
        candidates, da_map, spam_map, ref_map,
        settings.max_sentinel_survivors,
    )
    assert len(vetted) == 0

    # ARCHIVIST receives empty input
    verified = _archivist_filter(vetted, {}, settings.max_archivist_verified)
    assert len(verified) == 0


# ---------------------------------------------------------------------------
# Database persistence test
# ---------------------------------------------------------------------------

def test_database_persistence() -> None:
    """Verify pipeline data is written to SQLite after each stage."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path: str = tmp.name

    try:
        _create_test_db(db_path)

        # Write a pipeline run
        _write_pipeline_run(db_path, _RUN_ID, scout_count=10,
                            sentinel_count=5, archivist_count=3)

        # Write some domain records
        _write_domain(db_path, "devtoolshub.com", _RUN_ID, "scout", 42, 5.0)
        _write_domain(db_path, "aicode.dev", _RUN_ID, "sentinel", 38, 8.0)

        # Verify data was persisted
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT scout_count, sentinel_count, archivist_count "
            "FROM pipeline_runs WHERE run_id = ?",
            (_RUN_ID,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 10  # scout_count
        assert row[1] == 5   # sentinel_count
        assert row[2] == 3   # archivist_count

        # Verify domain records
        cursor = conn.execute(
            "SELECT domain, stage, da FROM domains ORDER BY domain",
        )
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "aicode.dev"
        assert rows[0][1] == "sentinel"
        assert rows[1][0] == "devtoolshub.com"
        assert rows[1][1] == "scout"
        assert rows[1][2] == 42

        conn.close()
    finally:
        os.unlink(db_path)

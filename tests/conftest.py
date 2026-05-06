"""Shared pytest fixtures for Domain Hunter test suite.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No mutable global state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from config.settings import Settings
from models.candidate import DomainCandidate
from models.scored import BrandAnalysis, GitHubSignal, RedditSignal, ScoredDomain
from models.verdict import DomainVerdict, ScoreBreakdown, VerdictType
from models.verified import VerifiedDomain
from models.vetted import VettedDomain

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_RUN_ID: str = "test-run-20260506-001"
_NOW: datetime = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)
_FIXTURES_DIR: Path = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixture: path helper
# ---------------------------------------------------------------------------
@pytest.fixture()
def fixture_path() -> Path:
    """Return the absolute path to the fixtures directory."""
    assert _FIXTURES_DIR.is_dir(), f"fixtures dir missing: {_FIXTURES_DIR}"
    return _FIXTURES_DIR


# ---------------------------------------------------------------------------
# Fixture: Settings with mock keys
# ---------------------------------------------------------------------------
@pytest.fixture()
def settings() -> Settings:
    """Return a Settings instance populated with test-only mock keys."""
    return Settings(
        whoisfreaks_api_key="test-wf-key-000",
        catchdoms_api_key="test-cd-key-000",
        apify_api_token="test-apify-token-000",
        dataforseo_login="test-dfs-login",
        dataforseo_password="test-dfs-pass",
        google_cse_api_key="test-gcse-key",
        google_cse_cx="test-gcse-cx",
        github_token="test-gh-token",
        reddit_client_id="test-reddit-id",
        reddit_client_secret="test-reddit-secret",
        anthropic_api_key="test-anthropic-key",
        database_url="sqlite:///test_domainhunter.db",
        max_scout_candidates=100,
        max_sentinel_survivors=20,
        max_archivist_verified=10,
        max_spectre_scored=5,
    )


# ---------------------------------------------------------------------------
# Fixture: DomainCandidate list (10 items)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_candidates() -> list[DomainCandidate]:
    """Return 10 realistic DomainCandidate objects."""
    domains: list[tuple[str, str, str]] = [
        ("devtoolshub.com", ".com", "whoisfreaks"),
        ("aicode.dev", ".dev", "catchdoms"),
        ("stackreview.io", ".io", "whoisfreaks"),
        ("codebench.dev", ".dev", "catchdoms"),
        ("mlcompare.io", ".io", "whoisfreaks"),
        ("promptguide.dev", ".dev", "catchdoms"),
        ("toolchain.io", ".io", "whoisfreaks"),
        ("syntaxcheck.dev", ".dev", "catchdoms"),
        ("apibuild.io", ".io", "whoisfreaks"),
        ("codetest.dev", ".dev", "catchdoms"),
    ]
    result: list[DomainCandidate] = []
    for domain, tld, source in domains:
        result.append(DomainCandidate(
            domain=domain,
            tld=tld,
            source=source,
            discovered_at=_NOW,
            run_id=_RUN_ID,
            niche_keyword_hits=("code",),
            niche_relevance_score=0.4,
        ))
    assert len(result) == 10
    return result


# ---------------------------------------------------------------------------
# Fixture: VettedDomain list (5 items)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_vetted() -> list[VettedDomain]:
    """Return 5 realistic VettedDomain objects."""
    entries: list[dict[str, Any]] = [
        {"domain": "devtoolshub.com", "tld": ".com", "da": 42, "pa": 38,
         "spam": 5.0, "ref": 450, "bl": 2300, "dof": 0.80, "idx": 2450},
        {"domain": "aicode.dev", "tld": ".dev", "da": 38, "pa": 35,
         "spam": 8.0, "ref": 320, "bl": 1500, "dof": 0.84, "idx": 1200},
        {"domain": "stackreview.io", "tld": ".io", "da": 35, "pa": 30,
         "spam": 10.0, "ref": 200, "bl": 900, "dof": 0.75, "idx": 800},
        {"domain": "codebench.dev", "tld": ".dev", "da": 30, "pa": 28,
         "spam": 12.0, "ref": 180, "bl": 700, "dof": 0.70, "idx": 500},
        {"domain": "mlcompare.io", "tld": ".io", "da": 28, "pa": 25,
         "spam": 15.0, "ref": 150, "bl": 600, "dof": 0.68, "idx": 350},
    ]
    result: list[VettedDomain] = []
    for e in entries:
        result.append(VettedDomain(
            domain=e["domain"], tld=e["tld"], source="whoisfreaks",
            discovered_at=_NOW, run_id=_RUN_ID,
            domain_authority=e["da"], page_authority=e["pa"],
            spam_score=e["spam"], referring_domains=e["ref"],
            backlinks_total=e["bl"], dofollow_ratio=e["dof"],
            indexed_pages=e["idx"],
            niche_keyword_hits=("code",), niche_relevance_score=0.4,
        ))
    assert len(result) == 5
    return result


# ---------------------------------------------------------------------------
# Fixture: VerifiedDomain list (3 items)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_verified() -> list[VerifiedDomain]:
    """Return 3 realistic VerifiedDomain objects."""
    entries: list[dict[str, Any]] = [
        {"domain": "devtoolshub.com", "tld": ".com", "da": 42, "pa": 38,
         "spam": 5.0, "ref": 450, "bl": 2300, "dof": 0.80, "idx": 2450,
         "age": 10.0, "snaps": 120, "consistency": 0.85, "gap": 4,
         "lang": False, "owners": 2},
        {"domain": "aicode.dev", "tld": ".dev", "da": 38, "pa": 35,
         "spam": 8.0, "ref": 320, "bl": 1500, "dof": 0.84, "idx": 1200,
         "age": 7.0, "snaps": 80, "consistency": 0.78, "gap": 6,
         "lang": False, "owners": 1},
        {"domain": "stackreview.io", "tld": ".io", "da": 35, "pa": 30,
         "spam": 10.0, "ref": 200, "bl": 900, "dof": 0.75, "idx": 800,
         "age": 5.5, "snaps": 60, "consistency": 0.72, "gap": 8,
         "lang": False, "owners": 3},
    ]
    result: list[VerifiedDomain] = []
    for e in entries:
        result.append(VerifiedDomain(
            domain=e["domain"], tld=e["tld"], source="whoisfreaks",
            discovered_at=_NOW, run_id=_RUN_ID,
            domain_authority=e["da"], page_authority=e["pa"],
            spam_score=e["spam"], referring_domains=e["ref"],
            backlinks_total=e["bl"], dofollow_ratio=e["dof"],
            indexed_pages=e["idx"],
            archive_age_years=e["age"], total_snapshots=e["snaps"],
            first_snapshot_date=datetime(2016, 3, 15, tzinfo=timezone.utc),
            last_snapshot_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            title_consistency=e["consistency"],
            max_content_gap_months=e["gap"],
            language_change_detected=e["lang"],
            ownership_changes=e["owners"],
            niche_keyword_hits=("code",), niche_relevance_score=0.4,
        ))
    assert len(result) == 3
    return result


# ---------------------------------------------------------------------------
# Fixture: ScoredDomain list (2 items)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_scored() -> list[ScoredDomain]:
    """Return 2 realistic ScoredDomain objects."""
    gh_signal = GitHubSignal(
        repo_mentions=5, total_stars=120, total_forks=30,
        readme_mentions=8, issue_mentions=12,
    )
    reddit_signal = RedditSignal(
        total_mentions=3, total_upvotes=85,
        subreddits_seen=("programming", "webdev"),
        avg_sentiment=0.6,
    )
    brand_ok = BrandAnalysis(
        brand_name="devtoolshub", is_pronounceable=True,
        is_memorable=True, trademark_conflict=False,
        exact_match_searches=320, brand_searchability_score=0.75,
    )
    brand_b = BrandAnalysis(
        brand_name="aicode", is_pronounceable=True,
        is_memorable=True, trademark_conflict=False,
        exact_match_searches=180, brand_searchability_score=0.70,
    )
    scored_a = ScoredDomain(
        domain="devtoolshub.com", tld=".com", run_id=_RUN_ID,
        scored_at=_NOW, github_signal=gh_signal,
        reddit_signal=reddit_signal, brand_analysis=brand_ok,
        github_score=72.0, reddit_score=58.0, brand_score=75.0,
        social_recency_score=65.0, spectre_score=68.0,
        domain_authority=42, spam_score=5.0, referring_domains=450,
        trust_flow=35, citation_flow=40, years_active=10.0,
        total_snapshots=120, content_drift_score=0.15,
        niche_relevance_score=0.8, niche_keyword_hits=("devtools",),
        source="whoisfreaks",
    )
    scored_b = ScoredDomain(
        domain="aicode.dev", tld=".dev", run_id=_RUN_ID,
        scored_at=_NOW, github_signal=gh_signal,
        reddit_signal=reddit_signal, brand_analysis=brand_b,
        github_score=65.0, reddit_score=50.0, brand_score=70.0,
        social_recency_score=60.0, spectre_score=62.0,
        domain_authority=38, spam_score=8.0, referring_domains=320,
        trust_flow=30, citation_flow=35, years_active=7.0,
        total_snapshots=80, content_drift_score=0.20,
        niche_relevance_score=0.7, niche_keyword_hits=("ai", "code"),
        source="catchdoms",
    )
    return [scored_a, scored_b]


# ---------------------------------------------------------------------------
# Fixture: load JSON fixture files
# ---------------------------------------------------------------------------
@pytest.fixture()
def load_fixture(fixture_path: Path):
    """Return a callable that loads a JSON fixture by filename."""
    def _load(name: str) -> Any:
        path = fixture_path / name
        assert path.is_file(), f"fixture not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _load

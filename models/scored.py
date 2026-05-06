"""ScoredDomain — frozen dataclass output from SPECTRE agent.

Contains social signal analysis, brand searchability, and community presence.
NASA Rule 2: frozen=True prevents mutation after creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GitHubSignal:
    """Immutable GitHub social signal data."""

    repo_mentions: int
    total_stars: int
    total_forks: int
    readme_mentions: int
    issue_mentions: int
    last_mention_date: datetime | None = None

    def __post_init__(self) -> None:
        assert self.repo_mentions >= 0, "repo_mentions must be non-negative"
        assert self.total_stars >= 0, "total_stars must be non-negative"
        assert self.total_forks >= 0, "total_forks must be non-negative"
        assert self.readme_mentions >= 0, "readme_mentions must be non-negative"
        assert self.issue_mentions >= 0, "issue_mentions must be non-negative"


@dataclass(frozen=True)
class RedditSignal:
    """Immutable Reddit social signal data."""

    total_mentions: int
    total_upvotes: int
    subreddits_seen: tuple[str, ...]
    avg_sentiment: float  # -1.0 to 1.0
    last_mention_date: datetime | None = None

    def __post_init__(self) -> None:
        assert self.total_mentions >= 0, "total_mentions must be non-negative"
        assert self.total_upvotes >= 0, "total_upvotes must be non-negative"
        assert -1.0 <= self.avg_sentiment <= 1.0, "avg_sentiment must be -1.0 to 1.0"


@dataclass(frozen=True)
class BrandAnalysis:
    """Immutable brand searchability and trademark analysis."""

    brand_name: str
    is_pronounceable: bool
    is_memorable: bool
    trademark_conflict: bool
    exact_match_searches: int  # monthly volume estimate
    brand_searchability_score: float  # 0.0-1.0

    def __post_init__(self) -> None:
        assert isinstance(self.brand_name, str), "brand_name must be str"
        assert len(self.brand_name) > 0, "brand_name must not be empty"
        assert self.exact_match_searches >= 0, "exact_match_searches non-negative"
        assert 0.0 <= self.brand_searchability_score <= 1.0, "searchability 0-1"


@dataclass(frozen=True)
class ScoredDomain:
    """Immutable domain with social scoring from SPECTRE agent."""

    domain: str
    tld: str
    run_id: str
    scored_at: datetime

    # Social signals
    github_signal: GitHubSignal
    reddit_signal: RedditSignal
    brand_analysis: BrandAnalysis

    # Weighted component scores (each 0.0-100.0)
    github_score: float
    reddit_score: float
    brand_score: float
    social_recency_score: float

    # Final SPECTRE composite score (0.0-100.0)
    spectre_score: float

    # Pass-through from ARCHIVIST
    domain_authority: int
    spam_score: float
    referring_domains: int
    trust_flow: int
    citation_flow: int
    years_active: float
    total_snapshots: int
    content_drift_score: float
    niche_relevance_score: float
    niche_keyword_hits: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and len(self.domain) >= 4, "invalid domain"
        assert isinstance(self.run_id, str) and len(self.run_id) > 0, "invalid run_id"
        assert 0.0 <= self.github_score <= 100.0, "github_score must be 0-100"
        assert 0.0 <= self.reddit_score <= 100.0, "reddit_score must be 0-100"
        assert 0.0 <= self.brand_score <= 100.0, "brand_score must be 0-100"
        assert 0.0 <= self.social_recency_score <= 100.0, "recency_score 0-100"
        assert 0.0 <= self.spectre_score <= 100.0, (
            f"spectre_score must be 0-100, got {self.spectre_score}"
        )
        assert 0 <= self.domain_authority <= 100, "DA must be 0-100"

"""SPECTRE — Niche Relevance Agent (Pipeline Stage 4).

Scores verified domains for AI dev tools niche relevance using:
1. Backlink source classification (tech vs general)
2. GitHub repo mentions
3. Reddit dev community mentions
4. LLM content classification (Claude Sonnet)

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
NASA Rule 3: All loops have fixed upper bounds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from clients.anthropic_client import AnthropicClient
from clients.github_search import GitHubSearchClient
from clients.reddit_search import RedditSearchClient
from clients.wayback import WaybackClient
from config.constants import (
    MAX_LOOP_ITERATIONS,
    MAX_SPECTRE_SCORED,
    NICHE_KEYWORD_WEIGHTS,
    NICHE_KEYWORDS_TIER1,
    NICHE_KEYWORDS_TIER2,
    NICHE_KEYWORDS_TIER3,
    NICHE_KEYWORDS_TIER4,
)
from config.settings import Settings
from models.scored import (
    BrandAnalysis,
    GitHubSignal,
    RedditSignal,
    ScoredDomain,
)
from models.verified import VerifiedDomain

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Composite score weight constants (frozen by design, module-level Final)
# ---------------------------------------------------------------------------
_WEIGHT_TECH_BACKLINK: float = 0.40
_WEIGHT_LLM_TOPIC: float = 0.25
_WEIGHT_COMMUNITY: float = 0.20
_WEIGHT_KEYWORD: float = 0.15
_MIN_NICHE_SCORE: float = 30.0


async def run(
    settings: Settings,
    verified: list[VerifiedDomain],
    *,
    mock: bool = False,
) -> list[ScoredDomain]:
    """Score domains for AI dev tools niche relevance.

    Args:
        settings: Pipeline configuration.
        verified: Domains verified by ARCHIVIST.
        mock: If True, generate mock scores without API calls.

    Returns:
        List of ScoredDomain sorted by spectre_score descending,
        filtered to score > 30, capped at max_spectre_scored.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(verified, list), "verified must be a list"

    if not verified:
        logger.info("spectre_no_input", count=0)
        return []

    max_scored: int = min(settings.max_spectre_scored, MAX_SPECTRE_SCORED)
    scored: list[ScoredDomain] = []

    if mock:
        scored = _generate_mock_scores(verified, max_scored)
    else:
        scored = await _score_all_domains(settings, verified, max_scored)

    filtered = [s for s in scored if s.spectre_score > _MIN_NICHE_SCORE]
    filtered.sort(key=lambda d: d.spectre_score, reverse=True)
    result = filtered[:max_scored]

    logger.info(
        "spectre_complete",
        input_count=len(verified),
        scored_count=len(scored),
        filtered_count=len(result),
    )
    return result


async def _score_all_domains(
    settings: Settings,
    verified: list[VerifiedDomain],
    max_scored: int,
) -> list[ScoredDomain]:
    """Score all verified domains using live API calls.

    Args:
        settings: Pipeline settings with API keys.
        verified: List of verified domains.
        max_scored: Maximum domains to score.

    Returns:
        List of scored domains.
    """
    assert isinstance(verified, list) and len(verified) > 0, "need at least one domain"
    assert max_scored > 0, "max_scored must be positive"

    github_client = GitHubSearchClient(settings) if settings.github_token else None
    reddit_client = (
        RedditSearchClient(settings)
        if settings.reddit_client_id and settings.reddit_client_secret
        else None
    )
    anthropic = AnthropicClient(settings) if settings.anthropic_api_key else None
    wayback = WaybackClient(settings)

    scored: list[ScoredDomain] = []

    try:
        for idx, domain in enumerate(verified):
            if idx >= MAX_LOOP_ITERATIONS or idx >= max_scored * 3:
                break
            try:
                result = await _score_single_domain(
                    domain, github_client, reddit_client, anthropic, wayback,
                )
                if result is not None:
                    scored.append(result)
            except Exception as exc:
                logger.error("spectre_domain_failed", domain=domain.domain, error=str(exc))
    finally:
        # All clients use per-request sessions or sync PRAW; no close() needed
        pass

    return scored


async def _score_single_domain(
    domain: VerifiedDomain,
    github_client: GitHubSearchClient | None,
    reddit_client: RedditSearchClient | None,
    anthropic: AnthropicClient | None,
    wayback: WaybackClient,
) -> ScoredDomain | None:
    """Score a single domain using all available signals.

    Args:
        domain: Verified domain to score.
        github_client: Optional GitHub search client.
        reddit_client: Optional Reddit search client.
        anthropic: Optional Anthropic client for LLM classification.
        wayback: Wayback client for content retrieval.

    Returns:
        ScoredDomain or None if scoring fails.
    """
    assert isinstance(domain, VerifiedDomain), "domain must be VerifiedDomain"
    assert wayback is not None, "wayback client required"

    # 1. GitHub mentions
    github_data = await _fetch_github_data(github_client, domain.domain)
    # 2. Reddit mentions
    reddit_data = await _fetch_reddit_data(reddit_client, domain.domain)
    # 3. Wayback content
    content_text = await _fetch_wayback_content(wayback, domain.domain)
    # 4. LLM classification
    llm_result = await _classify_with_llm(anthropic, domain.domain, content_text)
    # 5. Keyword scoring
    keyword_score, tier_matches = _calculate_keyword_score(domain.domain, content_text)
    # 6. Community score
    github_mentions = github_data.get("total_count", 0)
    reddit_mentions = reddit_data.get("total_mentions", 0)
    community_score = _calculate_community_score(github_mentions, reddit_mentions)
    # 7. Tech backlink estimate
    tech_backlink_pct = _estimate_tech_backlink_pct(domain, github_mentions, reddit_mentions)
    # 8. LLM topic score (normalize 0-1 to 0-100)
    llm_topic_raw = llm_result.get("relevance_score", 0.0)
    llm_topic_score = min(100.0, llm_topic_raw * 100.0)

    # Composite
    spectre_score = _calculate_composite_score(
        tech_backlink_pct, llm_topic_score, community_score, keyword_score,
    )

    return _build_scored_domain(domain, spectre_score, github_data, reddit_data)


async def _fetch_wayback_content(wayback: WaybackClient, domain: str) -> str:
    """Fetch archived content text for a domain via Wayback.

    Uses get_availability to find the closest snapshot URL,
    then fetch_snapshot_content to retrieve the HTML.

    Args:
        wayback: WaybackClient instance.
        domain: Domain name to look up.

    Returns:
        Extracted text content, or empty string on failure.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert wayback is not None, "wayback client required"

    try:
        avail = await wayback.get_availability(domain)
        if avail is None:
            return ""
        closest = avail.get("archived_snapshots", {}).get("closest", {})
        snapshot_url = closest.get("url", "")
        if not snapshot_url:
            return ""
        html = await wayback.fetch_snapshot_content(snapshot_url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())[:8000]
    except Exception as exc:
        logger.warning("wayback_content_failed", domain=domain, error=str(exc))
        return ""


async def _fetch_github_data(
    client: GitHubSearchClient | None,
    domain: str,
) -> dict[str, Any]:
    """Fetch GitHub mentions for a domain.

    Adapts the single-int response from GitHubSearchClient
    into the normalized dict used by SPECTRE scoring.

    Args:
        client: Optional GitHub client.
        domain: Domain name to search.

    Returns:
        Dict with total_count, repo_names, readme_mentions.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert client is None or isinstance(client, GitHubSearchClient), "invalid client type"

    default: dict[str, Any] = {"total_count": 0, "repo_names": [], "readme_mentions": 0}
    if client is None:
        return default
    try:
        count: int = await client.search_domain_mentions(domain)
        return {"total_count": count, "repo_names": [], "readme_mentions": 0}
    except Exception as exc:
        logger.warning("github_fetch_failed", domain=domain, error=str(exc))
        return default


async def _fetch_reddit_data(
    client: RedditSearchClient | None,
    domain: str,
) -> dict[str, Any]:
    """Fetch Reddit mentions for a domain.

    Adapts the PRAW-based client (returns dict[str, int]) into
    the normalized format used by SPECTRE scoring.

    Args:
        client: Optional Reddit client.
        domain: Domain name to search.

    Returns:
        Dict with total_mentions, subreddits_found, total_upvotes.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert client is None or isinstance(client, RedditSearchClient), "invalid client type"

    default: dict[str, Any] = {"total_mentions": 0, "subreddits_found": [], "total_upvotes": 0}
    if client is None:
        return default
    try:
        raw: dict[str, int] = await client.search_domain_mentions(domain)
        total = sum(raw.values())
        return {
            "total_mentions": total,
            "subreddits_found": list(raw.keys()),
            "total_upvotes": 0,
        }
    except Exception as exc:
        logger.warning("reddit_fetch_failed", domain=domain, error=str(exc))
        return default


async def _classify_with_llm(
    client: AnthropicClient | None,
    domain: str,
    content_text: str,
) -> dict[str, Any]:
    """Classify domain content with LLM.

    Adapts classify_domain_content (returns {score:1-10, label:str})
    into the normalized format used by SPECTRE scoring.

    Args:
        client: Optional Anthropic client.
        domain: Domain name.
        content_text: Archived content text.

    Returns:
        Dict with relevance_score (0.0-1.0), label.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert isinstance(content_text, str), "content must be string"

    default: dict[str, Any] = {"relevance_score": 0.0, "label": "unknown"}
    if client is None or not content_text:
        return default
    try:
        raw = await client.classify_domain_content(content_text, domain)
        score_1_10 = int(raw.get("score", 0))
        return {
            "relevance_score": min(1.0, max(0.0, score_1_10 / 10.0)),
            "label": raw.get("label", "unknown"),
        }
    except Exception as exc:
        logger.warning("llm_classify_failed", domain=domain, error=str(exc))
        return default


def _calculate_community_score(github_mentions: int, reddit_mentions: int) -> float:
    """Calculate community presence score from GitHub and Reddit mentions.

    Formula: min(100, (github_mentions * 10) + (reddit_mentions * 5))

    Args:
        github_mentions: Number of GitHub code/repo mentions.
        reddit_mentions: Number of Reddit post mentions.

    Returns:
        Community score 0-100.
    """
    assert isinstance(github_mentions, int) and github_mentions >= 0, "github must be non-negative int"
    assert isinstance(reddit_mentions, int) and reddit_mentions >= 0, "reddit must be non-negative int"

    raw = (github_mentions * 10) + (reddit_mentions * 5)
    return min(100.0, float(raw))


def _calculate_keyword_score(
    domain: str,
    content: str,
) -> tuple[float, dict[str, list[str]]]:
    """Match domain name + content against niche keyword tiers.

    Score: sum(tier_weight * 25 for each matched tier keyword), capped at 100.

    Args:
        domain: Domain name to analyze.
        content: Content text to search for keywords.

    Returns:
        Tuple of (score 0-100, dict of tier_name -> matched_keywords).
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert isinstance(content, str), "content must be string"

    combined = (domain + " " + content).lower()
    tier_matches: dict[str, list[str]] = {
        "tier1": [],
        "tier2": [],
        "tier3": [],
        "tier4": [],
    }

    raw_score: float = 0.0
    tiers = (
        ("tier1", NICHE_KEYWORDS_TIER1, 1.0),
        ("tier2", NICHE_KEYWORDS_TIER2, 0.7),
        ("tier3", NICHE_KEYWORDS_TIER3, 0.4),
        ("tier4", NICHE_KEYWORDS_TIER4, 0.2),
    )

    for tier_name, keywords, weight in tiers:
        for kw_idx, kw in enumerate(keywords):
            if kw_idx >= MAX_LOOP_ITERATIONS:
                break
            if kw in combined:
                tier_matches[tier_name].append(kw)
                raw_score += weight * 25.0

    return min(100.0, raw_score), tier_matches


def _calculate_composite_score(
    tech_pct: float,
    llm_score: float,
    community: float,
    keyword: float,
) -> float:
    """Calculate weighted composite SPECTRE niche relevance score.

    Formula:
      score = (tech_backlink_pct * 0.40)
            + (llm_topic_score * 0.25)
            + (community_score * 0.20)
            + (keyword_score * 0.15)

    Args:
        tech_pct: Tech backlink percentage (0-100).
        llm_score: LLM topic relevance score (0-100).
        community: Community presence score (0-100).
        keyword: Keyword match score (0-100).

    Returns:
        Composite score 0-100.
    """
    assert 0.0 <= tech_pct <= 100.0, f"tech_pct must be 0-100, got {tech_pct}"
    assert 0.0 <= llm_score <= 100.0, f"llm_score must be 0-100, got {llm_score}"
    assert 0.0 <= community <= 100.0, f"community must be 0-100, got {community}"
    assert 0.0 <= keyword <= 100.0, f"keyword must be 0-100, got {keyword}"

    score = (
        (tech_pct * _WEIGHT_TECH_BACKLINK)
        + (llm_score * _WEIGHT_LLM_TOPIC)
        + (community * _WEIGHT_COMMUNITY)
        + (keyword * _WEIGHT_KEYWORD)
    )
    return min(100.0, max(0.0, score))


def _estimate_tech_backlink_pct(
    domain: VerifiedDomain,
    github_mentions: int,
    reddit_mentions: int,
) -> float:
    """Estimate percentage of backlinks from tech sources.

    Heuristic based on available signals: trust/citation ratio,
    community signals, and niche keyword hits.

    Args:
        domain: Verified domain with backlink metrics.
        github_mentions: GitHub mention count.
        reddit_mentions: Reddit mention count.

    Returns:
        Estimated tech backlink percentage (0-100).
    """
    assert isinstance(domain, VerifiedDomain), "must be VerifiedDomain"
    assert github_mentions >= 0 and reddit_mentions >= 0, "mentions must be non-negative"

    base: float = 20.0

    # Trust/citation ratio signal
    if domain.citation_flow > 0:
        tf_cf_ratio = domain.trust_flow / domain.citation_flow
        if tf_cf_ratio > 0.8:
            base += 20.0
        elif tf_cf_ratio > 0.5:
            base += 10.0

    # Community presence boosts tech likelihood
    if github_mentions > 5:
        base += 25.0
    elif github_mentions > 0:
        base += 15.0

    if reddit_mentions > 3:
        base += 15.0
    elif reddit_mentions > 0:
        base += 8.0

    # Niche keyword hits from ARCHIVIST pass-through
    kw_count = len(domain.niche_keyword_hits)
    if kw_count > 3:
        base += 15.0
    elif kw_count > 0:
        base += 8.0

    return min(100.0, base)


def _build_signal_objects(
    github_data: dict[str, Any],
    reddit_data: dict[str, Any],
    domain_name: str,
) -> tuple[GitHubSignal, RedditSignal, BrandAnalysis]:
    """Build GitHub, Reddit, and Brand analysis objects from raw data.

    Args:
        github_data: Raw GitHub API response data.
        reddit_data: Raw Reddit API response data.
        domain_name: Full domain string for brand extraction.

    Returns:
        Tuple of (GitHubSignal, RedditSignal, BrandAnalysis).
    """
    assert isinstance(github_data, dict), "github_data must be dict"
    assert isinstance(domain_name, str) and len(domain_name) >= 4, "invalid domain_name"

    github_signal = GitHubSignal(
        repo_mentions=github_data.get("total_count", 0),
        total_stars=0, total_forks=0,
        readme_mentions=github_data.get("readme_mentions", 0), issue_mentions=0,
    )
    reddit_signal = RedditSignal(
        total_mentions=reddit_data.get("total_mentions", 0),
        total_upvotes=reddit_data.get("total_upvotes", 0),
        subreddits_seen=tuple(reddit_data.get("subreddits_found", [])),
        avg_sentiment=0.0,
    )
    brand_name = domain_name.rsplit(".", 1)[0] if "." in domain_name else domain_name
    brand_analysis = BrandAnalysis(
        brand_name=brand_name,
        is_pronounceable=len(brand_name) <= 12, is_memorable=len(brand_name) <= 10,
        trademark_conflict=False, exact_match_searches=0,
        brand_searchability_score=min(1.0, max(0.0, (15 - len(brand_name)) / 15)),
    )
    return github_signal, reddit_signal, brand_analysis


def _build_scored_domain(
    domain: VerifiedDomain,
    spectre_score: float,
    github_data: dict[str, Any],
    reddit_data: dict[str, Any],
) -> ScoredDomain:
    """Build a ScoredDomain from scoring components and raw API data.

    Args:
        domain: Source VerifiedDomain.
        spectre_score: Final composite score.
        github_data: Raw GitHub API response data.
        reddit_data: Raw Reddit API response data.

    Returns:
        Fully constructed ScoredDomain.
    """
    assert isinstance(domain, VerifiedDomain), "must be VerifiedDomain"
    assert 0.0 <= spectre_score <= 100.0, "spectre_score must be 0-100"

    now = datetime.now(timezone.utc)
    gh, rd, brand = _build_signal_objects(github_data, reddit_data, domain.domain)

    return ScoredDomain(
        domain=domain.domain, tld=domain.tld, run_id=domain.run_id, scored_at=now,
        github_signal=gh, reddit_signal=rd, brand_analysis=brand,
        github_score=min(100.0, github_data.get("total_count", 0) * 10.0),
        reddit_score=min(100.0, reddit_data.get("total_mentions", 0) * 10.0),
        brand_score=brand.brand_searchability_score * 100.0,
        social_recency_score=50.0, spectre_score=round(spectre_score, 2),
        domain_authority=domain.domain_authority, spam_score=domain.spam_score,
        referring_domains=domain.referring_domains,
        trust_flow=domain.trust_flow, citation_flow=domain.citation_flow,
        years_active=domain.years_active, total_snapshots=domain.total_snapshots,
        content_drift_score=domain.content_analysis.content_drift_score,
        niche_relevance_score=domain.niche_relevance_score,
        niche_keyword_hits=domain.niche_keyword_hits, source=domain.source,
    )


def _build_mock_scored(domain: VerifiedDomain, idx: int, now: datetime) -> ScoredDomain:
    """Build a single mock ScoredDomain for dry-run mode.

    Args:
        domain: Source VerifiedDomain.
        idx: Index in the mock list (affects scores).
        now: Timestamp for scored_at.

    Returns:
        Mock ScoredDomain instance.
    """
    assert isinstance(domain, VerifiedDomain), "domain must be VerifiedDomain"
    assert idx >= 0, "idx must be non-negative"

    base_score = 40.0 + (idx * 5.0) % 50.0
    mock_gh = {"total_count": idx * 2, "readme_mentions": 0, "repo_names": []}
    mock_rd = {"total_mentions": idx, "subreddits_found": [], "total_upvotes": idx * 10}
    gh, rd, brand = _build_signal_objects(mock_gh, mock_rd, domain.domain)

    return ScoredDomain(
        domain=domain.domain, tld=domain.tld, run_id=domain.run_id, scored_at=now,
        github_signal=gh, reddit_signal=rd, brand_analysis=brand,
        github_score=min(100.0, idx * 20.0), reddit_score=min(100.0, idx * 10.0),
        brand_score=70.0, social_recency_score=50.0,
        spectre_score=round(min(100.0, base_score), 2),
        domain_authority=domain.domain_authority, spam_score=domain.spam_score,
        referring_domains=domain.referring_domains,
        trust_flow=domain.trust_flow, citation_flow=domain.citation_flow,
        years_active=domain.years_active, total_snapshots=domain.total_snapshots,
        content_drift_score=domain.content_analysis.content_drift_score,
        niche_relevance_score=domain.niche_relevance_score,
        niche_keyword_hits=domain.niche_keyword_hits, source=domain.source,
    )


def _generate_mock_scores(
    verified: list[VerifiedDomain],
    max_scored: int,
) -> list[ScoredDomain]:
    """Generate mock ScoredDomain results for dry-run mode.

    Args:
        verified: Input domains to generate mock scores for.
        max_scored: Maximum number to generate.

    Returns:
        List of mock ScoredDomain instances.
    """
    assert isinstance(verified, list), "verified must be a list"
    assert max_scored > 0, "max_scored must be positive"

    now = datetime.now(timezone.utc)
    results: list[ScoredDomain] = []
    for idx, domain in enumerate(verified):
        if idx >= max_scored or idx >= MAX_LOOP_ITERATIONS:
            break
        results.append(_build_mock_scored(domain, idx, now))
    return results

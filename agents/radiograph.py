"""RADIOGRAPH Agent — Deep backlink quality analysis.
Sprint 3: Backlinks-first scoring pivot.

Analyzes backlink quality using Wayback CDX API data and authority
domain matching. Produces a quality_score (0-100) per domain with
red flag detection for spam patterns.

Scoring matrix:
  tier1_backlinks * 15 (DR 70+ sites)
  tier2_backlinks * 5  (DR 40-70 sites)
  tier3_backlinks * 1  (DR 10-40 sites)
  spam_backlinks * -10

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import structlog

from config.constants import (
    MAX_LOOP_ITERATIONS,
    TIER1_AUTHORITY_DOMAINS,
)
from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
_TIER1_WEIGHT: int = 15
_TIER2_WEIGHT: int = 5
_TIER3_WEIGHT: int = 1
_SPAM_WEIGHT: int = -10
_MAX_RAW_SCORE: int = 200
_MAX_QUALITY_SCORE: float = 100.0
_CDX_RATE_LIMIT_DELAY: float = 1.0
_CDX_TIMEOUT_SECONDS: int = 30
_MAX_CDX_RESULTS: int = 500
_MAX_DOMAINS_PER_RUN: int = 100

# ---------------------------------------------------------------------------
# Tier 2 domains (DR 40-70) — well-known but not top-tier
# ---------------------------------------------------------------------------
_TIER2_AUTHORITY_DOMAINS: tuple[str, ...] = (
    "stackexchange.com", "stackoverflow.com", "dev.to", "hackernoon.com",
    "dzone.com", "infoq.com", "smashingmagazine.com", "css-tricks.com",
    "freecodecamp.org", "producthunt.com", "ycombinator.com",
    "digitalocean.com", "heroku.com", "netlify.com", "vercel.com",
    "npmjs.com", "pypi.org", "rubygems.org", "crunchbase.com",
    "angel.co", "dribbble.com", "behance.net", "codepen.io",
    "gitlab.com", "bitbucket.org", "sourceforge.net",
)

# ---------------------------------------------------------------------------
# Spam domain patterns
# ---------------------------------------------------------------------------
_SPAM_DOMAIN_PATTERNS: tuple[str, ...] = (
    "casino", "poker", "slots", "betting", "gambling",
    "payday", "pharma", "viagra", "cialis", "xanax",
    "porn", "xxx", "adult", "escort", "webcam",
    "cheap-", "buy-", "free-", "discount-",
    "spamlink", "linkfarm", "seo-link", "backlink-",
)

_SPAM_TLDS: tuple[str, ...] = (
    ".xyz", ".top", ".buzz", ".click", ".link",
    ".win", ".loan", ".racing", ".stream", ".gdn",
    ".men", ".party", ".science", ".work", ".date",
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
class BacklinkProfile:
    """Immutable backlink analysis result for a single domain."""

    __slots__ = (
        "domain", "tier1_count", "tier2_count", "tier3_count",
        "spam_count", "total_backlinks", "quality_score",
        "red_flags", "tier1_sources", "referring_domains_seen",
    )

    def __init__(
        self,
        domain: str,
        tier1_count: int,
        tier2_count: int,
        tier3_count: int,
        spam_count: int,
        total_backlinks: int,
        quality_score: float,
        red_flags: tuple[str, ...],
        tier1_sources: tuple[str, ...],
        referring_domains_seen: int,
    ) -> None:
        assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
        assert quality_score >= 0.0, "quality_score must be non-negative"
        self.domain = domain
        self.tier1_count = tier1_count
        self.tier2_count = tier2_count
        self.tier3_count = tier3_count
        self.spam_count = spam_count
        self.total_backlinks = total_backlinks
        self.quality_score = min(_MAX_QUALITY_SCORE, quality_score)
        self.red_flags = red_flags
        self.tier1_sources = tier1_sources
        self.referring_domains_seen = referring_domains_seen

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for reporting."""
        assert isinstance(self.domain, str), "domain must be a string"
        assert self.quality_score >= 0.0, "score must be non-negative"
        return {
            "domain": self.domain,
            "tier1_count": self.tier1_count,
            "tier2_count": self.tier2_count,
            "tier3_count": self.tier3_count,
            "spam_count": self.spam_count,
            "total_backlinks": self.total_backlinks,
            "quality_score": round(self.quality_score, 2),
            "red_flags": list(self.red_flags),
            "tier1_sources": list(self.tier1_sources),
            "referring_domains_seen": self.referring_domains_seen,
        }


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------
def _classify_referring_domain(ref_domain: str) -> str:
    """Classify a referring domain into tier1/tier2/tier3/spam.

    Args:
        ref_domain: The referring domain name (e.g., 'github.com').

    Returns:
        One of 'tier1', 'tier2', 'tier3', 'spam'.
    """
    assert isinstance(ref_domain, str), "ref_domain must be a string"
    assert len(ref_domain) > 0, "ref_domain must not be empty"

    lower: str = ref_domain.lower().strip()

    # Check spam patterns first
    for pattern in _SPAM_DOMAIN_PATTERNS:
        if pattern in lower:
            return "spam"
    for tld in _SPAM_TLDS:
        if lower.endswith(tld):
            return "spam"

    # Check tier 1
    for t1_domain in TIER1_AUTHORITY_DOMAINS:
        if lower == t1_domain or lower.endswith("." + t1_domain):
            return "tier1"

    # Check tier 2
    for t2_domain in _TIER2_AUTHORITY_DOMAINS:
        if lower == t2_domain or lower.endswith("." + t2_domain):
            return "tier2"

    return "tier3"


def _extract_domain_from_url(url: str) -> str:
    """Extract the root domain from a full URL.

    Args:
        url: Full URL string.

    Returns:
        Extracted domain name (lowercase).
    """
    assert isinstance(url, str), "url must be a string"
    assert len(url) > 0, "url must not be empty"

    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        hostname: str = parsed.hostname or url
        return hostname.lower().strip()
    except Exception:
        return url.lower().strip()


def _calculate_quality_score(
    tier1: int, tier2: int, tier3: int, spam: int,
) -> float:
    """Calculate quality score from tier counts.

    Formula: (t1*15 + t2*5 + t3*1 + spam*-10) normalized to 0-100.

    Args:
        tier1: Count of tier 1 backlinks.
        tier2: Count of tier 2 backlinks.
        tier3: Count of tier 3 backlinks.
        spam: Count of spam backlinks.

    Returns:
        Quality score clamped to 0-100.
    """
    assert isinstance(tier1, int) and tier1 >= 0, "tier1 must be non-negative int"
    assert isinstance(spam, int), "spam must be int"

    raw: int = (
        tier1 * _TIER1_WEIGHT
        + tier2 * _TIER2_WEIGHT
        + tier3 * _TIER3_WEIGHT
        + spam * _SPAM_WEIGHT
    )

    # Normalize: cap raw at _MAX_RAW_SCORE, floor at 0
    clamped: float = max(0.0, min(float(raw), float(_MAX_RAW_SCORE)))
    score: float = (clamped / _MAX_RAW_SCORE) * _MAX_QUALITY_SCORE
    return round(min(_MAX_QUALITY_SCORE, max(0.0, score)), 2)


def _detect_red_flags(
    tier1: int, tier2: int, tier3: int, spam: int,
    total: int, unique_domains: int,
) -> list[str]:
    """Detect quality red flags from backlink profile.

    Args:
        tier1: Tier 1 backlink count.
        tier2: Tier 2 backlink count.
        tier3: Tier 3 backlink count.
        spam: Spam backlink count.
        total: Total backlinks analyzed.
        unique_domains: Number of unique referring domains.

    Returns:
        List of red flag description strings.
    """
    assert isinstance(total, int) and total >= 0, "total must be non-negative"
    assert isinstance(unique_domains, int), "unique_domains must be int"

    flags: list[str] = []

    if total > 0 and spam / total > 0.30:
        flags.append(f"High spam ratio: {spam}/{total} ({spam/total*100:.0f}%)")

    if total > 0 and tier1 == 0 and tier2 == 0:
        flags.append("Zero authority backlinks (no tier 1 or tier 2)")

    if total > 50 and unique_domains < 5:
        flags.append(
            f"Low domain diversity: {unique_domains} domains for {total} links"
        )

    if total > 100 and unique_domains > 0:
        links_per_domain: float = total / unique_domains
        if links_per_domain > 20.0:
            flags.append(
                f"Suspicious link concentration: {links_per_domain:.1f} links/domain"
            )

    if spam > 10:
        flags.append(f"Elevated spam backlinks: {spam}")

    return flags


def _analyze_single_domain(
    domain: str,
    referring_urls: list[str],
) -> BacklinkProfile:
    """Analyze backlink quality for a single domain.

    Args:
        domain: The target domain being analyzed.
        referring_urls: List of referring URLs/domains.

    Returns:
        BacklinkProfile with tier counts and quality score.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert isinstance(referring_urls, list), "referring_urls must be a list"

    tier1: int = 0
    tier2: int = 0
    tier3: int = 0
    spam: int = 0
    unique_domains: set[str] = set()
    tier1_sources: list[str] = []

    for idx, url in enumerate(referring_urls):
        if idx >= MAX_LOOP_ITERATIONS:
            break
        ref_domain: str = _extract_domain_from_url(url)
        unique_domains.add(ref_domain)
        tier: str = _classify_referring_domain(ref_domain)

        if tier == "tier1":
            tier1 += 1
            if ref_domain not in tier1_sources:
                tier1_sources.append(ref_domain)
        elif tier == "tier2":
            tier2 += 1
        elif tier == "spam":
            spam += 1
        else:
            tier3 += 1

    total: int = len(referring_urls)
    quality: float = _calculate_quality_score(tier1, tier2, tier3, spam)
    flags: list[str] = _detect_red_flags(
        tier1, tier2, tier3, spam, total, len(unique_domains),
    )

    return BacklinkProfile(
        domain=domain,
        tier1_count=tier1,
        tier2_count=tier2,
        tier3_count=tier3,
        spam_count=spam,
        total_backlinks=total,
        quality_score=quality,
        red_flags=tuple(flags),
        tier1_sources=tuple(tier1_sources[:20]),
        referring_domains_seen=len(unique_domains),
    )


def _generate_mock_referring_urls(domain: str) -> list[str]:
    """Generate mock referring URLs for dry-run mode.

    Args:
        domain: Target domain for mock data.

    Returns:
        List of mock referring URLs.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) >= 4, "domain must be at least 4 chars"

    return [
        f"https://github.com/project/mentions-{domain}",
        f"https://reddit.com/r/programming/comments/{domain}",
        f"https://medium.com/article-about-{domain}",
        f"https://stackoverflow.com/questions/about-{domain}",
        f"https://dev.to/post-{domain}",
        f"https://news.ycombinator.com/item?id={domain}",
        f"https://techcrunch.com/article/{domain}",
        f"https://forbes.com/sites/article-{domain}",
        f"https://random-blog.xyz/link-{domain}",
        f"https://hackernoon.com/topic-{domain}",
    ]


def _parse_cdx_response(raw_data: list[list[str]]) -> list[str]:
    """Parse CDX JSON response into a list of URLs.

    The CDX API returns a list of lists where the first row
    contains headers. This extracts the original URLs from
    subsequent rows.

    Args:
        raw_data: Raw CDX JSON response (list of lists).

    Returns:
        List of URL strings extracted from the response.
    """
    assert isinstance(raw_data, list), "raw_data must be a list"
    assert all(isinstance(row, list) for row in raw_data[:1]), "rows must be lists"

    urls: list[str] = []
    if len(raw_data) > 1:
        for i, row in enumerate(raw_data[1:]):
            if i >= _MAX_CDX_RESULTS:
                break
            if len(row) >= 1:
                urls.append(row[0])

    assert isinstance(urls, list), "urls must be a list"
    return urls


async def _fetch_cdx_backlinks(
    domain: str, *, mock: bool = False,
) -> list[str]:
    """Fetch backlink-like data from Wayback CDX API.

    Uses CDX to find pages that referenced the target domain.
    This is a proxy for backlink discovery from archived pages.

    Args:
        domain: Target domain to find references for.
        mock: If True, return mock data.

    Returns:
        List of referring URL strings.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert isinstance(mock, bool), "mock must be bool"

    if mock:
        return _generate_mock_referring_urls(domain)

    import aiohttp

    cdx_url: str = "https://web.archive.org/cdx/search/cdx"
    params: dict[str, str | int] = {
        "url": f"*.{domain}",
        "output": "json",
        "fl": "original,timestamp",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "limit": _MAX_CDX_RESULTS,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=_CDX_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(cdx_url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "cdx_fetch_error",
                        domain=domain, status=response.status,
                    )
                    return []
                raw_data: list[list[str]] = await response.json()

        urls = _parse_cdx_response(raw_data)
        await asyncio.sleep(_CDX_RATE_LIMIT_DELAY)
        return urls

    except Exception as exc:
        logger.error(
            "cdx_backlink_fetch_failed",
            domain=domain, error=str(exc),
        )
        return []


async def run(
    settings: Settings,
    domains: list[str],
    *,
    mock: bool = False,
) -> list[BacklinkProfile]:
    """Run RADIOGRAPH backlink quality analysis on a list of domains.

    Args:
        settings: Pipeline settings (for future API key use).
        domains: List of domain name strings to analyze.
        mock: If True, use mock CDX data.

    Returns:
        List of BacklinkProfile sorted by quality_score descending.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(domains, list), "domains must be a list"

    if not domains:
        logger.warning("radiograph_empty_input")
        return []

    log = logger.bind(agent="radiograph", input_count=len(domains))
    log.info("radiograph_start")

    capped: list[str] = domains[:_MAX_DOMAINS_PER_RUN]
    profiles: list[BacklinkProfile] = []

    for idx, domain in enumerate(capped):
        if idx >= MAX_LOOP_ITERATIONS:
            break
        try:
            referring_urls: list[str] = await _fetch_cdx_backlinks(
                domain, mock=mock,
            )
            profile: BacklinkProfile = _analyze_single_domain(
                domain, referring_urls,
            )
            profiles.append(profile)
            log.info(
                "radiograph_analyzed",
                domain=domain,
                quality_score=profile.quality_score,
                tier1=profile.tier1_count,
                red_flags=len(profile.red_flags),
            )
        except Exception as exc:
            log.error(
                "radiograph_domain_failed",
                domain=domain, error=str(exc),
            )

    profiles.sort(key=lambda p: p.quality_score, reverse=True)
    log.info(
        "radiograph_complete",
        input=len(capped), analyzed=len(profiles),
    )

    assert isinstance(profiles, list), "result must be a list"
    assert all(isinstance(p, BacklinkProfile) for p in profiles), (
        "all items must be BacklinkProfile"
    )
    return profiles

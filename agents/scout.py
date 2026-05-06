"""SCOUT Discovery Agent — Pipeline Stage 1.

Pulls raw expired domain feeds from WhoisFreaks and CatchDoms,
filters by TLD, quality, and niche keywords, then deduplicates.

Target: 200-500 DomainCandidate per day.
Kill rate: 95-97% of raw domains filtered out.

NASA Power of 10 rules enforced throughout.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from clients.catchdoms import CatchDomsClient
from clients.whoisfreaks import WhoisFreaksClient
from config.constants import (
    ALLOWED_TLDS,
    MAX_DOMAIN_LENGTH,
    MAX_HYPHENS_IN_DOMAIN,
    MAX_LOOP_ITERATIONS,
    MAX_NUMBERS_IN_DOMAIN,
    NICHE_KEYWORDS,
    NICHE_KEYWORDS_TIER1,
    NICHE_KEYWORDS_TIER2,
    NICHE_KEYWORDS_TIER3,
    NICHE_KEYWORDS_TIER4,
    NICHE_KEYWORD_WEIGHTS,
    SPAM_TLDS,
)
from config.settings import Settings
from models.candidate import DomainCandidate

logger = structlog.get_logger(__name__)

_DIGIT_RE: re.Pattern[str] = re.compile(r"\d")
_HYPHEN_RE: re.Pattern[str] = re.compile(r"-")


def _passes_tld_filter(domain: str) -> bool:
    """Check if domain has an allowed TLD and not a spam TLD.

    Args:
        domain: Full domain string (e.g. "example.com").

    Returns:
        True if TLD is in ALLOWED_TLDS and not in SPAM_TLDS.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) > 0, "domain must not be empty"

    dot_idx = domain.rfind(".")
    if dot_idx < 0:
        return False
    tld = domain[dot_idx:].lower()
    if tld in SPAM_TLDS:
        return False
    return tld in ALLOWED_TLDS


def _passes_quality_filter(domain: str) -> bool:
    """Check domain quality: length, digit count, hyphen count.

    Args:
        domain: Full domain string.

    Returns:
        True if domain passes all quality checks.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) > 0, "domain must not be empty"

    if len(domain) > MAX_DOMAIN_LENGTH:
        return False
    dot_idx = domain.rfind(".")
    if dot_idx < 0:
        return False
    name_part = domain[:dot_idx]
    if len(name_part) < 3:
        return False
    if len(_DIGIT_RE.findall(name_part)) > MAX_NUMBERS_IN_DOMAIN:
        return False
    if len(_HYPHEN_RE.findall(name_part)) > MAX_HYPHENS_IN_DOMAIN:
        return False
    if name_part.startswith("-") or name_part.endswith("-"):
        return False
    return True


def _match_niche_keywords(domain: str) -> list[str]:
    """Match domain name against all 4 niche keyword tiers.

    Args:
        domain: Full domain string.

    Returns:
        List of matched keyword strings.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) > 0, "domain must not be empty"

    dot_idx = domain.rfind(".")
    if dot_idx < 0:
        return []
    name_lower = domain[:dot_idx].lower()
    matched: list[str] = []
    all_tiers = (
        NICHE_KEYWORDS_TIER1 + NICHE_KEYWORDS_TIER2
        + NICHE_KEYWORDS_TIER3 + NICHE_KEYWORDS_TIER4
    )
    for i, kw in enumerate(all_tiers):
        if i >= MAX_LOOP_ITERATIONS:
            break
        if kw in name_lower:
            matched.append(kw)
    return matched


def _deduplicate(domains: list[str]) -> list[str]:
    """Remove duplicate domains (case-insensitive).

    Args:
        domains: List of domain strings.

    Returns:
        Deduplicated list preserving first-seen order.
    """
    assert isinstance(domains, list), "domains must be a list"
    assert len(domains) <= MAX_LOOP_ITERATIONS, f"too large: {len(domains)}"

    seen: set[str] = set()
    result: list[str] = []
    for i, d in enumerate(domains):
        if i >= MAX_LOOP_ITERATIONS:
            break
        key = d.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _build_candidate(
    domain: str, source: str, keywords: list[str], run_id: str,
) -> DomainCandidate:
    """Build an immutable DomainCandidate from raw data.

    Args:
        domain: The domain name string.
        source: Feed source identifier.
        keywords: Matched niche keywords.
        run_id: Pipeline run identifier.

    Returns:
        Frozen DomainCandidate instance.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert "." in domain, f"domain must contain a dot: {domain}"

    dot_idx = domain.rfind(".")
    tld = domain[dot_idx:]
    score = min(1.0, sum(NICHE_KEYWORD_WEIGHTS.get(kw, 0.0) for kw in keywords))

    candidate = DomainCandidate(
        domain=domain, tld=tld, source=source,
        discovered_at=datetime.now(tz=timezone.utc),
        run_id=run_id,
        niche_keyword_hits=tuple(keywords),
        niche_relevance_score=round(score, 4),
    )
    assert isinstance(candidate, DomainCandidate), "build failed"
    return candidate


def _keyword_sort_key(candidate: DomainCandidate) -> float:
    """Return sort key: higher relevance score first.

    Args:
        candidate: A DomainCandidate to score.

    Returns:
        Negative relevance score (for descending sort).
    """
    assert isinstance(candidate, DomainCandidate), "must be DomainCandidate"
    assert hasattr(candidate, "niche_relevance_score"), "missing score"
    return -candidate.niche_relevance_score


async def _fetch_all_sources(
    settings: Settings, mock: bool, log: Any,
) -> list[tuple[str, str]]:
    """Pull raw domains from WhoisFreaks and CatchDoms.

    Args:
        settings: Pipeline settings with API keys.
        mock: Whether to use mock mode for clients.
        log: Bound structlog logger.

    Returns:
        List of (domain, source) tuples.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert log is not None, "log must not be None"

    raw: list[tuple[str, str]] = []
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # WhoisFreaks
    if settings.whoisfreaks_api_key or mock:
        wf = WhoisFreaksClient(settings, mock=mock)
        try:
            wf_doms = await wf.fetch_expired_domains(today)
            for i_wf, d in enumerate(wf_doms):
                if i_wf >= MAX_LOOP_ITERATIONS:
                    break
                raw.append((d, "whoisfreaks"))
            log.info("whoisfreaks_fetched", count=len(wf_doms))
        except Exception as exc:
            log.error("whoisfreaks_error", error=str(exc))

    # CatchDoms
    if settings.catchdoms_api_key or mock:
        cd = CatchDomsClient(settings, mock=mock)
        try:
            cd_results = await cd.fetch_domains()
            for i_cd, entry in enumerate(cd_results):
                if i_cd >= MAX_LOOP_ITERATIONS:
                    break
                name = entry.get("domain", "") if isinstance(entry, dict) else str(entry)
                if name:
                    raw.append((name.lower().strip(), "catchdoms"))
            log.info("catchdoms_fetched", count=len(cd_results))
        except Exception as exc:
            log.error("catchdoms_error", error=str(exc))

    return raw


def _apply_keyword_filter(
    domains: list[str], log: Any,
) -> tuple[dict[str, list[str]], list[str]]:
    """Match niche keywords and keep only domains with hits.

    Args:
        domains: Quality-filtered domain list.
        log: Bound structlog logger.

    Returns:
        Tuple of (keyword_map, matched_domain_list).
    """
    assert isinstance(domains, list), "domains must be a list"
    assert log is not None, "log must not be None"

    kw_map: dict[str, list[str]] = {}
    matched: list[str] = []
    for i, d in enumerate(domains):
        if i >= MAX_LOOP_ITERATIONS:
            break
        kws = _match_niche_keywords(d)
        if kws:
            kw_map[d] = kws
            matched.append(d)
    log.info("keyword_filter", before=len(domains), after=len(matched))
    return kw_map, matched


def _filter_and_build(
    raw_domains: list[tuple[str, str]],
    run_id: str, cap: int, log: Any,
) -> list[DomainCandidate]:
    """Apply filters, dedup, and build candidates.

    Args:
        raw_domains: (domain, source) tuples from feeds.
        run_id: Pipeline run identifier.
        cap: Maximum candidates to return.
        log: Bound structlog logger.

    Returns:
        Filtered, sorted list of DomainCandidate.
    """
    assert isinstance(raw_domains, list), "raw_domains must be a list"
    assert isinstance(run_id, str), "run_id must be string"

    domain_source: dict[str, str] = {}
    all_names: list[str] = []
    for i, (d, src) in enumerate(raw_domains):
        if i >= MAX_LOOP_ITERATIONS:
            break
        key = d.lower().strip()
        if key not in domain_source:
            domain_source[key] = src
            all_names.append(key)

    tld_ok = [d for i, d in enumerate(all_names)
              if i < MAX_LOOP_ITERATIONS and _passes_tld_filter(d)]
    log.info("tld_filter", before=len(all_names), after=len(tld_ok))

    qual_ok = [d for i, d in enumerate(tld_ok)
               if i < MAX_LOOP_ITERATIONS and _passes_quality_filter(d)]
    log.info("quality_filter", before=len(tld_ok), after=len(qual_ok))

    kw_map, matched = _apply_keyword_filter(qual_ok, log)
    unique = _deduplicate(matched)
    capped = unique[:cap]

    candidates: list[DomainCandidate] = []
    for i, d in enumerate(capped):
        if i >= MAX_LOOP_ITERATIONS:
            break
        try:
            candidates.append(
                _build_candidate(d, domain_source.get(d, "unknown"),
                                 kw_map.get(d, []), run_id)
            )
        except Exception as exc:
            log.error("build_failed", domain=d, error=str(exc))

    candidates.sort(key=_keyword_sort_key)
    return candidates


async def run(
    settings: Settings, *, mock: bool = False,
) -> list[DomainCandidate]:
    """Run SCOUT discovery pipeline.

    Args:
        settings: Frozen pipeline settings.
        mock: If True, use mock client data.

    Returns:
        List of DomainCandidate sorted by niche relevance.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(mock, bool), "mock must be boolean"

    run_id = str(uuid.uuid4())
    log = logger.bind(run_id=run_id, agent="scout")

    raw_domains = await _fetch_all_sources(settings, mock, log)
    raw_count = len(raw_domains)
    log.info("raw_domains_total", count=raw_count)

    candidates = _filter_and_build(
        raw_domains, run_id, settings.max_scout_candidates, log,
    )

    kill_rate = (
        round((1.0 - len(candidates) / raw_count) * 100, 1)
        if raw_count > 0 else 0.0
    )
    log.info("scout_complete", raw=raw_count,
             survivors=len(candidates), kill_rate_pct=kill_rate)

    assert isinstance(candidates, list), "result must be a list"
    assert all(isinstance(c, DomainCandidate) for c in candidates), (
        "all must be DomainCandidate"
    )
    return candidates

"""SENTINEL SEO Vetting Agent — Pipeline Stage 2.

Performs 3-layer SEO quality checks: Moz DA/PA/spam, DataForSEO
backlinks, and Google index verification.

Input: list[DomainCandidate] from SCOUT (200-500).
Output: list[VettedDomain] (20-60 per day target).
Kill rate: 85-90% of input.

NASA Power of 10 rules enforced throughout.
"""
from __future__ import annotations

from typing import Any

import structlog

from clients.dataforseo import DataForSEOClient
from clients.google_cse import GoogleCSEClient
from clients.moz_apify import MozApifyClient
from config.constants import MAX_LOOP_ITERATIONS
from config.settings import Settings
from models.candidate import DomainCandidate
from models.vetted import VettedDomain

logger = structlog.get_logger(__name__)

_MOZ_BATCH_SIZE: int = 10


def _check_kill_rules(
    da: int, spam: float, ref_domains: int, indexed: int,
    settings: Settings,
) -> tuple[bool, str]:
    """Evaluate kill rules. Any trigger kills the domain.

    Args:
        da: Domain Authority score (0-100).
        spam: Spam score percentage (0-100).
        ref_domains: Number of referring domains.
        indexed: Number of Google-indexed pages.
        settings: Pipeline settings with thresholds.

    Returns:
        Tuple of (killed, reason).
    """
    assert isinstance(da, int), "da must be an int"
    assert isinstance(spam, float), "spam must be a float"

    if da < settings.min_da_threshold:
        return (True, f"DA {da} < {settings.min_da_threshold}")
    if spam > settings.max_spam_score:
        return (True, f"Spam {spam}% > {settings.max_spam_score}%")
    if ref_domains < settings.min_referring_domains:
        return (True, f"RefDoms {ref_domains} < {settings.min_referring_domains}")
    if indexed == 0:
        return (True, "Zero indexed pages")
    return (False, "")


def _check_flag_rules(
    exact_match_pct: float, top_country_pct: float,
    top_country: str,
) -> list[str]:
    """Evaluate flag rules -- warnings that don't kill.

    Args:
        exact_match_pct: Exact-match anchor text percentage.
        top_country_pct: Percentage from top referring country.
        top_country: ISO code of the top country.

    Returns:
        List of flag description strings.
    """
    assert isinstance(exact_match_pct, float), "must be float"
    assert isinstance(top_country_pct, float), "must be float"

    flags: list[str] = []
    if exact_match_pct > 30.0:
        flags.append(f"High exact-match anchors: {exact_match_pct:.1f}%")
    en_countries = {"us", "gb", "uk", "ca", "au", "nz", "ie"}
    if top_country_pct > 80.0 and top_country.lower() not in en_countries:
        flags.append(f"Country dominance: {top_country} {top_country_pct:.1f}%")
    return flags


def _build_vetted(
    candidate: DomainCandidate, moz: dict[str, Any],
    backlinks: dict[str, Any], indexed: int, flags: list[str],
) -> VettedDomain:
    """Build an immutable VettedDomain from API results.

    Args:
        candidate: Source DomainCandidate.
        moz: Moz metrics dict (da, pa, spam_score).
        backlinks: DataForSEO backlink dict.
        indexed: Google-indexed page count.
        flags: Warning flags.

    Returns:
        Frozen VettedDomain instance.
    """
    assert isinstance(candidate, DomainCandidate), "must be DomainCandidate"
    assert isinstance(moz, dict), "moz must be a dict"

    vetted = VettedDomain(
        domain=candidate.domain, tld=candidate.tld,
        source=candidate.source, discovered_at=candidate.discovered_at,
        run_id=candidate.run_id,
        domain_authority=int(moz.get("da", moz.get("domain_authority", 0))),
        page_authority=int(moz.get("pa", moz.get("page_authority", 0))),
        spam_score=float(moz.get("spam_score", 0.0)),
        referring_domains=int(backlinks.get("referring_domains", 0)),
        backlinks_total=int(backlinks.get("total_backlinks", backlinks.get("backlinks_total", 0))),
        dofollow_ratio=float(backlinks.get("dofollow_ratio", 0.0)),
        indexed_pages=indexed,
        niche_keyword_hits=candidate.niche_keyword_hits,
        niche_relevance_score=candidate.niche_relevance_score,
        flags=tuple(flags),
    )
    assert isinstance(vetted, VettedDomain), "build failed"
    return vetted


def _init_clients(
    settings: Settings, mock: bool,
) -> tuple[MozApifyClient | None, DataForSEOClient | None, GoogleCSEClient | None]:
    """Create API client instances from settings.

    Args:
        settings: Pipeline settings with API credentials.
        mock: Whether to use mock mode.

    Returns:
        Tuple of (moz, dseo, gcse). None if unconfigured.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(mock, bool), "mock must be bool"

    moz: MozApifyClient | None = None
    dseo: DataForSEOClient | None = None
    gcse: GoogleCSEClient | None = None

    if settings.apify_api_token or mock:
        moz = MozApifyClient(settings, mock=mock)
    if (settings.dataforseo_login and settings.dataforseo_password) or mock:
        dseo = DataForSEOClient(settings, mock=mock)
    if (settings.google_cse_api_key and settings.google_cse_cx) or mock:
        gcse = GoogleCSEClient(settings, mock=mock)

    return moz, dseo, gcse


async def _get_moz_for_domain(
    domain: str, moz_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Look up Moz metrics from pre-fetched batch cache.

    Args:
        domain: Domain to look up.
        moz_cache: Dict mapping domain -> moz metrics.

    Returns:
        Moz metrics dict for this domain.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert isinstance(moz_cache, dict), "moz_cache must be a dict"

    if domain in moz_cache:
        return moz_cache[domain]
    return {"da": 0, "pa": 0, "spam_score": 100.0}


async def _batch_fetch_moz(
    moz_client: MozApifyClient,
    domains: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch Moz metrics in batches and build lookup dict.

    Args:
        moz_client: Initialized MozApifyClient.
        domains: List of domain strings.

    Returns:
        Dict mapping domain -> moz metrics dict.
    """
    assert isinstance(domains, list), "domains must be a list"
    assert moz_client is not None, "moz_client must not be None"

    cache: dict[str, dict[str, Any]] = {}
    for batch_start in range(0, len(domains), _MOZ_BATCH_SIZE):
        if batch_start >= MAX_LOOP_ITERATIONS:
            break
        batch = domains[batch_start:batch_start + _MOZ_BATCH_SIZE]
        try:
            results = await moz_client.get_domain_authority(batch)
            for i_m, item in enumerate(results):
                if i_m >= MAX_LOOP_ITERATIONS:
                    break
                d = item.get("domain", "")
                if d:
                    cache[d] = item
        except Exception as exc:
            logger.error("moz_batch_failed", error=str(exc))
    return cache


async def _vet_single(
    candidate: DomainCandidate, settings: Settings,
    moz_data: dict[str, Any],
    dseo: DataForSEOClient | None, gcse: GoogleCSEClient | None,
    log: Any,
) -> VettedDomain | None:
    """Run 3-layer vetting on one candidate.

    Args:
        candidate: The DomainCandidate to vet.
        settings: Pipeline settings.
        moz_data: Pre-fetched Moz metrics.
        dseo: DataForSEO client or None.
        gcse: Google CSE client or None.
        log: Bound structlog logger.

    Returns:
        VettedDomain if survived, None if killed.
    """
    assert isinstance(candidate, DomainCandidate), "must be DomainCandidate"
    assert isinstance(settings, Settings), "settings must be Settings"

    domain = candidate.domain
    da = int(moz_data.get("da", moz_data.get("domain_authority", 0)))
    spam = float(moz_data.get("spam_score", 100.0))

    if da < settings.min_da_threshold or spam > settings.max_spam_score:
        return None

    bl_data: dict[str, Any] = {}
    if dseo is not None:
        try:
            bl_data = await dseo.get_backlink_summary(domain)
        except Exception as exc:
            log.error("dseo_failed", domain=domain, error=str(exc))

    ref_doms = int(bl_data.get("referring_domains", 0))
    if ref_doms < settings.min_referring_domains:
        return None

    indexed = 1
    if gcse is not None:
        try:
            indexed = await gcse.get_indexed_pages(domain)
        except Exception as exc:
            log.warning("gcse_failed", domain=domain, error=str(exc))
            indexed = 1

    killed, _ = _check_kill_rules(da, spam, ref_doms, indexed, settings)
    if killed:
        return None

    flags = _check_flag_rules(
        float(bl_data.get("exact_match_anchor_pct", 0.0)),
        float(bl_data.get("top_country_pct", 0.0)),
        str(bl_data.get("top_country", "unknown")),
    )
    return _build_vetted(candidate, moz_data, bl_data, indexed, flags)


async def run(
    settings: Settings, candidates: list[DomainCandidate],
    *, mock: bool = False,
) -> list[VettedDomain]:
    """Run SENTINEL 3-layer SEO quality checks on candidates.

    Args:
        settings: Frozen pipeline settings.
        candidates: DomainCandidate list from SCOUT.
        mock: If True, use mock client data.

    Returns:
        List of VettedDomain sorted by DA descending.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(candidates, list), "candidates must be a list"

    if len(candidates) == 0:
        logger.warning("sentinel_empty_input")
        return []

    log = logger.bind(agent="sentinel", input_count=len(candidates))
    log.info("sentinel_start")

    moz_c, dseo_c, gcse_c = _init_clients(settings, mock)

    # Batch-fetch Moz metrics
    moz_cache: dict[str, dict[str, Any]] = {}
    if moz_c is not None:
        all_domains = [c.domain for c in candidates[:MAX_LOOP_ITERATIONS]]
        moz_cache = await _batch_fetch_moz(moz_c, all_domains)

    survivors: list[VettedDomain] = []
    killed: int = 0
    for idx, cand in enumerate(candidates):
        if idx >= MAX_LOOP_ITERATIONS:
            break
        try:
            m = await _get_moz_for_domain(cand.domain, moz_cache)
            result = await _vet_single(cand, settings, m, dseo_c, gcse_c, log)
            if result is not None:
                survivors.append(result)
            else:
                killed += 1
        except Exception as exc:
            log.error("vet_failed", domain=cand.domain, error=str(exc))

    survivors.sort(key=lambda v: -v.domain_authority)
    capped = survivors[:settings.max_sentinel_survivors]
    log.info("sentinel_complete", input=len(candidates),
             survivors=len(capped), killed=killed)

    assert isinstance(capped, list), "result must be a list"
    assert all(isinstance(v, VettedDomain) for v in capped), "all must be VettedDomain"
    return capped

"""ORACLE — Decision Agent (Pipeline Stage 5, Final).

Generates BUY_NOW / WATCH / SKIP verdicts with full reasoning.

Scoring bands (intentionally non-linear):
  DA: 25-35 -> 60, 35-50 -> 90, 50+ -> 70 (50+ without matching history = likely PBN)
  Referring domains: 100-300 -> 70, 300-1000 -> 95, 1000+ -> 80
  Niche relevance: direct SPECTRE score (0-100)
  Archive history: 3-5yr -> 70, 5-10yr -> 90, 10+ -> 100
  Anchor profile: >60% branded -> 90, 40-60% -> 70, <40% -> 40
  Price: <$500 -> 100, $500-2000 -> 80, $2000-5000 -> 50, >$5K -> 20

Weighted formula:
  overall = (da * 0.25) + (ref * 0.20) + (niche * 0.20)
          + (archive * 0.15) + (anchor * 0.10) + (price * 0.10)

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
NASA Rule 3: All loops have fixed upper bounds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from clients.anthropic_client import AnthropicClient
from config.constants import MAX_LOOP_ITERATIONS, MAX_SPECTRE_SCORED
from config.settings import Settings
from models.scored import ScoredDomain
from models.verdict import DomainVerdict, ScoreBreakdown, VerdictType

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------
_BUY_NOW_THRESHOLD: float = 80.0
_WATCH_THRESHOLD: float = 60.0

# ---------------------------------------------------------------------------
# Weight constants for the composite formula
# ---------------------------------------------------------------------------
_W_DA: float = 0.25
_W_REF: float = 0.20
_W_NICHE: float = 0.20
_W_ARCHIVE: float = 0.15
_W_ANCHOR: float = 0.10
_W_PRICE: float = 0.10


async def run(
    settings: Settings,
    scored: list[ScoredDomain],
    *,
    mock: bool = False,
) -> list[DomainVerdict]:
    """Generate final verdicts with Claude Opus reasoning.

    Args:
        settings: Pipeline configuration.
        scored: Domains scored by SPECTRE.
        mock: If True, generate mock verdicts without API calls.

    Returns:
        List of DomainVerdict sorted by final_score descending.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(scored, list), "scored must be a list"

    if not scored:
        logger.info("oracle_no_input", count=0)
        return []

    if mock:
        verdicts = _generate_mock_verdicts(scored)
    else:
        verdicts = await _judge_all_domains(settings, scored)

    verdicts.sort(key=lambda v: v.final_score, reverse=True)
    logger.info("oracle_complete", input_count=len(scored), verdict_count=len(verdicts))
    return verdicts


async def _judge_all_domains(
    settings: Settings,
    scored: list[ScoredDomain],
) -> list[DomainVerdict]:
    """Judge all scored domains using live API calls.

    Args:
        settings: Pipeline settings with API keys.
        scored: List of scored domains from SPECTRE.

    Returns:
        List of domain verdicts.
    """
    assert isinstance(scored, list) and len(scored) > 0, "need at least one domain"
    assert isinstance(settings, Settings), "settings required"

    anthropic = AnthropicClient(settings) if settings.anthropic_api_key else None
    verdicts: list[DomainVerdict] = []

    try:
        for idx, domain in enumerate(scored):
            if idx >= MAX_LOOP_ITERATIONS or idx >= MAX_SPECTRE_SCORED * 2:
                break
            try:
                verdict = await _judge_single_domain(domain, anthropic)
                verdicts.append(verdict)
            except Exception as exc:
                logger.error("oracle_domain_failed", domain=domain.domain, error=str(exc))
    finally:
        # AnthropicClient uses anthropic SDK (no explicit close needed)
        pass

    return verdicts


async def _judge_single_domain(
    domain: ScoredDomain,
    anthropic: AnthropicClient | None,
) -> DomainVerdict:
    """Evaluate a single domain and produce a verdict.

    Args:
        domain: Scored domain from SPECTRE.
        anthropic: Optional Anthropic client for reasoning generation.

    Returns:
        Complete DomainVerdict.
    """
    assert isinstance(domain, ScoredDomain), "domain must be ScoredDomain"
    assert anthropic is None or isinstance(anthropic, AnthropicClient), "invalid anthropic"

    # Calculate component scores
    estimated_price = _estimate_price(domain.domain_authority, domain.referring_domains)
    da_score = _score_domain_rating(domain.domain_authority)
    ref_score = _score_referring_domains(domain.referring_domains)
    niche_score = min(100.0, max(0.0, domain.spectre_score))
    archive_score = _score_archive_history(domain.years_active)
    anchor_score = _score_anchor_profile(
        domain.niche_relevance_score if domain.niche_relevance_score <= 100.0 else 50.0,
    )
    price_score = _score_price(estimated_price)

    # Weighted composite
    overall = (
        (da_score * _W_DA)
        + (ref_score * _W_REF)
        + (niche_score * _W_NICHE)
        + (archive_score * _W_ARCHIVE)
        + (anchor_score * _W_ANCHOR)
        + (price_score * _W_PRICE)
    )
    overall = round(min(100.0, max(0.0, overall)), 2)

    # Verdict
    verdict_type = _determine_verdict(overall)

    # Risk assessment
    risk_level, risk_factors = _assess_risk(domain)

    # LLM reasoning
    dossier = _build_dossier_for_llm(domain)
    reasoning_data = await _get_reasoning(anthropic, dossier)

    breakdown = _build_breakdown(
        da_score, ref_score, niche_score, archive_score,
        anchor_score, price_score, domain.spam_score,
    )
    return _build_verdict(domain, overall, verdict_type, breakdown, estimated_price, reasoning_data)


async def _get_reasoning(
    anthropic: AnthropicClient | None,
    dossier: dict[str, Any],
) -> dict[str, Any]:
    """Get LLM reasoning or generate a default.

    Args:
        anthropic: Optional Anthropic client.
        dossier: Domain dossier for the LLM.

    Returns:
        Dict with reasoning, strengths, weaknesses, recommended_use_cases.
    """
    assert isinstance(dossier, dict), "dossier must be a dict"
    assert "domain" in dossier, "dossier must have domain key"

    domain_name = dossier.get("domain", "unknown")
    default: dict[str, Any] = {
        "reasoning": f"Automated analysis for {domain_name} based on composite metrics.",
        "strengths": ["Passed all pipeline filters"],
        "weaknesses": ["Requires manual verification"],
        "recommended_use_cases": ["AI/dev tools content site"],
    }

    if anthropic is None:
        return default
    try:
        raw = await anthropic.generate_verdict(dossier)
        return {
            "reasoning": raw.get("reasoning", default["reasoning"]),
            "strengths": raw.get("risk_factors", default["strengths"])[:3],
            "weaknesses": raw.get("risk_factors", default["weaknesses"]),
            "recommended_use_cases": default["recommended_use_cases"],
        }
    except Exception as exc:
        logger.warning("oracle_reasoning_failed", domain=domain_name, error=str(exc))
        return default


def _score_domain_rating(da: int) -> float:
    """Score domain authority with non-linear bands.

    DA 25-35 -> 60pts, 35-50 -> 90pts, 50+ -> 70pts (PBN risk).

    Args:
        da: Domain authority (0-100).

    Returns:
        Component score (0-100).
    """
    assert isinstance(da, int), "da must be int"
    assert 0 <= da <= 100, f"da must be 0-100, got {da}"

    if da < 25:
        return max(0.0, da * 2.4)  # Linear ramp up to 60
    if da < 35:
        return 60.0
    if da < 50:
        return 90.0
    return 70.0  # 50+ penalty: likely PBN without matching history


def _score_referring_domains(count: int) -> float:
    """Score referring domain count with non-linear bands.

    100-300 -> 70pts, 300-1000 -> 95pts, 1000+ -> 80pts.

    Args:
        count: Number of referring domains.

    Returns:
        Component score (0-100).
    """
    assert isinstance(count, int), "count must be int"
    assert count >= 0, f"count must be non-negative, got {count}"

    if count < 100:
        return max(0.0, count * 0.7)  # Linear ramp
    if count < 300:
        return 70.0
    if count < 1000:
        return 95.0
    return 80.0  # 1000+ may include spam


def _score_archive_history(years: float) -> float:
    """Score archive history duration with non-linear bands.

    3-5yr -> 70pts, 5-10yr -> 90pts, 10+ -> 100pts.

    Args:
        years: Years of archive activity.

    Returns:
        Component score (0-100).
    """
    assert isinstance(years, (int, float)), "years must be numeric"
    assert years >= 0.0, f"years must be non-negative, got {years}"

    if years < 3.0:
        return max(0.0, years * 23.3)  # Linear ramp to ~70
    if years < 5.0:
        return 70.0
    if years < 10.0:
        return 90.0
    return 100.0


def _score_anchor_profile(branded_pct: float) -> float:
    """Score anchor text profile based on branded percentage.

    >60% branded -> 90pts, 40-60% -> 70pts, <40% -> 40pts.

    Args:
        branded_pct: Percentage of branded anchor text (0-100).

    Returns:
        Component score (0-100).
    """
    assert isinstance(branded_pct, (int, float)), "branded_pct must be numeric"
    assert 0.0 <= branded_pct <= 100.0, f"branded_pct must be 0-100, got {branded_pct}"

    if branded_pct > 60.0:
        return 90.0
    if branded_pct >= 40.0:
        return 70.0
    return 40.0


def _score_price(estimated_usd: float) -> float:
    """Score estimated acquisition price.

    <$500 -> 100pts, $500-2000 -> 80pts, $2000-5000 -> 50pts, >$5K -> 20pts.

    Args:
        estimated_usd: Estimated price in USD.

    Returns:
        Component score (0-100).
    """
    assert isinstance(estimated_usd, (int, float)), "price must be numeric"
    assert estimated_usd >= 0.0, f"price must be non-negative, got {estimated_usd}"

    if estimated_usd < 500.0:
        return 100.0
    if estimated_usd < 2000.0:
        return 80.0
    if estimated_usd < 5000.0:
        return 50.0
    return 20.0


def _estimate_price(da: int, ref_domains: int) -> float:
    """Heuristic price estimation based on DA and referring domains.

    Simple model: base from DA bracket + ref_domains multiplier.

    Args:
        da: Domain authority (0-100).
        ref_domains: Number of referring domains.

    Returns:
        Estimated price in USD.
    """
    assert isinstance(da, int) and 0 <= da <= 100, "da must be 0-100 int"
    assert isinstance(ref_domains, int) and ref_domains >= 0, "ref_domains must be non-negative"

    if da < 20:
        base = 50.0
    elif da < 30:
        base = 200.0
    elif da < 40:
        base = 800.0
    elif da < 50:
        base = 2000.0
    elif da < 60:
        base = 4000.0
    else:
        base = 8000.0

    ref_multiplier = 1.0 + min(2.0, ref_domains / 1000.0)
    price = base * ref_multiplier
    assert price >= 0.0, "estimated price must be non-negative"
    return round(price, 2)


def _determine_verdict(score: float) -> VerdictType:
    """Map overall score to verdict category.

    >= 80 -> BUY_NOW, >= 60 -> WATCH, < 60 -> SKIP.

    Args:
        score: Overall weighted score (0-100).

    Returns:
        VerdictType enum value.
    """
    assert isinstance(score, (int, float)), "score must be numeric"
    assert 0.0 <= score <= 100.0, f"score must be 0-100, got {score}"

    if score >= _BUY_NOW_THRESHOLD:
        return VerdictType.BUY_NOW
    if score >= _WATCH_THRESHOLD:
        return VerdictType.WATCH
    return VerdictType.SKIP


def _assess_risk(domain_data: ScoredDomain) -> tuple[str, list[str]]:
    """Assess risk level and identify risk factors.

    Args:
        domain_data: Scored domain with all metrics.

    Returns:
        Tuple of (risk_level, list of risk factor strings).
    """
    assert isinstance(domain_data, ScoredDomain), "must be ScoredDomain"
    assert domain_data.domain_authority >= 0, "DA must be non-negative"

    factors: list[str] = []

    if domain_data.spam_score > 15.0:
        factors.append(f"Elevated spam score: {domain_data.spam_score:.1f}")
    if domain_data.domain_authority > 50 and domain_data.spectre_score < 40:
        factors.append("High DA with low niche relevance suggests PBN history")
    if domain_data.content_drift_score > 0.5:
        factors.append(f"High content drift: {domain_data.content_drift_score:.2f}")
    if domain_data.referring_domains > 1000 and domain_data.trust_flow < 20:
        factors.append("High ref domains with low trust flow suggests link spam")
    if domain_data.years_active < 3.0:
        factors.append(f"Short archive history: {domain_data.years_active:.1f} years")

    risk_count = len(factors)
    if risk_count >= 3:
        level = "HIGH"
    elif risk_count >= 1:
        level = "MEDIUM"
    else:
        level = "LOW"

    return level, factors


def _build_dossier_for_llm(domain_data: ScoredDomain) -> dict[str, Any]:
    """Build a comprehensive dossier dict for LLM reasoning.

    Args:
        domain_data: Scored domain with all metrics.

    Returns:
        Dict with all relevant domain data for the LLM.
    """
    assert isinstance(domain_data, ScoredDomain), "must be ScoredDomain"
    assert len(domain_data.domain) >= 4, "invalid domain"

    return {
        "domain": domain_data.domain,
        "tld": domain_data.tld,
        "domain_authority": domain_data.domain_authority,
        "spam_score": domain_data.spam_score,
        "referring_domains": domain_data.referring_domains,
        "trust_flow": domain_data.trust_flow,
        "citation_flow": domain_data.citation_flow,
        "years_active": domain_data.years_active,
        "total_snapshots": domain_data.total_snapshots,
        "content_drift_score": domain_data.content_drift_score,
        "spectre_score": domain_data.spectre_score,
        "niche_relevance_score": domain_data.niche_relevance_score,
        "github_mentions": domain_data.github_signal.repo_mentions,
        "reddit_mentions": domain_data.reddit_signal.total_mentions,
        "brand_name": domain_data.brand_analysis.brand_name,
        "niche_keyword_hits": list(domain_data.niche_keyword_hits),
    }


def _build_breakdown(
    da_score: float,
    ref_score: float,
    niche_score: float,
    archive_score: float,
    anchor_score: float,
    price_score: float,
    spam_score: float,
) -> ScoreBreakdown:
    """Build a ScoreBreakdown from component scores.

    Args:
        da_score: DA component score.
        ref_score: Referring domains component score.
        niche_score: Niche relevance component score.
        archive_score: Archive history component score.
        anchor_score: Anchor profile component score.
        price_score: Price component score.
        spam_score: Raw spam score to invert.

    Returns:
        Immutable ScoreBreakdown.
    """
    assert 0.0 <= da_score <= 100.0, "da_score must be 0-100"
    assert 0.0 <= spam_score <= 100.0, "spam_score must be 0-100"

    return ScoreBreakdown(
        domain_authority_score=da_score,
        backlink_quality_score=ref_score,
        niche_relevance_score=niche_score,
        archive_integrity_score=archive_score,
        social_signal_score=anchor_score,
        brand_value_score=price_score,
        spam_safety_score=max(0.0, 100.0 - spam_score),
        registration_feasibility_score=80.0,
    )


def _build_verdict(
    domain: ScoredDomain,
    overall: float,
    verdict_type: VerdictType,
    breakdown: ScoreBreakdown,
    estimated_price: float,
    reasoning_data: dict[str, Any],
) -> DomainVerdict:
    """Construct the final DomainVerdict from all components.

    Args:
        domain: Source scored domain.
        overall: Weighted composite score.
        verdict_type: BUY_NOW, WATCH, or SKIP.
        breakdown: Pre-built score breakdown.
        estimated_price: Estimated acquisition price USD.
        reasoning_data: LLM reasoning output.

    Returns:
        Complete DomainVerdict.
    """
    assert isinstance(domain, ScoredDomain), "must be ScoredDomain"
    assert 0.0 <= overall <= 100.0, "overall must be 0-100"

    now = datetime.now(timezone.utc)
    reasoning_str = reasoning_data.get("reasoning", "No reasoning available")
    strengths = tuple(reasoning_data.get("strengths", ["Passed pipeline filters"]))
    weaknesses = tuple(reasoning_data.get("weaknesses", ["Manual review needed"]))
    use_cases = tuple(reasoning_data.get("recommended_use_cases", ["Content site"]))

    return DomainVerdict(
        domain=domain.domain, tld=domain.tld, run_id=domain.run_id, judged_at=now,
        verdict=verdict_type, final_score=overall,
        confidence=min(1.0, overall / 100.0), score_breakdown=breakdown,
        reasoning=reasoning_str, strengths=strengths, weaknesses=weaknesses,
        recommended_use_cases=use_cases, estimated_value_usd=estimated_price,
        registrar_availability="unknown", recommended_registrar="Namecheap",
        domain_authority=domain.domain_authority, spam_score=domain.spam_score,
        spectre_score=domain.spectre_score, years_active=domain.years_active,
        referring_domains=domain.referring_domains,
    )


def _build_mock_single_verdict(domain: ScoredDomain, now: datetime) -> DomainVerdict:
    """Build a single mock verdict for dry-run mode.

    Args:
        domain: Scored domain to create verdict for.
        now: Timestamp for judged_at.

    Returns:
        Mock DomainVerdict.
    """
    assert isinstance(domain, ScoredDomain), "must be ScoredDomain"
    assert isinstance(now, datetime), "now must be datetime"

    da_score = _score_domain_rating(domain.domain_authority)
    ref_score = _score_referring_domains(domain.referring_domains)
    niche_score = min(100.0, max(0.0, domain.spectre_score))
    archive_score = _score_archive_history(domain.years_active)
    anchor_score = 70.0
    estimated_price = _estimate_price(domain.domain_authority, domain.referring_domains)
    price_score = _score_price(estimated_price)

    overall = round(
        (da_score * _W_DA) + (ref_score * _W_REF) + (niche_score * _W_NICHE)
        + (archive_score * _W_ARCHIVE) + (anchor_score * _W_ANCHOR)
        + (price_score * _W_PRICE), 2,
    )
    overall = min(100.0, max(0.0, overall))
    verdict_type = _determine_verdict(overall)
    breakdown = _build_breakdown(
        da_score, ref_score, niche_score, archive_score,
        anchor_score, price_score, domain.spam_score,
    )
    reasoning_data: dict[str, Any] = {
        "reasoning": f"Mock analysis: {domain.domain} scores {overall:.1f}/100.",
        "strengths": ["Pipeline survivor", f"DA {domain.domain_authority}"],
        "weaknesses": ["Mock data -- not verified"],
        "recommended_use_cases": ["AI dev tools content"],
    }
    return _build_verdict(domain, overall, verdict_type, breakdown, estimated_price, reasoning_data)


def _generate_mock_verdicts(scored: list[ScoredDomain]) -> list[DomainVerdict]:
    """Generate mock verdicts for dry-run mode.

    Args:
        scored: List of scored domains.

    Returns:
        List of mock DomainVerdict instances.
    """
    assert isinstance(scored, list), "scored must be a list"
    assert len(scored) > 0, "need at least one domain"

    now = datetime.now(timezone.utc)
    verdicts: list[DomainVerdict] = []
    for idx, domain in enumerate(scored):
        if idx >= MAX_LOOP_ITERATIONS:
            break
        verdicts.append(_build_mock_single_verdict(domain, now))
    return verdicts

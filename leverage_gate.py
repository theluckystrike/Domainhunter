"""
Agentic Sprint OS — Leverage Gate Scoring Module.

Enforces minimum leverage thresholds before sprint execution.
Each sprint must pass the leverage gate (default: total >= 12/20)
to ensure resources are allocated to high-compound-return work.

NASA Power of 10 compliant:
- All functions < 60 lines
- 2+ assertions per function
- No global mutable state
- Bounded loops, validated inputs/outputs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Constants — immutable scoring bounds
_MIN_AXIS: Final[int] = 1
_MAX_AXIS: Final[int] = 5
_AXIS_COUNT: Final[int] = 4
_MAX_TOTAL: Final[int] = _MAX_AXIS * _AXIS_COUNT
_DEFAULT_MIN_TOTAL: Final[int] = 12

# Domain Hunter specific thresholds
_HIGH_SEARCH_VOLUME: Final[int] = 1000
_MED_SEARCH_VOLUME: Final[int] = 300
_HIGH_DA: Final[int] = 30
_MED_DA: Final[int] = 15
_LOW_COST_THRESHOLD: Final[float] = 50.0
_MED_COST_THRESHOLD: Final[float] = 200.0


@dataclass(frozen=True)
class LeverageScore:
    """Immutable leverage score for a sprint or action."""

    scalability: int
    compounding: int
    autonomy: int
    revenue_path: int
    total: int
    evidence: dict[str, str] = field(default_factory=dict)


def _validate_axis(value: int, name: str) -> None:
    """Validate a single axis score is within bounds."""
    assert isinstance(value, int), f"{name} must be int, got {type(value).__name__}"
    assert _MIN_AXIS <= value <= _MAX_AXIS, (
        f"{name} must be {_MIN_AXIS}-{_MAX_AXIS}, got {value}"
    )


def _validate_evidence(evidence: dict[str, str]) -> None:
    """Validate evidence dict has correct structure."""
    assert isinstance(evidence, dict), "evidence must be a dict"
    required_keys = {"scalability", "compounding", "autonomy", "revenue_path"}
    missing = required_keys - set(evidence.keys())
    assert not missing, f"evidence missing keys: {missing}"


def score_sprint(
    objective: str,
    scalability: int,
    compounding: int,
    autonomy: int,
    revenue_path: int,
    evidence: dict[str, str],
) -> LeverageScore:
    """Score a sprint's leverage across 4 axes.

    Args:
        objective: Sprint objective description (non-empty).
        scalability: 1-5, how well this scales without linear effort.
        compounding: 1-5, how much value compounds over time.
        autonomy: 1-5, how autonomous the execution is.
        revenue_path: 1-5, how direct the path to revenue.
        evidence: One evidence string per axis key.

    Returns:
        Frozen LeverageScore dataclass.
    """
    # Input validation
    assert isinstance(objective, str) and len(objective) > 0, (
        "objective must be non-empty string"
    )
    _validate_axis(scalability, "scalability")
    _validate_axis(compounding, "compounding")
    _validate_axis(autonomy, "autonomy")
    _validate_axis(revenue_path, "revenue_path")
    _validate_evidence(evidence)

    total = scalability + compounding + autonomy + revenue_path

    result = LeverageScore(
        scalability=scalability,
        compounding=compounding,
        autonomy=autonomy,
        revenue_path=revenue_path,
        total=total,
        evidence=dict(evidence),
    )

    # Output validation
    assert result.total == sum([
        result.scalability, result.compounding, result.autonomy, result.revenue_path
    ]), "total must equal sum of axes"
    assert _AXIS_COUNT <= result.total <= _MAX_TOTAL, (
        f"total must be {_AXIS_COUNT}-{_MAX_TOTAL}"
    )

    return result


def enforce_gate(
    score: LeverageScore, min_total: int = _DEFAULT_MIN_TOTAL
) -> tuple[bool, str]:
    """Enforce the leverage gate threshold.

    Args:
        score: A LeverageScore to evaluate.
        min_total: Minimum total score to pass (default 12/20).

    Returns:
        Tuple of (passes: bool, reason: str).
    """
    # Input validation
    assert isinstance(score, LeverageScore), "score must be a LeverageScore"
    assert isinstance(min_total, int) and _AXIS_COUNT <= min_total <= _MAX_TOTAL, (
        f"min_total must be {_AXIS_COUNT}-{_MAX_TOTAL}, got {min_total}"
    )

    passes = score.total >= min_total

    if passes:
        reason = (
            f"PASS: {score.total}/{_MAX_TOTAL} >= {min_total} threshold. "
            f"Sprint approved for execution."
        )
    else:
        deficit = min_total - score.total
        weakest_axis = min(
            ["scalability", "compounding", "autonomy", "revenue_path"],
            key=lambda a: getattr(score, a),
        )
        reason = (
            f"FAIL: {score.total}/{_MAX_TOTAL} < {min_total} threshold "
            f"(deficit: {deficit}). Weakest axis: {weakest_axis} "
            f"({getattr(score, weakest_axis)}/{_MAX_AXIS}). "
            f"Refactor sprint to increase leverage before executing."
        )

    # Output validation
    assert isinstance(passes, bool), "passes must be bool"
    assert len(reason) > 0, "reason must be non-empty"

    return passes, reason


def format_gate_table(score: LeverageScore) -> str:
    """Format a LeverageScore as a markdown table.

    Args:
        score: The LeverageScore to format.

    Returns:
        Markdown-formatted table string.
    """
    # Input validation
    assert isinstance(score, LeverageScore), "score must be a LeverageScore"
    assert _AXIS_COUNT <= score.total <= _MAX_TOTAL, "score.total out of range"

    bar_width = 5
    axes = [
        ("Scalability", score.scalability, score.evidence.get("scalability", "")),
        ("Compounding", score.compounding, score.evidence.get("compounding", "")),
        ("Autonomy", score.autonomy, score.evidence.get("autonomy", "")),
        ("Revenue Path", score.revenue_path, score.evidence.get("revenue_path", "")),
    ]

    lines = [
        "| Axis | Score | Bar | Evidence |",
        "|------|-------|-----|----------|",
    ]

    for name, value, ev in axes:
        bar = "\u2588" * value + "\u2591" * (bar_width - value)
        lines.append(f"| {name} | {value}/{_MAX_AXIS} | {bar} | {ev} |")

    lines.append(f"| **TOTAL** | **{score.total}/{_MAX_TOTAL}** | | |")

    result = "\n".join(lines)

    # Output validation
    assert "| Axis |" in result, "table must contain header"
    assert f"{score.total}/{_MAX_TOTAL}" in result, "table must contain total"

    return result


def _tier_score(value: float, thresholds: tuple[float, ...]) -> int:
    """Map a value to a 1-5 score using 4 descending thresholds.

    thresholds must be (t5, t4, t3, t2) in descending order.
    value >= t5 → 5, value >= t4 → 4, ..., else → 1.
    """
    assert len(thresholds) == 4, "must provide exactly 4 thresholds"
    assert all(thresholds[i] >= thresholds[i + 1] for i in range(3)), (
        "thresholds must be descending"
    )
    for i, t in enumerate(thresholds):
        if value >= t:
            return 5 - i
    return 1


def _tier_score_ascending(value: float, thresholds: tuple[float, ...]) -> int:
    """Map a value to a 1-5 score using 4 ascending thresholds (lower=better).

    thresholds must be (t5, t4, t3, t2) in ascending order.
    value <= t5 → 5, value <= t4 → 4, ..., else → 1.
    """
    assert len(thresholds) == 4, "must provide exactly 4 thresholds"
    assert all(thresholds[i] <= thresholds[i + 1] for i in range(3)), (
        "thresholds must be ascending"
    )
    for i, t in enumerate(thresholds):
        if value <= t:
            return 5 - i
    return 1


def _build_domain_evidence(
    domain: str, monthly_searches: int, da: int, cost: float, rev_signal: float
) -> dict[str, str]:
    """Build evidence dict for domain acquisition scoring."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(rev_signal, float), "rev_signal must be float"
    cost_label = (
        "low" if cost <= _LOW_COST_THRESHOLD
        else "moderate" if cost <= _MED_COST_THRESHOLD
        else "high"
    )
    return {
        "scalability": f"{monthly_searches} monthly searches for {domain}",
        "compounding": f"DA {da} — existing authority compounds rankings",
        "autonomy": f"${cost:.0f} acquisition — {cost_label} capital dependency",
        "revenue_path": f"rev_signal={rev_signal:.2f} (traffic + authority)",
    }


def score_domain_acquisition(
    domain: str, monthly_searches: int, da: int, cost: float
) -> LeverageScore:
    """Score a domain acquisition opportunity for Domain Hunter.

    Args:
        domain: The domain name being evaluated.
        monthly_searches: Estimated monthly search volume for primary keyword.
        da: Domain authority (0-100).
        cost: Acquisition cost in USD.

    Returns:
        LeverageScore with domain-specific evidence.
    """
    # Input validation
    assert isinstance(domain, str) and len(domain) > 0, (
        "domain must be non-empty string"
    )
    assert isinstance(monthly_searches, int) and monthly_searches >= 0, (
        "monthly_searches must be non-negative int"
    )
    assert isinstance(da, int) and 0 <= da <= 100, "da must be 0-100"
    assert isinstance(cost, (int, float)) and cost >= 0, "cost must be non-negative"

    scalability = _tier_score(monthly_searches, (1000, 300, 100, 30))
    compounding = _tier_score(da, (30, 15, 8, 3))
    autonomy = _tier_score_ascending(cost, (50.0, 200.0, 500.0, 1000.0))
    rev_signal = (monthly_searches / max(_HIGH_SEARCH_VOLUME, 1)) + (da / 50.0)
    revenue_path = _tier_score(rev_signal, (2.0, 1.2, 0.6, 0.3))

    evidence = _build_domain_evidence(domain, monthly_searches, da, cost, rev_signal)

    result = score_sprint(
        objective=f"Acquire domain: {domain}",
        scalability=scalability,
        compounding=compounding,
        autonomy=autonomy,
        revenue_path=revenue_path,
        evidence=evidence,
    )

    # Output validation
    assert result.total >= _AXIS_COUNT, "total cannot be below minimum"
    assert domain in result.evidence["scalability"], "evidence must reference domain"

    return result


def score_tool_build(domain: str, niche: str, competition: str) -> LeverageScore:
    """Score building a tool on a domain for Domain Hunter.

    Args:
        domain: The domain to deploy the tool on.
        niche: The tool niche/category (e.g., "seo", "dev", "finance").
        competition: Competition level — "low", "medium", or "high".

    Returns:
        LeverageScore for the tool build decision.
    """
    # Input validation
    assert isinstance(domain, str) and len(domain) > 0, (
        "domain must be non-empty string"
    )
    assert isinstance(niche, str) and len(niche) > 0, (
        "niche must be non-empty string"
    )
    valid_competition = ("low", "medium", "high")
    assert competition in valid_competition, (
        f"competition must be one of {valid_competition}, got '{competition}'"
    )

    # Scalability: tools scale infinitely once built
    scalability = 5

    # Compounding: tools compound through SEO + backlinks + usage data
    compounding = 5

    # Autonomy: tools run autonomously after deployment
    autonomy = 5

    # Revenue path: depends on competition
    competition_scores = {"low": 5, "medium": 3, "high": 2}
    revenue_path = competition_scores[competition]

    evidence = {
        "scalability": f"Tool on {domain} serves unlimited users at zero marginal cost",
        "compounding": f"Tool in '{niche}' niche compounds via SEO + backlinks + usage",
        "autonomy": f"Fully autonomous after deployment — zero manual ops",
        "revenue_path": f"Competition: {competition} — {'clear' if competition == 'low' else 'contested' if competition == 'medium' else 'saturated'} revenue path",
    }

    result = score_sprint(
        objective=f"Build {niche} tool on {domain}",
        scalability=scalability,
        compounding=compounding,
        autonomy=autonomy,
        revenue_path=revenue_path,
        evidence=evidence,
    )

    # Output validation
    assert result.scalability == 5, "tool builds always score 5 scalability"
    assert result.autonomy == 5, "tool builds always score 5 autonomy"

    return result


def score_deployment(domains: list[str], tools_ready: int) -> LeverageScore:
    """Score a batch deployment sprint for Domain Hunter.

    Args:
        domains: List of domain names being deployed to.
        tools_ready: Number of tools ready to deploy.

    Returns:
        LeverageScore for the deployment batch.
    """
    # Input validation
    assert isinstance(domains, list) and len(domains) > 0, (
        "domains must be non-empty list"
    )
    assert all(isinstance(d, str) and len(d) > 0 for d in domains), (
        "all domains must be non-empty strings"
    )
    assert isinstance(tools_ready, int) and tools_ready >= 0, (
        "tools_ready must be non-negative int"
    )

    domain_count = len(domains)
    product = domain_count * tools_ready

    scalability = _tier_score(domain_count, (10, 5, 3, 2))
    compounding = _tier_score(tools_ready, (5, 3, 2, 1))
    autonomy = 5
    revenue_path = _tier_score(product, (20, 10, 5, 2))

    evidence = {
        "scalability": f"Deploying to {domain_count} domains in single batch",
        "compounding": f"{tools_ready} tools ready — each compounds independently",
        "autonomy": "Fully scripted batch deploy — zero manual intervention",
        "revenue_path": f"{domain_count} x {tools_ready} = {product} revenue surfaces",
    }

    result = score_sprint(
        objective=f"Batch deploy {tools_ready} tools to {domain_count} domains",
        scalability=scalability,
        compounding=compounding,
        autonomy=autonomy,
        revenue_path=revenue_path,
        evidence=evidence,
    )

    # Output validation
    assert result.autonomy == 5, "batch deploys always score 5 autonomy"
    assert result.total >= _AXIS_COUNT, "total cannot be below minimum"

    return result

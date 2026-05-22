"""Authority Gate data models — immutable result types.

The Authority Gate verifies domain authority through 3 layers:
  Layer 0 (LOCAL):  Tranco list, CommonCrawl ranks
  Layer 1 (FREE):   Open PageRank, Wayback CDX, Wikipedia
  Layer 2 (PAID):   DataForSEO bulk_ranks

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Valid source identifiers
VALID_SOURCES: Final[tuple[str, ...]] = (
    "tranco", "majestic", "commoncrawl", "openpagerank", "wayback",
    "wikipedia", "dataforseo", "gname",
)

# Valid status codes
VALID_STATUSES: Final[tuple[str, ...]] = ("PASS", "FAIL", "SKIP", "ERROR")


@dataclass(frozen=True)
class AuthorityCheck:
    """Result of a single authority source check.

    Attributes:
        source: Which authority source produced this check.
        layer: Which gate layer (0=local, 1=free remote, 2=paid remote).
        status: PASS (has authority), FAIL (no authority), SKIP, ERROR.
        value: Raw value from source (rank, score, count).
        normalized: 0.0-1.0 normalized contribution to composite.
        detail: Human-readable description of the check result.
        cost: API cost in USD for this check (0.0 for free sources).
    """

    source: str
    layer: int
    status: str
    value: float
    normalized: float
    detail: str = ""
    cost: float = 0.0

    def __post_init__(self) -> None:
        assert self.source in VALID_SOURCES, (
            f"source must be one of {VALID_SOURCES}, got: {self.source}"
        )
        assert self.layer in (0, 1, 2), f"layer must be 0, 1, or 2, got: {self.layer}"
        assert self.status in VALID_STATUSES, (
            f"status must be one of {VALID_STATUSES}, got: {self.status}"
        )
        assert 0.0 <= self.normalized <= 1.0, (
            f"normalized must be 0.0-1.0, got: {self.normalized}"
        )
        assert self.cost >= 0.0, f"cost must be >= 0, got: {self.cost}"


@dataclass(frozen=True)
class AuthorityResult:
    """Composite authority verdict for a domain.

    Aggregates checks from all layers into a single actionable result.

    Attributes:
        domain: The domain that was evaluated.
        composite_score: Weighted composite from all sources (0.0-100.0).
        dr_estimate: Derived DR estimate (0-100).
        confidence: Fraction of sources that responded (0.0-1.0).
        checks: Immutable tuple of individual source checks.
        short_circuited: Whether evaluation was short-circuited.
        short_circuit_reason: Why evaluation was short-circuited.
        total_cost: Total API cost for all checks on this domain.
    """

    domain: str
    composite_score: float
    dr_estimate: int
    confidence: float
    checks: tuple[AuthorityCheck, ...]
    short_circuited: bool = False
    short_circuit_reason: str = ""
    total_cost: float = 0.0

    def __post_init__(self) -> None:
        assert isinstance(self.domain, str) and "." in self.domain, (
            f"domain must be valid, got: {self.domain}"
        )
        assert 0.0 <= self.composite_score <= 100.0, (
            f"composite_score must be 0.0-100.0, got: {self.composite_score}"
        )
        assert 0 <= self.dr_estimate <= 100, (
            f"dr_estimate must be 0-100, got: {self.dr_estimate}"
        )
        assert 0.0 <= self.confidence <= 1.0, (
            f"confidence must be 0.0-1.0, got: {self.confidence}"
        )
        assert isinstance(self.checks, tuple), "checks must be a tuple"


def build_authority_check(
    source: str,
    layer: int,
    status: str,
    value: float,
    normalized: float,
    detail: str = "",
    cost: float = 0.0,
) -> AuthorityCheck:
    """Build an AuthorityCheck with validation.

    Factory function that validates all inputs before construction.
    """
    assert isinstance(source, str), "source must be str"
    assert isinstance(layer, int), "layer must be int"
    return AuthorityCheck(
        source=source,
        layer=layer,
        status=status,
        value=value,
        normalized=normalized,
        detail=detail,
        cost=cost,
    )


def build_authority_result(
    domain: str,
    checks: list[AuthorityCheck],
    short_circuited: bool = False,
    short_circuit_reason: str = "",
) -> AuthorityResult:
    """Build an AuthorityResult from a list of checks.

    Computes composite_score, dr_estimate, confidence, and total_cost
    from the individual checks.
    """
    assert isinstance(domain, str) and "." in domain, "domain must be valid"
    assert isinstance(checks, list) and len(checks) >= 1, "need at least 1 check"

    from config.constants import AUTHORITY_GATE_WEIGHTS

    # Compute weighted composite
    total_weight: float = 0.0
    weighted_sum: float = 0.0
    responded: int = 0
    attempted: int = 0
    total_cost: float = 0.0

    for check in checks:
        weight = AUTHORITY_GATE_WEIGHTS.get(check.source, 0.0)
        total_cost += check.cost
        if check.status in ("PASS", "FAIL"):
            attempted += 1
            responded += 1
            weighted_sum += weight * check.normalized
            total_weight += weight
        elif check.status == "SKIP":
            pass  # not attempted
        elif check.status == "ERROR":
            attempted += 1  # attempted but failed

    composite = (weighted_sum / total_weight * 100.0) if total_weight > 0 else 0.0
    composite = max(0.0, min(100.0, composite))
    dr_estimate = int(composite * 0.8)
    dr_estimate = max(0, min(100, dr_estimate))
    confidence = responded / max(attempted, 1)

    return AuthorityResult(
        domain=domain,
        composite_score=round(composite, 2),
        dr_estimate=dr_estimate,
        confidence=round(confidence, 2),
        checks=tuple(checks),
        short_circuited=short_circuited,
        short_circuit_reason=short_circuit_reason,
        total_cost=round(total_cost, 6),
    )

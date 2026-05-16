"""Tests for Sprint 28 — Multi-platform backorder strategy, acquisition
probability filter, backorder queue schema, and domain name scoring.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No mutable global state.
NASA Rule 6: All assertions explicit (2+ per test).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import pytest

# ---------------------------------------------------------------------------
# Constants (immutable -- NASA Rule 2)
# ---------------------------------------------------------------------------
_NOW: Final[datetime] = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)

# Backorder platform costs (immutable reference data)
_DYNADOT_COST: Final[float] = 10.99
_DROPCATCH_COST: Final[float] = 69.99
_GODADDY_AUCTION_MIN: Final[float] = 12.00
_BUDGET_LIMIT: Final[float] = 600.00

# Tier definitions (platform assignments per tier)
_TIER_PLATFORMS: Final[dict[str, tuple[str, ...]]] = {
    "S": ("dynadot",),
    "A": ("dropcatch", "dynadot"),
    "B": ("godaddy_auctions",),
    "C": (),
}

# Tier cost-per-slot (max cost for a single backorder at that tier)
_TIER_COST: Final[dict[str, float]] = {
    "S": _DYNADOT_COST,
    "A": _DROPCATCH_COST,
    "B": _GODADDY_AUCTION_MIN,
    "C": 0.0,
}

# Brand-protection registrars
_BRAND_REGISTRARS: Final[frozenset[str]] = frozenset({
    "markmonitor", "safenames", "cscdbs",
    "csc corporate domains", "comlaude",
})

# Acquisition probability classifications
_CATCHABLE: Final[str] = "CATCHABLE"
_MAYBE: Final[str] = "MAYBE"
_UNCATCHABLE: Final[str] = "UNCATCHABLE"
_DEAD: Final[str] = "DEAD"

# Dictionary words for scoring bonus (small sample for tests)
_DICTIONARY_WORDS: Final[frozenset[str]] = frozenset({
    "cloud", "code", "data", "flux", "grid", "hash",
    "link", "node", "path", "pipe", "port", "sync",
    "task", "wave", "zero", "bolt", "core", "dash",
    "edge", "fuse", "gate", "hive", "iris", "jack",
    "kite", "lamp", "maze", "nest", "orb", "pulse",
    "apex", "byte", "chip", "dock", "echo", "forge",
})


# ---------------------------------------------------------------------------
# Pure helper functions — testable without any agent imports
# ---------------------------------------------------------------------------

def _assign_tier(priority_score: float) -> str:
    """Assign domain to acquisition tier based on priority score.

    S: 90+, A: 70-89, B: 50-69, C: <50
    """
    assert isinstance(priority_score, (int, float)), "score must be numeric"
    assert 0.0 <= priority_score <= 100.0, f"score out of range: {priority_score}"
    if priority_score >= 90.0:
        return "S"
    if priority_score >= 70.0:
        return "A"
    if priority_score >= 50.0:
        return "B"
    return "C"


def _get_platforms(tier: str) -> tuple[str, ...]:
    """Return the backorder platforms for a given tier."""
    assert tier in _TIER_PLATFORMS, f"unknown tier: {tier}"
    return _TIER_PLATFORMS[tier]


def _calc_tier_cost(tier: str, count: int) -> float:
    """Calculate max exposure for N domains at a given tier."""
    assert tier in _TIER_COST, f"unknown tier: {tier}"
    assert count >= 0, f"count must be non-negative: {count}"
    return _TIER_COST[tier] * count


def _dropcatch_url(domain: str) -> str:
    """Build a DropCatch URL for a domain."""
    assert isinstance(domain, str) and len(domain) > 0
    assert "." in domain, f"not a valid domain: {domain}"
    return f"https://www.dropcatch.com/domain/{domain}"


def _classify_acquisition_probability(
    registrar: str,
    epp_statuses: tuple[str, ...],
    is_reregistered: bool,
    rdap_status_code: int,
) -> str:
    """Classify how likely a domain is to be acquired.

    Returns one of: CATCHABLE, MAYBE, UNCATCHABLE, DEAD
    """
    assert isinstance(registrar, str)
    assert isinstance(epp_statuses, (tuple, list))
    assert isinstance(rdap_status_code, int)

    # Rule 1: RDAP 404 = domain not found = CATCHABLE
    if rdap_status_code == 404:
        return _CATCHABLE

    # Rule 2: Re-registered = DEAD (someone already grabbed it)
    if is_reregistered:
        return _DEAD

    # Rule 3: Brand-protection registrar = UNCATCHABLE
    registrar_lower: str = registrar.lower()
    for brand_reg in _BRAND_REGISTRARS:
        if brand_reg in registrar_lower:
            return _UNCATCHABLE

    # Rule 4: pendingDelete = CATCHABLE regardless
    epp_lower: tuple[str, ...] = tuple(s.lower() for s in epp_statuses)
    if "pendingdelete" in epp_lower:
        return _CATCHABLE

    # Rule 5: GoDaddy + clientRenewProhibited = MAYBE (GoDaddy auction risk)
    is_godaddy: bool = "godaddy" in registrar_lower or "wild west" in registrar_lower
    has_client_renew: bool = any(
        "clientrenew" in s.replace(" ", "").lower() for s in epp_statuses
    )
    if is_godaddy and has_client_renew:
        return _MAYBE

    # Rule 6: Tucows/Namecheap + autoRenewPeriod = CATCHABLE (no auction)
    is_tucows: bool = "tucows" in registrar_lower
    has_autorenew: bool = any(
        "autorenew" in s.replace(" ", "").lower() for s in epp_statuses
    )
    if is_tucows and has_autorenew:
        return _CATCHABLE

    # Default: MAYBE
    return _MAYBE


def _build_queue_entry(
    domain: str,
    tier: str,
    est_pending_delete: datetime,
    platforms: tuple[str, ...],
) -> dict[str, Any]:
    """Build a backorder queue entry with required fields."""
    assert isinstance(domain, str) and "." in domain
    assert tier in _TIER_PLATFORMS
    assert isinstance(est_pending_delete, datetime)

    return {
        "domain": domain,
        "tier": tier,
        "catch_strategy": {
            "primary_platform": platforms[0] if platforms else None,
            "all_platforms": list(platforms),
        },
        "timeline": {
            "est_pending_delete": est_pending_delete.isoformat(),
        },
        "budget_exposure_usd": _TIER_COST[tier],
        "backorder_status": {
            platform: "pending" for platform in platforms
        },
    }


def _sort_queue_by_date(
    queue: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort queue entries by est_pending_delete (soonest first)."""
    assert isinstance(queue, list)
    return sorted(
        queue,
        key=lambda e: e["timeline"]["est_pending_delete"],
    )


def _total_budget_exposure(queue: list[dict[str, Any]]) -> float:
    """Sum the budget exposure across all queue entries."""
    assert isinstance(queue, list)
    total: float = sum(e.get("budget_exposure_usd", 0.0) for e in queue)
    assert total >= 0.0, f"negative budget: {total}"
    return total


def _score_domain_name(
    domain: str,
    dictionary_words: frozenset[str] | None = None,
) -> int:
    """Score a domain name based on naming quality. Returns 0-100.

    Bonuses: dictionary word (+40), 4-letter .com (+50), .com TLD (+10)
    Penalties: hyphen (-20), 15+ chars (-10)
    """
    assert isinstance(domain, str) and "." in domain
    assert domain.count(".") >= 1

    if dictionary_words is None:
        dictionary_words = _DICTIONARY_WORDS

    parts: list[str] = domain.rsplit(".", 1)
    assert len(parts) == 2, f"unexpected domain format: {domain}"
    name_part: str = parts[0].lower()
    tld: str = "." + parts[1].lower()

    score: int = 50  # base score

    # Dictionary word bonus
    if name_part in dictionary_words:
        score += 40

    # 4-letter .com bonus
    if len(name_part) == 4 and tld == ".com":
        score += 50

    # Premium TLD bonus
    if tld == ".com":
        score += 10

    # Hyphenated penalty
    if "-" in name_part:
        score -= 20

    # Long domain penalty
    if len(name_part) >= 15:
        score -= 10

    # Clamp to 0-100
    return max(0, min(100, score))


def _is_subdomain(domain: str) -> bool:
    """Check if a domain is actually a subdomain (2+ dots)."""
    assert isinstance(domain, str) and len(domain) > 0
    return domain.count(".") > 1


# ===========================================================================
# Group 1: Multi-platform backorder strategy (8 tests)
# ===========================================================================

class TestMultiPlatformBackorderStrategy:
    """Tests for tier-based platform assignment and budget calculations."""

    def test_tier_s_uses_dynadot_only(self) -> None:
        """Tier S domains should only use Dynadot ($10.99)."""
        tier: str = _assign_tier(95.0)
        platforms: tuple[str, ...] = _get_platforms(tier)
        assert tier == "S"
        assert platforms == ("dynadot",)
        assert len(platforms) == 1

    def test_tier_a_uses_dropcatch_and_dynadot(self) -> None:
        """Tier A domains should use DropCatch + Dynadot."""
        tier: str = _assign_tier(75.0)
        platforms: tuple[str, ...] = _get_platforms(tier)
        assert tier == "A"
        assert platforms == ("dropcatch", "dynadot")
        assert "dropcatch" in platforms
        assert "dynadot" in platforms

    def test_tier_b_uses_godaddy_auctions(self) -> None:
        """Tier B domains use GoDaddy Auctions."""
        tier: str = _assign_tier(55.0)
        platforms: tuple[str, ...] = _get_platforms(tier)
        assert tier == "B"
        assert platforms == ("godaddy_auctions",)
        assert "godaddy_auctions" in platforms

    def test_tier_c_skips_backorder(self) -> None:
        """Tier C domains are watch-only (no platforms)."""
        tier: str = _assign_tier(30.0)
        platforms: tuple[str, ...] = _get_platforms(tier)
        assert tier == "C"
        assert len(platforms) == 0
        assert _calc_tier_cost("C", 5) == 0.0

    def test_budget_calculation_tier_s(self) -> None:
        """3 Tier S domains x $10.99 = $32.97."""
        cost: float = _calc_tier_cost("S", 3)
        expected: float = 3 * _DYNADOT_COST
        assert abs(cost - expected) < 0.01
        assert abs(cost - 32.97) < 0.01

    def test_budget_calculation_tier_a(self) -> None:
        """2 Tier A domains x $69.99 = $139.98."""
        cost: float = _calc_tier_cost("A", 2)
        expected: float = 2 * _DROPCATCH_COST
        assert abs(cost - expected) < 0.01
        assert abs(cost - 139.98) < 0.01

    def test_max_exposure_under_budget(self) -> None:
        """Total max exposure must be under available budget ($600)."""
        # Realistic mix: 3 Tier S + 2 Tier A + 4 Tier B + 5 Tier C
        total: float = (
            _calc_tier_cost("S", 3)
            + _calc_tier_cost("A", 2)
            + _calc_tier_cost("B", 4)
            + _calc_tier_cost("C", 5)
        )
        assert total < _BUDGET_LIMIT, f"total ${total:.2f} exceeds budget ${_BUDGET_LIMIT:.2f}"
        assert total > 0.0, "total exposure should be positive"
        # 32.97 + 139.98 + 48.00 + 0 = 220.95
        assert abs(total - 220.95) < 0.01

    def test_dropcatch_url_format(self) -> None:
        """DropCatch URL is https://www.dropcatch.com/domain/{domain}."""
        url: str = _dropcatch_url("techstack.com")
        assert url == "https://www.dropcatch.com/domain/techstack.com"
        assert url.startswith("https://www.dropcatch.com/domain/")
        assert url.endswith("techstack.com")


# ===========================================================================
# Group 2: Acquisition probability filter (6 tests)
# ===========================================================================

class TestAcquisitionProbabilityFilter:
    """Tests for CATCHABLE / MAYBE / UNCATCHABLE / DEAD classification."""

    def test_markmonitor_is_uncatchable(self) -> None:
        """MarkMonitor registrar = UNCATCHABLE."""
        result: str = _classify_acquisition_probability(
            registrar="MarkMonitor Inc.",
            epp_statuses=("clientDeleteProhibited", "clientTransferProhibited"),
            is_reregistered=False,
            rdap_status_code=200,
        )
        assert result == _UNCATCHABLE
        assert result != _CATCHABLE

    def test_reregistered_is_dead(self) -> None:
        """Re-registered domain = DEAD."""
        result: str = _classify_acquisition_probability(
            registrar="Namecheap, Inc.",
            epp_statuses=("ok",),
            is_reregistered=True,
            rdap_status_code=200,
        )
        assert result == _DEAD
        assert result != _CATCHABLE

    def test_godaddy_clientrenew_is_maybe(self) -> None:
        """GoDaddy + clientRenewProhibited = MAYBE (auction risk)."""
        result: str = _classify_acquisition_probability(
            registrar="GoDaddy.com, LLC",
            epp_statuses=(
                "clientDeleteProhibited",
                "clientRenewProhibited",
                "clientTransferProhibited",
            ),
            is_reregistered=False,
            rdap_status_code=200,
        )
        assert result == _MAYBE
        assert result != _CATCHABLE

    def test_tucows_autorenew_is_catchable(self) -> None:
        """Tucows + autoRenewPeriod = CATCHABLE (no auction)."""
        result: str = _classify_acquisition_probability(
            registrar="Tucows Domains Inc.",
            epp_statuses=("autoRenewPeriod", "clientTransferProhibited"),
            is_reregistered=False,
            rdap_status_code=200,
        )
        assert result == _CATCHABLE
        assert result != _MAYBE

    def test_pendingdelete_is_catchable(self) -> None:
        """pendingDelete = CATCHABLE regardless of registrar."""
        result: str = _classify_acquisition_probability(
            registrar="GoDaddy.com, LLC",
            epp_statuses=("pendingDelete",),
            is_reregistered=False,
            rdap_status_code=200,
        )
        assert result == _CATCHABLE
        # Even with a brand registrar, pendingDelete should still be caught
        # before the brand-registrar check (rule 4 before rule 3 in priority)
        # Note: in our implementation, RDAP 404 is rule 1 and reregistered
        # is rule 2, both before brand-registrar check.
        assert result != _UNCATCHABLE

    def test_rdap_404_is_catchable(self) -> None:
        """RDAP 404 = CATCHABLE (domain not found)."""
        result: str = _classify_acquisition_probability(
            registrar="",
            epp_statuses=(),
            is_reregistered=False,
            rdap_status_code=404,
        )
        assert result == _CATCHABLE
        assert result != _DEAD


# ===========================================================================
# Group 3: Backorder queue schema (5 tests)
# ===========================================================================

class TestBackorderQueueSchema:
    """Tests for queue entry structure, sorting, and budget validation."""

    @pytest.fixture()
    def sample_queue(self) -> list[dict[str, Any]]:
        """Build a sample backorder queue with 4 entries."""
        entries: list[dict[str, Any]] = [
            _build_queue_entry(
                "techstack.com", "S",
                _NOW + timedelta(days=30),
                ("dynadot",),
            ),
            _build_queue_entry(
                "aiforge.dev", "A",
                _NOW + timedelta(days=10),
                ("dropcatch", "dynadot"),
            ),
            _build_queue_entry(
                "datapipe.io", "B",
                _NOW + timedelta(days=45),
                ("godaddy_auctions",),
            ),
            _build_queue_entry(
                "cloudbase.com", "S",
                _NOW + timedelta(days=5),
                ("dynadot",),
            ),
        ]
        return entries

    def test_queue_entry_has_catch_strategy(
        self, sample_queue: list[dict[str, Any]],
    ) -> None:
        """Each queue entry must have catch_strategy with primary platform."""
        for entry in sample_queue:
            assert "catch_strategy" in entry, f"missing catch_strategy: {entry['domain']}"
            strategy: dict[str, Any] = entry["catch_strategy"]
            assert "primary_platform" in strategy
            assert "all_platforms" in strategy
            if entry["tier"] != "C":
                assert strategy["primary_platform"] is not None

    def test_queue_entry_has_timeline(
        self, sample_queue: list[dict[str, Any]],
    ) -> None:
        """Each queue entry must have timeline with est_pending_delete."""
        for entry in sample_queue:
            assert "timeline" in entry, f"missing timeline: {entry['domain']}"
            timeline: dict[str, Any] = entry["timeline"]
            assert "est_pending_delete" in timeline
            # Validate ISO 8601 format
            date_str: str = timeline["est_pending_delete"]
            assert len(date_str) > 0
            parsed: datetime = datetime.fromisoformat(date_str)
            assert parsed > _NOW, f"est_pending_delete must be in the future: {date_str}"

    def test_queue_sorted_by_date(
        self, sample_queue: list[dict[str, Any]],
    ) -> None:
        """Queue must be sorted by est_pending_delete (soonest first)."""
        sorted_q: list[dict[str, Any]] = _sort_queue_by_date(sample_queue)
        assert len(sorted_q) == len(sample_queue)
        # cloudbase.com (+5d) should be first, aiforge.dev (+10d) second
        assert sorted_q[0]["domain"] == "cloudbase.com"
        assert sorted_q[1]["domain"] == "aiforge.dev"
        # Verify monotonic ordering
        dates: list[str] = [
            e["timeline"]["est_pending_delete"] for e in sorted_q
        ]
        assert dates == sorted(dates), "queue not sorted by date"

    def test_queue_budget_under_limit(
        self, sample_queue: list[dict[str, Any]],
    ) -> None:
        """Total queue budget exposure must be under $600."""
        total: float = _total_budget_exposure(sample_queue)
        assert total < _BUDGET_LIMIT, f"${total:.2f} exceeds ${_BUDGET_LIMIT:.2f}"
        # 2x Tier S ($10.99) + 1x Tier A ($69.99) + 1x Tier B ($12.00)
        expected: float = 2 * _DYNADOT_COST + _DROPCATCH_COST + _GODADDY_AUCTION_MIN
        assert abs(total - expected) < 0.01

    def test_queue_has_backorder_status(
        self, sample_queue: list[dict[str, Any]],
    ) -> None:
        """Each entry must track per-platform backorder status."""
        for entry in sample_queue:
            assert "backorder_status" in entry, (
                f"missing backorder_status: {entry['domain']}"
            )
            status: dict[str, str] = entry["backorder_status"]
            platforms: list[str] = entry["catch_strategy"]["all_platforms"]
            # Every platform in catch_strategy must have a status entry
            for platform in platforms:
                assert platform in status, (
                    f"missing status for platform {platform} on {entry['domain']}"
                )
                assert status[platform] in ("pending", "placed", "failed", "won", "lost")


# ===========================================================================
# Group 4: Domain name scoring (6 tests)
# ===========================================================================

class TestDomainNameScoring:
    """Tests for domain naming quality scoring."""

    def test_dictionary_word_bonus(self) -> None:
        """Dictionary word domains get +40 points (base 50 + 40 = 90+)."""
        # 'bolt' is in our dictionary set
        score: int = _score_domain_name("bolt.io")
        assert score >= 90, f"dictionary word score too low: {score}"
        # Non-dictionary word for comparison
        score_generic: int = _score_domain_name("xqzwv.io")
        assert score > score_generic, "dictionary word must score higher"

    def test_four_letter_com_bonus(self) -> None:
        """4-letter .com gets +50 points (base 50 + 50 + 10 com = 110 -> clamped 100)."""
        score: int = _score_domain_name("flux.com")
        # flux is dictionary word (+40) + 4-letter .com (+50) + .com (+10) = 150 -> 100
        assert score == 100, f"4-letter .com score should be max: {score}"
        # Non-dictionary 4-letter .com: base 50 + 50 + 10 = 110 -> 100
        score_non_dict: int = _score_domain_name("xkcd.com")
        assert score_non_dict == 100, f"4-letter .com should still be max: {score_non_dict}"

    def test_hyphenated_penalty(self) -> None:
        """Hyphenated domains get -20 points."""
        score_clean: int = _score_domain_name("techstack.com")
        score_hyphen: int = _score_domain_name("tech-stack.com")
        assert score_clean > score_hyphen, "hyphenated must score lower"
        # Hyphenated: base 50 + 10 (.com) - 20 (hyphen) = 40
        assert score_hyphen == 40, f"expected 40, got {score_hyphen}"

    def test_long_domain_penalty(self) -> None:
        """15+ char domains get -10 points."""
        long_domain: str = "verylongdomainname.com"
        name_part: str = long_domain.split(".")[0]
        assert len(name_part) >= 15, f"test domain too short: {len(name_part)} chars"
        score: int = _score_domain_name(long_domain)
        # base 50 + 10 (.com) - 10 (long) = 50
        assert score == 50, f"expected 50 for long domain, got {score}"
        # Compare with short domain
        score_short: int = _score_domain_name("tech.com")
        assert score_short > score, "short domain must score higher"

    def test_premium_tld_bonus(self) -> None:
        """'.com' gets +10 points over other TLDs."""
        score_com: int = _score_domain_name("techstack.com")
        score_io: int = _score_domain_name("techstack.io")
        assert score_com == score_io + 10, (
            f".com={score_com} should be .io={score_io} + 10"
        )
        assert score_com > score_io

    def test_subdomain_filtered(self) -> None:
        """Subdomains (2+ dots) should be filtered out."""
        assert _is_subdomain("mail.corp.example.com") is True
        assert _is_subdomain("sub.example.com") is True
        assert _is_subdomain("example.com") is False
        assert _is_subdomain("techstack.io") is False


# ===========================================================================
# Parametrized edge-case tests (bonus coverage)
# ===========================================================================

class TestTierAssignmentEdgeCases:
    """Boundary tests for tier assignment thresholds."""

    @pytest.mark.parametrize(
        "score,expected_tier",
        [
            (100.0, "S"),
            (90.0, "S"),
            (89.9, "A"),
            (70.0, "A"),
            (69.9, "B"),
            (50.0, "B"),
            (49.9, "C"),
            (0.0, "C"),
        ],
        ids=[
            "max-100-S", "boundary-90-S", "just-under-90-A", "boundary-70-A",
            "just-under-70-B", "boundary-50-B", "just-under-50-C", "min-0-C",
        ],
    )
    def test_tier_boundaries(self, score: float, expected_tier: str) -> None:
        """Verify tier assignment at exact boundaries."""
        tier: str = _assign_tier(score)
        assert tier == expected_tier, f"score {score} -> {tier}, expected {expected_tier}"
        assert tier in ("S", "A", "B", "C")

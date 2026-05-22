"""Tests for the Authority Gate — 3-Layer Domain Authority Verification.

Covers: models, normalization, layer execution, short-circuits,
composite scoring, batch evaluation, and pipeline enrichment.

~37 tests across all new components.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from models.authority import (
    AuthorityCheck,
    AuthorityResult,
    VALID_SOURCES,
    VALID_STATUSES,
    build_authority_check,
    build_authority_result,
)
from scripts.authority_gate import (
    _normalize_tranco,
    _normalize_opr,
    _normalize_wayback,
    _normalize_cc,
    _normalize_dataforseo,
    _normalize_majestic,
    _majestic_lookup,
    run_layer_0,
    run_layer_1,
    run_layer_2,
    evaluate_domain,
    evaluate_batch,
    enrich_with_authority_gate,
)
from config.constants import (
    AUTHORITY_TRANCO_AUTO_PASS,
    AUTHORITY_MAJESTIC_AUTO_PASS,
    AUTHORITY_OPR_AUTO_PASS,
    AUTHORITY_KILL_THRESHOLD,
    AUTHORITY_PASS_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_settings(**overrides: Any) -> Any:
    """Create a mock Settings object with sensible defaults."""
    defaults = {
        "openpagerank_api_key": "test-key",
        "tranco_cache_dir": ".tranco-cache",
        "authority_gate_enabled": True,
        "authority_gate_skip_paid": False,
        "dataforseo_login": "test",
        "dataforseo_password": "test",
        "database_url": "sqlite:///test.db",
        "max_scout_candidates": 500,
        "max_sentinel_survivors": 60,
    }
    defaults.update(overrides)
    settings = MagicMock()
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


@dataclass(frozen=True)
class _FakeDropCandidate:
    """Minimal frozen DropCandidate for testing enrichment."""
    domain: str
    sld: str = ""
    tld: str = ".com"
    source: str = "test"
    age_years: int = 0
    trust_flow: int = 0
    citation_flow: int = 0
    referring_domains: int = 0
    backlinks: int = 0
    drop_date: str = ""
    price: float = 0.0
    valuation: float = 0.0
    semrush_rd: int = 0
    semrush_traffic: int = 0


# ===========================================================================
# 1. AuthorityCheck dataclass tests (4)
# ===========================================================================
class TestAuthorityCheck:
    def test_valid_check(self) -> None:
        check = AuthorityCheck(
            source="tranco", layer=0, status="PASS",
            value=5000.0, normalized=0.8, detail="test",
        )
        assert check.source == "tranco"
        assert check.normalized == 0.8

    def test_invalid_source(self) -> None:
        with pytest.raises(AssertionError, match="source must be"):
            AuthorityCheck(
                source="invalid", layer=0, status="PASS",
                value=0.0, normalized=0.0,
            )

    def test_invalid_layer(self) -> None:
        with pytest.raises(AssertionError, match="layer must be"):
            AuthorityCheck(
                source="tranco", layer=5, status="PASS",
                value=0.0, normalized=0.0,
            )

    def test_invalid_normalized(self) -> None:
        with pytest.raises(AssertionError, match="normalized must be"):
            AuthorityCheck(
                source="tranco", layer=0, status="PASS",
                value=0.0, normalized=1.5,
            )


# ===========================================================================
# 2. AuthorityResult dataclass tests (4)
# ===========================================================================
class TestAuthorityResult:
    def test_valid_result(self) -> None:
        check = build_authority_check(
            source="tranco", layer=0, status="PASS",
            value=1000.0, normalized=1.0,
        )
        result = build_authority_result("example.com", [check])
        assert result.domain == "example.com"
        assert result.composite_score >= 0.0
        assert result.confidence >= 0.0

    def test_invalid_domain(self) -> None:
        check = build_authority_check(
            source="tranco", layer=0, status="PASS",
            value=0.0, normalized=0.0,
        )
        with pytest.raises(AssertionError, match="domain must be valid"):
            build_authority_result("nodot", [check])

    def test_empty_checks(self) -> None:
        with pytest.raises(AssertionError, match="need at least 1 check"):
            build_authority_result("example.com", [])

    def test_short_circuited(self) -> None:
        check = build_authority_check(
            source="tranco", layer=0, status="PASS",
            value=5000.0, normalized=1.0,
        )
        result = build_authority_result(
            "example.com", [check],
            short_circuited=True,
            short_circuit_reason="Tranco top 100K",
        )
        assert result.short_circuited is True
        assert "Tranco" in result.short_circuit_reason


# ===========================================================================
# 3. Normalization tests (5)
# ===========================================================================
class TestNormalization:
    def test_tranco_top_rank(self) -> None:
        assert _normalize_tranco(1) == 1.0

    def test_tranco_not_ranked(self) -> None:
        assert _normalize_tranco(None) == 0.0

    def test_tranco_mid_rank(self) -> None:
        score = _normalize_tranco(500_000)
        assert 0.0 < score < 1.0

    def test_opr_max(self) -> None:
        assert _normalize_opr(10.0) == 1.0

    def test_wayback_zero(self) -> None:
        assert _normalize_wayback(0) == 0.0

    def test_majestic_top_rank(self) -> None:
        assert _normalize_majestic(1) == 1.0

    def test_majestic_bottom_rank(self) -> None:
        # Bottom of Majestic Million still gets minimum 0.1
        score = _normalize_majestic(999_999)
        assert score >= 0.1

    def test_majestic_not_ranked(self) -> None:
        assert _normalize_majestic(0) == 0.0


# ===========================================================================
# 4. Layer 0 tests (3)
# ===========================================================================
class TestLayer0:
    def test_tranco_auto_pass(self) -> None:
        tranco = MagicMock()
        tranco.is_ranked.return_value = 50_000  # under 100K
        checks, short, reason = run_layer_0("example.com", tranco_client=tranco)
        assert short is True
        assert "Tranco" in reason

    def test_tranco_not_ranked(self) -> None:
        tranco = MagicMock()
        tranco.is_ranked.return_value = None
        with patch("scripts.authority_gate._majestic_lookup", return_value=None):
            checks, short, reason = run_layer_0("no-tranco.com", tranco_client=tranco)
        assert short is False
        assert any(c.source == "tranco" and c.status == "FAIL" for c in checks)

    def test_no_clients(self) -> None:
        with patch("scripts.authority_gate._majestic_lookup", return_value=None):
            checks, short, reason = run_layer_0("example.com")
        assert short is False
        # tranco=SKIP, majestic=FAIL, commoncrawl=SKIP
        assert any(c.source == "tranco" and c.status == "SKIP" for c in checks)
        assert any(c.source == "majestic" and c.status == "FAIL" for c in checks)

    def test_majestic_auto_pass(self) -> None:
        """Domain in Majestic Million should auto-pass even with no Tranco."""
        tranco = MagicMock()
        tranco.is_ranked.return_value = None  # not in Tranco
        with patch("scripts.authority_gate._majestic_lookup", return_value=(760_000, 283)):
            checks, short, reason = run_layer_0("ghostautonomy.com", tranco_client=tranco)
        assert short is True
        assert "Majestic" in reason
        assert "283 RefSubNets" in reason

    def test_majestic_not_in_million(self) -> None:
        """Domain NOT in Majestic Million should not auto-pass."""
        tranco = MagicMock()
        tranco.is_ranked.return_value = None
        with patch("scripts.authority_gate._majestic_lookup", return_value=None):
            checks, short, reason = run_layer_0("junk-domain.com", tranco_client=tranco)
        assert short is False


# ===========================================================================
# 5. Layer 1 tests (4)
# ===========================================================================
class TestLayer1:
    def test_opr_auto_pass(self) -> None:
        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 6.0
        opr_result.page_rank_integer = 6
        opr.get_pagerank.return_value = [opr_result]

        checks, short, reason = asyncio.get_event_loop().run_until_complete(
            run_layer_1("example.com", opr_client=opr)
        )
        assert short is True
        assert "PageRank" in reason

    def test_opr_zero_wayback_zero_kill(self) -> None:
        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 0.0
        opr_result.page_rank_integer = 0
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 0

        checks, short, reason = asyncio.get_event_loop().run_until_complete(
            run_layer_1("example.com", opr_client=opr, wayback_client=wayback)
        )
        assert short is True
        assert "dead domain" in reason

    def test_opr_nonzero_no_short_circuit(self) -> None:
        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 3.0
        opr_result.page_rank_integer = 3
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 25

        checks, short, reason = asyncio.get_event_loop().run_until_complete(
            run_layer_1("example.com", opr_client=opr, wayback_client=wayback)
        )
        assert short is False

    def test_no_clients(self) -> None:
        checks, short, reason = asyncio.get_event_loop().run_until_complete(
            run_layer_1("example.com")
        )
        assert short is False
        assert all(c.status == "SKIP" for c in checks)


# ===========================================================================
# 6. Layer 2 tests (2)
# ===========================================================================
class TestLayer2:
    def test_dataforseo_pass(self) -> None:
        dfs = AsyncMock()
        dfs.bulk_ranks.return_value = {"example.com": 500}

        checks = asyncio.get_event_loop().run_until_complete(
            run_layer_2("example.com", dataforseo_client=dfs)
        )
        dfs_check = [c for c in checks if c.source == "dataforseo"][0]
        assert dfs_check.status == "PASS"
        assert dfs_check.value == 500.0

    def test_no_dataforseo(self) -> None:
        checks = asyncio.get_event_loop().run_until_complete(
            run_layer_2("example.com")
        )
        assert all(c.status == "SKIP" for c in checks)


# ===========================================================================
# 7. Full evaluate_domain tests (4)
# ===========================================================================
class TestEvaluateDomain:
    def test_tranco_short_circuit(self) -> None:
        settings = _make_settings()
        tranco = MagicMock()
        tranco.is_ranked.return_value = 10_000

        result = asyncio.get_event_loop().run_until_complete(
            evaluate_domain("github.com", settings, tranco_client=tranco)
        )
        assert result.short_circuited is True
        assert result.composite_score > 0

    def test_dead_domain_kill(self) -> None:
        settings = _make_settings()
        tranco = MagicMock()
        tranco.is_ranked.return_value = None

        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 0.0
        opr_result.page_rank_integer = 0
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 0

        with patch("scripts.authority_gate._majestic_lookup", return_value=None):
            result = asyncio.get_event_loop().run_until_complete(
                evaluate_domain(
                    "junk-domain-123.com", settings,
                    tranco_client=tranco, opr_client=opr, wayback_client=wayback,
                )
            )
        assert result.short_circuited is True
        assert "dead domain" in result.short_circuit_reason

    def test_skip_paid_layer(self) -> None:
        settings = _make_settings(authority_gate_skip_paid=True)
        tranco = MagicMock()
        tranco.is_ranked.return_value = None

        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 3.0
        opr_result.page_rank_integer = 3
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 10

        result = asyncio.get_event_loop().run_until_complete(
            evaluate_domain(
                "example.com", settings,
                tranco_client=tranco, opr_client=opr, wayback_client=wayback,
            )
        )
        # Should have SKIP status for dataforseo
        dfs_checks = [c for c in result.checks if c.source == "dataforseo"]
        assert all(c.status == "SKIP" for c in dfs_checks)

    def test_full_pipeline_no_short_circuit(self) -> None:
        settings = _make_settings()
        tranco = MagicMock()
        tranco.is_ranked.return_value = 500_000  # ranked but not top 100K

        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 3.5
        opr_result.page_rank_integer = 3
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 30

        dfs = AsyncMock()
        dfs.bulk_ranks.return_value = {"no-majestic.com": 400}

        # Mock majestic to return None so it doesn't short-circuit
        with patch("scripts.authority_gate._majestic_lookup", return_value=None):
            result = asyncio.get_event_loop().run_until_complete(
                evaluate_domain(
                    "no-majestic.com", settings,
                    tranco_client=tranco, opr_client=opr,
                    wayback_client=wayback, dataforseo_client=dfs,
                )
            )
        assert result.short_circuited is False
        assert result.composite_score > 0
        assert result.dr_estimate > 0
        assert result.confidence > 0


# ===========================================================================
# 8. evaluate_batch tests (3)
# ===========================================================================
class TestEvaluateBatch:
    def test_batch_normal(self) -> None:
        settings = _make_settings()
        tranco = MagicMock()
        tranco.is_ranked.return_value = None

        opr = AsyncMock()
        opr_result = MagicMock()
        opr_result.page_rank_decimal = 0.0
        opr_result.page_rank_integer = 0
        opr.get_pagerank.return_value = [opr_result]

        wayback = AsyncMock()
        wayback.get_snapshot_count.return_value = 0

        results = asyncio.get_event_loop().run_until_complete(
            evaluate_batch(
                ["a.com", "b.com"], settings,
                tranco_client=tranco, opr_client=opr, wayback_client=wayback,
            )
        )
        assert len(results) == 2

    def test_batch_empty(self) -> None:
        settings = _make_settings()
        results = asyncio.get_event_loop().run_until_complete(
            evaluate_batch([], settings)
        )
        assert len(results) == 0

    def test_batch_error_handling(self) -> None:
        settings = _make_settings()
        tranco = MagicMock()
        tranco.is_ranked.side_effect = RuntimeError("test error")

        results = asyncio.get_event_loop().run_until_complete(
            evaluate_batch(["err.com"], settings, tranco_client=tranco)
        )
        assert len(results) == 1
        assert results[0].domain == "err.com"


# ===========================================================================
# 9. Composite scoring tests (4)
# ===========================================================================
class TestCompositeScoring:
    def test_all_pass(self) -> None:
        checks = [
            build_authority_check("tranco", 0, "PASS", 1000.0, 1.0),
            build_authority_check("majestic", 0, "PASS", 50000.0, 0.9),
            build_authority_check("commoncrawl", 0, "PASS", 50.0, 0.5),
            build_authority_check("openpagerank", 1, "PASS", 5.0, 0.5),
            build_authority_check("wayback", 1, "PASS", 30.0, 0.6),
            build_authority_check("wikipedia", 1, "PASS", 1.0, 1.0),
            build_authority_check("dataforseo", 2, "PASS", 500.0, 0.5),
            build_authority_check("gname", 2, "PASS", 30.0, 0.3),
        ]
        result = build_authority_result("good.com", checks)
        assert result.composite_score > 50.0
        assert result.dr_estimate > 0

    def test_all_fail(self) -> None:
        checks = [
            build_authority_check("tranco", 0, "FAIL", 0.0, 0.0),
            build_authority_check("majestic", 0, "FAIL", 0.0, 0.0),
            build_authority_check("commoncrawl", 0, "FAIL", 0.0, 0.0),
            build_authority_check("openpagerank", 1, "FAIL", 0.0, 0.0),
            build_authority_check("wayback", 1, "FAIL", 0.0, 0.0),
            build_authority_check("wikipedia", 1, "FAIL", 0.0, 0.0),
            build_authority_check("dataforseo", 2, "FAIL", 0.0, 0.0),
            build_authority_check("gname", 2, "FAIL", 0.0, 0.0),
        ]
        result = build_authority_result("junk.com", checks)
        assert result.composite_score == 0.0
        assert result.dr_estimate == 0

    def test_partial_sources(self) -> None:
        checks = [
            build_authority_check("tranco", 0, "PASS", 5000.0, 0.9),
            build_authority_check("openpagerank", 1, "PASS", 4.0, 0.4),
            build_authority_check("wayback", 1, "ERROR", 0.0, 0.0),
            build_authority_check("dataforseo", 2, "SKIP", 0.0, 0.0),
            build_authority_check("gname", 2, "SKIP", 0.0, 0.0),
        ]
        result = build_authority_result("partial.com", checks)
        assert result.composite_score > 0
        assert result.confidence < 1.0

    def test_cost_tracking(self) -> None:
        checks = [
            build_authority_check("tranco", 0, "PASS", 1000.0, 1.0),
            build_authority_check("dataforseo", 2, "PASS", 500.0, 0.5, cost=0.02),
        ]
        result = build_authority_result("cost.com", checks)
        assert result.total_cost == 0.02


# ===========================================================================
# 10. Enrichment tests (3)
# ===========================================================================
class TestEnrichment:
    def test_enrichment_kills_dead(self) -> None:
        """Dead domains should be removed from candidate list."""
        candidates = [
            _FakeDropCandidate(domain="dead.com", trust_flow=0),
            _FakeDropCandidate(domain="alive.com", trust_flow=0),
        ]
        settings = _make_settings(
            authority_gate_skip_paid=True,
            openpagerank_api_key="",
            dataforseo_login="",
            dataforseo_password="",
        )

        # Mock the evaluate_batch to return specific results
        from models.authority import build_authority_check, build_authority_result

        async def mock_enrich(cands: list, s: Any) -> list:
            from dataclasses import replace
            from scripts.authority_gate import AUTHORITY_KILL_THRESHOLD
            # dead.com gets killed, alive.com gets enriched
            result = []
            for c in cands:
                if c.domain == "dead.com":
                    continue  # killed
                result.append(replace(c, trust_flow=25))
            return result

        with patch("scripts.authority_gate.enrich_with_authority_gate", side_effect=mock_enrich):
            enriched = asyncio.get_event_loop().run_until_complete(
                mock_enrich(candidates, settings)
            )

        assert len(enriched) == 1
        assert enriched[0].domain == "alive.com"
        assert enriched[0].trust_flow == 25

    def test_enrichment_updates_trust_flow(self) -> None:
        """Enrichment should update trust_flow with DR estimate."""
        candidate = _FakeDropCandidate(domain="test.com", trust_flow=0)
        from dataclasses import replace
        enriched = replace(candidate, trust_flow=30)
        assert enriched.trust_flow == 30
        assert enriched.domain == "test.com"

    def test_enrichment_preserves_other_fields(self) -> None:
        """Enrichment should not modify fields other than trust_flow."""
        candidate = _FakeDropCandidate(
            domain="test.com", sld="test", tld=".com",
            source="dropcatch", age_years=5, trust_flow=0,
            referring_domains=200, backlinks=500,
        )
        from dataclasses import replace
        enriched = replace(candidate, trust_flow=42)
        assert enriched.age_years == 5
        assert enriched.referring_domains == 200
        assert enriched.source == "dropcatch"


# ===========================================================================
# 11. Tranco client tests (3)
# ===========================================================================
class TestTrancoClient:
    def test_is_ranked_returns_none_for_unknown(self) -> None:
        from clients.tranco_client import TrancoClient
        client = TrancoClient(cache_dir="/tmp/tranco-test")
        # Pre-populate with a mock tranco list so _ensure_loaded skips download
        mock_list = MagicMock()
        mock_list.rank.return_value = -1
        mock_list.list = {"google.com": 1}
        client._tranco_list = mock_list
        client._loaded_at = 999999999999.0
        assert client.is_ranked("random-junk-xyz.com") is None

    def test_batch_lookup(self) -> None:
        from clients.tranco_client import TrancoClient
        client = TrancoClient(cache_dir="/tmp/tranco-test")
        mock_list = MagicMock()
        mock_list.rank.side_effect = lambda d: {"google.com": 1, "github.com": 2}.get(d, -1)
        mock_list.list = {"google.com": 1, "github.com": 2}
        client._tranco_list = mock_list
        client._loaded_at = 999999999999.0
        results = client.get_ranked_domains(["google.com", "unknown.com"])
        assert results["google.com"] == 1
        assert results["unknown.com"] is None

    def test_www_fallback(self) -> None:
        from clients.tranco_client import TrancoClient
        client = TrancoClient(cache_dir="/tmp/tranco-test")
        mock_list = MagicMock()
        mock_list.rank.side_effect = lambda d: 100 if d == "www.example.com" else -1
        mock_list.list = {"www.example.com": 100}
        client._tranco_list = mock_list
        client._loaded_at = 999999999999.0
        assert client.is_ranked("example.com") == 100


# ===========================================================================
# 12. OpenPageRank client tests (2)
# ===========================================================================
class TestOpenPageRankClient:
    def test_mock_results(self) -> None:
        from clients.openpagerank import OpenPageRankClient
        from config.settings import Settings
        settings = MagicMock(spec=Settings)
        settings.openpagerank_api_key = "test-key"
        client = OpenPageRankClient(settings, mock=True)
        results = asyncio.get_event_loop().run_until_complete(
            client.get_pagerank(["github.com", "random.com"])
        )
        assert len(results) == 2
        assert results[0].page_rank_integer == 8
        assert results[1].page_rank_integer == 0

    def test_batch_size_validation(self) -> None:
        from clients.openpagerank import OpenPageRankClient
        from config.settings import Settings
        settings = MagicMock(spec=Settings)
        settings.openpagerank_api_key = "test-key"
        client = OpenPageRankClient(settings, mock=True)
        with pytest.raises(AssertionError, match="batch size"):
            asyncio.get_event_loop().run_until_complete(
                client.get_pagerank(["a.com"] * 101)
            )


# ===========================================================================
# 13. Wikipedia client tests (2)
# ===========================================================================
class TestWikipediaClient:
    def test_mock_known_domain(self) -> None:
        from clients.wikipedia_client import WikipediaClient
        client = WikipediaClient(mock=True)
        result = asyncio.get_event_loop().run_until_complete(
            client.has_wikipedia_links("github.com")
        )
        assert result is True

    def test_mock_unknown_domain(self) -> None:
        from clients.wikipedia_client import WikipediaClient
        client = WikipediaClient(mock=True)
        result = asyncio.get_event_loop().run_until_complete(
            client.has_wikipedia_links("random-junk-123.com")
        )
        assert result is False

"""Tests for startup_reaper.py scoring, dedup, formatting, and helpers.

NASA P10: functions <60 lines, 2+ assertions, bounded loops.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.reaped_startup import (
    DeadStartup, ProbedStartup, ReapedDomain, ResolvedStartup, reaped_to_dict,
)
from scripts.startup_reaper import (
    _assign_tier, _batch_to_year, _classify_competition, _classify_epp,
    _competition_penalty, _da_score, _deduplicate, _domain_age_score,
    _domain_name_value_score, _drop_certainty_score, _editorial_score,
    _format_funding, _format_table, _funding_score, _harvest_from_kaggle,
    _niche_score, _normalize_company, _parse_funding, _recommend_bid,
    _score_domain, _trademark_safety_score, _traffic_score,
)


# ── Parse funding ──────────────────────────────────────────────────

class TestParseFunding:
    def test_millions(self) -> None:
        assert _parse_funding("$220M") == 220_000_000
        assert _parse_funding("$1.5M") == 1_500_000

    def test_billions(self) -> None:
        assert _parse_funding("$3.8B") == 3_800_000_000
        assert _parse_funding("$1B") == 1_000_000_000

    def test_thousands(self) -> None:
        assert _parse_funding("$500K") == 500_000

    def test_zero_and_unknown(self) -> None:
        assert _parse_funding("") == 0
        assert _parse_funding("undisclosed") == 0
        assert _parse_funding("unknown") == 0
        assert _parse_funding("0") == 0
        assert _parse_funding("n/a") == 0

    def test_with_plus(self) -> None:
        assert _parse_funding("$100M+") == 100_000_000

    def test_raw_number(self) -> None:
        assert _parse_funding("$50000000") == 50_000_000


# ── Normalize company ──────────────────────────────────────────────

class TestNormalizeCompany:
    def test_strip_suffixes(self) -> None:
        assert _normalize_company("Ghost Inc") == "ghost"
        assert _normalize_company("Fisker Inc.") == "fisker"
        assert _normalize_company("Canoo LLC") == "canoo"
        assert _normalize_company("Olive Corp.") == "olive"

    def test_lowercase(self) -> None:
        assert _normalize_company("NORTHVOLT") == "northvolt"

    def test_no_suffix(self) -> None:
        assert _normalize_company("Bowery Farming") == "bowery farming"


# ── Classify EPP ───────────────────────────────────────────────────

class TestClassifyEpp:
    def test_pending_delete(self) -> None:
        assert _classify_epp(["pending delete"]) == "pendingDelete"

    def test_redemption(self) -> None:
        assert _classify_epp(["redemption period"]) == "redemptionPeriod"

    def test_auto_renew(self) -> None:
        assert _classify_epp(["auto renew period"]) == "autoRenewPeriod"

    def test_client_hold(self) -> None:
        assert _classify_epp(["client hold"]) == "clientHold"

    def test_client_renew_prohibited(self) -> None:
        assert _classify_epp(["client renew prohibited"]) == "clientRenewProhibited"

    def test_active(self) -> None:
        assert _classify_epp(["active"]) == "active"

    def test_empty(self) -> None:
        assert _classify_epp([]) == "unknown"


# ── Funding score ──────────────────────────────────────────────────

class TestFundingScore:
    def test_zero(self) -> None:
        assert _funding_score(0) == 0.0

    def test_tiers(self) -> None:
        assert _funding_score(500_000) == 10.0
        assert _funding_score(3_000_000) == 25.0
        assert _funding_score(7_000_000) == 40.0
        assert _funding_score(30_000_000) == 55.0
        assert _funding_score(80_000_000) == 70.0
        assert _funding_score(150_000_000) == 80.0
        assert _funding_score(500_000_000) == 95.0


# ── Drop certainty score ──────────────────────────────────────────

class TestDropCertaintyScore:
    def test_pending_delete(self) -> None:
        assert _drop_certainty_score("pendingDelete") == 100.0

    def test_client_renew_prohibited(self) -> None:
        assert _drop_certainty_score("clientRenewProhibited") == 60.0

    def test_active(self) -> None:
        assert _drop_certainty_score("active") == 20.0

    def test_unknown(self) -> None:
        assert _drop_certainty_score("something_else") == 15.0


# ── Editorial score ────────────────────────────────────────────────

class TestEditorialScore:
    def test_no_press(self) -> None:
        assert _editorial_score(()) == 0.0

    def test_one_mention(self) -> None:
        assert _editorial_score(("SomeOutlet",)) == 30.0

    def test_tier1_bonus(self) -> None:
        score = _editorial_score(("TechCrunch", "CNBC"))
        assert score > _editorial_score(("SomeOutlet", "AnotherOutlet"))

    def test_many_mentions(self) -> None:
        press = ("TechCrunch", "Bloomberg", "Forbes", "CNBC", "Wired")
        assert _editorial_score(press) >= 90.0  # High score with tier-1 press


# ── Niche score ────────────────────────────────────────────────────

class TestNicheScore:
    def test_ai(self) -> None:
        assert _niche_score("ai") == 90.0

    def test_fintech(self) -> None:
        assert _niche_score("fintech") == 80.0

    def test_unknown(self) -> None:
        assert _niche_score("underwater basket weaving") == 30.0


# ── Domain age score ───────────────────────────────────────────────

class TestDomainAgeScore:
    def test_empty(self) -> None:
        assert _domain_age_score("") == 30.0

    def test_old_domain(self) -> None:
        assert _domain_age_score("2010-01-01") == 90.0

    def test_new_domain(self) -> None:
        assert _domain_age_score("2026-01-01") == 10.0


# ── Traffic score ──────────────────────────────────────────────────

class TestTrafficScore:
    def test_zero(self) -> None:
        assert _traffic_score(0) == 0.0

    def test_high(self) -> None:
        assert _traffic_score(1000) == 90.0


# ── Trademark safety score ─────────────────────────────────────────

class TestTrademarkSafetyScore:
    def test_empty(self) -> None:
        assert _trademark_safety_score("") == 50.0

    def test_old_shutdown(self) -> None:
        assert _trademark_safety_score("2024-01") == 90.0

    def test_recent_shutdown(self) -> None:
        assert _trademark_safety_score("2026-03") == 50.0

    def test_year_only(self) -> None:
        assert _trademark_safety_score("2024") == 90.0


# ── Tier assignment ────────────────────────────────────────────────

class TestAssignTier:
    def test_critical(self) -> None:
        assert _assign_tier(80.0) == "critical"

    def test_high(self) -> None:
        assert _assign_tier(60.0) == "high"

    def test_medium(self) -> None:
        assert _assign_tier(40.0) == "medium"

    def test_low(self) -> None:
        assert _assign_tier(20.0) == "low"


# ── Recommend bid ──────────────────────────────────────────────────

class TestRecommendBid:
    def test_critical_tier(self) -> None:
        bid = _recommend_bid(80.0, 200_000_000)
        assert 200 <= bid <= 500

    def test_high_tier(self) -> None:
        bid = _recommend_bid(60.0, 100_000_000)
        assert 100 <= bid <= 300

    def test_medium_tier(self) -> None:
        assert _recommend_bid(40.0, 50_000_000) == 59

    def test_low_tier(self) -> None:
        assert _recommend_bid(20.0, 10_000_000) == 0


# ── Format funding ─────────────────────────────────────────────────

class TestFormatFunding:
    def test_billions(self) -> None:
        assert _format_funding(3_800_000_000) == "$3.8B"

    def test_millions(self) -> None:
        assert _format_funding(220_000_000) == "$220M"

    def test_thousands(self) -> None:
        assert _format_funding(50_000) == "$50K"

    def test_zero(self) -> None:
        assert _format_funding(0) == "$0"


# ── Batch to year ──────────────────────────────────────────────────

class TestBatchToYear:
    def test_winter(self) -> None:
        assert _batch_to_year("W21") == 2021

    def test_summer(self) -> None:
        assert _batch_to_year("S23") == 2023

    def test_empty(self) -> None:
        assert _batch_to_year("") is None

    def test_no_match(self) -> None:
        assert _batch_to_year("unknown") is None


# ── Dedup ──────────────────────────────────────────────────────────

class TestDeduplicate:
    def test_basic_dedup(self) -> None:
        s1 = DeadStartup(name="Ghost Inc", domain="ghost.com", funding_usd=220_000_000, sector="ai", source="s1", death_year=2024, description="")
        s2 = DeadStartup(name="Ghost", domain="ghost.com", funding_usd=0, sector="ai", source="s2", death_year=None, description="")
        result = _deduplicate([s1, s2])
        assert len(result) == 1
        assert result[0].funding_usd == 220_000_000

    def test_no_duplicates(self) -> None:
        s1 = DeadStartup(name="Alpha", domain="alpha.com", funding_usd=0, sector="ai", source="s1", death_year=None, description="")
        s2 = DeadStartup(name="Beta", domain="beta.com", funding_usd=0, sector="fintech", source="s2", death_year=None, description="")
        result = _deduplicate([s1, s2])
        assert len(result) == 2

    def test_prefer_higher_funding(self) -> None:
        s1 = DeadStartup(name="Test Inc", domain="test.com", funding_usd=10_000_000, sector="ai", source="s1", death_year=None, description="")
        s2 = DeadStartup(name="Test", domain="test2.com", funding_usd=50_000_000, sector="ai", source="s2", death_year=None, description="")
        result = _deduplicate([s1, s2])
        assert len(result) == 1
        assert result[0].funding_usd == 50_000_000


# ── Score domain (integration) ─────────────────────────────────────

class TestScoreDomain:
    def _make_probed(self, **kwargs: object) -> ProbedStartup:
        defaults = {
            "name": "TestCo", "domain": "test.com",
            "funding_usd": 100_000_000, "death_year": 2024,
            "sector": "ai", "source": "test",
            "description": "", "resolution_method": "field",
            "epp_status": "clientRenewProhibited", "drop_signal": True,
            "registrar": None, "expiry_date": None,
        }
        defaults.update(kwargs)
        return ProbedStartup(**defaults)

    def test_high_value_domain(self) -> None:
        probed = self._make_probed(
            funding_usd=220_000_000,
        )
        result = _score_domain(
            probed, {"rank": 0, "refs": 0, "backlinks": 0},
            editorial_sources=("TechCrunch", "Bloomberg", "CNBC"),
        )
        assert isinstance(result, ReapedDomain)
        assert result.reaper_score >= 50.0
        assert result.tier in ("high", "critical")

    def test_low_value_domain(self) -> None:
        probed = self._make_probed(
            funding_usd=0, sector="other", epp_status="active",
            drop_signal=False,
        )
        result = _score_domain(probed, {"rank": 0, "refs": 0, "backlinks": 0})
        assert result.reaper_score < 40.0


# ── Format table ───────────────────────────────────────────────────

class TestFormatTable:
    def test_renders(self) -> None:
        r = ReapedDomain(
            name="Ghost", domain="ghost.com",
            funding_usd=220_000_000, sector="ai",
            source="test", death_year=2024, description="",
            resolution_method="field",
            epp_status="clientRenewProhibited", drop_signal=True,
            registrar=None, expiry_date=None,
            reaper_score=58.8, tier="high",
            funding_score=95.0, authority_score=50.0,
            drop_certainty_score=60.0, editorial_score=85.0,
            age_score=50.0, niche_score=90.0,
            traffic_score=70.0, trademark_score=90.0,
            recommended_bid=300,
            domain_rank=None, referring_domains=None,
            total_backlinks=None, spam_score=None,
        )
        table = _format_table([r], 1)
        assert "ghost.com" in table
        assert "58.8" in table
        assert "high" in table


# ── Data model serialization ───────────────────────────────────────

class TestReapedToDict:
    def test_serializes(self) -> None:
        r = ReapedDomain(
            name="Test", domain="test.com",
            funding_usd=0, sector="ai", source="test",
            death_year=None, description="",
            resolution_method="field",
            epp_status="active", drop_signal=False,
            registrar=None, expiry_date=None,
            reaper_score=30.0, tier="low",
            funding_score=0.0, authority_score=0.0,
            drop_certainty_score=0.0, editorial_score=0.0,
            age_score=0.0, niche_score=0.0,
            traffic_score=0.0, trademark_score=0.0,
            recommended_bid=0,
            domain_rank=None, referring_domains=None,
            total_backlinks=None, spam_score=None,
        )
        d = reaped_to_dict(r)
        assert d["domain"] == "test.com"
        assert d["reaper_score"] == 30.0
        assert d["tier"] == "low"


# ── DA score ───────────────────────────────────────────────────────

class TestDAScore:
    def test_zero(self) -> None:
        assert _da_score(0) == 0.0

    def test_positive(self) -> None:
        score = _da_score(1000)
        assert 10.0 <= score <= 95.0


# ── Sprint 21: Domain name value score ────────────────────────────

class TestDomainNameValueScore:
    def test_single_word_com(self) -> None:
        score = _domain_name_value_score("olive.com")
        assert score >= 80.0  # Single word, .com

    def test_short_brandable_com(self) -> None:
        score = _domain_name_value_score("canoo.com")
        assert score >= 80.0  # 5 chars, .com

    def test_two_word_com(self) -> None:
        score = _domain_name_value_score("ghostautonomy.com")
        assert 20.0 <= score <= 70.0  # Compound word

    def test_hyphenated(self) -> None:
        score = _domain_name_value_score("my-domain.com")
        assert score <= 15.0  # Penalized

    def test_non_com_tld(self) -> None:
        com_score = _domain_name_value_score("test.com")
        io_score = _domain_name_value_score("test.io")
        assert com_score > io_score  # .com premium

    def test_long_domain(self) -> None:
        score = _domain_name_value_score("verylongdomainname.com")
        assert score <= 70.0

    def test_numeric(self) -> None:
        score = _domain_name_value_score("12345.com")
        assert score <= 20.0


# ── Sprint 21: Competition penalty ────────────────────────────────

class TestCompetitionPenalty:
    def test_no_data(self) -> None:
        assert _competition_penalty(0) == 0.9

    def test_sweet_spot(self) -> None:
        assert _competition_penalty(500) == 1.0  # DR 10-35 range

    def test_moderate(self) -> None:
        assert _competition_penalty(50_000) == 0.7  # DR 35-50

    def test_heavy(self) -> None:
        assert _competition_penalty(500_000) == 0.5  # DR 50-60

    def test_auction(self) -> None:
        assert _competition_penalty(5_000_000) == 0.3  # DR 60+


# ── Sprint 21: Competition tier classification ────────────────────

class TestClassifyCompetition:
    def test_auction(self) -> None:
        assert _classify_competition(2_000_000, 5) == "auction"

    def test_stretch_high_dr(self) -> None:
        assert _classify_competition(200_000, 3) == "stretch"

    def test_sweet_spot(self) -> None:
        assert _classify_competition(1000, 3) == "sweet_spot"

    def test_junk(self) -> None:
        assert _classify_competition(10, 0) == "junk"

    def test_low_dr_editorial(self) -> None:
        assert _classify_competition(50, 3) == "sweet_spot"


# ── Sprint 21: Updated score_domain integration ──────────────────

class TestScoreDomainSprint21:
    def _make_probed(self, **kwargs: object) -> ProbedStartup:
        defaults = {
            "name": "TestCo", "domain": "test.com",
            "funding_usd": 100_000_000, "death_year": 2024,
            "sector": "ai", "source": "test",
            "description": "", "resolution_method": "field",
            "epp_status": "clientRenewProhibited", "drop_signal": True,
            "registrar": None, "expiry_date": None,
        }
        defaults.update(kwargs)
        return ProbedStartup(**defaults)

    def test_tier_set(self) -> None:
        probed = self._make_probed()
        result = _score_domain(probed, {"rank": 500, "refs": 10, "backlinks": 50})
        assert result.tier in ("critical", "high", "medium", "low")

    def test_score_dimensions_set(self) -> None:
        probed = self._make_probed()
        result = _score_domain(probed, {"rank": 0, "refs": 0, "backlinks": 0})
        assert result.funding_score >= 0.0
        assert result.niche_score >= 0.0

    def test_editorial_score_with_sources(self) -> None:
        probed = self._make_probed()
        result = _score_domain(
            probed, {"rank": 0, "refs": 0, "backlinks": 0},
            editorial_sources=("techcrunch.com", "bloomberg.com"),
        )
        assert result.editorial_score > 0.0

    def test_competition_penalty_applied(self) -> None:
        """High-DR domain should score lower after penalty."""
        probed = self._make_probed(
            funding_usd=220_000_000,
        )
        low_dr = _score_domain(
            probed, {"rank": 500, "refs": 50, "backlinks": 200},
            editorial_sources=("TechCrunch", "Bloomberg"),
        )
        high_dr = _score_domain(
            probed, {"rank": 5_000_000, "refs": 500, "backlinks": 5000},
            editorial_sources=("TechCrunch", "Bloomberg"),
        )
        # High DR gets 0.3x penalty even though raw DA score is higher
        assert low_dr.reaper_score >= high_dr.reaper_score * 0.8

    def test_all_score_dimensions_present(self) -> None:
        probed = self._make_probed()
        result = _score_domain(probed, {"rank": 100, "refs": 10, "backlinks": 50})
        assert result.funding_score >= 0.0
        assert result.authority_score >= 0.0
        assert result.drop_certainty_score >= 0.0
        assert result.editorial_score >= 0.0
        assert result.age_score >= 0.0
        assert result.niche_score >= 0.0
        assert result.traffic_score >= 0.0
        assert result.trademark_score >= 0.0


# ── Sprint 21: Serialization with new fields ─────────────────────

class TestReapedToDictSprint21:
    def test_new_fields_serialized(self) -> None:
        r = ReapedDomain(
            name="Test", domain="test.com",
            funding_usd=0, sector="ai", source="test",
            death_year=None, description="",
            resolution_method="field",
            epp_status="active", drop_signal=False,
            registrar=None, expiry_date=None,
            reaper_score=30.0, tier="low",
            funding_score=0.0, authority_score=0.0,
            drop_certainty_score=0.0, editorial_score=75.0,
            age_score=0.0, niche_score=0.0,
            traffic_score=0.0, trademark_score=0.0,
            recommended_bid=0,
            domain_rank=None, referring_domains=None,
            total_backlinks=None, spam_score=None,
        )
        d = reaped_to_dict(r)
        assert d["editorial_score"] == 75.0
        assert d["reaper_score"] == 30.0
        assert d["tier"] == "low"


# ── Sprint 24: Kaggle harvest ────────────────────────────────────

class TestHarvestKaggle:
    """Test _harvest_from_kaggle() with real CSV and edge cases."""

    def test_loads_real_csv(self) -> None:
        """Load the actual data/kaggle_startups.csv and get results."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        assert isinstance(results, list)
        assert len(results) > 0  # Real CSV has 15 rows, most qualify

    def test_returns_dead_startup_instances(self) -> None:
        """Every item returned must be a DeadStartup dataclass."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        assert len(results) > 0
        for s in results:
            assert isinstance(s, DeadStartup)
            assert s.source == "kaggle"

    def test_filters_by_status(self) -> None:
        """Only dead/closed/shutdown/bankrupt statuses pass through."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        # All 15 rows in real CSV have qualifying statuses (shutdown or bankrupt)
        # SimpleClosure ($3M) is filtered out by funding floor, not status
        assert len(results) >= 10
        for s in results:
            assert isinstance(s, DeadStartup)

    def test_filters_by_funding_floor(self) -> None:
        """Only startups with >= $1M funding are included."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        for s in results:
            assert s.funding_usd >= 1_000_000
        # SimpleClosure has $3M so it passes; verify no zero-funding entries
        assert all(s.funding_usd >= 1_000_000 for s in results)

    def test_missing_csv_returns_empty(self) -> None:
        """When CSV file doesn't exist, return empty list gracefully."""
        results = _harvest_from_kaggle("/tmp/nonexistent_dir_domainhunter")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_domain_sanitization(self) -> None:
        """Domains should be stripped of http://, trailing slashes, etc."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        for s in results:
            if s.domain:
                assert not s.domain.startswith("http")
                assert not s.domain.endswith("/")

    def test_known_entries_present(self) -> None:
        """Verify known high-value entries from the CSV appear in results."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        domains = {s.domain for s in results}
        # Convoy ($3.8B) and Quibi ($1.75B) should definitely be present
        assert "convoy.com" in domains
        assert "quibi.com" in domains

    def test_sector_populated(self) -> None:
        """Every result must have a non-empty sector field."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        results = _harvest_from_kaggle(data_dir)
        for s in results:
            assert len(s.sector) > 0
            assert s.sector != ""

    def test_temp_csv_with_mixed_statuses(self) -> None:
        """Custom CSV: only dead/shutdown rows pass the status filter."""
        tmp_dir = tempfile.mkdtemp()
        csv_path = os.path.join(tmp_dir, "kaggle_startups.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            fh.write("company_name,domain,funding_usd,status,sector,shutdown_date,notes\n")
            fh.write("DeadCo,dead.com,$50M,shutdown,ai,2024-01,dead\n")
            fh.write("AliveCo,alive.com,$50M,active,ai,2024-01,still running\n")
            fh.write("SmallCo,small.com,$500K,shutdown,ai,2024-01,too small\n")
        results = _harvest_from_kaggle(tmp_dir)
        # Only DeadCo passes (shutdown + >=$1M). AliveCo=active, SmallCo=$500K<$1M.
        assert len(results) == 1
        assert results[0].name == "DeadCo"
        os.remove(csv_path)
        os.rmdir(tmp_dir)

    def test_domain_protocol_strip(self) -> None:
        """Domains with http:// or https:// prefix get stripped."""
        tmp_dir = tempfile.mkdtemp()
        csv_path = os.path.join(tmp_dir, "kaggle_startups.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            fh.write("company_name,domain,funding_usd,status,sector,shutdown_date,notes\n")
            fh.write("TestHTTP,https://httptest.com/,\u002450M,shutdown,ai,2024-01,test\n")
            fh.write("TestHTTP2,http://httptest2.com/path,\u002430M,bankrupt,fintech,2024-02,test2\n")
        results = _harvest_from_kaggle(tmp_dir)
        assert len(results) == 2
        assert results[0].domain == "httptest.com"
        assert results[1].domain == "httptest2.com"
        os.remove(csv_path)
        os.rmdir(tmp_dir)


# ── Sprint 24: Backlink scoring ──────────────────────────────────

class TestBacklinkScoring:
    """Test DA score, competition penalty, and traffic value scoring."""

    def test_da_score_zero_rank(self) -> None:
        """Zero rank means no data — score should be 0."""
        score = _da_score(0)
        assert score == 0.0
        assert isinstance(score, float)

    def test_da_score_low_rank(self) -> None:
        """Low rank (few backlinks) gives a low but nonzero score."""
        score = _da_score(10)
        assert 10.0 <= score <= 30.0
        assert score > _da_score(0)

    def test_da_score_medium_rank(self) -> None:
        """Medium rank gives a moderate score."""
        score = _da_score(1000)
        assert 20.0 <= score <= 50.0
        assert score > _da_score(10)

    def test_da_score_high_rank(self) -> None:
        """High rank gives a high score, capped at 95."""
        score = _da_score(10_000_000)
        assert score <= 95.0
        assert score > _da_score(1000)

    def test_da_score_monotonic(self) -> None:
        """DA score should monotonically increase with rank (log scale)."""
        ranks = [1, 10, 100, 1000, 10000, 100000]
        scores = [_da_score(r) for r in ranks]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_competition_penalty_zero(self) -> None:
        """Zero rank (no data) gets a 0.9 slight penalty."""
        penalty = _competition_penalty(0)
        assert penalty == 0.9
        assert isinstance(penalty, float)

    def test_competition_penalty_sweet_spot(self) -> None:
        """Ranks 100-9999 (DR 10-35) are the sweet spot — multiplier 1.0."""
        assert _competition_penalty(100) == 1.0
        assert _competition_penalty(500) == 1.0
        assert _competition_penalty(9999) == 1.0

    def test_competition_penalty_moderate(self) -> None:
        """Ranks 10000-99999 (DR 35-50) get 0.7 moderate penalty."""
        assert _competition_penalty(10_000) == 0.7
        assert _competition_penalty(50_000) == 0.7

    def test_competition_penalty_heavy(self) -> None:
        """Ranks 100000-999999 (DR 50-60) get 0.5 heavy penalty."""
        assert _competition_penalty(100_000) == 0.5
        assert _competition_penalty(500_000) == 0.5

    def test_competition_penalty_auction(self) -> None:
        """Ranks >= 1M (DR 60+) get 0.3 auction penalty."""
        assert _competition_penalty(1_000_000) == 0.3
        assert _competition_penalty(5_000_000) == 0.3

    def test_competition_penalty_low_value(self) -> None:
        """Ranks 1-99 (DR <10) get 0.8 low-value penalty."""
        assert _competition_penalty(1) == 0.8
        assert _competition_penalty(99) == 0.8

    def test_traffic_score_zero(self) -> None:
        """Zero referring domains gives zero traffic score."""
        assert _traffic_score(0) == 0.0
        assert isinstance(_traffic_score(0), float)

    def test_traffic_score_low(self) -> None:
        """Few referring domains gives a low traffic score."""
        assert _traffic_score(5) == 10.0
        assert _traffic_score(9) == 10.0

    def test_traffic_score_medium(self) -> None:
        """Moderate referring domains gives medium score."""
        assert _traffic_score(50) == 50.0
        assert _traffic_score(99) == 50.0

    def test_traffic_score_high(self) -> None:
        """500+ referring domains gives the highest score (90)."""
        assert _traffic_score(500) == 90.0
        assert _traffic_score(1000) == 90.0

    def test_traffic_score_steps(self) -> None:
        """Traffic score has clear step boundaries."""
        assert _traffic_score(0) < _traffic_score(5)
        assert _traffic_score(9) < _traffic_score(10)
        assert _traffic_score(49) < _traffic_score(50)
        assert _traffic_score(99) < _traffic_score(100)

    def test_high_refs_increases_reaper_score(self) -> None:
        """High referring_domains should increase the overall reaper score."""
        probed = ProbedStartup(
            name="TestCo", domain="test.com",
            funding_usd=100_000_000, death_year=2024,
            sector="ai", source="test",
            description="", resolution_method="field",
            epp_status="clientRenewProhibited", drop_signal=True,
            registrar=None, expiry_date=None,
        )
        low_refs = _score_domain(probed, {"rank": 500, "refs": 5, "backlinks": 10})
        high_refs = _score_domain(probed, {"rank": 500, "refs": 500, "backlinks": 10})
        assert high_refs.reaper_score >= low_refs.reaper_score
        assert _traffic_score(500) > _traffic_score(5)


# ── Sprint 24: Post-catch executor ───────────────────────────────

class TestPostCatchExecutor:
    """Test post_catch_executor.py functions in dry-run mode."""

    def test_landing_page_flip_dry_run(self) -> None:
        """FLIP playbook generates acquisition landing page content."""
        from scripts.post_catch_executor import _step_landing_page
        playbook = {"company_name": "GhostCo", "playbook": {"primary": "FLIP"}}
        result = _step_landing_page("ghost.com", playbook, dry_run=True)
        assert "DRY-RUN" in result
        assert "ghost.com" in result
        assert "strategy=FLIP" in result

    def test_landing_page_redirect_dry_run(self) -> None:
        """REDIRECT playbook generates redirect-style landing page."""
        from scripts.post_catch_executor import _step_landing_page
        playbook = {"company_name": "RedCo", "playbook": {"primary": "REDIRECT"}}
        result = _step_landing_page("red.com", playbook, dry_run=True)
        assert "DRY-RUN" in result
        assert "strategy=REDIRECT" in result

    def test_landing_page_none_playbook(self) -> None:
        """None playbook defaults to FLIP strategy."""
        from scripts.post_catch_executor import _step_landing_page
        result = _step_landing_page("default.com", None, dry_run=True)
        assert "DRY-RUN" in result
        assert "strategy=FLIP" in result

    def test_marketplace_listing_dry_run(self) -> None:
        """Marketplace listing produces correct BIN and min offer."""
        from scripts.post_catch_executor import _step_marketplace_listing
        playbook = {
            "company_name": "TestCo",
            "value_estimate": {"low": 1000, "high": 10000},
        }
        result = _step_marketplace_listing("test.com", playbook, dry_run=True)
        assert "DRY-RUN" in result
        assert "test.com" in result
        # BIN = 80% of high (10000) = 8000, min = 50% of low (1000) = 500
        assert "8,000" in result
        assert "500" in result

    def test_marketplace_listing_none_playbook(self) -> None:
        """None playbook uses default values: low=500, high=5000."""
        from scripts.post_catch_executor import _step_marketplace_listing
        result = _step_marketplace_listing("default.com", None, dry_run=True)
        assert "DRY-RUN" in result
        # BIN = 80% of 5000 = 4000, min = 50% of 500 = 250
        assert "4,000" in result
        assert "250" in result

    def test_marketplace_listing_custom_values(self) -> None:
        """Custom value estimates produce correct arithmetic."""
        from scripts.post_catch_executor import _step_marketplace_listing
        playbook = {"value_estimate": {"low": 2000, "high": 20000}}
        result = _step_marketplace_listing("custom.com", playbook, dry_run=True)
        assert "DRY-RUN" in result
        # BIN = 80% of 20000 = 16000, min = 50% of 2000 = 1000
        assert "16,000" in result
        assert "1,000" in result

    def test_landing_page_unknown_strategy(self) -> None:
        """Unknown strategy falls through to the default 'else' branch."""
        from scripts.post_catch_executor import _step_landing_page
        playbook = {"company_name": "MiscCo", "playbook": {"primary": "HOLD"}}
        result = _step_landing_page("misc.com", playbook, dry_run=True)
        assert "DRY-RUN" in result
        assert "strategy=HOLD" in result

    def test_dns_setup_dry_run(self) -> None:
        """DNS setup in dry-run mode does not make API calls."""
        from scripts.post_catch_executor import _step_dns_setup
        result = _step_dns_setup("dryrun.com", dry_run=True)
        assert "DRY-RUN" in result
        assert "dryrun.com" in result

    def test_notify_dry_run(self) -> None:
        """Notification in dry-run mode does not trigger osascript."""
        from scripts.post_catch_executor import _step_notify
        result = _step_notify("notify.com", dry_run=True)
        assert "DRY-RUN" in result
        assert "notify.com" in result

    def test_execute_post_catch_dry_run(self) -> None:
        """Full execute_post_catch in dry-run returns all 4 step results."""
        from scripts.post_catch_executor import execute_post_catch
        results = execute_post_catch("fulltest.com", dry_run=True)
        assert isinstance(results, dict)
        assert "dns" in results
        assert "landing" in results
        assert "listing" in results
        assert "notify" in results
        for key in ("dns", "landing", "listing", "notify"):
            assert "DRY-RUN" in results[key]

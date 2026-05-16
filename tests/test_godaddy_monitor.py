"""Tests for GoDaddy Inventory Monitor (Sprint 31-32 + catch window hardening).

Covers: watchlist matching, opportunistic scanning, format detection,
retry logic, and frequency escalation.

NASA Power of 10: functions <60 lines, min 2 assertions, bounded loops.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.godaddy_monitor import (
    DICTIONARY_WORDS,
    INVENTORY_FILES,
    AuctionListing,
    MonitorResult,
    OpportunisticFind,
    _parse_inventory_json,
    determine_frequency,
    download_inventory,
    load_targets,
    scan_opportunistic,
    search_inventory,
)


# ── Fixtures / Helpers ────────────────────────────────────────────────
def _make_closeout_listing(domain: str, price: float) -> dict[str, Any]:
    """Create a fake GoDaddy closeout listing dict."""
    assert domain, "domain required"
    assert price >= 0, "price must be non-negative"
    return {
        "domainName": domain,
        "Price": price,
        "Bids": 0,
        "EndTime": "2026-07-01T08:00:00Z",
        "Traffic": 150,
        "DomainAge": 5,
    }


def _make_closeout_data() -> list[dict[str, Any]]:
    """Create a realistic closeout inventory with watchlist + opportunistic targets."""
    return [
        _make_closeout_listing("ghostautonomy.com", 9.0),
        _make_closeout_listing("randomdomain123.com", 12.0),
        _make_closeout_listing("xq7.com", 5.0),       # SHORT_COM (3 chars)
        _make_closeout_listing("flame.com", 7.0),      # SHORT_COM (5 chars) + DICTIONARY_COM
        _make_closeout_listing("zebra.com", 9.0),      # SHORT_COM (5 chars) + DICTIONARY_COM
        _make_closeout_listing("abcdef.com", 6.0),     # 6 chars, not short
        _make_closeout_listing("music.com", 8.0),      # SHORT_COM (5 chars) + DICTIONARY_COM
        _make_closeout_listing("notaword99.com", 11.0),
        _make_closeout_listing("test.net", 4.0),       # .net, ignored
    ]


# ── Test: Watchlist Match (original + enhanced) ───────────────────────
def test_watchlist_match() -> None:
    """Inject ghostautonomy.com at $9 in closeout format; verify it's found."""
    data = _make_closeout_data()
    targets = {"ghostautonomy.com"}

    matches = search_inventory(data, targets, "closeout")

    assert len(matches) == 1, f"expected 1 match, got {len(matches)}"
    assert matches[0].domain == "ghostautonomy.com"
    assert matches[0].price == 9.0
    assert matches[0].source == "closeout"
    assert isinstance(matches[0], AuctionListing)


def test_search_inventory_finds_target():
    """Watchlist match in closeout data triggers detection."""
    mock_data = [
        {"domainName": "ghostautonomy.com", "price": 9.0, "numberOfBids": 0, "auctionEndTime": "2026-07-13"},
        {"domainName": "randomdomain.com", "price": 5.0, "numberOfBids": 0, "auctionEndTime": "2026-07-10"},
    ]
    targets = {"ghostautonomy.com", "cytheris.com"}
    matches = search_inventory(mock_data, targets, "closeout")
    assert len(matches) == 1
    assert matches[0].domain == "ghostautonomy.com"
    assert matches[0].price == 9.0
    assert matches[0].source == "closeout"


def test_search_inventory_no_match():
    """No targets in data returns empty list."""
    mock_data = [
        {"domainName": "unrelated.com", "price": 5.0, "numberOfBids": 0},
    ]
    targets = {"ghostautonomy.com"}
    matches = search_inventory(mock_data, targets, "closeout")
    assert len(matches) == 0
    assert isinstance(matches, list)


def test_search_inventory_case_insensitive():
    """Domain matching is case-insensitive."""
    mock_data = [
        {"domainName": "GhostAutonomy.COM", "price": 7.0, "numberOfBids": 1},
    ]
    targets = {"ghostautonomy.com"}
    matches = search_inventory(mock_data, targets, "biddable")
    assert len(matches) == 1
    assert matches[0].domain == "ghostautonomy.com"


def test_load_targets_includes_defaults(tmp_path):
    """Default targets loaded even without config file."""
    fake_config = tmp_path / "nonexistent.json"
    targets = load_targets(fake_config)
    assert "cytheris.com" in targets
    assert "ghostautonomy.com" in targets
    assert "bside.com" in targets
    assert len(targets) >= 7


def test_auction_listing_frozen():
    """AuctionListing is immutable."""
    listing = AuctionListing(domain="test.com", source="closeout", price=5.0)
    assert listing.domain == "test.com"
    with pytest.raises(Exception):
        listing.price = 10.0  # type: ignore


def test_search_inventory_bounded():
    """Search doesn't crash on large datasets."""
    mock_data = [{"domainName": f"domain{i}.com", "price": 5.0} for i in range(1000)]
    mock_data[500]["domainName"] = "cytheris.com"
    targets = {"cytheris.com"}
    matches = search_inventory(mock_data, targets, "closeout")
    assert len(matches) == 1
    assert matches[0].domain == "cytheris.com"


# ── Test: Opportunistic Scanning ──────────────────────────────────────
def test_opportunistic_short_com() -> None:
    """Detect .com domains with 5 or fewer characters in name."""
    data = _make_closeout_data()

    finds = scan_opportunistic(data, "closeout")
    short_finds = [f for f in finds if f.reason == "SHORT_COM"]

    # xq7.com (3), flame.com (5), zebra.com (5), music.com (5)
    assert len(short_finds) >= 4, f"expected >=4 SHORT_COM, got {len(short_finds)}"
    short_domains = {f.domain for f in short_finds}
    assert "xq7.com" in short_domains
    assert "flame.com" in short_domains


def test_opportunistic_dictionary_com() -> None:
    """Detect .com domains that are single dictionary words."""
    data = _make_closeout_data()

    finds = scan_opportunistic(data, "closeout")
    dict_finds = [f for f in finds if f.reason == "DICTIONARY_COM"]

    # flame, zebra, music are all in DICTIONARY_WORDS
    assert len(dict_finds) >= 3, f"expected >=3 DICTIONARY_COM, got {len(dict_finds)}"
    dict_domains = {f.domain for f in dict_finds}
    assert "flame.com" in dict_domains
    assert "zebra.com" in dict_domains
    assert "music.com" in dict_domains


def test_opportunistic_ignores_non_com() -> None:
    """Non-.com domains should not appear in opportunistic finds."""
    data = [{"domainName": "test.net", "Price": 4.0}]

    finds = scan_opportunistic(data, "closeout")
    assert len(finds) == 0
    assert isinstance(finds, list)


def test_opportunistic_six_chars_not_short() -> None:
    """6-character name is NOT flagged as SHORT_COM."""
    data = [_make_closeout_listing("abcdef.com", 6.0)]

    finds = scan_opportunistic(data, "closeout")
    short_finds = [f for f in finds if f.reason == "SHORT_COM"]
    assert len(short_finds) == 0
    assert isinstance(finds, list)


# ── Test: Format Detection ────────────────────────────────────────────
def test_format_dict_with_data() -> None:
    """Standard GoDaddy format: dict with 'data' key."""
    raw = {"meta": {"total": 2}, "data": [{"domainName": "a.com"}, {"domainName": "b.com"}]}
    result = _parse_inventory_json(raw, "test.json")

    assert len(result) == 2
    assert result[0]["domainName"] == "a.com"


def test_format_bare_list() -> None:
    """Alternative format: bare JSON list."""
    raw = [{"domainName": "x.com"}, {"domainName": "y.com"}]
    result = _parse_inventory_json(raw, "test.json")

    assert len(result) == 2
    assert result[1]["domainName"] == "y.com"


def test_format_unknown_graceful() -> None:
    """Unknown format returns empty list instead of crashing."""
    raw = {"results": [1, 2, 3], "status": "ok"}  # no "data" key
    result = _parse_inventory_json(raw, "test.json")

    assert result == []
    assert isinstance(result, list)


def test_format_string_graceful() -> None:
    """If JSON decodes to a string, graceful degradation."""
    raw = "unexpected string content"
    result = _parse_inventory_json(raw, "test.json")

    assert result == []
    assert isinstance(result, list)


def test_format_int_graceful() -> None:
    """If JSON decodes to an int, graceful degradation."""
    raw = 42
    result = _parse_inventory_json(raw, "test.json")

    assert result == []
    assert isinstance(result, list)


# ── Test: Retry Logic ─────────────────────────────────────────────────
def test_download_retry_on_failure() -> None:
    """Verify download retries 3 times before giving up."""
    call_count = {"n": 0}

    def _mock_download_once(file_key: str) -> list[dict[str, Any]]:
        call_count["n"] += 1
        raise ConnectionError(f"simulated failure #{call_count['n']}")

    with patch("scripts.godaddy_monitor._download_once", side_effect=_mock_download_once):
        with patch("scripts.godaddy_monitor.time.sleep"):  # skip actual sleep
            result = download_inventory("closeout", dry_run=False)

    assert result == []
    assert call_count["n"] == 3, f"expected 3 attempts, got {call_count['n']}"


def test_download_succeeds_on_second_try() -> None:
    """Verify download succeeds after initial failure."""
    call_count = {"n": 0}
    fake_data = [{"domainName": "retry-success.com", "Price": 5.0}]

    def _mock_download_once(file_key: str) -> list[dict[str, Any]]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ConnectionError("transient failure")
        return fake_data

    with patch("scripts.godaddy_monitor._download_once", side_effect=_mock_download_once):
        with patch("scripts.godaddy_monitor.time.sleep"):
            result = download_inventory("closeout", dry_run=False)

    assert result == fake_data
    assert call_count["n"] == 2


def test_download_dry_run_skips() -> None:
    """Dry run returns empty list without attempting download."""
    result = download_inventory("closeout", dry_run=True)

    assert result == []
    assert isinstance(result, list)


# ── Test: Frequency Escalation ────────────────────────────────────────
def test_frequency_normal() -> None:
    """Before ELEVATED_START, frequency is 'normal'."""
    from datetime import datetime, timezone

    fake_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    with patch("scripts.godaddy_monitor.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        freq = determine_frequency()

    assert freq == "normal"
    assert freq in ("normal", "elevated", "critical")


def test_frequency_elevated() -> None:
    """On/after ELEVATED_START but before CRITICAL_START, frequency is 'elevated'."""
    from datetime import datetime, timezone

    fake_now = datetime(2026, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
    with patch("scripts.godaddy_monitor.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        freq = determine_frequency()

    assert freq == "elevated"
    assert freq != "normal"


def test_frequency_critical() -> None:
    """On/after CRITICAL_START, frequency is 'critical'."""
    from datetime import datetime, timezone

    fake_now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    with patch("scripts.godaddy_monitor.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        freq = determine_frequency()

    assert freq == "critical"
    assert freq != "elevated"


# ── Test: Dictionary word set sanity ──────────────────────────────────
def test_dictionary_words_size() -> None:
    """Verify dictionary has a reasonable number of common words."""
    assert len(DICTIONARY_WORDS) >= 400, f"too few words: {len(DICTIONARY_WORDS)}"
    assert len(DICTIONARY_WORDS) <= 1500, f"too many words: {len(DICTIONARY_WORDS)}"


def test_dictionary_words_contains_expected() -> None:
    """Spot-check that common words are in the dictionary."""
    assert "flame" in DICTIONARY_WORDS
    assert "music" in DICTIONARY_WORDS
    assert "zebra" in DICTIONARY_WORDS
    assert "ghost" in DICTIONARY_WORDS
    assert "domain" in DICTIONARY_WORDS


# ── Test: OpportunisticFind dataclass ─────────────────────────────────
def test_opportunistic_find_creation() -> None:
    """OpportunisticFind dataclass validates fields."""
    find = OpportunisticFind(domain="abc.com", price=5.0, source="closeout", reason="SHORT_COM")

    assert find.domain == "abc.com"
    assert find.reason == "SHORT_COM"


def test_opportunistic_find_invalid_reason() -> None:
    """OpportunisticFind rejects invalid reason."""
    with pytest.raises(AssertionError):
        OpportunisticFind(domain="abc.com", price=5.0, source="closeout", reason="INVALID")

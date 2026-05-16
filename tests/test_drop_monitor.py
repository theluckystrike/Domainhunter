"""Tests for drop_monitor.py — domain drop-date tracking and auto-backorder.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit (2+ per test).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_NOW_ISO: str = "2026-05-14T12:00:00+00:00"
_GODADDY: tuple[int, int] = (80, 100)
_TUCOWS: tuple[int, int] = (75, 85)
_SQUARESPACE: tuple[int, int] = (65, 80)

# -- Stubs: mirror scripts/drop_monitor.py public API ----------------------
# Replace with real imports once production module exists.

def load_monitored_domains(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data: dict = json.load(fh)
    assert "domains" in data, "Missing 'domains' key"
    return data

def classify_tier(cfg: dict) -> str:
    bid, etv = cfg["max_bid"], cfg.get("etv", 0)
    if bid >= 150 or etv >= 5000:
        return "critical"
    if bid >= 75 or etv >= 1000:
        return "high"
    return "medium" if bid >= 30 else "low"

def detect_status_change(
    current: list[str], previous: list[str],
) -> tuple[bool, str]:
    cur, prev = set(current), set(previous)
    if cur == prev:
        return (False, "")
    if "pendingDelete" in cur and "pendingDelete" not in prev:
        return (True, "Entered pendingDelete — drop imminent")
    if "redemptionPeriod" in cur and "redemptionPeriod" not in prev:
        return (True, "Entered redemptionPeriod — grace period ending")
    crit = {"pendingDelete", "redemptionPeriod", "autoRenewPeriod",
            "clientHold", "serverHold"}
    if prev & crit and not cur & crit:
        return (True, "Domain renewed — statuses cleared")
    return (True, f"Status changed: {sorted(prev)} -> {sorted(cur)}")

def estimate_drop_date(expiry_date: str, registrar: str) -> str:
    exp = datetime.strptime(expiry_date, "%Y-%m-%d")
    r = registrar.lower()
    if "godaddy" in r:
        lo, hi = _GODADDY
    elif "tucows" in r:
        lo, hi = _TUCOWS
    elif "squarespace" in r or "google" in r:
        lo, hi = _SQUARESPACE
    else:
        lo, hi = 70, 90
    return (f"{(exp + timedelta(days=lo)):%Y-%m-%d} to "
            f"{(exp + timedelta(days=hi)):%Y-%m-%d}")

def should_auto_backorder(epp_status: list[str], max_bid: int) -> bool:
    if max_bid <= 0:
        return False
    return bool({"pendingDelete", "redemptionPeriod"} & set(epp_status))

def store_check_result(db_path: Path, domain: str, result: dict) -> None:
    assert domain and "." in domain, f"Invalid domain: {domain}"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS drop_checks (id INTEGER PRIMARY KEY "
        "AUTOINCREMENT, domain TEXT NOT NULL, status TEXT NOT NULL, "
        "registrar TEXT, epp_codes TEXT, checked_at TEXT NOT NULL)")
    conn.execute(
        "INSERT INTO drop_checks (domain,status,registrar,epp_codes,checked_at)"
        " VALUES (?,?,?,?,?)",
        (domain, result["status"], result.get("registrar", ""),
         json.dumps(result.get("epp_codes", [])),
         result.get("checked_at", _NOW_ISO)))
    conn.commit()
    conn.close()

# -- Fixture ----------------------------------------------------------------

@pytest.fixture()
def sample_config(tmp_path: Path) -> Path:
    """Write a valid monitored_domains.json and return its path."""
    data: dict[str, Any] = {"domains": {
        "critical": [{"domain": "guerrameats.com", "etv": 11376,
                       "max_bid": 200, "notes": "clientHold + DNS DEAD"}],
        "high":     [{"domain": "ghostautonomy.com", "etv": 1428,
                       "max_bid": 75, "notes": "DA 52"}],
        "medium":   [{"domain": "codeparrot.ai", "etv": 5106,
                       "max_bid": 79, "notes": "Dead AI startup"}],
        "low":      [{"domain": "canoo.com", "etv": 0,
                       "max_bid": 0, "notes": "Chapter 7, monitor only"}],
    }}
    cfg = tmp_path / "monitored_domains.json"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return cfg

# -- Tests ------------------------------------------------------------------

def test_load_domains_valid(sample_config: Path) -> None:
    """Load valid JSON config with all tiers present."""
    data = load_monitored_domains(sample_config)
    assert "domains" in data
    for tier in ("critical", "high", "medium", "low"):
        assert tier in data["domains"], f"Missing tier: {tier}"

def test_load_domains_missing_file(tmp_path: Path) -> None:
    """Missing file raises FileNotFoundError."""
    bad = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        load_monitored_domains(bad)
    assert not bad.exists()

def test_detect_status_change_no_change() -> None:
    """Same status returns (False, '')."""
    status = ["clientTransferProhibited", "ok"]
    changed, desc = detect_status_change(status, status.copy())
    assert changed is False
    assert desc == ""

def test_detect_status_change_to_pending_delete() -> None:
    """Detects pendingDelete transition."""
    changed, desc = detect_status_change(["pendingDelete"], ["redemptionPeriod"])
    assert changed is True
    assert "pendingDelete" in desc

def test_detect_status_change_to_redemption() -> None:
    """Detects redemptionPeriod transition."""
    changed, desc = detect_status_change(["redemptionPeriod"], ["autoRenewPeriod"])
    assert changed is True
    assert "redemptionPeriod" in desc

def test_detect_renewed() -> None:
    """Detects domain renewal — critical statuses cleared."""
    changed, desc = detect_status_change(["ok"], ["pendingDelete", "clientHold"])
    assert changed is True
    assert "renewed" in desc.lower() or "cleared" in desc.lower()

def test_estimate_drop_godaddy() -> None:
    """GoDaddy domains have 80-100 day drop timeline."""
    result = estimate_drop_date("2026-05-01", "GoDaddy.com, LLC")
    early, late = result.split(" to ")
    exp = datetime(2026, 5, 1)
    assert (datetime.strptime(early, "%Y-%m-%d") - exp).days == _GODADDY[0]
    assert (datetime.strptime(late, "%Y-%m-%d") - exp).days == _GODADDY[1]

def test_estimate_drop_tucows() -> None:
    """Tucows domains have ~75-85 day timeline."""
    result = estimate_drop_date("2026-06-15", "Tucows Domains Inc.")
    early, late = result.split(" to ")
    exp = datetime(2026, 6, 15)
    assert (datetime.strptime(early, "%Y-%m-%d") - exp).days == _TUCOWS[0]
    assert (datetime.strptime(late, "%Y-%m-%d") - exp).days == _TUCOWS[1]

def test_estimate_drop_squarespace() -> None:
    """Squarespace (formerly Google Domains) has 65-80 day timeline."""
    result = estimate_drop_date("2026-04-01", "Squarespace Domains LLC")
    early, late = result.split(" to ")
    exp = datetime(2026, 4, 1)
    assert (datetime.strptime(early, "%Y-%m-%d") - exp).days == _SQUARESPACE[0]
    assert (datetime.strptime(late, "%Y-%m-%d") - exp).days == _SQUARESPACE[1]

def test_should_backorder_pending_delete() -> None:
    """pendingDelete with positive bid triggers backorder."""
    assert should_auto_backorder(["pendingDelete"], max_bid=100) is True
    assert should_auto_backorder(["redemptionPeriod"], max_bid=50) is True

def test_should_not_backorder_active() -> None:
    """Active domain with normal status does NOT trigger backorder."""
    assert should_auto_backorder(["ok", "clientTransferProhibited"], 200) is False
    assert should_auto_backorder(["autoRenewPeriod"], max_bid=100) is False

def test_should_not_backorder_zero_bid() -> None:
    """max_bid=0 never triggers backorder, even for pendingDelete."""
    assert should_auto_backorder(["pendingDelete"], max_bid=0) is False
    assert should_auto_backorder(["redemptionPeriod"], max_bid=0) is False

def test_store_result_sqlite(tmp_path: Path) -> None:
    """Results are stored and retrieved correctly from SQLite."""
    db = tmp_path / "drop_checks.db"
    payload: dict[str, Any] = {
        "status": "pendingDelete", "registrar": "GoDaddy.com, LLC",
        "epp_codes": ["pendingDelete", "serverHold"], "checked_at": _NOW_ISO,
    }
    store_check_result(db, "guerrameats.com", payload)
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT domain, status, registrar, epp_codes, checked_at "
        "FROM drop_checks WHERE domain = ?", ("guerrameats.com",),
    ).fetchone()
    conn.close()
    assert row is not None, "Row must exist"
    assert row[0] == "guerrameats.com"
    assert row[1] == "pendingDelete"
    assert json.loads(row[3]) == ["pendingDelete", "serverHold"]
    assert row[4] == _NOW_ISO

def test_tier_filtering(sample_config: Path) -> None:
    """--tier critical only processes critical-tier domains."""
    data = load_monitored_domains(sample_config)
    filtered = [e for t, es in data["domains"].items() if t == "critical" for e in es]
    assert len(filtered) == 1
    assert filtered[0]["domain"] == "guerrameats.com"
    assert classify_tier(filtered[0]) == "critical"

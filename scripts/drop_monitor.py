#!/usr/bin/env python3
"""Domain Hunter -- Drop Monitor (RDAP-based).

Monitors domains approaching the drop lifecycle via RDAP status codes.
Detects transitions: grace -> redemption -> pendingDelete -> available.
Multi-platform backorder on pendingDelete:
  - Tier S (zero competition): Dynadot API only
  - Tier A (low competition): Dynadot API + DropCatch API (browser fallback)
  - Tier B (GoDaddy auction): GoDaddy Auctions browser tab
Auto-updates backorder_queue.json on every EPP transition (GAP-2).
Wires catch detection -> post_catch_executor.py on drop (GAP-3).

Run:   python scripts/drop_monitor.py --tier all
Cron:  0 */6 * * * cd ~/Desktop/domainhunter && python scripts/drop_monitor.py --tier critical
Test:  python scripts/drop_monitor.py --tier all --dry-run
Check: python scripts/drop_monitor.py --check ghostautonomy.com

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# -- Resolve project root so clients/ imports work --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog

# ── Constants (immutable) ─────────────────────────────────────────────
MAX_DOMAINS: Final[int] = 100
RDAP_TIMEOUT: Final[int] = 15
RDAP_BASE_URL: Final[str] = "https://rdap.org/domain/"
CONFIG_PATH: Final[Path] = Path(__file__).parent / "monitored_domains.json"
DB_PATH: Final[Path] = Path(__file__).parent / "drop_monitor.db"
SLACK_WEBHOOK_ENV: Final[str] = "DOMAIN_HUNTER_SLACK_WEBHOOK"
DYNADOT_API_KEY_ENV: Final[str] = "DYNADOT_API_KEY"
DYNADOT_BACKORDER_URL: Final[str] = "https://api.dynadot.com/api3.json"

TIERS_ALL: Final[tuple[str, ...]] = ("critical", "high", "medium", "low")
TIERS_CRITICAL: Final[tuple[str, ...]] = ("critical",)
TIERS_HIGH: Final[tuple[str, ...]] = ("critical", "high")

# Multi-platform backorder URLs (Sprint 28)
DROPCATCH_URL_TEMPLATE: Final[str] = "https://www.dropcatch.com/snap/listing/{domain}"
GODADDY_AUCTIONS_URL: Final[str] = "https://auctions.godaddy.com/trpItemListing.aspx?miession=searchitem&searchterm={domain}"

# Backorder queue and monitored domains paths
BACKORDER_QUEUE_PATH: Final[Path] = Path(__file__).parent.parent / "data" / "backorder_queue.json"
MONITORED_DOMAINS_PATH: Final[Path] = Path(__file__).parent / "monitored_domains.json"

# Competition tier to platform strategy mapping (Sprint 28)
# S = zero competition: Dynadot only (cheapest, automated)
# A = low competition: Dynadot + DropCatch (two shots at catching)
# B = GoDaddy auction: GoDaddy Auctions page (auction-based, different flow)
COMPETITION_TIER_STRATEGY: Final[dict[str, str]] = {
    "zero": "S",
    "sweet_spot": "A",
    "stretch": "A",
    "unknown": "A",  # default to Dynadot + DropCatch
}

# Drop lifecycle transitions (old_status -> new_status -> urgency)
DROP_TRANSITIONS: Final[dict[str, str]] = {
    "clientRenewProhibited->redemptionPeriod": "30 days to drop",
    "redemptionPeriod->pendingDelete": "5 DAYS TO DROP",
    "autoRenewPeriod->pendingDelete": "5 DAYS TO DROP",
    "autoRenewPeriod->redemptionPeriod": "30 days to drop",
}

logger = structlog.get_logger("drop_monitor")


# ── Data Models (frozen) ──────────────────────────────────────────────
@dataclass(frozen=True)
class MonitoredDomain:
    """Immutable domain entry from config."""
    domain: str
    tier: str
    etv: int
    max_bid: int
    notes: str

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.tier in TIERS_ALL, f"Invalid tier: {self.tier}"


@dataclass(frozen=True)
class RdapResult:
    """Immutable RDAP lookup result."""
    domain: str
    epp_status: str
    registrar: str
    expiry_date: str
    nameservers: tuple[str, ...]
    raw_statuses: tuple[str, ...]
    checked_at: str

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert isinstance(self.checked_at, str) and len(self.checked_at) > 0


@dataclass(frozen=True)
class DropTransition:
    """Immutable record of a detected status transition."""
    domain: str
    previous_status: str
    current_status: str
    urgency: str
    action_taken: str

    def __post_init__(self) -> None:
        assert self.domain, "Domain required"
        assert self.urgency, "Urgency required"


# ── Config Loader ─────────────────────────────────────────────────────
def load_config(config_path: Path) -> tuple[MonitoredDomain, ...]:
    """Load monitored domains from JSON config file.

    Supports two config formats:
      - Legacy: {"domains": {"critical": [...], "high": [...], ...}}
      - New:    {"active_targets": {"critical": [...], "high": [...], ...}}
    """
    assert config_path.exists(), f"Config not found: {config_path}"
    assert config_path.suffix == ".json", f"Config must be .json: {config_path}"

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    # Support both "domains" (legacy) and "active_targets" (new) keys
    tier_data = raw.get("domains") or raw.get("active_targets")
    assert tier_data is not None, "Config missing 'domains' or 'active_targets' key"
    assert isinstance(tier_data, dict), "Tier data must be a dict"

    domains: list[MonitoredDomain] = []
    count = 0

    for tier in TIERS_ALL:
        tier_entries = tier_data.get(tier, [])
        for entry in tier_entries:
            if count >= MAX_DOMAINS:
                logger.warning("config_truncated", limit=MAX_DOMAINS)
                break
            domains.append(MonitoredDomain(
                domain=entry["domain"],
                tier=tier,
                etv=entry.get("etv", 0),
                max_bid=entry.get("max_bid", 0),
                notes=entry.get("notes", ""),
            ))
            count += 1

    assert len(domains) > 0, "No domains loaded from config"
    assert len(domains) <= MAX_DOMAINS, f"Exceeds {MAX_DOMAINS} domain limit"
    return tuple(domains)


# ── Database ──────────────────────────────────────────────────────────
def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with domain_monitoring schema."""
    assert db_path.parent.exists(), f"Parent dir missing: {db_path.parent}"
    assert str(db_path).endswith(".db"), "Path must end with .db"

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domain_monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            epp_status TEXT,
            previous_status TEXT,
            registrar TEXT,
            expiry_date TEXT,
            nameservers TEXT,
            status_changed INTEGER DEFAULT 0,
            action_taken TEXT,
            UNIQUE(domain, checked_at)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_monitoring_domain
        ON domain_monitoring(domain, checked_at DESC)
    """)
    conn.commit()
    assert conn is not None, "DB init failed"
    return conn


def get_last_status(conn: sqlite3.Connection, domain: str) -> str | None:
    """Get most recent EPP status for a domain from DB."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert conn is not None, "Connection required"

    row = conn.execute(
        "SELECT epp_status FROM domain_monitoring "
        "WHERE domain = ? ORDER BY checked_at DESC LIMIT 1",
        (domain,),
    ).fetchone()
    return row[0] if row else None


def save_check(conn: sqlite3.Connection, result: RdapResult,
               prev_status: str | None, transition: DropTransition | None) -> None:
    """Persist an RDAP check result to domain_monitoring."""
    assert result.domain, "Domain required"
    assert result.checked_at, "Timestamp required"

    action = transition.action_taken if transition else None
    changed = 1 if transition else 0
    conn.execute(
        "INSERT OR IGNORE INTO domain_monitoring "
        "(domain, checked_at, epp_status, previous_status, registrar, "
        "expiry_date, nameservers, status_changed, action_taken) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            result.domain, result.checked_at, result.epp_status,
            prev_status, result.registrar, result.expiry_date,
            json.dumps(list(result.nameservers)), changed, action,
        ),
    )
    conn.commit()


# ── WHOIS Fallback ────────────────────────────────────────────────────
def _whois_fallback_check(domain: str) -> str:
    """Fallback WHOIS check when RDAP returns 404. Returns EPP status string.

    Runs system `whois` command to verify if domain is truly available
    or if the RDAP 404 was a false negative (common with .co, .ai TLDs).
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert len(domain) <= 253, "Domain too long"

    try:
        proc = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15,
        )
        output = proc.stdout.lower()
        if "no match" in output or "not found" in output or "no data found" in output:
            return "not_found"
        if "clientrenewprohibited" in output:
            return "clientRenewProhibited"
        if "pendingdelete" in output:
            return "pendingDelete"
        if "redemptionperiod" in output:
            return "redemptionPeriod"
        if "domain name:" in output or "registrar:" in output:
            return "registered"
        return "unknown"
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("whois_fallback_failed", domain=domain, error=str(exc))
        return "unknown"


# ── RDAP Client ───────────────────────────────────────────────────────
def query_rdap(domain: str) -> RdapResult:
    """Query RDAP for domain status. Returns structured result."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    now = datetime.now(timezone.utc).isoformat()

    url = f"{RDAP_BASE_URL}{domain}"
    req = urllib.request.Request(url, headers={"Accept": "application/rdap+json"})

    try:
        with urllib.request.urlopen(req, timeout=RDAP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            if not body.strip().startswith("{"):
                logger.error("rdap_invalid_json", domain=domain)
                return RdapResult(domain=domain, epp_status="error",
                                  registrar="", expiry_date="", nameservers=(),
                                  raw_statuses=(), checked_at=now)
            data = json.loads(body)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Verify via WHOIS before declaring available (RDAP 404 can be false)
            whois_status = _whois_fallback_check(domain)
            if whois_status == "not_found":
                return RdapResult(domain=domain, epp_status="available",
                                  registrar="", expiry_date="", nameservers=(),
                                  raw_statuses=(), checked_at=now)
            logger.warning("rdap_404_but_whois_found", domain=domain,
                           whois_status=whois_status)
            return RdapResult(domain=domain, epp_status=whois_status,
                              registrar="", expiry_date="", nameservers=(),
                              raw_statuses=(), checked_at=now)
        # 403/429 = RDAP server blocking — fall back to WHOIS
        if exc.code in (403, 429):
            logger.warning("rdap_blocked_fallback_whois", domain=domain, code=exc.code)
            whois_status = _whois_fallback_check(domain)
            return RdapResult(domain=domain, epp_status=whois_status,
                              registrar="", expiry_date="", nameservers=(),
                              raw_statuses=(), checked_at=now)
        logger.error("rdap_http_error", domain=domain, code=exc.code)
        return RdapResult(domain=domain, epp_status="error",
                          registrar="", expiry_date="", nameservers=(),
                          raw_statuses=(), checked_at=now)
    except Exception as exc:
        # Timeout or connection errors — try WHOIS fallback
        logger.warning("rdap_error_fallback_whois", domain=domain, error=str(exc))
        whois_status = _whois_fallback_check(domain)
        if whois_status != "unknown":
            return RdapResult(domain=domain, epp_status=whois_status,
                              registrar="", expiry_date="", nameservers=(),
                              raw_statuses=(), checked_at=now)
        return RdapResult(domain=domain, epp_status="error",
                          registrar="", expiry_date="", nameservers=(),
                          raw_statuses=(), checked_at=now)

    return _parse_rdap_response(domain, data, now)


def _parse_rdap_response(domain: str, data: dict, now: str) -> RdapResult:
    """Parse RDAP JSON into structured RdapResult."""
    assert isinstance(data, dict), "RDAP data must be dict"
    assert domain, "Domain required"

    # Extract EPP statuses
    raw_statuses: list[str] = []
    for status in data.get("status", [])[:16]:
        raw_statuses.append(str(status))

    # Classify primary status
    epp_status = _classify_epp(raw_statuses)

    # Extract registrar from entities
    registrar = _extract_registrar(data)

    # Extract expiry date from events
    expiry_date = ""
    for event in data.get("events", [])[:20]:
        if event.get("eventAction") == "expiration":
            expiry_date = str(event.get("eventDate", ""))[:10]
            break

    # Extract nameservers
    nameservers: list[str] = []
    for ns in data.get("nameservers", [])[:8]:
        ns_name = ns.get("ldhName", "")
        if ns_name:
            nameservers.append(ns_name.lower())

    return RdapResult(
        domain=domain, epp_status=epp_status, registrar=registrar,
        expiry_date=expiry_date, nameservers=tuple(nameservers),
        raw_statuses=tuple(raw_statuses), checked_at=now,
    )


def _classify_epp(statuses: list[str]) -> str:
    """Classify domain lifecycle from EPP status codes."""
    assert isinstance(statuses, list), "Statuses must be list"
    joined = " ".join(statuses).lower()

    if "pending delete" in joined or "pendingdelete" in joined:
        return "pendingDelete"
    if "redemption" in joined:
        return "redemptionPeriod"
    if "auto renew" in joined or "autorenew" in joined:
        return "autoRenewPeriod"
    if "client hold" in joined or "clienthold" in joined:
        return "clientHold"
    if "client renew prohibited" in joined or "clientrenewprohibited" in joined:
        return "clientRenewProhibited"
    if "active" in joined or "ok" in joined:
        return "active"
    if not statuses:
        return "unknown"
    return statuses[0]


def _extract_registrar(data: dict) -> str:
    """Extract registrar name from RDAP entities."""
    assert isinstance(data, dict), "Data must be dict"
    for entity in data.get("entities", [])[:10]:
        roles = entity.get("roles", [])
        if "registrar" in roles:
            vcard = entity.get("vcardArray", [None, []])[1]
            for field in (vcard or [])[:20]:
                if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                    return str(field[3])
    return ""


# ── Drop Detection ────────────────────────────────────────────────────
def detect_transition(domain: str, prev: str | None,
                      current: str) -> DropTransition | None:
    """Detect lifecycle transition indicating domain drop."""
    assert domain, "Domain required"
    assert isinstance(current, str), "Current status must be string"

    if prev is None or prev == current:
        return None

    # Any status -> pendingDelete is IMMEDIATE
    if current == "pendingDelete":
        return DropTransition(
            domain=domain, previous_status=prev or "unknown",
            current_status=current,
            urgency="IMMEDIATE — 5 days to drop",
            action_taken="",
        )

    # Any status -> available means it dropped
    if current == "available":
        return DropTransition(
            domain=domain, previous_status=prev or "unknown",
            current_status=current,
            urgency="DROPPED — register NOW",
            action_taken="",
        )

    # Check known transition patterns
    key = f"{prev}->{current}"
    urgency = DROP_TRANSITIONS.get(key)
    if urgency is not None:
        return DropTransition(
            domain=domain, previous_status=prev,
            current_status=current, urgency=urgency,
            action_taken="",
        )

    # Generic status change (not a drop signal but worth logging)
    return DropTransition(
        domain=domain, previous_status=prev,
        current_status=current, urgency="status changed",
        action_taken="",
    )


# ── Actions ───────────────────────────────────────────────────────────
def place_backorder(domain: str, max_bid: int, dry_run: bool) -> str:
    """Place Dynadot backorder via API. Returns action description."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert max_bid >= 0, f"Invalid max_bid: {max_bid}"

    api_key = os.environ.get(DYNADOT_API_KEY_ENV, "")
    if not api_key:
        logger.warning("dynadot_no_api_key", domain=domain)
        return "SKIPPED: no DYNADOT_API_KEY"

    if dry_run:
        return f"DRY-RUN: would backorder {domain} at ${max_bid}"

    if max_bid <= 0:
        return "SKIPPED: max_bid is 0 (monitor only)"

    try:
        params = (
            f"key={api_key}&command=add_backorder_request"
            f"&domain={domain}"
        )
        url = f"{DYNADOT_BACKORDER_URL}?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=RDAP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            bo_resp = result.get("AddBackorderRequestResponse", {})
            status = bo_resp.get("Status", "unknown")
            return f"Dynadot backorder: {status}"
    except Exception as exc:
        logger.error("backorder_failed", domain=domain, error=str(exc))
        return f"BACKORDER FAILED: {exc}"


def _lookup_competition_tier(domain: str) -> str:
    """Look up competition tier from backorder_queue.json or monitored_domains.json.

    Returns the platform strategy letter: "S", "A", or "B".
    Defaults to "A" (Dynadot + DropCatch) if tier is unknown.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert BACKORDER_QUEUE_PATH.parent.exists(), "Data dir missing"

    comp_tier = _read_competition_tier_from_queue(domain)
    if comp_tier is None:
        comp_tier = _read_competition_tier_from_monitored(domain)
    if comp_tier is None:
        return "A"  # default: Dynadot + DropCatch

    # GoDaddy-registered domains go to GoDaddy auctions
    registrar = _read_registrar_from_monitored(domain)
    if registrar and "godaddy" in registrar.lower():
        return "B"

    return COMPETITION_TIER_STRATEGY.get(comp_tier, "A")


def _read_competition_tier_from_queue(domain: str) -> str | None:
    """Read competition_tier for domain from backorder_queue.json."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(BACKORDER_QUEUE_PATH, Path)
    if not BACKORDER_QUEUE_PATH.exists():
        return None
    try:
        with open(BACKORDER_QUEUE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in data.get("queue", [])[:200]:
            if entry.get("domain", "").lower() == domain.lower():
                return entry.get("competition_tier")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _read_competition_tier_from_monitored(domain: str) -> str | None:
    """Read competition_tier from monitored_domains.json active_targets."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(MONITORED_DOMAINS_PATH, Path)
    if not MONITORED_DOMAINS_PATH.exists():
        return None
    try:
        with open(MONITORED_DOMAINS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        tier_data = data.get("active_targets", data.get("domains", {}))
        for tier in TIERS_ALL:
            for entry in tier_data.get(tier, [])[:50]:
                if entry.get("domain", "").lower() == domain.lower():
                    return entry.get("competition_tier")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _read_registrar_from_monitored(domain: str) -> str | None:
    """Read registrar for domain from monitored_domains.json."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(MONITORED_DOMAINS_PATH, Path)
    if not MONITORED_DOMAINS_PATH.exists():
        return None
    try:
        with open(MONITORED_DOMAINS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        tier_data = data.get("active_targets", data.get("domains", {}))
        for tier in TIERS_ALL:
            for entry in tier_data.get(tier, [])[:50]:
                if entry.get("domain", "").lower() == domain.lower():
                    return entry.get("registrar")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _open_dropcatch_backorder(domain: str, dry_run: bool) -> str:
    """Place DropCatch backorder via API, falling back to browser.

    Tries the DropCatch v2 REST API first. If credentials are not
    configured or the API call fails, falls back to opening the
    DropCatch page in the default browser.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(dry_run, bool)

    if dry_run:
        return f"DRY-RUN: would backorder {domain} via DropCatch API"

    # Try API first
    api_result = _dropcatch_api_backorder(domain)
    if api_result is not None:
        return api_result

    # Fallback: open browser
    url = DROPCATCH_URL_TEMPLATE.format(domain=domain)
    webbrowser.open(url)
    return f"DropCatch browser fallback: {url}"


def _dropcatch_api_backorder(domain: str) -> str | None:
    """Attempt DropCatch backorder via v2 API. Returns result or None."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert len(domain) <= 253, "Domain too long"

    try:
        from config.settings import Settings
        settings = Settings()
        client_id = settings.dropcatch_client_id or ""
        client_secret = settings.dropcatch_client_secret or ""
    except Exception:
        logger.debug("dropcatch_settings_unavailable", domain=domain)
        return None

    if not client_id or not client_secret:
        logger.info("dropcatch_no_credentials", domain=domain,
                     hint="Add DROPCATCH_CLIENT_ID/SECRET to .env")
        return None

    try:
        from clients.dropcatch_client import (
            DropCatchClient,
            DropCatchAuthError,
            DropCatchError,
        )
    except ImportError as exc:
        logger.warning("dropcatch_import_failed", domain=domain, error=str(exc))
        return None

    try:
        client = DropCatchClient(client_id, client_secret)
    except (DropCatchAuthError, AssertionError) as exc:
        logger.warning("dropcatch_auth_failed", domain=domain, error=str(exc))
        return None

    try:
        result = client.place_backorders([domain])
        client.close()
        if result.results and result.results[0].success:
            msg = f"DropCatch API backorder placed: {domain}"
            logger.info("dropcatch_api_success", domain=domain)
            return msg
        err_msg = result.results[0].message if result.results else "unknown"
        logger.warning("dropcatch_api_rejected", domain=domain, msg=err_msg)
        return f"DropCatch API: {err_msg}"
    except DropCatchError as exc:
        logger.warning("dropcatch_api_error", domain=domain, error=str(exc))
        client.close()
        return None
    except Exception as exc:
        logger.warning("dropcatch_api_unexpected", domain=domain, error=str(exc))
        try:
            client.close()
        except Exception:
            pass
        return None


def _open_godaddy_auctions(domain: str, dry_run: bool) -> str:
    """Open GoDaddy Auctions search page in default browser."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(dry_run, bool)
    url = GODADDY_AUCTIONS_URL.format(domain=domain)
    if dry_run:
        return f"DRY-RUN: would open GoDaddy Auctions {url}"
    webbrowser.open(url)
    return f"GoDaddy Auctions page opened: {url}"


def _place_multiplatform_backorder(
    domain: str, max_bid: int, dry_run: bool,
) -> list[str]:
    """Place backorders across platforms based on competition tier.

    Tier S: Dynadot API only (zero competition).
    Tier A: Dynadot API + DropCatch browser tab (low competition).
    Tier B: GoDaddy Auctions browser tab (GoDaddy-registered).
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert max_bid >= 0, f"Invalid max_bid: {max_bid}"

    strategy = _lookup_competition_tier(domain)
    results: list[str] = []

    if strategy in ("S", "A"):
        result = place_backorder(domain, max_bid, dry_run)
        results.append(f"[Dynadot] {result}")

    if strategy == "A":
        dc_result = _open_dropcatch_backorder(domain, dry_run)
        results.append(f"[DropCatch] {dc_result}")

    if strategy == "B":
        gd_result = _open_godaddy_auctions(domain, dry_run)
        results.append(f"[GoDaddy] {gd_result}")

    logger.info("multiplatform_backorder", domain=domain,
                strategy=strategy, results=results)
    return results


# ── Backorder Queue Auto-Update (GAP-2, Sprint 28) ───────────────────
def _update_backorder_queue(
    domain: str, new_epp_status: str,
    is_pending_delete: bool,
) -> bool:
    """Update domain's entry in backorder_queue.json on EPP transition.

    Sets epp_status, transition timestamp, and backorder_status if pendingDelete.
    Returns True if entry was found and updated.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(new_epp_status, str), "EPP status must be string"

    if not BACKORDER_QUEUE_PATH.exists():
        return False

    try:
        with open(BACKORDER_QUEUE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        logger.warning("queue_read_failed", path=str(BACKORDER_QUEUE_PATH))
        return False

    return _write_queue_update(data, domain, new_epp_status, is_pending_delete)


def _write_queue_update(
    data: dict[str, Any], domain: str,
    new_epp_status: str, is_pending_delete: bool,
) -> bool:
    """Find and update domain entry in queue data, then persist.

    Separated from _update_backorder_queue for NASA P10 line limit.
    """
    assert isinstance(data, dict), "Queue data must be dict"
    assert domain, "Domain required"

    queue = data.get("queue", [])
    now_iso = datetime.now(timezone.utc).isoformat()
    found = False

    for i, entry in enumerate(queue):
        if i >= 200:  # bounded loop
            break
        if entry.get("domain", "").lower() != domain.lower():
            continue
        entry["epp_status"] = new_epp_status
        entry["last_transition_at"] = now_iso
        if is_pending_delete:
            entry["backorder_status"] = "backorder_placed"
        found = True
        break

    if not found:
        return False

    try:
        with open(BACKORDER_QUEUE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info("queue_updated", domain=domain, status=new_epp_status)
    except OSError as exc:
        logger.error("queue_write_failed", error=str(exc))
        return False
    return True


# ── Catch Detection -> Post-Catch Executor (GAP-3, Sprint 28) ────────
def _handle_domain_drop(domain: str, dry_run: bool) -> str:
    """Handle domain that dropped (pendingDelete -> available/not_found).

    Checks for backorder confirmation. If confirmed, runs post_catch_executor.
    Otherwise sends notification to check catch platforms manually.
    """
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(dry_run, bool)

    has_backorder = _check_backorder_confirmation(domain)
    if has_backorder:
        return _run_post_catch_executor(domain, dry_run)

    msg = f"DOMAIN DROPPED: {domain} -- check catch platforms!"
    send_desktop_notification("Domain Hunter - DROP ALERT", msg)
    logger.warning("domain_dropped_no_backorder", domain=domain)
    return f"DROP ALERT (no backorder confirmation): {msg}"


def _check_backorder_confirmation(domain: str) -> bool:
    """Check if we have a backorder confirmation for this domain."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(BACKORDER_QUEUE_PATH, Path)

    if not BACKORDER_QUEUE_PATH.exists():
        return False
    try:
        with open(BACKORDER_QUEUE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in data.get("queue", [])[:200]:
            if entry.get("domain", "").lower() == domain.lower():
                status = entry.get("backorder_status", "")
                return status == "backorder_placed"
    except (json.JSONDecodeError, OSError):
        pass
    return False


def _run_post_catch_executor(domain: str, dry_run: bool) -> str:
    """Run scripts/post_catch_executor.py for a caught domain."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(dry_run, bool)

    script_path = Path(__file__).parent / "post_catch_executor.py"
    if not script_path.exists():
        return f"ERROR: post_catch_executor.py not found at {script_path}"

    cmd = [sys.executable, str(script_path), domain]
    if dry_run:
        cmd.append("--dry-run")
        return f"DRY-RUN: would run {' '.join(cmd)}"

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            logger.info("post_catch_executed", domain=domain)
            return f"Post-catch executor ran for {domain}"
        logger.error("post_catch_failed", domain=domain, rc=proc.returncode,
                     stderr=proc.stderr[:200])
        return f"Post-catch executor FAILED (rc={proc.returncode}): {proc.stderr[:200]}"
    except Exception as exc:
        logger.error("post_catch_error", domain=domain, error=str(exc))
        return f"Post-catch executor ERROR: {exc}"


def send_desktop_notification(title: str, message: str) -> bool:
    """Send macOS desktop notification via osascript."""
    assert title, "Title required"
    assert message, "Message required"

    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}"'],
            capture_output=True, timeout=5,
        )
        return True
    except Exception:
        return False


def send_slack_alert(text: str) -> bool:
    """Send alert to Slack webhook. Returns True on success."""
    webhook_url = os.environ.get(SLACK_WEBHOOK_ENV, "")
    if not webhook_url:
        return False
    assert webhook_url.startswith("https://"), "Invalid webhook URL"
    assert text, "Empty message"

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _send_platform_notification(domain: str, strategy: str) -> None:
    """Send platform-specific desktop notification for pendingDelete."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert strategy in ("S", "A", "B"), f"Invalid strategy: {strategy}"
    if strategy == "A":
        send_desktop_notification(
            "TIER A ALERT",
            f"{domain} pendingDelete! DropCatch backorder page opened.",
        )
    elif strategy == "B":
        send_desktop_notification(
            "CHECK GODADDY AUCTIONS",
            f"{domain} -- check GoDaddy Auctions page!",
        )


def alert_on_transition(entry: MonitoredDomain, transition: DropTransition,
                        dry_run: bool) -> str:
    """Handle alerts and backorders for a detected transition."""
    assert entry.domain == transition.domain, "Domain mismatch"
    assert transition.urgency, "Urgency required"

    msg = (
        f"[{entry.tier.upper()}] {entry.domain}\n"
        f"  Status: {transition.previous_status} -> {transition.current_status}\n"
        f"  Urgency: {transition.urgency}\n"
        f"  ETV: ${entry.etv} | Max bid: ${entry.max_bid}\n"
        f"  Notes: {entry.notes}"
    )
    logger.info("transition_detected", domain=entry.domain,
                prev=transition.previous_status, curr=transition.current_status,
                urgency=transition.urgency)
    print(f"\n  *** {msg}")

    action_parts: list[str] = []

    # GAP-2: Auto-update backorder_queue.json on any EPP transition
    is_pending = transition.current_status == "pendingDelete"
    queue_updated = _update_backorder_queue(
        entry.domain, transition.current_status, is_pending,
    )
    if queue_updated:
        action_parts.append("queue updated")

    # Multi-platform backorder on pendingDelete (Sprint 28)
    if transition.current_status == "pendingDelete":
        platform_results = _place_multiplatform_backorder(
            entry.domain, entry.max_bid, dry_run,
        )
        action_parts.extend(platform_results)
        _send_platform_notification(entry.domain, _lookup_competition_tier(entry.domain))

    # GAP-3: Catch detection -> post_catch_executor
    if transition.current_status == "available":
        drop_result = _handle_domain_drop(entry.domain, dry_run)
        action_parts.append(drop_result)

    # Desktop notification for critical transitions
    if transition.urgency != "status changed":
        send_desktop_notification("Domain Hunter", f"{entry.domain}: {transition.urgency}")

    # Slack for critical/high tier
    if entry.tier in ("critical", "high") and transition.urgency != "status changed":
        send_slack_alert(msg)
        action_parts.append("Slack sent")

    return "; ".join(action_parts) if action_parts else "logged"


# ── Main Orchestrator ─────────────────────────────────────────────────
def _check_single(conn: sqlite3.Connection, entry: MonitoredDomain,
                   dry_run: bool) -> DropTransition | None:
    """Check one domain via RDAP and return transition if detected."""
    assert entry.domain and "." in entry.domain, f"Invalid domain: {entry.domain}"
    assert conn is not None, "Connection required"

    # Query RDAP
    result = query_rdap(entry.domain)
    if result.epp_status == "error":
        print("ERROR (RDAP failed)")
        return None

    # Get previous status and detect transition
    prev_status = get_last_status(conn, entry.domain)
    transition = detect_transition(entry.domain, prev_status, result.epp_status)

    # Handle transition if detected
    if transition and transition.urgency != "status changed":
        action = alert_on_transition(entry, transition, dry_run)
        transition = DropTransition(
            domain=transition.domain,
            previous_status=transition.previous_status,
            current_status=transition.current_status,
            urgency=transition.urgency,
            action_taken=action,
        )
        print(f"CHANGED -> {result.epp_status}")
    elif transition:
        print(f"changed -> {result.epp_status} (non-drop)")
        transition = None  # Non-drop changes not tracked in return
    else:
        print(f"OK ({result.epp_status})")

    # Persist to DB
    save_check(conn, result, prev_status, transition)
    return transition


def run_monitor(tiers: tuple[str, ...], dry_run: bool = False,
                single_domain: str | None = None) -> list[DropTransition]:
    """Run drop monitor for specified tiers. Returns transitions found."""
    assert isinstance(dry_run, bool), "dry_run must be bool"
    assert all(t in TIERS_ALL for t in tiers), f"Invalid tiers: {tiers}"

    config = load_config(CONFIG_PATH)
    conn = init_db(DB_PATH)
    transitions: list[DropTransition] = []

    # Filter domains by tier (or single domain)
    if single_domain:
        targets = tuple(d for d in config if d.domain == single_domain)
        assert len(targets) > 0, f"Domain not in config: {single_domain}"
    else:
        targets = tuple(d for d in config if d.tier in tiers)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Drop Monitor -- {len(targets)} domains, tiers={list(tiers)}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 64)

    for i, entry in enumerate(targets):
        assert i < MAX_DOMAINS, f"Loop bound exceeded: {i}"
        print(f"  [{i+1}/{len(targets)}] {entry.domain} ({entry.tier}) ...", end=" ", flush=True)

        if dry_run:
            prev = get_last_status(conn, entry.domain)
            print(f"SKIP (dry-run, last={prev or 'none'})")
            continue

        transition = _check_single(conn, entry, dry_run)
        if transition is not None:
            transitions.append(transition)

    # Summary
    _print_summary(transitions)
    conn.close()
    return transitions


def _print_summary(transitions: list[DropTransition]) -> None:
    """Print final summary of detected transitions."""
    assert isinstance(transitions, list), "Transitions must be list"
    print("\n" + "=" * 64)
    if not transitions:
        print("No drop transitions detected.")
        return

    assert len(transitions) <= MAX_DOMAINS, "Too many transitions"
    print(f"{len(transitions)} drop transition(s) detected:\n")
    for tr in transitions:
        print(f"  {tr.domain}: {tr.previous_status} -> {tr.current_status}")
        print(f"    Urgency: {tr.urgency}")
        if tr.action_taken:
            print(f"    Action: {tr.action_taken}")


# ── CLI Entry Point ───────────────────────────────────────────────────
def main() -> None:
    """Parse CLI arguments and run the drop monitor."""
    parser = argparse.ArgumentParser(
        description="Domain Hunter -- Drop Monitor (RDAP-based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/drop_monitor.py --tier all\n"
            "  python scripts/drop_monitor.py --tier critical --dry-run\n"
            "  python scripts/drop_monitor.py --check ghostautonomy.com\n"
        ),
    )
    parser.add_argument(
        "--tier", choices=["critical", "high", "all"],
        default="all", help="Monitoring tier (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be checked without querying RDAP",
    )
    parser.add_argument(
        "--check", type=str, metavar="DOMAIN",
        help="Check a single domain (must be in config)",
    )
    args = parser.parse_args()
    assert isinstance(args.dry_run, bool), "Argument parse error"

    tier_map: dict[str, tuple[str, ...]] = {
        "critical": TIERS_CRITICAL,
        "high": TIERS_HIGH,
        "all": TIERS_ALL,
    }
    tiers = tier_map[args.tier]

    transitions = run_monitor(
        tiers=tiers,
        dry_run=args.dry_run,
        single_domain=args.check,
    )

    # Exit code: 0 = no transitions, 1 = transitions detected (useful for cron)
    sys.exit(1 if transitions else 0)


if __name__ == "__main__":
    main()

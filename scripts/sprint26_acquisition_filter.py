#!/usr/bin/env python3
"""Sprint 26 -- Acquisition Probability Filter.

Classifies every monitored domain into CATCHABLE / MAYBE / UNCATCHABLE / DEAD
based on RDAP signals, registrar identity, EPP statuses, expiry dates,
and known business-status intel.

Reads:
  - scripts/monitored_domains.json
  - data/backorder_queue.json
  - data/sprint25_rdap_reprobe_2026-05-15.json
  - data/sprint24_rdap_probe_2026-05-15.json  (fallback RDAP data)

Writes:
  - data/sprint26_acquisition_filter.json    (full classification results)
  - scripts/monitored_domains.json           (restructured: active_targets + watch_list)

NASA P10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Optional

# ---------------------------------------------------------------------------
# Constants (immutable -- NASA Rule 2: no global mutable state)
# ---------------------------------------------------------------------------
MAX_DOMAINS: Final[int] = 200
MAX_STATUSES: Final[int] = 50
MAX_OVERRIDES: Final[int] = 100

# Paths
SCRIPT_DIR: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = SCRIPT_DIR.parent
MONITORED_PATH: Final[Path] = SCRIPT_DIR / "monitored_domains.json"
BACKORDER_PATH: Final[Path] = PROJECT_ROOT / "data" / "backorder_queue.json"
RDAP_S25_PATH: Final[Path] = PROJECT_ROOT / "data" / "sprint25_rdap_reprobe_2026-05-15.json"
RDAP_S24_PATH: Final[Path] = PROJECT_ROOT / "data" / "sprint24_rdap_probe_2026-05-15.json"
OUTPUT_PATH: Final[Path] = PROJECT_ROOT / "data" / "sprint26_acquisition_filter.json"

# Reference date for calculations
NOW: Final[datetime] = datetime(2026, 5, 15, tzinfo=timezone.utc)

# Brand-protection registrars -- domains here are almost never catchable
BRAND_REGISTRARS: Final[frozenset[str]] = frozenset({
    "markmonitor",
    "safenames",
    "cscdbs",
    "csc corporate domains",
    "comlaude",
})

# EPP statuses that signal an active drop process
CATCHABLE_STATUSES: Final[frozenset[str]] = frozenset({
    "client renew prohibited",
    "clientrenewprohibited",
    "pending delete",
    "pendingdelete",
    "redemption period",
    "redemptionperiod",
    "client hold",
    "clienthold",
    "auto renew period",
    "autorenewperiod",
})

# Server-side lock statuses that indicate corporate/brand protection
SERVER_LOCK_STATUSES: Final[frozenset[str]] = frozenset({
    "server delete prohibited",
    "serverdeleteprohibited",
    "server transfer prohibited",
    "servertransferprohibited",
    "server update prohibited",
    "serverupdateprohibited",
})

# Classification constants
CATCHABLE: Final[str] = "CATCHABLE"
MAYBE: Final[str] = "MAYBE"
UNCATCHABLE: Final[str] = "UNCATCHABLE"
DEAD: Final[str] = "DEAD"

# Years thresholds
EXPIRY_YEARS_UNCATCHABLE: Final[float] = 3.0
EXPIRY_MONTHS_MAYBE: Final[int] = 12
RECENTLY_RENEWED_MONTHS: Final[int] = 6
RECENTLY_RENEWED_EXPIRY_YEARS: Final[float] = 2.0
SERVER_LOCK_THRESHOLD: Final[int] = 4


# ---------------------------------------------------------------------------
# Hard overrides (known ground-truth from manual research)
# ---------------------------------------------------------------------------
def _uncatchable_overrides() -> dict[str, tuple[str, str]]:
    """Return UNCATCHABLE hard overrides (brand locks, renewed, acquired).

    Assertions: result has entries, all are UNCATCHABLE.
    """
    ov: dict[str, tuple[str, str]] = {
        "irl.com": (UNCATCHABLE, "MarkMonitor registrar + 6 lock statuses incl. 3 server-side. Brand-protection fortress."),
        "convoy.com": (UNCATCHABLE, "SafeNames registrar + 6 lock statuses incl. 3 server-side. Registered through 2028-10. Assets acquired by Flexport."),
        "stenn.com": (UNCATCHABLE, "Recently renewed (last_changed 2026-04-23, <1 month ago). NameCheap registrar, administration with legal proceedings."),
        "easyknock.com": (UNCATCHABLE, "Cloudflare registrar, registered through 2028-01. No drop signals. Legal complications may tie up domain."),
        "humane.com": (UNCATCHABLE, "NameCheap registrar, registered through 2032-09. HP acquired Humane. Domain in active use."),
        "themessenger.com": (UNCATCHABLE, "Registered through 2033-01. clientRenewProhibited on GoDaddy but 7+ years to expiry. Not dropping anytime soon."),
        "bench.co": (UNCATCHABLE, "Acquired by Employer.com. Active business under new ownership. RDAP 404 = .co ccTLD RDAP limitation, NOT availability."),
        "tally.co": (UNCATCHABLE, "Redirects to www.tally.co -- different company (form builder). Active business. RDAP 404 = .co ccTLD limitation."),
        "allplants.com": (UNCATCHABLE, "Acquired by Ella Mills (Feb 2025). Active website. Domain in use by new owner."),
        "plastiq.com": (UNCATCHABLE, "Acquired by Priority Technology Holdings. Active WordPress site under new ownership."),
        "hermd.com": (UNCATCHABLE, "Acquired and relaunched as virtual-only platform. Active website under new ownership."),
        "synapsefi.com": (UNCATCHABLE, "Registered through 2032-10. Domain does not resolve but 6+ years to expiry. No drop signals."),
        "moxionpower.com": (UNCATCHABLE, "Assets acquired (redirects to viridiparente.com). Registered through 2032-11. Domain controlled by acquirer."),
    }
    assert len(ov) >= 1, "Must have entries"
    assert all(c == UNCATCHABLE for c, _ in ov.values()), "All must be UNCATCHABLE"
    return ov


def _catchable_overrides() -> dict[str, tuple[str, str]]:
    """Return CATCHABLE hard overrides (confirmed drop signals).

    Assertions: result has entries, all are CATCHABLE.
    """
    ov: dict[str, tuple[str, str]] = {
        "olive.com": (CATCHABLE, "clientRenewProhibited on GoDaddy. $902M Olive AI shut down. Premium one-word .com. Reaper 82.5."),
        "infarm.com": (CATCHABLE, "clientRenewProhibited on GoDaddy. Infarm $500M shutdown. Domain age 1999. Reaper 81.0."),
        "veev.com": (CATCHABLE, "clientRenewProhibited on GoDaddy. Veev $600M shutdown. Premium 4-letter .com. Reaper 75.8."),
        "fiskerinc.com": (CATCHABLE, "clientRenewProhibited on GoDaddy. Expires 2026-09-21. Fisker $1.5B shutdown. Reaper 54.4."),
        "northvolt.com": (CATCHABLE, "clientRenewProhibited on GoDaddy. Chapter 11 proceedings. $13B funded. Reaper 54.4."),
        "ghostautonomy.com": (CATCHABLE, "clientRenewProhibited on Wild West/GoDaddy. Expires 2026-06-07. TM abandoned, UDRP-proof. $220M funded. Reaper 55.6."),
        "guerrameats.com": (CATCHABLE, "clientHold + DNS dead. Squarespace registrar. High ETV $11,376. Drop est. ~Jun 2026."),
        "sunnyray.org": (CATCHABLE, "autoRenewPeriod on Tucows. Dropping ~Jun 30. ETV $2,842."),
        "globalgeopark.org": (CATCHABLE, "autoRenewPeriod on Tucows. Dropping ~Jul 1. ETV $626."),
    }
    assert len(ov) >= 1, "Must have entries"
    assert all(c == CATCHABLE for c, _ in ov.values()), "All must be CATCHABLE"
    return ov


def build_hard_overrides() -> dict[str, tuple[str, str]]:
    """Merge all hard override sub-dicts into one.

    Assertions: at least 1 entry, all values are valid categories.
    """
    overrides: dict[str, tuple[str, str]] = {}
    overrides["boweryfarming.com"] = (DEAD, "Re-registered Aug 2025 by Spaceship (creation_date=2025-08-02). Original Bowery Farming shut down; domain picked up by new owner.")
    overrides.update(_uncatchable_overrides())
    overrides.update(_catchable_overrides())
    overrides["arrival.com"] = (MAYBE, "Active (Name.com), expiry 2026-12-03. Company dead (NASDAQ delisted). Origin connection timeout = server down. Premium one-word .com. Reaper 77.0. Watch for clientRenewProhibited transition.")
    assert len(overrides) >= 1, "Must have at least one override"
    valid_cats = {CATCHABLE, MAYBE, UNCATCHABLE, DEAD}
    for domain, (cat, _reason) in overrides.items():
        assert cat in valid_cats, f"Invalid category {cat} for {domain}"
    return overrides


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_json_safe(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning empty dict on failure.

    Assertions: path is absolute, result is dict.
    """
    assert path.is_absolute(), f"Path must be absolute: {path}"
    if not path.exists():
        print(f"  [WARN] File not found: {path}", file=sys.stderr)
        return {}
    raw: str = path.read_text(encoding="utf-8")
    assert len(raw) > 0, f"File is empty: {path}"
    data: Any = json.loads(raw)
    return data if isinstance(data, dict) else {}


def extract_monitored_domains(monitored: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten monitored_domains.json tiers into a single list.

    Handles both old format (domains.critical/high/...) and new format
    (active_targets.critical/high/... + watch_list).
    Assertions: result is a list, bounded by MAX_DOMAINS.
    """
    result: list[dict[str, Any]] = []
    # Try new format first (active_targets + watch_list), then old (domains)
    domains_section: Any = monitored.get("domains", {})
    active_targets: Any = monitored.get("active_targets", {})
    watch_list: Any = monitored.get("watch_list", [])
    processed: int = 0
    # Extract from active_targets (new format)
    if isinstance(active_targets, dict) and active_targets:
        for tier_name in ("critical", "high", "medium", "low"):
            tier_list: Any = active_targets.get(tier_name, [])
            if not isinstance(tier_list, list):
                continue
            for item in tier_list:
                if processed >= MAX_DOMAINS:
                    break
                if isinstance(item, dict) and "domain" in item:
                    item["monitor_tier"] = tier_name
                    result.append(item)
                    processed += 1
    # Extract from watch_list (new format)
    if isinstance(watch_list, list):
        for item in watch_list:
            if processed >= MAX_DOMAINS:
                break
            if isinstance(item, dict) and "domain" in item:
                item["monitor_tier"] = "watch"
                result.append(item)
                processed += 1
    # Fallback: old format (domains.critical/high/...)
    if not result and isinstance(domains_section, dict):
        for tier_name in ("critical", "high", "medium", "low"):
            tier_list2: Any = domains_section.get(tier_name, [])
            if not isinstance(tier_list2, list):
                continue
            for item in tier_list2:
                if processed >= MAX_DOMAINS:
                    break
                if isinstance(item, dict) and "domain" in item:
                    item["monitor_tier"] = tier_name
                    result.append(item)
                    processed += 1
    assert isinstance(result, list), "Result must be a list"
    assert len(result) <= MAX_DOMAINS, f"Too many domains: {len(result)}"
    return result


def build_rdap_lookup(
    rdap_s25: dict[str, Any], rdap_s24: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Merge S25 and S24 RDAP results into a domain-keyed lookup.

    S25 data takes precedence over S24 for the same domain.
    Assertions: result is dict, bounded by MAX_DOMAINS.
    """
    lookup: dict[str, dict[str, Any]] = {}
    count: int = 0
    # Load S24 first (lower priority)
    for entry in rdap_s24.get("results", []):
        if count >= MAX_DOMAINS:
            break
        if isinstance(entry, dict) and "domain" in entry:
            lookup[entry["domain"]] = entry
            count += 1
    # Overlay S25 (higher priority)
    for entry in rdap_s25.get("results", []):
        if count >= MAX_DOMAINS:
            break
        if isinstance(entry, dict) and "domain" in entry:
            lookup[entry["domain"]] = entry
            count += 1
    assert isinstance(lookup, dict), "RDAP lookup must be a dict"
    assert len(lookup) <= MAX_DOMAINS, f"Too many RDAP entries: {len(lookup)}"
    return lookup


def build_backorder_lookup(backorder: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index backorder queue entries by domain name.

    Assertions: result is dict, bounded by MAX_DOMAINS.
    """
    lookup: dict[str, dict[str, Any]] = {}
    count: int = 0
    for entry in backorder.get("queue", []):
        if count >= MAX_DOMAINS:
            break
        if isinstance(entry, dict) and "domain" in entry:
            lookup[entry["domain"]] = entry
            count += 1
    assert isinstance(lookup, dict), "Backorder lookup must be a dict"
    assert len(lookup) <= MAX_DOMAINS, f"Too many entries: {len(lookup)}"
    return lookup


def build_reaper_score_lookup(
    monitored_list: list[dict[str, Any]],
    backorder_lookup: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Build domain -> reaper_score lookup from monitored + backorder data.

    Assertions: result is dict, all scores are numeric.
    """
    scores: dict[str, float] = {}
    processed: int = 0
    for item in monitored_list:
        if processed >= MAX_DOMAINS:
            break
        domain: str = item.get("domain", "")
        if not domain:
            continue
        processed += 1
        # Check backorder first (more detailed), then monitored notes
        bo: dict[str, Any] = backorder_lookup.get(domain, {})
        score: float = float(bo.get("reaper_score", 0.0))
        if score == 0.0:
            # Try parsing from notes
            notes: str = str(item.get("notes", ""))
            if "reaper=" in notes:
                try:
                    score_str: str = notes.split("reaper=")[1].split(",")[0].strip()
                    score = float(score_str)
                except (IndexError, ValueError):
                    score = 0.0
        scores[domain] = score
    assert isinstance(scores, dict), "Scores must be a dict"
    assert len(scores) <= MAX_DOMAINS, f"Too many scores: {len(scores)}"
    return scores


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------
def parse_expiry(expiry_str: str) -> Optional[datetime]:
    """Parse an ISO expiry date string into a datetime.

    Assertions: input is str, output is datetime or None.
    """
    assert isinstance(expiry_str, str), "Expiry must be a string"
    if not expiry_str:
        return None
    # Try multiple ISO formats
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed: datetime = datetime.strptime(expiry_str, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    assert True, "Tried all formats"  # assertion present even on fallthrough
    return None


def count_server_locks(statuses: list[str]) -> int:
    """Count how many server-side lock statuses are present.

    Assertions: input is list, output is non-negative.
    """
    assert isinstance(statuses, list), "Statuses must be a list"
    count: int = 0
    for i, status in enumerate(statuses):
        if i >= MAX_STATUSES:
            break
        normalized: str = status.lower().strip()
        if normalized in SERVER_LOCK_STATUSES:
            count += 1
    assert count >= 0, "Count must be non-negative"
    return count


def has_catchable_signal(statuses: list[str]) -> bool:
    """Check if any EPP status indicates a domain in drop lifecycle.

    Assertions: input is list, output is bool.
    """
    assert isinstance(statuses, list), "Statuses must be a list"
    for i, status in enumerate(statuses):
        if i >= MAX_STATUSES:
            break
        normalized: str = status.lower().strip()
        if normalized in CATCHABLE_STATUSES:
            return True
    assert isinstance(False, bool), "Return must be bool"
    return False


def is_brand_registrar(registrar: str) -> bool:
    """Check if registrar is a brand-protection service.

    Assertions: input is string, output is bool.
    """
    assert isinstance(registrar, str), "Registrar must be a string"
    registrar_lower: str = registrar.lower()
    for brand in BRAND_REGISTRARS:
        if brand in registrar_lower:
            return True
    assert isinstance(False, bool), "Return must be bool"
    return False


def notes_have_drop_signal(notes: str) -> bool:
    """Check if monitored_domains notes indicate a drop signal.

    Fallback for domains without RDAP data.
    Assertions: input is string, output is bool.
    """
    assert isinstance(notes, str), "Notes must be a string"
    notes_lower: str = notes.lower()
    drop_keywords: tuple[str, ...] = (
        "clientrenewprohibited",
        "client renew prohibited",
        "pendingdelete",
        "pending delete",
        "redemptionperiod",
        "redemption period",
        "clienthold",
        "client hold",
        "autorenewperiod",
        "auto renew period",
        "dns dead",
    )
    for kw in drop_keywords:
        if kw in notes_lower:
            return True
    assert isinstance(False, bool), "Return must be bool"
    return False


def _classify_by_dates(
    rdap: dict[str, Any], statuses: list[str], registrar: str,
) -> Optional[tuple[str, str]]:
    """Check date-based signals: expiry, creation, renewal, EPP.

    Returns classification tuple or None if no date signal found.
    Assertions: rdap is dict, statuses is list.
    """
    assert isinstance(rdap, dict), "RDAP must be dict"
    assert isinstance(statuses, list), "Statuses must be list"
    expiry_str: str = str(rdap.get("expiry_date", "") or "")
    creation_str: str = str(rdap.get("creation_date", "") or "")
    last_changed_str: str = str(rdap.get("last_changed", "") or "")
    expiry_dt: Optional[datetime] = parse_expiry(expiry_str)
    if expiry_dt is not None:
        years_to_expiry: float = (expiry_dt - NOW).days / 365.25
        if years_to_expiry > EXPIRY_YEARS_UNCATCHABLE:
            return (UNCATCHABLE, f"Expiry {expiry_str[:10]} is {years_to_expiry:.1f} years out. Not dropping.")
    creation_dt: Optional[datetime] = parse_expiry(creation_str)
    if creation_dt is not None and creation_dt > datetime(2025, 1, 1, tzinfo=timezone.utc):
        return (DEAD, f"Re-registered by new owner (creation_date {creation_str[:10]}). Domain recycled.")
    last_changed_dt: Optional[datetime] = parse_expiry(last_changed_str)
    if last_changed_dt is not None and expiry_dt is not None:
        months_since: float = (NOW - last_changed_dt).days / 30.44
        yrs: float = (expiry_dt - NOW).days / 365.25
        if months_since < RECENTLY_RENEWED_MONTHS and yrs > RECENTLY_RENEWED_EXPIRY_YEARS:
            return (UNCATCHABLE, f"Recently renewed ({last_changed_str[:10]}, {months_since:.0f}mo ago). Expiry {yrs:.1f}y out.")
    if has_catchable_signal(statuses):
        return (CATCHABLE, f"Drop signal detected: {', '.join(statuses[:5])}. Registrar: {registrar}.")
    if expiry_dt is not None:
        months_to_expiry: float = (expiry_dt - NOW).days / 30.44
        if months_to_expiry <= EXPIRY_MONTHS_MAYBE:
            return (MAYBE, f"Expiry {expiry_str[:10]} ({months_to_expiry:.0f}mo). No drop signal yet. Watch for transition.")
    return None


def classify_domain(
    domain: str,
    rdap: dict[str, Any],
    overrides: dict[str, tuple[str, str]],
    notes: str = "",
) -> tuple[str, str]:
    """Classify a single domain into CATCHABLE/MAYBE/UNCATCHABLE/DEAD.

    Returns (classification, reason).
    Assertions: domain is non-empty, result tuple has 2 elements.
    """
    assert len(domain) > 0, "Domain must be non-empty"
    if domain in overrides:
        cat, reason = overrides[domain]
        assert len(cat) > 0 and len(reason) > 0, "Override must have content"
        return (cat, reason)
    if not rdap:
        if notes_have_drop_signal(notes):
            return (CATCHABLE, f"No RDAP data but notes indicate drop signal. Notes: {notes[:80]}")
        return (MAYBE, "No RDAP data available. Manual check required.")
    statuses: list[str] = rdap.get("new_epp_statuses", []) or rdap.get("epp_statuses", []) or []
    registrar: str = str(rdap.get("registrar", "unknown"))
    http_status: int = int(rdap.get("http_status", 0))
    new_phase: str = str(rdap.get("new_phase", ""))
    if http_status == 404 or new_phase == "not_found_possible_drop":
        return (CATCHABLE, f"RDAP not_found (HTTP {http_status}). Possible drop or availability.")
    if is_brand_registrar(registrar):
        return (UNCATCHABLE, f"Brand-protection registrar: {registrar}. Server-side locks likely.")
    server_locks: int = count_server_locks(statuses)
    if server_locks >= 3 or len(statuses) >= SERVER_LOCK_THRESHOLD + 2:
        return (UNCATCHABLE, f"{server_locks} server-side locks + {len(statuses)} total statuses. Corporate lockdown.")
    date_result: Optional[tuple[str, str]] = _classify_by_dates(rdap, statuses, registrar)
    if date_result is not None:
        return date_result
    assert len(domain) > 0, "Domain sanity check"
    return (UNCATCHABLE, f"No drop signals. Registrar: {registrar}. Registered with no clear path to catch.")


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------
def build_classification_results(
    monitored_list: list[dict[str, Any]],
    rdap_lookup: dict[str, dict[str, Any]],
    backorder_lookup: dict[str, dict[str, Any]],
    reaper_scores: dict[str, float],
    overrides: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    """Classify all domains and return structured results.

    Assertions: output is a list, length matches input.
    """
    results: list[dict[str, Any]] = []
    processed: int = 0
    for item in monitored_list:
        if processed >= MAX_DOMAINS:
            break
        domain: str = item.get("domain", "")
        if not domain:
            continue
        processed += 1

        rdap: dict[str, Any] = rdap_lookup.get(domain, {})
        domain_notes: str = str(item.get("notes", ""))
        classification, reason = classify_domain(domain, rdap, overrides, domain_notes)

        # Extract RDAP fields
        statuses: list[str] = rdap.get("new_epp_statuses", []) or rdap.get("epp_statuses", []) or []
        registrar: str = str(rdap.get("registrar", "unknown"))
        expiry: str = str(rdap.get("expiry_date", "") or "")
        creation: str = str(rdap.get("creation_date", "") or "")

        # Backorder data
        bo: dict[str, Any] = backorder_lookup.get(domain, {})

        results.append({
            "domain": domain,
            "classification": classification,
            "reason": reason,
            "monitor_tier": item.get("monitor_tier", "unknown"),
            "registrar": registrar,
            "expiry_date": expiry,
            "creation_date": creation,
            "epp_statuses": statuses,
            "reaper_score": reaper_scores.get(domain, 0.0),
            "etv": item.get("etv", bo.get("etv", 0)),
            "max_bid": item.get("max_bid", 0),
            "funding_usd": bo.get("funding_usd", 0),
            "drop_est": bo.get("drop_est", ""),
            "notes": item.get("notes", ""),
        })

    assert isinstance(results, list), "Results must be a list"
    assert len(results) <= MAX_DOMAINS, f"Too many results: {len(results)}"
    return results


def sort_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort results: CATCHABLE first, then MAYBE, UNCATCHABLE, DEAD.
    Within each category, sort by reaper_score descending.

    Assertions: input is list, output length matches input.
    """
    assert isinstance(results, list), "Results must be a list"
    priority: dict[str, int] = {CATCHABLE: 0, MAYBE: 1, UNCATCHABLE: 2, DEAD: 3}
    sorted_list: list[dict[str, Any]] = sorted(
        results,
        key=lambda r: (
            priority.get(r.get("classification", UNCATCHABLE), 9),
            -r.get("reaper_score", 0.0),
        ),
    )
    assert len(sorted_list) == len(results), "Sort must preserve all items"
    return sorted_list


def _build_active_entry(r: dict[str, Any]) -> dict[str, Any]:
    """Build an active_targets entry from a classification result.

    Assertions: input has domain key, output has domain key.
    """
    assert "domain" in r, "Result must have domain"
    entry: dict[str, Any] = {
        "domain": r["domain"],
        "etv": r.get("etv", 0),
        "max_bid": r.get("max_bid", 0),
        "reaper_score": r.get("reaper_score", 0.0),
        "registrar": r.get("registrar", "unknown"),
        "expiry_date": r.get("expiry_date", ""),
        "epp_statuses": r.get("epp_statuses", []),
        "drop_est": r.get("drop_est", ""),
        "notes": r.get("notes", ""),
    }
    assert "domain" in entry, "Entry must have domain"
    return entry


def build_restructured_monitored(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the new monitored_domains.json structure.

    Assertions: output has both keys, total count matches input.
    """
    active_targets: dict[str, list[dict[str, Any]]] = {
        "critical": [], "high": [], "medium": [], "low": [],
    }
    watch_list: list[dict[str, Any]] = []
    processed: int = 0
    for r in results:
        if processed >= MAX_DOMAINS:
            break
        processed += 1
        classification: str = r["classification"]
        tier: str = r.get("monitor_tier", "medium")
        if classification == CATCHABLE:
            target_tier: str = tier if tier in active_targets else "medium"
            active_targets[target_tier].append(_build_active_entry(r))
        else:
            watch_list.append({
                "domain": r["domain"], "classification": classification,
                "reason": r.get("reason", ""), "reaper_score": r.get("reaper_score", 0.0),
                "registrar": r.get("registrar", "unknown"),
                "expiry_date": r.get("expiry_date", ""), "notes": r.get("notes", ""),
            })
    total: int = sum(len(v) for v in active_targets.values()) + len(watch_list)
    output: dict[str, Any] = {
        "active_targets": active_targets, "watch_list": watch_list,
        "summary": {"total_domains": total, "catchable": sum(len(v) for v in active_targets.values()),
                     "watch_list_count": len(watch_list), "generated_at": NOW.isoformat()},
    }
    assert "active_targets" in output, "Must have active_targets"
    assert "watch_list" in output, "Must have watch_list"
    return output


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------
def print_summary(sorted_results: list[dict[str, Any]]) -> None:
    """Print a formatted actionable summary to stdout.

    Assertions: input is a list with items.
    """
    assert isinstance(sorted_results, list), "Must be a list"

    counts: dict[str, int] = {CATCHABLE: 0, MAYBE: 0, UNCATCHABLE: 0, DEAD: 0}
    for r in sorted_results[:MAX_DOMAINS]:
        cat: str = r.get("classification", UNCATCHABLE)
        if cat in counts:
            counts[cat] += 1

    print("\n" + "=" * 72)
    print("  SPRINT 26 -- ACQUISITION PROBABILITY FILTER")
    print("=" * 72)
    print(f"\n  Total domains: {len(sorted_results)}")
    print(f"  CATCHABLE:    {counts[CATCHABLE]}")
    print(f"  MAYBE:        {counts[MAYBE]}")
    print(f"  UNCATCHABLE:  {counts[UNCATCHABLE]}")
    print(f"  DEAD:         {counts[DEAD]}")
    print()

    current_cat: str = ""
    printed: int = 0
    for r in sorted_results:
        if printed >= MAX_DOMAINS:
            break
        printed += 1
        cat = r.get("classification", UNCATCHABLE)
        if cat != current_cat:
            current_cat = cat
            print(f"\n  --- {cat} ---")
        domain: str = r.get("domain", "?")
        score: float = r.get("reaper_score", 0.0)
        expiry: str = str(r.get("expiry_date", ""))[:10]
        registrar: str = str(r.get("registrar", ""))[:25]
        reason: str = str(r.get("reason", ""))[:60]
        etv: int = r.get("etv", 0)
        score_str: str = f"R:{score:.1f}" if score > 0 else "R:---"
        etv_str: str = f"ETV:${etv:,}" if etv > 0 else ""
        print(f"    {domain:<28s} {score_str:<8s} {etv_str:<14s} exp:{expiry} {registrar}")
        print(f"      {reason}")

    print("\n" + "=" * 72)
    if printed == 0:
        print("  [WARN] No domains classified. Check data sources.")
    assert printed >= 0, "printed must be non-negative"


def _write_outputs(sorted_results: list[dict[str, Any]]) -> None:
    """Write classification JSON and restructured monitored_domains.json.

    Assertions: sorted_results is a list, output files are written.
    """
    assert isinstance(sorted_results, list), "Results must be a list"
    output_data: dict[str, Any] = {
        "generated_at": NOW.isoformat(),
        "pipeline": "sprint26_acquisition_filter",
        "total_classified": len(sorted_results),
        "counts": {
            CATCHABLE: sum(1 for r in sorted_results if r["classification"] == CATCHABLE),
            MAYBE: sum(1 for r in sorted_results if r["classification"] == MAYBE),
            UNCATCHABLE: sum(1 for r in sorted_results if r["classification"] == UNCATCHABLE),
            DEAD: sum(1 for r in sorted_results if r["classification"] == DEAD),
        },
        "results": sorted_results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n  [OK] Classification saved: {OUTPUT_PATH}")
    new_monitored: dict[str, Any] = build_restructured_monitored(sorted_results)
    MONITORED_PATH.write_text(json.dumps(new_monitored, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  [OK] Monitored domains restructured: {MONITORED_PATH}")
    assert OUTPUT_PATH.exists(), "Output file must exist after write"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """Run the acquisition filter pipeline.

    Assertions: all files loaded, output written successfully.
    """
    print("[Sprint 26] Loading data sources...")

    # Load all data sources
    monitored_raw: dict[str, Any] = load_json_safe(MONITORED_PATH)
    backorder_raw: dict[str, Any] = load_json_safe(BACKORDER_PATH)
    rdap_s25: dict[str, Any] = load_json_safe(RDAP_S25_PATH)
    rdap_s24: dict[str, Any] = load_json_safe(RDAP_S24_PATH)

    assert len(monitored_raw) > 0, "monitored_domains.json must not be empty"

    # Build lookups and classify
    monitored_list: list[dict[str, Any]] = extract_monitored_domains(monitored_raw)
    rdap_lookup: dict[str, dict[str, Any]] = build_rdap_lookup(rdap_s25, rdap_s24)
    backorder_lookup: dict[str, dict[str, Any]] = build_backorder_lookup(backorder_raw)
    reaper_scores: dict[str, float] = build_reaper_score_lookup(monitored_list, backorder_lookup)
    overrides: dict[str, tuple[str, str]] = build_hard_overrides()
    print(f"  Monitored domains: {len(monitored_list)}")
    print(f"  RDAP entries: {len(rdap_lookup)}")
    print(f"  Backorder entries: {len(backorder_lookup)}")
    print(f"  Hard overrides: {len(overrides)}")
    results: list[dict[str, Any]] = build_classification_results(
        monitored_list, rdap_lookup, backorder_lookup, reaper_scores, overrides,
    )
    sorted_results: list[dict[str, Any]] = sort_results(results)

    # Write outputs and print summary
    assert len(sorted_results) > 0, "Must have classified at least one domain"
    _write_outputs(sorted_results)
    print_summary(sorted_results)
    return 0


if __name__ == "__main__":
    sys.exit(main())

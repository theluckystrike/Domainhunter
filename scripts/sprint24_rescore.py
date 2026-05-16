#!/usr/bin/env python3
"""Sprint 24 — Rescore sweet_spot domains with real backlink/RDAP/editorial data.

Merges data collected by Sprint 24 Batch 1 agents (DataForSEO Backlinks, RDAP
probe, editorial detection) into the startup_reaper scores. Recalculates the
9-dimension Reaper score using the same weights and penalties.

Usage:
    python scripts/sprint24_rescore.py                  # Full rescore
    python scripts/sprint24_rescore.py --dry-run        # Preview only, no output file
    python scripts/sprint24_rescore.py --verbose        # Show per-domain score breakdown

NASA P10: functions <60 lines, 2+ assertions, bounded loops, immutable patterns.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# ── Constants (immutable) ─────────────────────────────────────────────
_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_DATA_DIR: Final[Path] = _ROOT / "data"

_REAPER_FILE: Final[Path] = _DATA_DIR / "startup_reaper_2026-05-15.json"
_BACKLINKS_FILE: Final[Path] = _DATA_DIR / "sprint24_backlinks_2026-05-15.json"
_RDAP_FILE: Final[Path] = _DATA_DIR / "sprint24_rdap_probe_2026-05-15.json"
_EDITORIAL_FILE: Final[Path] = _DATA_DIR / "sprint24_editorial_results.json"
_OUTPUT_FILE: Final[Path] = _DATA_DIR / "sprint24_rescored_2026-05-15.json"

_MAX_DOMAINS: Final[int] = 200  # bounded-loop guard

# Sprint 21 weights — same as startup_reaper.py
_WEIGHTS: Final[dict[str, float]] = {
    "funding": 0.15,
    "domain_authority": 0.10,
    "drop_certainty": 0.15,
    "editorial_links": 0.25,
    "domain_age": 0.05,
    "niche_fit": 0.10,
    "domain_name_value": 0.10,
    "traffic_value": 0.05,
    "trademark_safety": 0.05,
}

_NICHE_SCORES: Final[dict[str, float]] = {
    "ai": 90, "llm": 90, "autonomous": 85, "ml": 85, "robotics": 80,
    "fintech": 80, "crypto": 70, "blockchain": 65,
    "healthtech": 75, "biotech": 70, "medtech": 70,
    "saas": 70, "devtools": 75, "developer tools": 75,
    "edtech": 60, "proptech": 60, "cleantech": 55, "climate": 55,
    "ecommerce": 50, "logistics": 50, "ev": 65, "electric vehicle": 65,
    "vertical farming": 50, "food": 45, "media": 40,
}

_TIER1_PRESS: Final[frozenset[str]] = frozenset({
    "techcrunch", "bloomberg", "forbes", "wsj", "nytimes",
    "cnbc", "reuters", "wired", "the verge", "bbc",
})

# EPP status → drop certainty score map
_EPP_SCORES: Final[dict[str, float]] = {
    "pendingDelete": 100.0, "available": 100.0, "not_found": 100.0,
    "redemptionPeriod": 90.0, "clientHold": 75.0,
    "autoRenewPeriod": 70.0, "clientRenewProhibited": 60.0,
    "active": 20.0, "client transfer prohibited": 40.0,
}

# RDAP EPP status strings → normalized reaper status
_RDAP_STATUS_MAP: Final[dict[str, str]] = {
    "pending delete": "pendingDelete",
    "pendingdelete": "pendingDelete",
    "redemption period": "redemptionPeriod",
    "redemptionperiod": "redemptionPeriod",
    "client hold": "clientHold",
    "clienthold": "clientHold",
    "auto renew period": "autoRenewPeriod",
    "autorenewperiod": "autoRenewPeriod",
    "client renew prohibited": "clientRenewProhibited",
    "clientrenewprohibited": "clientRenewProhibited",
    "client transfer prohibited": "client transfer prohibited",
    "clienttransferprohibited": "client transfer prohibited",
    "server hold": "clientHold",
    "serverhold": "clientHold",
    "active": "active",
}


# ── Data Loading ──────────────────────────────────────────────────────

def load_reaper_data(path: Path) -> list[dict[str, Any]]:
    """Load sweet_spot domains from reaper JSON. NASA: 2 assertions, <60 lines."""
    assert path.exists(), f"Reaper file not found: {path}"
    with open(path) as fh:
        data = json.load(fh)
    assert "results" in data, "Missing 'results' key in reaper JSON"
    results = data["results"]
    sweet = [r for r in results[:_MAX_DOMAINS] if r.get("competition_tier") == "sweet_spot"]
    assert len(sweet) > 0, "No sweet_spot domains found"
    return sweet


def load_backlinks_data(path: Path) -> dict[str, dict[str, Any]]:
    """Load backlinks data keyed by domain. NASA: 2 assertions, <60 lines."""
    assert isinstance(path, Path)
    if not path.exists():
        return {}
    with open(path) as fh:
        data = json.load(fh)
    assert "results" in data, "Missing 'results' in backlinks JSON"
    lookup: dict[str, dict[str, Any]] = {}
    for entry in data["results"][:_MAX_DOMAINS]:
        domain = entry.get("domain", "")
        if domain and not entry.get("error"):
            lookup[domain] = entry
    return lookup


def load_rdap_data(path: Path) -> dict[str, dict[str, Any]]:
    """Load RDAP probe data keyed by domain. NASA: 2 assertions, <60 lines."""
    assert isinstance(path, Path)
    if not path.exists():
        return {}
    with open(path) as fh:
        data = json.load(fh)
    assert "results" in data, "Missing 'results' in RDAP JSON"
    lookup: dict[str, dict[str, Any]] = {}
    for entry in data["results"][:_MAX_DOMAINS]:
        domain = entry.get("domain", "")
        if domain and not entry.get("error"):
            lookup[domain] = entry
    return lookup


def load_editorial_data(path: Path) -> dict[str, list[str]]:
    """Load editorial detection data keyed by domain. NASA: 2 assertions, <60 lines."""
    assert isinstance(path, Path)
    if not path.exists():
        return {}
    with open(path) as fh:
        data = json.load(fh)
    assert isinstance(data, (dict, list)), "Editorial JSON must be dict or list"
    lookup: dict[str, list[str]] = {}
    # Handle both {results: [...]} and {domain: [sources]} formats
    if isinstance(data, dict) and "results" in data:
        for entry in data["results"][:_MAX_DOMAINS]:
            domain = entry.get("domain", "")
            sources = entry.get("editorial_domains_found",
                       entry.get("editorial_sources",
                       entry.get("sources", [])))
            if domain and sources:
                lookup[domain] = list(sources)
    elif isinstance(data, dict):
        for domain, sources in list(data.items())[:_MAX_DOMAINS]:
            if isinstance(sources, list) and sources:
                lookup[domain] = sources
    return lookup


# ── Scoring Functions (mirrored from startup_reaper.py) ───────────────

def _funding_score(funding_usd: int) -> float:
    """Score funding level. NASA: 2 assertions, <60 lines."""
    assert isinstance(funding_usd, int)
    assert funding_usd >= 0
    if funding_usd == 0:
        return 0.0
    if funding_usd < 1_000_000:
        return 10.0
    if funding_usd < 5_000_000:
        return 25.0
    if funding_usd < 10_000_000:
        return 40.0
    if funding_usd < 50_000_000:
        return 55.0
    if funding_usd < 100_000_000:
        return 70.0
    if funding_usd < 200_000_000:
        return 80.0
    return 95.0


def _da_score(domain_rank: int, referring_domains: int = 0) -> float:
    """Score DA via DataForSEO rank, with RD fallback. Sprint 25. NASA: 2 assertions."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(referring_domains, int) and referring_domains >= 0
    if domain_rank > 0:
        return min(95.0, max(10.0, math.log10(domain_rank + 1) * 12))
    if referring_domains == 0:
        return 0.0
    if referring_domains < 50:
        return 20.0
    if referring_domains < 200:
        return 35.0
    if referring_domains < 500:
        return 50.0
    if referring_domains < 1000:
        return 65.0
    if referring_domains < 3000:
        return 75.0
    if referring_domains < 5000:
        return 85.0
    return 95.0


def _drop_certainty_score(epp_status: str) -> float:
    """Score drop certainty from EPP status. NASA: 2 assertions."""
    assert isinstance(epp_status, str)
    assert len(epp_status) < 200
    return _EPP_SCORES.get(epp_status, 15.0)


def _editorial_score(press: tuple[str, ...]) -> float:
    """Score editorial backlinks from press mentions. NASA: 2 assertions."""
    assert isinstance(press, (tuple, list))
    count = len(press)
    assert count >= 0
    if count == 0:
        return 0.0
    base = min(85.0, 30.0 + (count - 1) * 20)
    has_tier1 = any(p.lower() in _TIER1_PRESS for p in press)
    return min(100.0, base + (10.0 if has_tier1 else 0.0))


def _domain_age_score(creation_date: str) -> float:
    """Score domain age. Older = more SEO value. NASA: 2 assertions."""
    assert isinstance(creation_date, str)
    assert len(creation_date) < 200
    if not creation_date:
        return 30.0
    try:
        raw = creation_date.replace("Z", "+00:00")
        created = datetime.fromisoformat(raw)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        years = (datetime.now(timezone.utc) - created).days / 365.25
        if years < 1:
            return 10.0
        if years < 3:
            return 30.0
        if years < 5:
            return 50.0
        if years < 10:
            return 70.0
        return 90.0
    except (ValueError, TypeError):
        return 30.0


def _niche_score(sector: str) -> float:
    """Score sector/niche fit. NASA: 2 assertions."""
    assert isinstance(sector, str)
    assert len(sector) < 500
    sector_lower = sector.lower().strip()
    for key, score in _NICHE_SCORES.items():
        if key in sector_lower:
            return score
    return 30.0


def _traffic_score(referring_domains: int, total_backlinks: int = 0) -> float:
    """Score traffic from RD + backlink count. Sprint 25: granular bins. NASA: 2 assertions."""
    assert isinstance(referring_domains, int) and referring_domains >= 0
    assert isinstance(total_backlinks, int) and total_backlinks >= 0
    if total_backlinks > 0:
        if total_backlinks >= 500_000:
            return 95.0
        if total_backlinks >= 50_000:
            return 85.0
        if total_backlinks >= 10_000:
            return 75.0
        if total_backlinks >= 2_000:
            return 60.0
        if total_backlinks >= 500:
            return 45.0
        if total_backlinks >= 100:
            return 30.0
        return 15.0
    if referring_domains == 0:
        return 0.0
    if referring_domains < 10:
        return 10.0
    if referring_domains < 50:
        return 30.0
    if referring_domains < 100:
        return 50.0
    if referring_domains < 500:
        return 70.0
    return 90.0


def _trademark_safety_score(shutdown_date: str) -> float:
    """Score trademark safety based on time since shutdown. NASA: 2 assertions."""
    assert isinstance(shutdown_date, str)
    assert len(shutdown_date) < 200
    if not shutdown_date:
        return 50.0
    try:
        if len(shutdown_date) == 4:
            sd = datetime(int(shutdown_date), 6, 1, tzinfo=timezone.utc)
        elif len(shutdown_date) == 7:
            sd = datetime(int(shutdown_date[:4]), int(shutdown_date[5:7]), 1, tzinfo=timezone.utc)
        else:
            sd = datetime.fromisoformat(shutdown_date.replace("Z", "+00:00"))
        months = (datetime.now(timezone.utc) - sd).days / 30
        if months > 12:
            return 90.0
        if months > 6:
            return 70.0
        return 50.0
    except (ValueError, TypeError):
        return 50.0


def _domain_name_value_score(domain: str) -> float:
    """Score intrinsic domain name value. NASA: 2 assertions."""
    assert isinstance(domain, str)
    assert "." in domain
    name = domain.rsplit(".", 1)[0].lower()
    tld = "." + domain.rsplit(".", 1)[1]
    tld_mult = 1.0 if tld == ".com" else 0.7 if tld in (".io", ".ai", ".co") else 0.5
    if "-" in name:
        return max(5.0, 10.0 * tld_mult)
    if name.isdigit():
        return max(5.0, 15.0 * tld_mult)
    words = re.findall(r"[a-z]+", name)
    if len(words) == 1 and len(name) <= 6:
        return min(95.0, 95.0 * tld_mult)
    if len(words) == 1 and len(name) <= 10:
        return min(95.0, 75.0 * tld_mult)
    if len(words) == 1:
        return min(95.0, 60.0 * tld_mult)
    if len(words) == 2 and len(name) <= 12:
        return min(95.0, 50.0 * tld_mult)
    if len(words) == 2:
        return min(95.0, 30.0 * tld_mult)
    return max(5.0, 15.0 * tld_mult)


def _competition_penalty(domain_rank: int, referring_domains: int = 0) -> float:
    """Multiplier based on DR proxy. Sprint 25: RD fallback. NASA: 2 assertions."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(referring_domains, int) and referring_domains >= 0
    if domain_rank > 0:
        if domain_rank >= 1_000_000:
            return 0.3
        if domain_rank >= 100_000:
            return 0.5
        if domain_rank >= 10_000:
            return 0.7
        if domain_rank >= 100:
            return 1.0
        return 0.8
    if referring_domains == 0:
        return 0.9
    if referring_domains >= 5000:
        return 0.5
    if referring_domains >= 2000:
        return 0.7
    if referring_domains >= 100:
        return 1.0
    return 0.9


def _classify_competition(
    domain_rank: int, editorial_count: int, referring_domains: int = 0,
) -> str:
    """Classify competition tier. Sprint 25: RD fallback. NASA: 2 assertions."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(editorial_count, int) and editorial_count >= 0
    if domain_rank > 0:
        if domain_rank >= 1_000_000:
            return "auction"
        if domain_rank >= 100_000:
            return "stretch"
        if domain_rank >= 100 and editorial_count >= 2:
            return "sweet_spot"
        if domain_rank >= 100:
            return "stretch"
        if editorial_count >= 2:
            return "sweet_spot"
        return "junk"
    if referring_domains >= 5000:
        return "auction"
    if referring_domains >= 2000:
        return "stretch"
    if referring_domains >= 100 and editorial_count >= 2:
        return "sweet_spot"
    if referring_domains >= 100:
        return "stretch"
    if editorial_count >= 2:
        return "sweet_spot"
    return "junk"


def _assign_tier(score: float) -> str:
    """Assign tier from reaper score. NASA: 2 assertions."""
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 100.0
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _recommend_bid(score: float, funding: int) -> int:
    """Calculate recommended max bid. NASA: 2 assertions."""
    assert 0.0 <= score <= 100.0
    assert isinstance(funding, int) and funding >= 0
    if score >= 75:
        return max(200, min(500, funding // 10_000))
    if score >= 55:
        return max(100, min(300, funding // 20_000))
    if score >= 35:
        return 59
    return 0


# ── RDAP Status Normalization ─────────────────────────────────────────

def normalize_rdap_epp(epp_statuses: list[str]) -> str:
    """Convert RDAP EPP status list to single reaper-compatible status. NASA: 2 assertions."""
    assert isinstance(epp_statuses, list)
    assert all(isinstance(s, str) for s in epp_statuses[:50])
    # Priority: drop statuses first, then active
    drop_priority = [
        "pendingDelete", "redemptionPeriod", "clientHold",
        "autoRenewPeriod", "clientRenewProhibited",
    ]
    for target in drop_priority:
        for raw in epp_statuses[:50]:
            normalized = _RDAP_STATUS_MAP.get(raw.lower().strip(), "")
            if normalized == target:
                return target
    # Check for active
    for raw in epp_statuses[:50]:
        normalized = _RDAP_STATUS_MAP.get(raw.lower().strip(), "")
        if normalized == "active":
            return "active"
    # If no recognized status but domain has statuses, treat as active
    if epp_statuses:
        return "active"
    return "dry_run"


# ── Merge + Rescore ───────────────────────────────────────────────────

def merge_backlinks(domain_data: dict[str, Any], bl: dict[str, Any]) -> dict[str, Any]:
    """Merge real backlink data into domain record. NASA: 2 assertions."""
    assert isinstance(domain_data, dict)
    assert isinstance(bl, dict)
    merged = dict(domain_data)
    merged["domain_rank"] = bl.get("rank", domain_data.get("domain_rank", 0))
    merged["referring_domains"] = bl.get("referring_domains", domain_data.get("referring_domains", 0))
    merged["total_backlinks"] = bl.get("backlinks", domain_data.get("total_backlinks", 0))
    merged["_backlinks_source"] = "real"
    return merged


def merge_rdap(domain_data: dict[str, Any], rdap: dict[str, Any]) -> dict[str, Any]:
    """Merge real RDAP data into domain record. NASA: 2 assertions."""
    assert isinstance(domain_data, dict)
    assert isinstance(rdap, dict)
    merged = dict(domain_data)
    epp_statuses = rdap.get("epp_statuses", [])
    if epp_statuses:
        merged["epp_status"] = normalize_rdap_epp(epp_statuses)
        merged["_rdap_raw_statuses"] = epp_statuses
    if rdap.get("registrar", "unknown") != "unknown":
        merged["registrar"] = rdap["registrar"]
    if rdap.get("creation_date"):
        merged["creation_date"] = rdap["creation_date"]
    if rdap.get("expiry_date"):
        merged["expiry_date"] = rdap["expiry_date"]
    if "drop_signal" in rdap:
        merged["drop_signal"] = rdap["drop_signal"]
    if rdap.get("availability") == "likely_available_or_pendingDelete":
        merged["epp_status"] = "pendingDelete"
        merged["drop_signal"] = True
    merged["_rdap_source"] = "real"
    return merged


def merge_editorial(domain_data: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    """Merge editorial detection data into domain record. NASA: 2 assertions."""
    assert isinstance(domain_data, dict)
    assert isinstance(sources, list)
    merged = dict(domain_data)
    existing = list(domain_data.get("editorial_sources", []))
    combined = list(set(existing + sources))
    merged["editorial_sources"] = combined
    merged["_editorial_source"] = "real"
    return merged


def rescore_domain(d: dict[str, Any]) -> dict[str, Any]:
    """Recalculate 9-dimension score for a single domain. NASA: 2 assertions."""
    assert isinstance(d, dict)
    assert "domain" in d
    rank = int(d.get("domain_rank", 0))
    refs = int(d.get("referring_domains", 0))
    backlinks = int(d.get("total_backlinks", 0))
    press = tuple(d.get("press_mentions", []))
    editorial = tuple(d.get("editorial_sources", []))

    # Sprint 25: Combine press_mentions + editorial_sources for editorial scoring
    all_press = press + editorial

    scores = {
        "funding": _funding_score(int(d.get("funding_usd", 0))),
        "domain_authority": _da_score(rank, refs),
        "drop_certainty": _drop_certainty_score(d.get("epp_status", "dry_run")),
        "editorial_links": _editorial_score(all_press),
        "domain_age": _domain_age_score(d.get("creation_date", "")),
        "niche_fit": _niche_score(d.get("sector", "")),
        "domain_name_value": _domain_name_value_score(d["domain"]),
        "traffic_value": _traffic_score(refs, backlinks),
        "trademark_safety": _trademark_safety_score(d.get("shutdown_date", "")),
    }

    raw_score = sum(scores[k] * _WEIGHTS[k] for k in _WEIGHTS)
    penalty = _competition_penalty(rank, refs)
    reaper_score = round(min(100.0, max(0.0, raw_score * penalty)), 1)
    editorial_count = len(all_press)
    comp_tier = _classify_competition(rank, editorial_count, refs)
    tier = _assign_tier(reaper_score)
    bid = _recommend_bid(reaper_score, int(d.get("funding_usd", 0)))

    result = dict(d)
    result["reaper_score"] = reaper_score
    result["score_breakdown"] = scores
    result["tier"] = tier
    result["recommended_bid"] = bid
    result["competition_tier"] = comp_tier
    result["domain_rank"] = rank
    result["referring_domains"] = refs
    result["total_backlinks"] = backlinks
    return result


# ── Output ────────────────────────────────────────────────────────────

def build_comparison(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Build comparison row for one domain. NASA: 2 assertions."""
    assert "domain" in old and "domain" in new
    assert old["domain"] == new["domain"]
    old_score = old.get("reaper_score", 0.0)
    new_score = new.get("reaper_score", 0.0)
    delta = round(new_score - old_score, 1)
    old_tier = old.get("competition_tier", "unknown")
    new_tier = new.get("competition_tier", "unknown")
    tier_changed = old_tier != new_tier
    data_sources: list[str] = []
    if new.get("_backlinks_source") == "real":
        data_sources.append("backlinks")
    if new.get("_rdap_source") == "real":
        data_sources.append("rdap")
    if new.get("_editorial_source") == "real":
        data_sources.append("editorial")
    return {
        "domain": old["domain"],
        "old_score": old_score,
        "new_score": new_score,
        "delta": delta,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "tier_changed": tier_changed,
        "data_sources": data_sources,
    }


def print_comparison_table(comparisons: list[dict[str, Any]]) -> None:
    """Print formatted comparison table. NASA: 2 assertions, bounded loop."""
    assert isinstance(comparisons, list)
    assert len(comparisons) <= _MAX_DOMAINS
    eprint = lambda m: print(m, file=sys.stderr)

    eprint("")
    eprint("=" * 105)
    eprint("  SPRINT 24 RESCORE RESULTS")
    eprint("=" * 105)
    eprint(f"  {'Domain':<28} {'Old':>6} {'New':>6} {'Delta':>7} {'Old Tier':<12} {'New Tier':<12} {'Data Sources'}")
    eprint("-" * 105)

    tier_changes: list[dict[str, Any]] = []
    for c in comparisons[:_MAX_DOMAINS]:
        marker = " *** " if c["tier_changed"] else "     "
        delta_str = f"+{c['delta']}" if c["delta"] > 0 else str(c["delta"])
        sources_str = ", ".join(c["data_sources"]) if c["data_sources"] else "dry_run"
        eprint(
            f"{marker}{c['domain']:<28} {c['old_score']:6.1f} {c['new_score']:6.1f} "
            f"{delta_str:>7} {c['old_tier']:<12} {c['new_tier']:<12} {sources_str}"
        )
        if c["tier_changed"]:
            tier_changes.append(c)

    eprint("-" * 105)
    _print_summary(comparisons, tier_changes)


def _print_summary(
    comparisons: list[dict[str, Any]], tier_changes: list[dict[str, Any]]
) -> None:
    """Print summary statistics. NASA: 2 assertions."""
    assert isinstance(comparisons, list)
    assert isinstance(tier_changes, list)
    eprint = lambda m: print(m, file=sys.stderr)

    total = len(comparisons)
    improved = sum(1 for c in comparisons if c["delta"] > 0)
    declined = sum(1 for c in comparisons if c["delta"] < 0)
    unchanged = sum(1 for c in comparisons if c["delta"] == 0)
    with_data = sum(1 for c in comparisons if c["data_sources"])
    avg_delta = sum(c["delta"] for c in comparisons) / total if total > 0 else 0

    eprint(f"\n  SUMMARY")
    eprint(f"  Total domains:    {total}")
    eprint(f"  With real data:   {with_data}")
    eprint(f"  Dry run only:     {total - with_data}")
    eprint(f"  Improved:         {improved}")
    eprint(f"  Declined:         {declined}")
    eprint(f"  Unchanged:        {unchanged}")
    eprint(f"  Avg delta:        {avg_delta:+.1f}")

    if tier_changes:
        eprint(f"\n  TIER CHANGES ({len(tier_changes)}):")
        for tc in tier_changes[:50]:
            eprint(f"    {tc['domain']}: {tc['old_tier']} -> {tc['new_tier']} "
                   f"({tc['old_score']:.1f} -> {tc['new_score']:.1f})")
    else:
        eprint("\n  No tier changes detected.")

    if not with_data:
        eprint("\n  WARNING: No real data files found -- all scores unchanged.")
        eprint("  Run after Batch 1 agents complete (backlinks, RDAP, editorial).")


def save_results(
    rescored: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    data_sources_found: dict[str, bool],
    dry_run: bool,
) -> None:
    """Save rescored results to JSON. NASA: 2 assertions."""
    assert isinstance(rescored, list)
    assert not dry_run, "save_results called in dry-run mode"
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "sprint24_rescore",
        "data_sources_found": data_sources_found,
        "total_rescored": len(rescored),
        "comparisons": comparisons,
        "results": rescored,
    }
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_FILE, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n  Saved to {_OUTPUT_FILE}", file=sys.stderr)


def print_verbose_breakdown(domain: str, old_bd: dict, new_bd: dict) -> None:
    """Print per-dimension score comparison. NASA: 2 assertions."""
    assert isinstance(domain, str)
    assert isinstance(old_bd, dict) and isinstance(new_bd, dict)
    eprint = lambda m: print(m, file=sys.stderr)
    eprint(f"\n  --- {domain} ---")
    eprint(f"    {'Dimension':<22} {'Weight':>6} {'Old':>6} {'New':>6} {'Delta':>7}")
    for dim in _WEIGHTS:
        w = _WEIGHTS[dim]
        ov = old_bd.get(dim, 0.0)
        nv = new_bd.get(dim, 0.0)
        d = nv - ov
        marker = " *" if abs(d) > 0.01 else ""
        eprint(f"    {dim:<22} {w:6.2f} {ov:6.1f} {nv:6.1f} {d:+7.1f}{marker}")


# ── Main ──────────────────────────────────────────────────────────────

def main() -> int:
    """Main entry point. NASA: 2 assertions."""
    parser = argparse.ArgumentParser(description="Sprint 24 Rescorer")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no output file")
    parser.add_argument("--verbose", action="store_true", help="Show per-domain breakdowns")
    args = parser.parse_args()

    assert _REAPER_FILE.exists(), f"Reaper file not found: {_REAPER_FILE}"
    eprint = lambda m: print(m, file=sys.stderr)

    # Load base data
    eprint("=" * 70)
    eprint("  SPRINT 24 RESCORE")
    eprint("=" * 70)
    sweet_spot = load_reaper_data(_REAPER_FILE)
    eprint(f"  Loaded {len(sweet_spot)} sweet_spot domains from reaper")

    # Load enrichment data
    backlinks_data = load_backlinks_data(_BACKLINKS_FILE)
    rdap_data = load_rdap_data(_RDAP_FILE)
    editorial_data = load_editorial_data(_EDITORIAL_FILE)

    data_sources_found = {
        "backlinks": len(backlinks_data) > 0,
        "rdap": len(rdap_data) > 0,
        "editorial": len(editorial_data) > 0,
    }
    eprint(f"  Backlinks data: {len(backlinks_data)} domains "
           f"({'found' if backlinks_data else 'NOT FOUND'})")
    eprint(f"  RDAP data:      {len(rdap_data)} domains "
           f"({'found' if rdap_data else 'NOT FOUND'})")
    eprint(f"  Editorial data: {len(editorial_data)} domains "
           f"({'found' if editorial_data else 'NOT FOUND'})")

    # Merge + rescore
    comparisons: list[dict[str, Any]] = []
    rescored: list[dict[str, Any]] = []
    for domain_rec in sweet_spot[:_MAX_DOMAINS]:
        domain = domain_rec["domain"]
        merged = dict(domain_rec)

        if domain in backlinks_data:
            merged = merge_backlinks(merged, backlinks_data[domain])
        if domain in rdap_data:
            merged = merge_rdap(merged, rdap_data[domain])
        if domain in editorial_data:
            merged = merge_editorial(merged, editorial_data[domain])

        new_rec = rescore_domain(merged)
        rescored.append(new_rec)

        comp = build_comparison(domain_rec, new_rec)
        comparisons.append(comp)

        if args.verbose and comp["delta"] != 0:
            old_bd = domain_rec.get("score_breakdown", {})
            new_bd = new_rec.get("score_breakdown", {})
            print_verbose_breakdown(domain, old_bd, new_bd)

    # Sort comparisons by delta (biggest improvements first)
    comparisons.sort(key=lambda c: -c["delta"])
    rescored.sort(key=lambda r: -r["reaper_score"])

    print_comparison_table(comparisons)

    if not args.dry_run:
        save_results(rescored, comparisons, data_sources_found, args.dry_run)
    else:
        eprint("\n  [DRY RUN] No output file written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

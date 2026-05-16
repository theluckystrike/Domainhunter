#!/usr/bin/env python3
"""Sprint 28 Kaggle Enrichment — proxy-score 53 CATCHABLE domains from RDAP probe.

Reads sprint27_kaggle_rdap_results.json, filters subdomains, applies 9-dimension
Reaper composite scoring using proxy estimates (no API calls), classifies tiers,
computes intrinsic domain name value, and outputs ranked results.

Cost: $0.00 (all proxy estimates from funding/sector data).

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable state.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_INPUT_PATH: Final[str] = os.path.join(_DATA_DIR, "sprint27_kaggle_rdap_results.json")
_OUTPUT_PATH: Final[str] = os.path.join(_DATA_DIR, "sprint28_kaggle_enriched.json")
_MAX_RESULTS: Final[int] = 200

# Niche fit scores (from startup_reaper.py)
_NICHE_SCORES: Final[dict[str, float]] = {
    "ai": 90, "llm": 90, "autonomous": 85, "ml": 85, "robotics": 80,
    "fintech": 80, "crypto": 70, "blockchain": 65,
    "healthtech": 75, "biotech": 70, "medtech": 70,
    "saas": 70, "devtools": 75, "developer tools": 75,
    "edtech": 60, "proptech": 60, "cleantech": 55, "climate": 55,
    "ecommerce": 50, "logistics": 50, "ev": 65, "electric vehicle": 65,
    "vertical farming": 50, "food": 45, "media": 40, "gaming": 55,
    "security": 70, "hardware": 50, "music": 35, "solar": 55,
    "wireless": 55, "networking": 60, "medical": 70, "medical devices": 70,
    "email": 50, "web hosting": 40,
}

# High-press sectors that tend to generate more editorial coverage
_HIGH_PRESS_SECTORS: Final[frozenset[str]] = frozenset({
    "ai", "fintech", "crypto", "blockchain", "autonomous", "healthtech",
    "biotech", "saas", "security", "cleantech", "ev",
})

# Sprint 21 weights (from startup_reaper.py _score_domain)
_WEIGHTS: Final[dict[str, float]] = {
    "funding": 0.20,
    "da_estimate": 0.20,
    "drop_certainty": 0.15,
    "editorial_estimate": 0.15,
    "age_estimate": 0.10,
    "niche_fit": 0.10,
    "traffic_estimate": 0.05,
    "trademark_default": 0.05,
}


# ── Subdomain filter ─────────────────────────────────────────────────


def is_subdomain(domain: str) -> bool:
    """Return True if domain has more than one dot (is a subdomain)."""
    assert isinstance(domain, str), "domain must be a string"
    assert len(domain) > 0, "domain must not be empty"
    return domain.count(".") > 1


# ── Scoring functions (proxy estimates) ──────────────────────────────


def funding_score(funding_usd: int) -> float:
    """Score company funding level. $0->0, $5M->40, $50M->70, $200M+->95."""
    assert isinstance(funding_usd, int) and funding_usd >= 0
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


def da_estimate_from_funding(funding_usd: int, sector: str) -> float:
    """Estimate Domain Authority from funding level (0.3 correlation proxy).

    Higher-funded startups had more marketing budget and press, correlating
    with higher DA. AI/fintech sectors get a sector bonus due to higher
    media coverage density.
    """
    assert isinstance(funding_usd, int) and funding_usd >= 0
    assert isinstance(sector, str)
    # Base DA estimate from funding
    if funding_usd == 0:
        return 0.0
    if funding_usd < 5_000_000:
        base = 15.0
    elif funding_usd < 10_000_000:
        base = 25.0
    elif funding_usd < 25_000_000:
        base = 35.0
    elif funding_usd < 50_000_000:
        base = 45.0
    elif funding_usd < 100_000_000:
        base = 55.0
    elif funding_usd < 200_000_000:
        base = 65.0
    else:
        base = 75.0
    # Sector bonus: high-press sectors correlate with more backlinks
    sector_lower = sector.lower().strip()
    if any(s in sector_lower for s in ("ai", "fintech", "crypto", "saas")):
        base = min(95.0, base + 10.0)
    elif any(s in sector_lower for s in ("biotech", "healthtech", "security")):
        base = min(95.0, base + 5.0)
    return base


def drop_certainty_score(epp_codes: list, rdap_status: str) -> float:
    """Score how certain the domain will drop. RDAP 404 = high certainty."""
    assert isinstance(rdap_status, str)
    # CATCHABLE with no EPP codes means RDAP returned 404 (domain not found)
    if rdap_status == "CATCHABLE" and not epp_codes:
        return 95.0
    # CATCHABLE with redemptionPeriod
    epp_lower = [e.lower() for e in epp_codes] if epp_codes else []
    if "redemption period" in epp_lower or "redemptionperiod" in epp_lower:
        return 90.0
    if "pendingdelete" in epp_lower or "pending delete" in epp_lower:
        return 100.0
    if "clienthold" in epp_lower or "client hold" in epp_lower:
        return 75.0
    # CATCHABLE with some EPP codes
    if rdap_status == "CATCHABLE":
        return 80.0
    return 50.0


def editorial_estimate_from_funding(funding_usd: int, sector: str) -> float:
    """Estimate editorial link score from funding and sector.

    Logic: higher funding => more press coverage. High-press sectors
    (AI, fintech, crypto) generate 2-3x more TechCrunch/Forbes articles
    than niche hardware/cleantech.
    """
    assert isinstance(funding_usd, int) and funding_usd >= 0
    assert isinstance(sector, str)
    sector_lower = sector.lower().strip()
    is_high_press = any(s in sector_lower for s in _HIGH_PRESS_SECTORS)
    # Base editorial estimate from funding
    if funding_usd >= 100_000_000:
        base = 70.0 if is_high_press else 55.0
    elif funding_usd >= 50_000_000:
        base = 55.0 if is_high_press else 40.0
    elif funding_usd >= 20_000_000:
        base = 45.0 if is_high_press else 30.0
    elif funding_usd >= 10_000_000:
        base = 35.0 if is_high_press else 20.0
    elif funding_usd >= 5_000_000:
        base = 25.0 if is_high_press else 15.0
    else:
        base = 10.0
    return base


def age_estimate_from_sector(sector: str) -> float:
    """Estimate domain age score. Kaggle startups are all dead/failed,
    so most domains are 5-15 years old. Default to 60 (moderate-old)."""
    assert isinstance(sector, str)
    # Most Kaggle dead startups are from 2005-2018 era => 8-20 years old
    return 60.0


def niche_score(sector: str) -> float:
    """Score sector/niche fit. AI/fintech = premium."""
    assert isinstance(sector, str)
    sector_lower = sector.lower().strip()
    for key, score in _NICHE_SCORES.items():
        if key in sector_lower:
            return score
    return 30.0


def traffic_estimate_from_funding(funding_usd: int) -> float:
    """Estimate traffic value from funding level.

    Dead startups with high funding had more users/traffic, but domains
    are now expired, so traffic is historical. Estimate conservatively.
    """
    assert isinstance(funding_usd, int) and funding_usd >= 0
    if funding_usd >= 100_000_000:
        return 45.0
    if funding_usd >= 50_000_000:
        return 35.0
    if funding_usd >= 20_000_000:
        return 25.0
    if funding_usd >= 10_000_000:
        return 20.0
    if funding_usd >= 5_000_000:
        return 15.0
    return 5.0


def trademark_default() -> float:
    """Default trademark safety for Kaggle domains (all dead startups, most 5+ years).

    Kaggle dataset domains are from defunct companies, most shut down years ago.
    Default to 70 (moderate safety — should verify individually).
    """
    return 70.0


# ── Domain name intrinsic value scoring ──────────────────────────────


def domain_name_value(domain: str) -> float:
    """Score intrinsic domain name value per task spec.

    Scoring rules:
    - Dictionary words: +40 points
    - 4-letter .com: +50 points
    - 5-letter .com: +30 points
    - Keyword-rich: +20 points
    - Hyphenated: -20 points
    - Long (15+ chars): -10 points
    - Premium TLD (.com): +10 points
    - Other TLD (.org, .io): +0 points
    """
    assert isinstance(domain, str) and "." in domain
    parts = domain.rsplit(".", 1)
    assert len(parts) == 2, f"invalid domain format: {domain}"
    name = parts[0].lower()
    tld = parts[1].lower()
    score = 0.0

    # TLD bonus
    if tld == "com":
        score += 10.0

    # Length-based scoring for .com
    name_len = len(name)
    if tld == "com":
        if name_len == 4 and "-" not in name:
            score += 50.0
        elif name_len == 5 and "-" not in name:
            score += 30.0

    # Hyphenation penalty
    if "-" in name:
        score -= 20.0

    # Long name penalty
    if name_len >= 15:
        score -= 10.0

    # Dictionary word check (common English words that make premium domains)
    clean_name = name.replace("-", "")
    if _is_dictionary_word(clean_name):
        score += 40.0

    # Keyword-rich check (contains common valuable keywords)
    if _is_keyword_rich(clean_name):
        score += 20.0

    return max(0.0, min(100.0, score))


def _is_dictionary_word(name: str) -> bool:
    """Check if the domain name is a single common English dictionary word."""
    assert isinstance(name, str)
    # Common single English words that would make premium domain names
    _COMMON_WORDS = frozenset({
        "solar", "quest", "oracle", "gate", "link", "mail", "core",
        "wave", "pulse", "grid", "bolt", "flux", "hive", "nest", "vault",
        "spark", "bloom", "swift", "alpha", "beta", "apex", "nova", "edge",
        "zero", "pure", "true", "brave", "prime", "clear", "smart", "bright",
        "cloud", "flame", "storm", "light", "power", "trust", "voice", "dream",
    })
    return name in _COMMON_WORDS


def _is_keyword_rich(name: str) -> bool:
    """Check if domain name contains valuable SEO keywords."""
    assert isinstance(name, str)
    _KEYWORDS = frozenset({
        "tech", "bio", "med", "health", "pharma", "soft", "data", "cloud",
        "cyber", "secure", "solar", "green", "smart", "digital", "crypto",
        "ai", "auto", "pay", "fin", "sys", "net", "app", "web", "dev",
        "code", "game", "lab", "pro", "hub", "link", "virtual", "power",
        "energy", "clean", "nano", "micro", "photo", "optic",
    })
    return any(kw in name for kw in _KEYWORDS)


# ── Composite scoring ────────────────────────────────────────────────


def compute_reaper_score(domain_entry: dict) -> dict:
    """Compute 9-dimension Reaper composite score for a single domain.

    Returns enriched dict with scores, tier, and recommendation.
    """
    assert isinstance(domain_entry, dict)
    assert "domain" in domain_entry
    domain = domain_entry["domain"]
    company = domain_entry.get("company_name", "")
    funding = domain_entry.get("funding_usd", 0)
    sector = domain_entry.get("sector", "other")
    epp_codes = domain_entry.get("epp_codes", [])
    rdap_status = domain_entry.get("rdap_status", "CATCHABLE")

    # Compute 9 dimension scores
    dims = {
        "funding": funding_score(funding),
        "da_estimate": da_estimate_from_funding(funding, sector),
        "drop_certainty": drop_certainty_score(epp_codes, rdap_status),
        "editorial_estimate": editorial_estimate_from_funding(funding, sector),
        "age_estimate": age_estimate_from_sector(sector),
        "niche_fit": niche_score(sector),
        "traffic_estimate": traffic_estimate_from_funding(funding),
        "trademark_default": trademark_default(),
    }

    # Weighted composite
    raw_score = sum(dims[k] * _WEIGHTS[k] for k in _WEIGHTS)
    reaper = round(min(100.0, max(0.0, raw_score)), 1)

    # Name value (separate scoring axis)
    name_val = round(domain_name_value(domain), 1)

    # Tier classification
    tier = _assign_tier(reaper)

    # Recommendation
    recommendation = _recommend(reaper, name_val)

    # Premium flag
    is_premium = name_val >= 70.0

    return {
        "domain": domain,
        "company": company,
        "funding_usd": funding,
        "sector": sector,
        "reaper_score": reaper,
        "name_value": name_val,
        "tier": tier.upper(),
        "is_premium": is_premium,
        "dimensions": dims,
        "recommendation": recommendation,
        "epp_codes": epp_codes,
        "expiry_date": domain_entry.get("expiry_date", ""),
        "registrar": domain_entry.get("registrar", ""),
    }


def _assign_tier(score: float) -> str:
    """Assign tier from reaper score."""
    assert 0.0 <= score <= 100.0
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _recommend(reaper: float, name_val: float) -> str:
    """Generate recommendation based on combined reaper + name value."""
    assert 0.0 <= reaper <= 100.0
    assert 0.0 <= name_val <= 100.0
    if reaper >= 75:
        return "BACKORDER"
    if reaper >= 55:
        return "BACKORDER"
    if reaper >= 35:
        if name_val >= 70:
            return "BACKORDER"  # Premium name overrides medium tier
        return "WATCH"
    return "SKIP"


# ── Main pipeline ────────────────────────────────────────────────────


def load_catchable(input_path: str) -> list[dict]:
    """Load CATCHABLE domains from RDAP results JSON."""
    assert os.path.isfile(input_path), f"input file not found: {input_path}"
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), "expected dict at top level"
    catchable = data.get("catchable", [])
    assert isinstance(catchable, list), "catchable must be a list"
    return catchable


def filter_subdomains(domains: list[dict]) -> tuple[list[dict], list[str]]:
    """Remove subdomains (domains with >1 dot). Return (valid, removed)."""
    assert isinstance(domains, list)
    valid = []
    removed = []
    for d in domains[:_MAX_RESULTS]:
        assert isinstance(d, dict)
        domain = d.get("domain", "")
        if is_subdomain(domain):
            removed.append(domain)
        else:
            valid.append(d)
    return valid, removed


def run_enrichment() -> dict:
    """Execute the full enrichment pipeline and return output dict."""
    # Step 1: Load data
    catchable = load_catchable(_INPUT_PATH)
    total_input = len(catchable)
    print(f"Loaded {total_input} CATCHABLE domains from RDAP probe")

    # Step 2: Filter subdomains
    valid, removed = filter_subdomains(catchable)
    print(f"After subdomain filter: {len(valid)} valid, {len(removed)} removed")
    if removed:
        print(f"  Removed subdomains: {', '.join(removed)}")

    # Step 3: Score each valid domain
    scored = []
    for entry in valid:
        result = compute_reaper_score(entry)
        scored.append(result)

    # Step 4: Sort by reaper_score descending
    scored.sort(key=lambda x: (-x["reaper_score"], x["domain"]))

    # Step 5: Compute summary
    summary = {
        "critical": sum(1 for s in scored if s["tier"] == "CRITICAL"),
        "high": sum(1 for s in scored if s["tier"] == "HIGH"),
        "medium": sum(1 for s in scored if s["tier"] == "MEDIUM"),
        "low": sum(1 for s in scored if s["tier"] == "LOW"),
        "premium_names": sum(1 for s in scored if s["is_premium"]),
        "backorder_recommended": sum(
            1 for s in scored if s["recommendation"] == "BACKORDER"
        ),
        "watch_recommended": sum(
            1 for s in scored if s["recommendation"] == "WATCH"
        ),
        "skip_recommended": sum(
            1 for s in scored if s["recommendation"] == "SKIP"
        ),
    }

    output = {
        "enrichment_date": "2026-05-16",
        "method": "proxy_scoring (no DataForSEO API calls)",
        "input_domains": total_input,
        "after_subdomain_filter": len(valid),
        "removed_subdomains": removed,
        "scored": scored,
        "summary": summary,
    }

    return output


def print_results(output: dict) -> None:
    """Pretty-print enrichment results to stdout."""
    assert isinstance(output, dict)
    scored = output.get("scored", [])
    summary = output.get("summary", {})

    print("\n" + "=" * 80)
    print("SPRINT 28 KAGGLE ENRICHMENT RESULTS")
    print("=" * 80)
    print(f"Input: {output['input_domains']} | After filter: {output['after_subdomain_filter']}")
    print(f"Method: {output['method']}")
    print("-" * 80)
    print(f"{'#':>3}  {'DOMAIN':<32} {'SCORE':>5}  {'TIER':<8} {'NAME':>4}  {'REC':<10}")
    print("-" * 80)

    for i, s in enumerate(scored, 1):
        premium_flag = " [P]" if s["is_premium"] else ""
        print(
            f"{i:>3}  {s['domain']:<32} {s['reaper_score']:>5.1f}  {s['tier']:<8} "
            f"{s['name_value']:>4.0f}  {s['recommendation']:<10}{premium_flag}"
        )

    print("-" * 80)
    print(
        f"Summary: CRITICAL={summary['critical']} HIGH={summary['high']} "
        f"MEDIUM={summary['medium']} LOW={summary['low']}"
    )
    print(
        f"         Premium names={summary['premium_names']} "
        f"Backorder={summary['backorder_recommended']} "
        f"Watch={summary['watch_recommended']} "
        f"Skip={summary['skip_recommended']}"
    )
    print("=" * 80)


def main() -> None:
    """Entry point."""
    output = run_enrichment()

    # Write output
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to: {_OUTPUT_PATH}")

    # Print results
    print_results(output)


if __name__ == "__main__":
    main()

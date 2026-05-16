#!/usr/bin/env python3
"""Startup Reaper — find 100x domains by starting from dead startups.

The ghostautonomy.com playbook: dead $220M startup → DA 52 → TM abandoned →
UDRP-proof → 4 TechCrunch backlinks → $50K+ domain. The dropcatch scanner
would score it 13/38 and filter it out. This script inverts the approach:
start from dead startups, work backward to their domains.

Pipeline: HARVEST → RESOLVE → PROBE → ENRICH → SCORE → OUTPUT → BACKORDER
Sprint 21: 9-dimension scoring, competition penalty, auto-backorder via Dynadot.
Cost per scan: ~$0.15 (DeepSeek + DataForSEO bulk)

Usage:
  python scripts/startup_reaper.py                       # Full scan
  python scripts/startup_reaper.py --dry-run             # Preview, no API calls
  python scripts/startup_reaper.py --sources existing    # Local data only ($0)
  python scripts/startup_reaper.py --sources deepseek,yc # DeepSeek + YC dead list
  python scripts/startup_reaper.py --sources kaggle      # Kaggle CSV dataset only ($0)
  python scripts/startup_reaper.py --min-score 50        # Display threshold
  python scripts/startup_reaper.py --sector ai,fintech   # Filter sectors
  python scripts/startup_reaper.py --no-monitor          # Skip auto-add to monitor

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _ROOT)

from models.reaped_startup import (  # noqa: E402
    ALLOWED_SECTORS, DeadStartup, ProbedStartup, ReapedDomain, ResolvedStartup,
    reaped_to_dict,
)

_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_MONITORED_PATH: Final[str] = os.path.join(_ROOT, "scripts", "monitored_domains.json")
_MAX_HARVEST: Final[int] = 1500
_MAX_RESULTS: Final[int] = 200
_MAX_DISPLAY: Final[int] = 80
_DEFAULT_MIN_SCORE: Final[float] = 25.0
_RDAP_TIMEOUT: Final[int] = 12
_YC_DEAD_URL: Final[str] = "https://yc-oss.github.io/api/companies/all.json"

# Drop signal EPP statuses
_DROP_SIGNALS: Final[frozenset[str]] = frozenset({
    "clientRenewProhibited", "pendingDelete", "redemptionPeriod",
    "autoRenewPeriod", "clientHold", "available", "not_found",
})

# Premium sectors (niche fit score)
_NICHE_SCORES: Final[dict[str, float]] = {
    "ai": 90, "llm": 90, "autonomous": 85, "ml": 85, "robotics": 80,
    "fintech": 80, "crypto": 70, "blockchain": 65,
    "healthtech": 75, "biotech": 70, "medtech": 70,
    "saas": 70, "devtools": 75, "developer tools": 75,
    "edtech": 60, "proptech": 60, "cleantech": 55, "climate": 55,
    "ecommerce": 50, "logistics": 50, "ev": 65, "electric vehicle": 65,
    "vertical farming": 50, "food": 45, "media": 40,
}

# Tier-1 press outlets (editorial link bonus)
_TIER1_PRESS: Final[frozenset[str]] = frozenset({
    "techcrunch", "bloomberg", "forbes", "wsj", "nytimes",
    "cnbc", "reuters", "wired", "the verge", "bbc",
})

# Sprint 21: Editorial domains for backlink detection
_EDITORIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "techcrunch.com", "bloomberg.com", "forbes.com", "wsj.com", "nytimes.com",
    "cnbc.com", "reuters.com", "wired.com", "theverge.com", "bbc.com",
    "venturebeat.com", "crunchbase.com", "businessinsider.com", "arstechnica.com",
    "thenextweb.com", "zdnet.com", "engadget.com", "mashable.com",
})

# Sprint 21: Backorder constants
_MAX_BACKORDERS: Final[int] = 20
_BACKORDER_BUDGET_USD: Final[float] = 220.0
_BACKORDER_PRICE_USD: Final[float] = 10.99


# ── HARVEST: Multi-source startup discovery ──────────────────────────


def _parse_funding(raw: str) -> int:
    """Parse funding strings like '$220M', '$1.5B', '$30M+' to int dollars."""
    assert isinstance(raw, str), "raw must be a string"
    if not raw or raw.lower() in ("undisclosed", "unknown", "n/a", "0"):
        return 0
    clean = raw.replace(",", "").replace("+", "").replace("~", "").strip()
    m = re.search(r"\$?([\d.]+)\s*([BMKbmk])", clean)
    if not m:
        m2 = re.search(r"\$?([\d]+)", clean)
        return int(m2.group(1)) if m2 else 0
    val, unit = float(m.group(1)), m.group(2).upper()
    multiplier = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}
    return int(val * multiplier.get(unit, 1))


def _normalize_company(name: str) -> str:
    """Normalize company name for dedup: lowercase, strip suffixes."""
    assert isinstance(name, str) and len(name) > 0, "name required"
    clean = name.lower().strip()
    for suffix in (" inc", " inc.", " corp", " corp.", " llc", " ltd", " ltd."):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)].strip()
    return clean


def _parse_year(raw: str | None) -> int | None:
    """Parse a year from various date formats. Returns int year or None.

    Handles: '2024-04' -> 2024, '2026-05-06' -> 2026, '2023' -> 2023,
    'Winter 2021' -> 2021, '' -> None, None -> None.
    """
    assert raw is None or isinstance(raw, str), f"raw must be str or None, got {type(raw)}"
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    m = re.search(r"(\d{4})", raw)
    if m:
        yr = int(m.group(1))
        assert 1900 <= yr <= 2100, f"year out of range: {yr}"
        return yr
    return None


def _normalize_sector(raw: str) -> str:
    """Map arbitrary sector strings to ALLOWED_SECTORS values."""
    assert isinstance(raw, str), f"raw must be str, got {type(raw)}"
    sector = raw.strip().lower()[:30]
    if sector in ALLOWED_SECTORS:
        return sector
    _SECTOR_ALIASES: dict[str, str] = {
        "vertical farming": "cleantech", "food": "ecommerce", "media": "other",
        "saas": "ai", "devtools": "ai", "developer tools": "ai",
        "proptech": "ecommerce", "robotics": "ai", "ev": "cleantech",
        "electric vehicle": "cleantech", "insurance": "fintech",
        "agriculture": "cleantech", "manufacturing": "logistics",
        "real estate": "ecommerce", "social": "other", "gaming": "other",
        "marketplace": "ecommerce", "consumer": "other", "travel": "other",
        "security": "ai", "enterprise": "ai", "b2b": "other",
        "hardware": "other", "automotive": "logistics",
    }
    for alias, target in _SECTOR_ALIASES.items():
        if alias in sector:
            return target
    return "other"


def _load_sprint7(data_dir: str) -> list[DeadStartup]:
    """Load sprint7_dead_startups.json (42 startups)."""
    path = os.path.join(data_dir, "sprint7_dead_startups.json")
    if not os.path.isfile(path):
        return []
    raw = json.load(open(path, encoding="utf-8"))
    assert isinstance(raw, dict), "sprint7 must be a dict"
    results: list[DeadStartup] = []
    for s in raw.get("startups", [])[:_MAX_HARVEST]:
        results.append(DeadStartup(
            name=s.get("company", ""),
            domain=s.get("domain", ""),
            funding_usd=_parse_funding(s.get("funding_raised", "0")),
            death_year=_parse_year(s.get("shutdown_date", "")),
            sector=_normalize_sector(s.get("reason", "other").split(",")[0]),
            source="existing_s7",
            description=s.get("notes", ""),
        ))
    return results


def _load_sprint14(data_dir: str) -> list[DeadStartup]:
    """Load sprint14_startup_domains.json (205 startups)."""
    path = os.path.join(data_dir, "sprint14_startup_domains.json")
    if not os.path.isfile(path):
        return []
    raw = json.load(open(path, encoding="utf-8"))
    assert isinstance(raw, dict), "sprint14 must be a dict"
    results: list[DeadStartup] = []
    for s in raw.get("domains", [])[:_MAX_HARVEST]:
        results.append(DeadStartup(
            name=s.get("company", ""),
            domain=s.get("domain", ""),
            funding_usd=_parse_funding(s.get("funding", "0")),
            death_year=_parse_year(str(s.get("shutdown_year", ""))),
            sector=_normalize_sector(s.get("sector", "other")),
            source="existing_s14",
            description="",
        ))
    return results


def _load_sprint16(data_dir: str) -> list[DeadStartup]:
    """Load sprint16_fresh_startups.json (~21 startups)."""
    path = os.path.join(data_dir, "sprint16_fresh_startups.json")
    if not os.path.isfile(path):
        return []
    raw = json.load(open(path, encoding="utf-8"))
    assert isinstance(raw, dict), "sprint16 must be a dict"
    results: list[DeadStartup] = []
    for s in raw.get("new_shutdowns", [])[:_MAX_HARVEST]:
        results.append(DeadStartup(
            name=s.get("company", ""),
            domain=s.get("domain", ""),
            funding_usd=_parse_funding(s.get("funding", "0")),
            death_year=_parse_year(s.get("shutdown_date", "")),
            sector=_normalize_sector(s.get("reason", s.get("notes", "other"))),
            source="existing_s16",
            description=s.get("notes", ""),
        ))
    return results


def _load_existing(data_dir: str) -> list[DeadStartup]:
    """Load all existing data files."""
    assert os.path.isdir(data_dir), f"data dir not found: {data_dir}"
    all_startups: list[DeadStartup] = []
    all_startups.extend(_load_sprint7(data_dir))
    all_startups.extend(_load_sprint14(data_dir))
    all_startups.extend(_load_sprint16(data_dir))
    return all_startups[:_MAX_HARVEST]


def _harvest_from_deepseek(settings_dict: dict[str, str], dry_run: bool) -> list[DeadStartup]:
    """Ask DeepSeek for 50 dead startups with funding >$5M."""
    assert isinstance(settings_dict, dict), "settings must be dict"
    api_key = settings_dict.get("deepseek_api_key", "")
    if not api_key:
        print("  [HARVEST] DeepSeek: no API key, skipping", file=sys.stderr)
        return []
    if dry_run:
        print("  [HARVEST] DeepSeek: DRY RUN, skipping API call", file=sys.stderr)
        return []

    prompt = (
        "List 50 technology startups that are CONFIRMED SHUT DOWN, bankrupt, or ceased "
        "ALL operations between January 2023 and May 2026.\n\n"
        "CRITICAL RULES:\n"
        "- ONLY include companies that have ACTUALLY shut down. NO active companies.\n"
        "- DO NOT include: Stripe, Airbnb, Uber, OpenAI, Databricks, or any other company "
        "that is still operating as of May 2026.\n"
        "- Each company must have had public reporting of its shutdown (TechCrunch, Bloomberg, etc.)\n"
        "- If you are not 95%+ confident a company has shut down, DO NOT include it.\n"
        "- Focus on startups that raised $5M+ in venture funding before failing.\n\n"
        "For each, provide:\n"
        "- company_name: string (exact legal/common name)\n"
        "- domain: their primary website domain (e.g. example.com)\n"
        "- funding_usd: total funding raised as string (e.g. '$220M')\n"
        "- shutdown_date: YYYY-MM format (when they shut down or filed bankruptcy)\n"
        "- sector: one of [ai, fintech, healthtech, crypto, saas, devtools, edtech, "
        "proptech, cleantech, ecommerce, logistics, ev, media, biotech, robotics, other]\n"
        "- press: list of news outlets that covered the shutdown\n\n"
        "Good examples: Olive AI ($902M, shut down 2023), IronNet ($100M+, bankrupt 2023), "
        "Convoy ($3.8B, shut down 2023), Veev ($647M, bankrupt 2024), Bird ($275M, bankrupt 2023).\n\n"
        "Include companies from diverse sectors. "
        "Return ONLY a JSON array, no markdown fences or explanation."
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    import httpx
    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers, json=payload,
            )
        if resp.status_code != 200:
            print(f"  [HARVEST] DeepSeek error: {resp.status_code}", file=sys.stderr)
            return []
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        content = re.sub(r"^```json\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content.strip())
        items = json.loads(content)
        assert isinstance(items, list), "DeepSeek must return a list"
    except Exception as exc:
        print(f"  [HARVEST] DeepSeek failed: {exc}", file=sys.stderr)
        return []

    results: list[DeadStartup] = []
    for s in items[:60]:
        if not isinstance(s, dict):
            continue
        results.append(DeadStartup(
            name=s.get("company_name", ""),
            domain=s.get("domain", ""),
            funding_usd=_parse_funding(str(s.get("funding_usd", "0"))),
            death_year=_parse_year(s.get("shutdown_date", "")),
            sector=_normalize_sector(s.get("sector", "other")),
            source="deepseek",
            description=s.get("description", ""),
        ))
    print(f"  [HARVEST] DeepSeek: {len(results)} startups", file=sys.stderr)
    return results


def _harvest_from_yc(dry_run: bool) -> list[DeadStartup]:
    """Fetch YC dead/inactive startups from all.json (filter status=Inactive)."""
    if dry_run:
        print("  [HARVEST] YC Dead: DRY RUN, skipping", file=sys.stderr)
        return []
    try:
        req = urllib.request.Request(_YC_DEAD_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            all_companies = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [HARVEST] YC Dead fetch failed: {exc}", file=sys.stderr)
        return []

    assert isinstance(all_companies, list), "YC API must return a list"
    # Filter to inactive/dead companies only
    inactive = [c for c in all_companies if isinstance(c, dict)
                and str(c.get("status", "")).lower() == "inactive"]
    print(f"  [HARVEST] YC: {len(inactive)} inactive out of {len(all_companies)} total",
          file=sys.stderr)

    results: list[DeadStartup] = []
    for s in inactive[:1200]:  # bounded loop
        name = s.get("name", "")
        if not name:
            continue
        url = s.get("website", "") or s.get("url", "")
        domain = ""
        if url:
            domain = re.sub(r"^https?://", "", url).rstrip("/").split("/")[0].lower()
            # Skip bare IP addresses and localhost
            if domain.replace(".", "").isdigit() or "localhost" in domain:
                domain = ""
        batch = s.get("batch", "")
        # Map YC batch to approximate shutdown year (e.g. "W21" → "2021")
        year = _batch_to_year(str(batch)) if batch else None
        industry = s.get("tags", [])
        sector = _yc_tags_to_sector(industry) if industry else "other"
        results.append(DeadStartup(
            name=name,
            domain=domain,
            funding_usd=0,  # YC list doesn't include funding
            death_year=year,
            sector=sector,
            source="yc_dead",
            description=str(s.get("one_liner", "")),
        ))
    print(f"  [HARVEST] YC Dead: {len(results)} startups parsed", file=sys.stderr)
    return results


def _batch_to_year(batch: str) -> int | None:
    """Convert YC batch code to year int. 'W21' -> 2021, 'Winter 2021' -> 2021."""
    assert isinstance(batch, str)
    # Match "Winter 2021", "Summer 2019" etc.
    m = re.search(r"(\d{4})", batch)
    if m:
        return int(m.group(1))
    # Fallback: match "W21", "S23" short format
    m = re.search(r"[WSws](\d{2})", batch)
    if m:
        yr = int(m.group(1))
        return 2000 + yr if yr < 50 else 1900 + yr
    return None


def _yc_tags_to_sector(tags: Any) -> str:
    """Map YC company tags to a normalized sector."""
    if not isinstance(tags, list) or not tags:
        return "other"
    joined = " ".join(str(t).lower() for t in tags[:10])
    for key in ("artificial intelligence", "machine learning", "ai", "llm"):
        if key in joined:
            return "ai"
    sector_map = {
        "fintech": "fintech", "finance": "fintech", "crypto": "crypto",
        "blockchain": "crypto", "health": "healthtech", "biotech": "biotech",
        "developer tools": "ai", "saas": "ai", "education": "edtech",
        "real estate": "ecommerce", "climate": "cleantech", "energy": "cleantech",
        "e-commerce": "ecommerce", "logistics": "logistics", "robotics": "ai",
    }
    for keyword, sector in sector_map.items():
        if keyword in joined:
            return sector
    return "other"


def _harvest_from_kaggle(data_dir: str) -> list[DeadStartup]:
    """Load dead startups from Kaggle CSV dataset at data/kaggle_startups.csv.

    Expected columns: company_name, domain, funding_usd, status, sector,
    shutdown_date, notes.  Filters for dead/closed/shutdown status and
    funding >= $1M. Returns up to _MAX_HARVEST entries.
    NASA P10: <60 lines, 2 assertions, bounded loop.
    """
    assert isinstance(data_dir, str) and len(data_dir) > 0, "data_dir required"
    csv_path = os.path.join(data_dir, "kaggle_startups.csv")
    if not os.path.isfile(csv_path):
        print("  [HARVEST] Kaggle: CSV not found, skipping", file=sys.stderr)
        return []

    _DEAD_STATUSES: frozenset[str] = frozenset({
        "dead", "closed", "shutdown", "acquired-closed", "bankrupt",
        "defunct", "failed", "inactive", "wound down",
    })
    _MIN_FUNDING: int = 1_000_000  # $1M floor for Kaggle (larger dataset)

    results: list[DeadStartup] = []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None, "CSV must have a header row"
        for idx, row in enumerate(reader):
            if idx >= _MAX_HARVEST:
                break
            status = row.get("status", "").strip().lower()
            if status not in _DEAD_STATUSES:
                continue
            funding = _parse_funding(row.get("funding_usd", "0"))
            if funding < _MIN_FUNDING:
                continue
            name = row.get("company_name", "").strip()
            if not name:
                continue
            domain = row.get("domain", "").strip().lower()
            # Sanitize domain: strip protocol and trailing slashes
            domain = re.sub(r"^https?://", "", domain).rstrip("/").split("/")[0]
            if domain.replace(".", "").isdigit() or "localhost" in domain:
                domain = ""
            sector = row.get("sector", "other").strip().lower()[:30]
            results.append(DeadStartup(
                name=name,
                domain=domain,
                funding_usd=funding,
                death_year=_parse_year(row.get("shutdown_date", "").strip()),
                sector=_normalize_sector(sector) if sector else "other",
                source="kaggle",
                description=row.get("notes", "").strip()[:200],
            ))
    print(f"  [HARVEST] Kaggle: {len(results)} dead startups (>=$1M funding)",
          file=sys.stderr)
    return results


def _deduplicate(startups: list[DeadStartup]) -> list[DeadStartup]:
    """Deduplicate by normalized company name + domain, prefer entries with more metadata."""
    assert isinstance(startups, list), "startups must be a list"
    seen_name: dict[str, DeadStartup] = {}
    seen_domain: set[str] = set()
    for s in startups:
        key = _normalize_company(s.name) if s.name else s.domain
        if not key:
            continue
        # Also dedup by domain
        if s.domain and s.domain in seen_domain:
            continue
        existing = seen_name.get(key)
        if existing is None:
            seen_name[key] = s
            if s.domain:
                seen_domain.add(s.domain)
        elif s.funding_usd > existing.funding_usd or len(s.description) > len(existing.description):
            seen_name[key] = s
            if s.domain:
                seen_domain.add(s.domain)
    return list(seen_name.values())[:_MAX_HARVEST]


# ── RESOLVE: Map startup name → domain ───────────────────────────────


def _resolve_domains(
    startups: list[DeadStartup], settings_dict: dict[str, str], dry_run: bool,
) -> list[ResolvedStartup]:
    """Resolve startups with missing domains via DeepSeek."""
    assert isinstance(startups, list), "startups must be list"
    resolved: list[ResolvedStartup] = []
    needs_resolve: list[DeadStartup] = []

    for s in startups:
        if s.domain and "." in s.domain:
            tld = "." + s.domain.rsplit(".", 1)[-1]
            resolved.append(ResolvedStartup(
                name=s.name, domain=s.domain,
                funding_usd=s.funding_usd, death_year=s.death_year,
                sector=s.sector, source=s.source,
                description=s.description, resolution_method="field",
            ))
        elif s.name:
            needs_resolve.append(s)

    if needs_resolve and not dry_run:
        mapping = _resolve_via_deepseek(needs_resolve, settings_dict)
        for s in needs_resolve:
            domain = mapping.get(_normalize_company(s.name), "")
            if domain and "." in domain:
                tld = "." + domain.rsplit(".", 1)[-1]
                resolved.append(ResolvedStartup(
                    name=s.name, domain=domain,
                    funding_usd=s.funding_usd, death_year=s.death_year,
                    sector=s.sector, source=s.source,
                    description=s.description, resolution_method="deepseek",
                ))

    print(f"  [RESOLVE] {len(resolved)} domains resolved ({len(needs_resolve)} via DeepSeek)",
          file=sys.stderr)
    return resolved


def _resolve_via_deepseek(
    startups: list[DeadStartup], settings_dict: dict[str, str],
) -> dict[str, str]:
    """Batch-resolve company names to domains via DeepSeek."""
    assert isinstance(startups, list) and len(startups) > 0
    api_key = settings_dict.get("deepseek_api_key", "")
    if not api_key:
        return {}

    names = [s.name for s in startups[:50]]
    prompt = (
        "For each startup company name below, provide the primary website domain "
        "(e.g. 'example.com'). If you don't know, use 'unknown'.\n\n"
        + "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
        + "\n\nReturn ONLY a JSON array of objects: "
        '[{"company": "X", "domain": "x.com"}, ...]. No markdown fences.'
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048, "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    import httpx
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers, json=payload,
            )
        content = resp.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content.strip())
        items = json.loads(content)
        return {
            _normalize_company(i["company"]): i["domain"].lower().strip()
            for i in items if isinstance(i, dict) and i.get("domain", "unknown") != "unknown"
        }
    except Exception as exc:
        print(f"  [RESOLVE] DeepSeek resolve failed: {exc}", file=sys.stderr)
        return {}


# ── PROBE: RDAP status check ─────────────────────────────────────────


def _rdap_lookup(domain: str) -> dict[str, Any]:
    """Single RDAP lookup. Returns dict with status, registrar, dates."""
    assert isinstance(domain, str) and "." in domain
    url = f"https://rdap.org/domain/{domain}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/rdap+json"})
        with urllib.request.urlopen(req, timeout=_RDAP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"epp_status": "error", "registrar": "", "expiry": "", "creation": ""}

    statuses = [str(s).lower() for s in data.get("status", [])]
    epp = _classify_epp(statuses)
    registrar = ""
    for ent in data.get("entities", [])[:10]:
        if "registrar" in ent.get("roles", []):
            vc = ent.get("vcardArray", [None, []])[1]
            for f in (vc or [])[:20]:
                if isinstance(f, list) and len(f) >= 4 and f[0] == "fn":
                    registrar = str(f[3])
                    break
    expiry, creation = "", ""
    for ev in data.get("events", [])[:20]:
        if ev.get("eventAction") == "expiration":
            expiry = str(ev.get("eventDate", ""))[:10]
        if ev.get("eventAction") == "registration":
            creation = str(ev.get("eventDate", ""))[:10]
    return {"epp_status": epp, "registrar": registrar, "expiry": expiry, "creation": creation}


def _classify_epp(statuses: list[str]) -> str:
    """Classify EPP status from RDAP status list."""
    assert isinstance(statuses, list), "statuses must be list"
    joined = " ".join(statuses)
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
    return statuses[0] if statuses else "unknown"


def _probe_rdap(
    startups: list[ResolvedStartup], dry_run: bool,
) -> list[ProbedStartup]:
    """Check RDAP status for each domain. Keep those with drop signals."""
    assert isinstance(startups, list), "startups must be list"
    results: list[ProbedStartup] = []
    for idx, s in enumerate(startups):
        if idx >= _MAX_HARVEST:
            break
        if dry_run:
            results.append(ProbedStartup(
                name=s.name, domain=s.domain,
                funding_usd=s.funding_usd, death_year=s.death_year,
                sector=s.sector, source=s.source,
                description=s.description, resolution_method=s.resolution_method,
                epp_status="dry_run", drop_signal=True,
                registrar=None, expiry_date=None,
            ))
            continue
        if idx > 0:
            time.sleep(0.3)  # Rate-limit RDAP to ~3 req/sec
        rdap = _rdap_lookup(s.domain)
        epp = rdap["epp_status"]
        drop = epp in _DROP_SIGNALS
        # Also keep: active but expiring within 12 months AND high-funded dead startup
        if not drop and epp == "active" and rdap["expiry"]:
            try:
                exp = datetime.fromisoformat(rdap["expiry"])
                months_left = (exp - datetime.now(timezone.utc)).days / 30
                if months_left < 12 and s.funding_usd >= 10_000_000:
                    drop = True  # High-value watch target
            except (ValueError, TypeError):
                pass
        results.append(ProbedStartup(
            name=s.name, domain=s.domain,
            funding_usd=s.funding_usd, death_year=s.death_year,
            sector=s.sector, source=s.source,
            description=s.description, resolution_method=s.resolution_method,
            epp_status=epp, registrar=rdap["registrar"],
            expiry_date=rdap["expiry"],
            drop_signal=drop,
        ))
        if (idx + 1) % 25 == 0:
            print(f"    ... probed {idx + 1}/{len(startups)}", file=sys.stderr)
    drop_count = sum(1 for r in results if r.drop_signal)
    print(f"  [PROBE] {len(results)} checked, {drop_count} with drop signals", file=sys.stderr)
    return results


# ── ENRICH: DataForSEO bulk SEO metrics ──────────────────────────────


def _enrich_seo(
    startups: list[ProbedStartup], settings_dict: dict[str, str], dry_run: bool,
) -> dict[str, dict[str, int]]:
    """Bulk-fetch SEO metrics from DataForSEO. Returns {domain: {rank, refs, backlinks}}."""
    assert isinstance(startups, list), "startups must be list"
    domains = [s.domain for s in startups if s.drop_signal]
    if not domains or dry_run:
        return {}
    login = settings_dict.get("dataforseo_login", "")
    password = settings_dict.get("dataforseo_password", "")
    if not login or not password:
        print("  [ENRICH] DataForSEO: no credentials, skipping", file=sys.stderr)
        return {}

    seo_data: dict[str, dict[str, int]] = {}
    try:
        seo_data = asyncio.run(_fetch_seo_bulk(domains, login, password))
    except Exception as exc:
        print(f"  [ENRICH] DataForSEO failed: {exc}", file=sys.stderr)
    print(f"  [ENRICH] SEO data for {len(seo_data)}/{len(domains)} domains", file=sys.stderr)
    return seo_data


async def _fetch_seo_bulk(
    domains: list[str], login: str, password: str,
) -> dict[str, dict[str, int]]:
    """Async DataForSEO bulk_ranks + bulk_pages_summary."""
    assert len(domains) > 0 and len(domains) <= 1000
    import aiohttp
    from base64 import b64encode
    auth = f"Basic {b64encode(f'{login}:{password}'.encode()).decode()}"
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    result: dict[str, dict[str, int]] = {}

    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as session:
        # Bulk ranks
        body = [{"targets": domains}]
        async with session.post(
            "https://api.dataforseo.com/v3/backlinks/bulk_ranks/live",
            json=body,
        ) as resp:
            data = await resp.json()
            task = data.get("tasks", [{}])[0]
            for item in (task.get("result", None) or []):
                target = item.get("target", "")
                result[target] = {"rank": item.get("rank", 0), "refs": 0, "backlinks": 0}

        # Bulk pages summary
        async with session.post(
            "https://api.dataforseo.com/v3/backlinks/bulk_pages_summary/live",
            json=body,
        ) as resp:
            data = await resp.json()
            task = data.get("tasks", [{}])[0]
            for item in (task.get("result", None) or []):
                target = item.get("target", "")
                if target in result:
                    result[target]["refs"] = item.get("referring_domains", 0) or 0
                    result[target]["backlinks"] = item.get("backlinks", 0) or 0
                else:
                    result[target] = {
                        "rank": 0,
                        "refs": item.get("referring_domains", 0) or 0,
                        "backlinks": item.get("backlinks", 0) or 0,
                    }
    return result


# ── SCORE: 9-dimension Reaper composite + competition ────────────────


def _funding_score(funding_usd: int) -> float:
    """Score company funding level. $0→0, $5M→40, $50M→70, $200M+→95."""
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


def _da_score(domain_rank: int, referring_domains: int = 0) -> float:
    """Score domain authority via DataForSEO rank, with RD fallback. Sprint 25."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(referring_domains, int) and referring_domains >= 0
    if domain_rank > 0:
        return min(95.0, max(10.0, math.log10(domain_rank + 1) * 12))
    # Fallback: use referring_domains as DA proxy when rank=0 (Backlinks API 40204)
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
    """Score how certain the domain will drop."""
    assert isinstance(epp_status, str)
    scores: dict[str, float] = {
        "pendingDelete": 100.0, "available": 100.0, "not_found": 100.0,
        "redemptionPeriod": 90.0, "clientHold": 75.0,
        "autoRenewPeriod": 70.0, "clientRenewProhibited": 60.0,
        "active": 20.0, "client transfer prohibited": 40.0,
    }
    return scores.get(epp_status, 15.0)


def _editorial_score(press: tuple[str, ...]) -> float:
    """Score editorial backlinks. More press = higher DA/backlinks."""
    assert isinstance(press, tuple)
    count = len(press)
    if count == 0:
        return 0.0
    base = min(85.0, 30.0 + (count - 1) * 20)
    # Tier-1 bonus
    has_tier1 = any(p.lower() in _TIER1_PRESS for p in press)
    return min(100.0, base + (10.0 if has_tier1 else 0.0))


def _domain_age_score(creation_date: str) -> float:
    """Score domain age. Older = more SEO value."""
    assert isinstance(creation_date, str)
    if not creation_date:
        return 30.0  # Unknown, assume moderate
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
    """Score sector/niche fit. AI/fintech = premium."""
    assert isinstance(sector, str)
    sector_lower = sector.lower().strip()
    for key, score in _NICHE_SCORES.items():
        if key in sector_lower:
            return score
    return 30.0


def _traffic_score(referring_domains: int, total_backlinks: int = 0) -> float:
    """Score traffic from RD + backlink count. Sprint 25: granular bins."""
    assert isinstance(referring_domains, int) and referring_domains >= 0
    assert isinstance(total_backlinks, int) and total_backlinks >= 0
    # Use total_backlinks for finer granularity when available
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
    # Fallback to RD count
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
    """Score trademark safety. Longer since shutdown = safer."""
    assert isinstance(shutdown_date, str)
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
    """Score intrinsic domain name value. Single-word .com → 95, brandable → 60."""
    assert isinstance(domain, str) and "." in domain
    name = domain.rsplit(".", 1)[0].lower()  # strip TLD
    tld = "." + domain.rsplit(".", 1)[1]
    # Penalize non-.com TLDs
    tld_mult = 1.0 if tld == ".com" else 0.7 if tld in (".io", ".ai", ".co") else 0.5
    if "-" in name:
        return max(5.0, 10.0 * tld_mult)
    if name.isdigit():
        return max(5.0, 15.0 * tld_mult)
    words = re.findall(r"[a-z]+", name)
    if len(words) == 1 and len(name) <= 6:
        return min(95.0, 95.0 * tld_mult)  # single short word
    if len(words) == 1 and len(name) <= 10:
        return min(95.0, 75.0 * tld_mult)  # single longer word
    if len(words) == 1:
        return min(95.0, 60.0 * tld_mult)  # single very long word
    if len(words) == 2 and len(name) <= 12:
        return min(95.0, 50.0 * tld_mult)  # two-word compound
    if len(words) == 2:
        return min(95.0, 30.0 * tld_mult)  # longer two-word
    return max(5.0, 15.0 * tld_mult)  # 3+ words


def _competition_penalty(domain_rank: int, referring_domains: int = 0) -> float:
    """Score multiplier based on DR proxy. Sprint 25: RD fallback when rank=0."""
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
    # Fallback: estimate competition from referring domains
    if referring_domains == 0:
        return 0.9  # No data
    if referring_domains >= 5000:
        return 0.5  # High DR equivalent, auction territory
    if referring_domains >= 2000:
        return 0.7  # Moderate competition
    if referring_domains >= 100:
        return 1.0  # Sweet spot
    return 0.9  # Low RD


def _classify_competition(
    domain_rank: int, editorial_count: int, referring_domains: int = 0,
) -> str:
    """Classify competition tier. Sprint 25: RD fallback when rank=0."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(editorial_count, int) and editorial_count >= 0
    # Use rank when available
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
    # Fallback: use referring_domains as rank proxy
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


def _score_domain(
    startup: ProbedStartup, seo: dict[str, int],
    editorial_sources: tuple[str, ...] = (),
) -> ReapedDomain:
    """Compute 9-dimension Reaper score with competition penalty. Sprint 21."""
    assert isinstance(startup, ProbedStartup)
    rank = seo.get("rank", 0)
    refs = seo.get("refs", 0)
    backlinks = seo.get("backlinks", 0)

    # Sprint 25: Use editorial_sources for editorial scoring
    all_press = editorial_sources

    # 9-dimension raw scores — Sprint 25: wire real data into all dimensions
    scores = {
        "funding": _funding_score(startup.funding_usd),
        "domain_authority": _da_score(rank, refs),
        "drop_certainty": _drop_certainty_score(startup.epp_status),
        "editorial_links": _editorial_score(all_press),
        "domain_age": _domain_age_score(startup.expiry_date or ""),
        "niche_fit": _niche_score(startup.sector),
        "domain_name_value": _domain_name_value_score(startup.domain),
        "traffic_value": _traffic_score(refs, backlinks),
        "trademark_safety": _trademark_safety_score(str(startup.death_year) if startup.death_year else ""),
    }
    # Sprint 21 weights: editorial up (0.25), DA down (0.10), + domain_name_value (0.10)
    weights = {
        "funding": 0.15, "domain_authority": 0.10, "drop_certainty": 0.15,
        "editorial_links": 0.25, "domain_age": 0.05, "niche_fit": 0.10,
        "domain_name_value": 0.10, "traffic_value": 0.05, "trademark_safety": 0.05,
    }
    raw_score = sum(scores[k] * weights[k] for k in weights)

    # Sprint 25: Competition penalty — use RD fallback when rank=0
    penalty = _competition_penalty(rank, refs)
    reaper = round(min(100.0, max(0.0, raw_score * penalty)), 1)

    # Sprint 25: Competition tier — use combined editorial + RD fallback
    editorial_count = len(all_press)
    comp_tier = _classify_competition(rank, editorial_count, refs)

    tier = _assign_tier(reaper)
    bid = _recommend_bid(reaper, startup.funding_usd)
    name_value = round(_domain_name_value_score(startup.domain), 1)

    return ReapedDomain(
        name=startup.name, domain=startup.domain,
        funding_usd=startup.funding_usd, sector=startup.sector,
        source=startup.source, death_year=startup.death_year,
        description=startup.description,
        resolution_method=startup.resolution_method,
        epp_status=startup.epp_status, drop_signal=startup.drop_signal,
        registrar=startup.registrar, expiry_date=startup.expiry_date,
        reaper_score=reaper, tier=tier,
        funding_score=round(scores["funding"], 1),
        authority_score=round(scores["domain_authority"], 1),
        drop_certainty_score=round(scores["drop_certainty"], 1),
        editorial_score=round(scores["editorial_links"], 1),
        age_score=round(scores["domain_age"], 1),
        niche_score=round(scores["niche_fit"], 1),
        traffic_score=round(scores["traffic_value"], 1),
        trademark_score=round(scores["trademark_safety"], 1),
        recommended_bid=bid,
        domain_rank=rank, referring_domains=refs, total_backlinks=backlinks,
        spam_score=None,
    )


def _assign_tier(score: float) -> str:
    """Assign tier from reaper score."""
    assert 0.0 <= score <= 100.0
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _recommend_bid(score: float, funding: int) -> int:
    """Calculate recommended max bid."""
    assert 0.0 <= score <= 100.0
    if score >= 75:
        return max(200, min(500, funding // 10_000))
    if score >= 55:
        return max(100, min(300, funding // 20_000))
    if score >= 35:
        return 59
    return 0


# ── BACKORDER: Auto-place Dynadot backorders (Sprint 21) ─────────────


def _check_dynadot_balance(settings_dict: dict[str, str]) -> float:
    """Query Dynadot account balance. Returns balance in USD, -1 on error."""
    assert isinstance(settings_dict, dict)
    api_key = settings_dict.get("dynadot_api_key", "")
    if not api_key:
        return -1.0
    try:
        import httpx
        params = {"key": api_key, "command": "get_account_balance"}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.dynadot.com/api3.json", params=params)
        data = resp.json()
        bal_resp = data.get("GetAccountBalanceResponse", {})
        balance = float(bal_resp.get("Balance", -1))
        print(f"  [BALANCE] Dynadot balance: ${balance:.2f}", file=sys.stderr)
        if balance < 25.0:
            print(f"  [BALANCE] *** LOW BALANCE WARNING: ${balance:.2f} < $25 ***", file=sys.stderr)
        return balance
    except Exception as exc:
        print(f"  [BALANCE] Query failed: {exc}", file=sys.stderr)
        return -1.0


def _count_active_backorders(settings_dict: dict[str, str]) -> int:
    """Query Dynadot for active backorder count. Returns 0 on error."""
    assert isinstance(settings_dict, dict)
    api_key = settings_dict.get("dynadot_api_key", "")
    if not api_key:
        return 0
    try:
        import httpx
        params = {"key": api_key, "command": "backorder_request_list",
                  "startDate": "2020-01-01", "endDate": "2030-12-31"}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.dynadot.com/api3.json", params=params)
        data = resp.json()
        bl_resp = data.get("BackorderRequestListResponse", {})
        items = bl_resp.get("BackorderList", [])
        return len(items) if isinstance(items, list) else 0
    except Exception as exc:
        print(f"  [BACKORDER] List query failed: {exc}", file=sys.stderr)
        return 0


def _place_dynadot_backorder(domain: str, api_key: str, dry_run: bool) -> str:
    """Place a single Dynadot backorder. Returns status string."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(api_key, str) and len(api_key) > 0
    if dry_run:
        return f"DRY-RUN: would backorder {domain}"
    try:
        import httpx
        params = {"key": api_key, "command": "add_backorder_request", "domain": domain}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.dynadot.com/api3.json", params=params)
        data = resp.json()
        bo_resp = data.get("AddBackorderRequestResponse", {})
        status = bo_resp.get("Status", "unknown")
        return f"Dynadot: {status}"
    except Exception as exc:
        return f"FAILED: {exc}"


def _auto_backorder(
    scored: list[ReapedDomain], settings_dict: dict[str, str],
    dry_run: bool,
) -> int:
    """Auto-place backorders for sweet_spot/stretch domains in pendingDelete. Sprint 21."""
    assert isinstance(scored, list)
    api_key = settings_dict.get("dynadot_api_key", "")
    if not api_key:
        print("  [BACKORDER] No Dynadot API key, skipping", file=sys.stderr)
        return 0

    # Sprint 22: Check Dynadot balance before placing backorders
    balance = _check_dynadot_balance(settings_dict)
    if balance >= 0 and balance < _BACKORDER_PRICE_USD:
        print(f"  [BACKORDER] Insufficient balance (${balance:.2f}), skipping", file=sys.stderr)
        return 0

    # Check budget: count existing backorders
    active = _count_active_backorders(settings_dict)
    slots = _MAX_BACKORDERS - active
    budget_left = _BACKORDER_BUDGET_USD - (active * _BACKORDER_PRICE_USD)
    print(f"  [BACKORDER] Active: {active}/{_MAX_BACKORDERS}, "
          f"budget: ${budget_left:.2f}/{_BACKORDER_BUDGET_USD}", file=sys.stderr)

    if slots <= 0 or budget_left < _BACKORDER_PRICE_USD:
        print("  [BACKORDER] Budget/slot limit reached", file=sys.stderr)
        return 0

    # Filter candidates: sweet_spot or stretch, pendingDelete or redemptionPeriod
    candidates = [
        r for r in scored
        if r.tier in ("critical", "high")
        and r.epp_status in ("pendingDelete", "redemptionPeriod", "autoRenewPeriod")
        and r.reaper_score >= 40.0
    ]
    candidates.sort(key=lambda x: (-x.reaper_score, x.domain))

    placed = 0
    for r in candidates[:slots]:
        if budget_left < _BACKORDER_PRICE_USD:
            break
        result = _place_dynadot_backorder(r.domain, api_key, dry_run)
        print(f"    {r.domain} (score={r.reaper_score}, tier={r.tier}): {result}",
              file=sys.stderr)
        if "DRY-RUN" in result or "success" in result.lower():
            placed += 1
            budget_left -= _BACKORDER_PRICE_USD
    return placed


# ── EDITORIAL: DataForSEO referring domains (Sprint 21) ──────────────


def _fetch_editorial_sources(
    domains: list[str], login: str, password: str,
) -> dict[str, tuple[str, ...]]:
    """Fetch referring domains per target, return editorial sources found."""
    assert isinstance(domains, list) and len(domains) <= 200
    if not login or not password:
        return {}
    from base64 import b64encode
    import httpx
    auth = f"Basic {b64encode(f'{login}:{password}'.encode()).decode()}"
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    result: dict[str, tuple[str, ...]] = {}
    for domain in domains[:60]:  # Bounded: max 60 domains
        try:
            body = [{"target": domain, "limit": 100,
                     "order_by": ["rank,desc"]}]
            with httpx.Client(timeout=30, headers=headers) as client:
                resp = client.post(
                    "https://api.dataforseo.com/v3/backlinks/referring_domains/live",
                    json=body,
                )
            data = resp.json()
            task = data.get("tasks", [{}])[0]
            editorial: list[str] = []
            for item in (task.get("result", None) or []):
                ref_domain = str(item.get("target", "")).lower()
                if ref_domain in _EDITORIAL_DOMAINS:
                    editorial.append(ref_domain)
            if editorial:
                result[domain] = tuple(editorial)
        except Exception:
            continue  # Skip failures, don't block pipeline
        time.sleep(0.5)  # Rate limit DataForSEO
    return result


# ── OUTPUT: JSON + ASCII table + auto-monitor ─────────────────────────


def _format_table(results: list[ReapedDomain], limit: int) -> str:
    """Render top results as ASCII table with competition tier."""
    assert isinstance(results, list)
    assert 0 < limit <= _MAX_RESULTS
    display = results[:limit]
    hdr = (f"{'#':>3}  {'Domain':<30} {'Score':>5}  {'Tier':<8} "
           f"{'Funding':>10}  {'DA':>5}  {'Refs':>6}  {'EPP':<22} "
           f"{'Sector':<12}  {'Bid':>5}")
    sep = "-" * len(hdr)
    lines: list[str] = [sep, hdr, sep]
    for i, r in enumerate(display, 1):
        fund = _format_funding(r.funding_usd)
        da = r.domain_rank if r.domain_rank is not None else 0
        refs = r.referring_domains if r.referring_domains is not None else 0
        lines.append(
            f"{i:>3}  {r.domain:<30} {r.reaper_score:>5.1f}  {r.tier:<8} "
            f"{fund:>10}  "
            f"{da:>5}  {refs:>6}  {r.epp_status:<22} "
            f"{r.sector:<12}  ${r.recommended_bid:>4}"
        )
    lines.append(sep)
    return "\n".join(lines)


def _format_funding(usd: int) -> str:
    """Format funding as human-readable string."""
    assert isinstance(usd, (int, float)) and usd >= 0
    if usd >= 1_000_000_000:
        return f"${usd / 1_000_000_000:.1f}B"
    if usd >= 1_000_000:
        return f"${usd / 1_000_000:.0f}M"
    if usd >= 1_000:
        return f"${usd / 1_000:.0f}K"
    if usd > 0:
        return f"${usd}"
    return "$0"


def _save_results(results: list[ReapedDomain], filepath: str) -> None:
    """Write results to JSON."""
    assert isinstance(results, list) and len(results) > 0
    assert filepath.endswith(".json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "startup_reaper",
        "total_scored": len(results),
        "top_score": results[0].reaper_score if results else 0,
        "results": [reaped_to_dict(r) for r in results],
    }
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _auto_add_to_monitor(results: list[ReapedDomain], config_path: str) -> int:
    """Add critical+high results to monitored_domains.json. Returns count added."""
    assert isinstance(results, list)
    assert os.path.isfile(config_path), f"config not found: {config_path}"
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    assert "active_targets" in config, "monitored_domains.json must have 'active_targets' key"

    existing_domains: set[str] = set()
    for tier_list in config["active_targets"].values():
        for entry in tier_list:
            existing_domains.add(entry["domain"].lower())

    added = 0
    for r in results:
        if r.tier not in ("critical", "high") or not r.drop_signal:
            continue
        if r.domain.lower() in existing_domains:
            continue
        entry = {
            "domain": r.domain,
            "etv": 0,
            "max_bid": r.recommended_bid,
            "notes": f"{r.name}, {_format_funding(r.funding_usd)} funded, "
                     f"reaper={r.reaper_score}, {r.epp_status}, expires {r.expiry_date}",
        }
        config["active_targets"].setdefault(r.tier, []).append(entry)
        existing_domains.add(r.domain.lower())
        added += 1
    if added > 0:
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    return added


# ── CLI + Orchestrator ────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser. Sprint 21: added --auto-backorder, --dry-run-backorder."""
    p = argparse.ArgumentParser(description="Startup Reaper — dead startups → high-value domains")
    p.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    p.add_argument("--sources", type=str, default="all",
                   help="Comma-separated sources: existing,deepseek,yc,kaggle (default: all)")
    p.add_argument("--min-score", type=float, default=_DEFAULT_MIN_SCORE,
                   help=f"Min score for display (default: {_DEFAULT_MIN_SCORE})")
    p.add_argument("--sector", type=str, default=None,
                   help="Filter by sector (comma-separated, e.g. 'ai,fintech')")
    p.add_argument("--no-monitor", action="store_true",
                   help="Skip auto-add to monitored_domains.json")
    p.add_argument("--top", type=int, default=_MAX_DISPLAY,
                   help=f"Top N results to display (default: {_MAX_DISPLAY})")
    p.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    # Sprint 21: Backorder flags
    p.add_argument("--auto-backorder", action="store_true",
                   help="Auto-place Dynadot backorders for sweet_spot/stretch pendingDelete domains")
    p.add_argument("--dry-run-backorder", action="store_true",
                   help="Preview backorder placements without executing")
    return p


def run_reaper(args: argparse.Namespace) -> list[ReapedDomain]:
    """Main pipeline orchestrator."""
    sources = args.sources.lower().split(",") if args.sources != "all" else ["existing", "deepseek", "yc", "kaggle"]
    sector_filter = set(args.sector.lower().split(",")) if args.sector else None

    # Load settings from .env
    settings_dict: dict[str, str] = {}
    env_path = os.path.join(_ROOT, ".env")
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    settings_dict[k.strip().lower()] = v.strip()

    # ── Stage 1: HARVEST ──
    print("\n  Stage 1: HARVEST", file=sys.stderr)
    all_startups: list[DeadStartup] = []
    if "existing" in sources:
        all_startups.extend(_load_existing(_DATA_DIR))
        print(f"  [HARVEST] Existing: {len(all_startups)} startups", file=sys.stderr)
    if "deepseek" in sources:
        all_startups.extend(_harvest_from_deepseek(settings_dict, args.dry_run))
    if "yc" in sources:
        all_startups.extend(_harvest_from_yc(args.dry_run))
    if "kaggle" in sources:
        all_startups.extend(_harvest_from_kaggle(_DATA_DIR))
    all_startups = _deduplicate(all_startups)
    print(f"  [HARVEST] Total after dedup: {len(all_startups)}", file=sys.stderr)

    # ── Stage 2: RESOLVE ──
    print("\n  Stage 2: RESOLVE", file=sys.stderr)
    resolved = _resolve_domains(all_startups, settings_dict, args.dry_run)

    # Filter by sector if requested
    if sector_filter:
        resolved = [r for r in resolved if any(s in r.sector.lower() for s in sector_filter)]
        print(f"  [RESOLVE] After sector filter: {len(resolved)}", file=sys.stderr)

    # ── Stage 3: PROBE ──
    print("\n  Stage 3: PROBE (RDAP)", file=sys.stderr)
    probed = _probe_rdap(resolved, args.dry_run)

    # ── Stage 4: ENRICH (SEO + editorial) ──
    print("\n  Stage 4: ENRICH (DataForSEO)", file=sys.stderr)
    seo_data = _enrich_seo(probed, settings_dict, args.dry_run)

    # Sprint 21: Fetch editorial sources for drop-signal domains
    editorial_data: dict[str, tuple[str, ...]] = {}
    drop_domains = [s.domain for s in probed if s.drop_signal]
    login = settings_dict.get("dataforseo_login", "")
    password = settings_dict.get("dataforseo_password", "")
    if drop_domains and login and password and not args.dry_run:
        print("  [ENRICH] Fetching editorial sources...", file=sys.stderr)
        editorial_data = _fetch_editorial_sources(drop_domains, login, password)
        print(f"  [ENRICH] Editorial sources for {len(editorial_data)} domains", file=sys.stderr)

    # ── Stage 5: SCORE (9-dimension + competition) ──
    print("\n  Stage 5: SCORE (9-dim + competition penalty)", file=sys.stderr)
    scored: list[ReapedDomain] = []
    for s in probed:
        seo = seo_data.get(s.domain, {"rank": 0, "refs": 0, "backlinks": 0})
        ed_sources = editorial_data.get(s.domain, ())
        r = _score_domain(s, seo, editorial_sources=ed_sources)
        if r.reaper_score >= args.min_score:
            scored.append(r)
    scored.sort(key=lambda x: (-x.reaper_score, x.domain))
    scored = scored[:_MAX_RESULTS]
    # Sprint 21: Count by competition tier
    tier_counts: dict[str, int] = {}
    for r in scored:
        tier_counts[r.tier] = tier_counts.get(r.tier, 0) + 1
    print(f"  [SCORE] {len(scored)} domains above {args.min_score}", file=sys.stderr)
    print(f"  [SCORE] Tiers: {tier_counts}", file=sys.stderr)

    # ── Stage 6: OUTPUT ──
    print("\n  Stage 6: OUTPUT", file=sys.stderr)
    if scored:
        display_limit = min(args.top, len(scored), _MAX_RESULTS)
        print(f"\n{_format_table(scored, display_limit)}")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = args.output or os.path.join(_DATA_DIR, f"startup_reaper_{date_str}.json")
        _save_results(scored, out_path)
        print(f"\n  Results saved to: {out_path}", file=sys.stderr)
        if not args.no_monitor and os.path.isfile(_MONITORED_PATH):
            added = _auto_add_to_monitor(scored, _MONITORED_PATH)
            if added > 0:
                print(f"  Auto-added {added} domains to monitored_domains.json", file=sys.stderr)

    # ── Stage 7: BACKORDER (Sprint 21) ──
    if getattr(args, "auto_backorder", False) or getattr(args, "dry_run_backorder", False):
        print("\n  Stage 7: BACKORDER (Dynadot)", file=sys.stderr)
        bo_dry = args.dry_run or getattr(args, "dry_run_backorder", False)
        placed = _auto_backorder(scored, settings_dict, bo_dry)
        print(f"  [BACKORDER] {placed} backorders placed", file=sys.stderr)

    if not scored:
        print("  No domains matched the criteria.", file=sys.stderr)

    return scored


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    print("Startup Reaper v3 — Sprint 22: First Blood", file=sys.stderr)
    print(f"  Sources:    {args.sources}", file=sys.stderr)
    print(f"  Min score:  {args.min_score}", file=sys.stderr)
    print(f"  Dry run:    {args.dry_run}", file=sys.stderr)
    print(f"  Sector:     {args.sector or 'all'}", file=sys.stderr)
    print(f"  Backorder:  {args.auto_backorder}", file=sys.stderr)
    run_reaper(args)


if __name__ == "__main__":
    main()

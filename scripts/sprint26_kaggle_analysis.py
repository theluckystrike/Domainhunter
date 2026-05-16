#!/usr/bin/env python3
"""Sprint 26 Kaggle Analysis — find NEW high-value domains from Kaggle dataset.

Reads kaggle_startups.csv, filters for funding > $5M with .com/.co/.ai/.io domains,
cross-references against monitored_domains.json + existing reaper results to find
domains NOT yet in the pipeline. Outputs sorted by funding to JSON.

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable state.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_MONITORED_PATH: Final[str] = os.path.join(_ROOT, "scripts", "monitored_domains.json")
_KAGGLE_CSV: Final[str] = os.path.join(_DATA_DIR, "kaggle_startups.csv")
_OUTPUT_PATH: Final[str] = os.path.join(_DATA_DIR, "sprint26_kaggle_new_targets.json")
_TARGET_TLDS: Final[frozenset[str]] = frozenset({".com", ".co", ".ai", ".io"})
_MIN_FUNDING: Final[int] = 5_000_000
_MAX_RESULTS: Final[int] = 500


def parse_funding(raw: str) -> int:
    """Parse funding strings like '$220M', '$1.5B', '$30M+' to int dollars."""
    assert isinstance(raw, str), "raw must be a string"
    assert len(raw) < 200, "funding string too long"
    if not raw or raw.lower() in ("undisclosed", "unknown", "n/a", "0", ""):
        return 0
    clean = raw.replace(",", "").replace("+", "").replace("~", "").strip()
    match = re.search(r"\$?([\d.]+)\s*([BMKbmk])", clean)
    if not match:
        match2 = re.search(r"\$?([\d]+)", clean)
        return int(match2.group(1)) if match2 else 0
    val, unit = float(match.group(1)), match.group(2).upper()
    multiplier = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}
    return int(val * multiplier.get(unit, 1))


def clean_domain(raw: str) -> str:
    """Normalize domain: strip protocol, path, whitespace. Returns lowercase."""
    assert isinstance(raw, str), "raw must be a string"
    assert len(raw) < 500, "domain string too long"
    cleaned = re.sub(r"^https?://", "", raw.strip().lower())
    cleaned = cleaned.rstrip("/").split("/")[0]
    if cleaned.replace(".", "").isdigit() or "localhost" in cleaned:
        return ""
    return cleaned


def get_tld(domain: str) -> str:
    """Extract TLD from domain string."""
    assert isinstance(domain, str) and "." in domain, "valid domain required"
    assert len(domain) < 255, "domain exceeds max length"
    return "." + domain.rsplit(".", 1)[1]


def load_kaggle_entries(csv_path: str) -> list[dict[str, Any]]:
    """Load all entries from Kaggle CSV with parsed funding."""
    assert os.path.isfile(csv_path), f"CSV not found: {csv_path}"
    entries: list[dict[str, Any]] = []
    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None, "CSV must have a header row"
        for idx, row in enumerate(reader):
            if idx >= 5000:  # bounded loop
                break
            domain = clean_domain(row.get("domain", ""))
            funding = parse_funding(row.get("funding_usd", "0"))
            entries.append({
                "company_name": row.get("company_name", "").strip(),
                "domain": domain,
                "funding_usd": funding,
                "status": row.get("status", "").strip().lower(),
                "sector": row.get("sector", "").strip().lower(),
                "shutdown_date": row.get("shutdown_date", "").strip(),
                "notes": row.get("notes", "").strip()[:200],
            })
    return entries


def load_known_domains() -> set[str]:
    """Load all domains already tracked in monitored_domains.json + reaper results."""
    assert os.path.isdir(_DATA_DIR), f"data dir not found: {_DATA_DIR}"
    known: set[str] = set()
    # Monitored domains
    if os.path.isfile(_MONITORED_PATH):
        with open(_MONITORED_PATH, encoding="utf-8") as fh:
            mon = json.load(fh)
        assert isinstance(mon, dict), "monitored_domains must be dict"
        for section in ("active_targets", "watch_list", "domains"):
            if section not in mon:
                continue
            data = mon[section]
            _extract_domains_from_section(data, known)
    # Existing reaper results
    for fname in os.listdir(_DATA_DIR):
        if fname.startswith("startup_reaper") and fname.endswith(".json"):
            _load_reaper_domains(os.path.join(_DATA_DIR, fname), known)
    return known


def _extract_domains_from_section(data: Any, known: set[str]) -> None:
    """Extract domain strings from a JSON section (dict of lists or list)."""
    assert isinstance(known, set), "known must be a set"
    assert isinstance(data, (dict, list)), "data must be dict or list"
    if isinstance(data, dict):
        for _tier, entries in data.items():
            if isinstance(entries, list):
                for entry in entries[:500]:
                    if isinstance(entry, dict) and "domain" in entry:
                        known.add(entry["domain"].lower())
    elif isinstance(data, list):
        for entry in data[:500]:
            if isinstance(entry, dict) and "domain" in entry:
                known.add(entry["domain"].lower())


def _load_reaper_domains(filepath: str, known: set[str]) -> None:
    """Load domains from a reaper result JSON file."""
    assert os.path.isfile(filepath), f"file not found: {filepath}"
    assert isinstance(known, set), "known must be a set"
    try:
        with open(filepath, encoding="utf-8") as fh:
            data = json.load(fh)
        for result in data.get("results", [])[:2000]:
            if isinstance(result, dict) and "domain" in result:
                known.add(result["domain"].lower())
    except (json.JSONDecodeError, KeyError):
        pass  # Skip malformed files


def domain_name_value(domain: str) -> float:
    """Score intrinsic domain name quality. Short single-word .com = best."""
    assert isinstance(domain, str) and "." in domain
    assert len(domain) < 255, "domain exceeds max length"
    name = domain.rsplit(".", 1)[0].lower()
    tld = "." + domain.rsplit(".", 1)[1]
    tld_mult = 1.0 if tld == ".com" else 0.7 if tld in (".io", ".ai", ".co") else 0.5
    if "-" in name:
        return max(5.0, 10.0 * tld_mult)
    words = re.findall(r"[a-z]+", name)
    if len(words) == 1 and len(name) <= 6:
        return round(95.0 * tld_mult, 1)
    if len(words) == 1 and len(name) <= 10:
        return round(75.0 * tld_mult, 1)
    if len(words) == 1:
        return round(60.0 * tld_mult, 1)
    if len(words) == 2 and len(name) <= 12:
        return round(50.0 * tld_mult, 1)
    return round(max(5.0, 15.0 * tld_mult), 1)


def filter_new_targets(
    entries: list[dict[str, Any]], known: set[str],
) -> list[dict[str, Any]]:
    """Filter for high-value NEW domains not in known set."""
    assert isinstance(entries, list), "entries must be list"
    assert isinstance(known, set), "known must be set"
    targets: list[dict[str, Any]] = []
    for entry in entries:
        domain = entry["domain"]
        funding = entry["funding_usd"]
        if not domain or "." not in domain:
            continue
        if funding < _MIN_FUNDING:
            continue
        tld = get_tld(domain)
        if tld not in _TARGET_TLDS:
            continue
        if domain in known:
            continue
        name_val = domain_name_value(domain)
        entry["tld"] = tld
        entry["name_value"] = name_val
        entry["name_length"] = len(domain.rsplit(".", 1)[0])
        entry["is_premium"] = name_val >= 50.0
        targets.append(entry)
    targets.sort(key=lambda x: (-x["funding_usd"], -x["name_value"]))
    return targets[:_MAX_RESULTS]


def format_funding(usd: int) -> str:
    """Format funding as human-readable string."""
    assert isinstance(usd, int) and usd >= 0
    assert usd < 1_000_000_000_000, "funding exceeds $1T"
    if usd >= 1_000_000_000:
        return f"${usd / 1_000_000_000:.1f}B"
    if usd >= 1_000_000:
        return f"${usd / 1_000_000:.0f}M"
    if usd >= 1_000:
        return f"${usd / 1_000:.0f}K"
    return f"${usd}"


def save_results(targets: list[dict[str, Any]], output_path: str) -> None:
    """Save filtered targets to JSON."""
    assert isinstance(targets, list), "targets must be list"
    assert output_path.endswith(".json"), "output must be .json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "sprint26_kaggle_analysis",
        "total_new_targets": len(targets),
        "min_funding": _MIN_FUNDING,
        "allowed_tlds": sorted(_TARGET_TLDS),
        "targets": targets,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def print_summary(
    all_entries: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    known: set[str],
) -> None:
    """Print analysis summary to stdout."""
    assert isinstance(all_entries, list)
    assert isinstance(targets, list)
    total = len(all_entries)
    with_domain = sum(1 for e in all_entries if e.get("domain"))
    gt5m = sum(1 for e in all_entries if e["funding_usd"] >= _MIN_FUNDING)
    premium = sum(1 for t in targets if t.get("is_premium"))

    print("\n" + "=" * 70)
    print("  SPRINT 26 KAGGLE ANALYSIS — NEW DOMAIN TARGETS")
    print("=" * 70)
    print(f"  Total Kaggle entries:            {total:>6}")
    print(f"  Entries with valid domain:       {with_domain:>6}")
    print(f"  Entries with funding >= $5M:     {gt5m:>6}")
    print(f"  Already known/tracked domains:   {len(known):>6}")
    print(f"  NEW targets (.com/.co/.ai/.io):  {len(targets):>6}")
    print(f"  Premium short names (score>=50): {premium:>6}")
    print("-" * 70)

    # Sector breakdown
    from collections import Counter
    sectors = Counter(t["sector"] for t in targets)
    print("\n  SECTOR BREAKDOWN (top 10):")
    for sector, count in sectors.most_common(10):
        print(f"    {sector or '(unknown)':<20} {count:>4}")

    # TLD breakdown
    tlds = Counter(t["tld"] for t in targets)
    print("\n  TLD BREAKDOWN:")
    for tld, count in tlds.most_common():
        print(f"    {tld:<8} {count:>4}")

    # Top 20 new targets
    print(f"\n  TOP 20 NEW TARGETS (by funding):")
    print(f"  {'#':>3}  {'Domain':<30} {'Funding':>10}  {'NV':>4}  {'Sector':<15} {'Company'}")
    print(f"  {'---':>3}  {'-'*30:<30} {'-'*10:>10}  {'--':>4}  {'-'*15:<15} {'-'*20}")
    for i, target in enumerate(targets[:20], 1):
        fund = format_funding(target["funding_usd"])
        nv = target.get("name_value", 0)
        sector = target["sector"][:15]
        company = target["company_name"][:25]
        print(f"  {i:>3}  {target['domain']:<30} {fund:>10}  {nv:>4.0f}  {sector:<15} {company}")

    print("\n" + "=" * 70)


def main() -> None:
    """CLI entry point — runs full analysis pipeline."""
    assert os.path.isfile(_KAGGLE_CSV), f"Kaggle CSV not found: {_KAGGLE_CSV}"
    assert os.path.isdir(_DATA_DIR), f"Data dir not found: {_DATA_DIR}"
    print("Sprint 26: Kaggle Startup Analysis", file=sys.stderr)
    print(f"  CSV: {_KAGGLE_CSV}", file=sys.stderr)

    # Stage 1: Load Kaggle data
    all_entries = load_kaggle_entries(_KAGGLE_CSV)
    print(f"  Loaded {len(all_entries)} entries from Kaggle CSV", file=sys.stderr)

    # Stage 2: Load known domains
    known = load_known_domains()
    print(f"  Loaded {len(known)} already-known domains", file=sys.stderr)

    # Stage 3: Filter for new high-value targets
    targets = filter_new_targets(all_entries, known)
    print(f"  Found {len(targets)} new targets", file=sys.stderr)

    # Stage 4: Save results
    save_results(targets, _OUTPUT_PATH)
    print(f"  Saved to {_OUTPUT_PATH}", file=sys.stderr)

    # Stage 5: Print summary
    print_summary(all_entries, targets, known)


if __name__ == "__main__":
    main()

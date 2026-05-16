#!/usr/bin/env python3
"""Sprint 22 — Agent 1: DataForSEO Validation of 38 Sweet-Spot Domains.

The dry-run scan (2026-05-15) scored 149 domains but ALL have domain_rank=0,
referring_domains=0, total_backlinks=0 — DataForSEO enrichment never fired.
This means ALL sweet_spot classifications are based on heuristics only.

This script validates by calling DataForSEO bulk APIs with REAL data and
reclassifies each domain. Cost: ~$0.21 for 38 domains (2 bulk calls).

Usage:
  python scripts/sprint22_validate_sweetspot.py              # Live validation
  python scripts/sprint22_validate_sweetspot.py --dry-run     # Preview only
  python scripts/sprint22_validate_sweetspot.py --input FILE  # Custom input JSON

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
import time
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _ROOT)

_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_EDITORIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "techcrunch.com", "bloomberg.com", "forbes.com", "wsj.com", "nytimes.com",
    "cnbc.com", "reuters.com", "wired.com", "theverge.com", "bbc.com",
    "venturebeat.com", "crunchbase.com", "businessinsider.com", "arstechnica.com",
    "thenextweb.com", "zdnet.com", "engadget.com", "mashable.com",
})


# ── Load sweet_spot domains from reaper output ──────────────────────


def _find_latest_reaper_json(data_dir: str) -> str:
    """Find the most recent startup_reaper_*.json file."""
    assert os.path.isdir(data_dir), f"data dir not found: {data_dir}"
    candidates = sorted(
        [f for f in os.listdir(data_dir)
         if f.startswith("startup_reaper_") and f.endswith(".json")
         and not f.startswith("startup_reaper_existing")],
        reverse=True,
    )
    assert len(candidates) > 0, "no reaper output files found"
    return os.path.join(data_dir, candidates[0])


def _load_sweetspot_domains(filepath: str) -> list[dict[str, Any]]:
    """Load domains classified as sweet_spot from reaper JSON output."""
    assert os.path.isfile(filepath), f"file not found: {filepath}"
    with open(filepath, encoding="utf-8") as fh:
        data = json.load(fh)
    assert "results" in data, "JSON must have 'results' key"
    sweet = [r for r in data["results"] if r.get("competition_tier") == "sweet_spot"]
    print(f"  Loaded {len(sweet)} sweet_spot domains from {os.path.basename(filepath)}", file=sys.stderr)
    return sweet


# ── DataForSEO bulk API calls ───────────────────────────────────────


async def _fetch_bulk_ranks(domains: list[str], auth: str) -> dict[str, int]:
    """Call DataForSEO bulk_ranks. Returns {domain: rank}."""
    assert 0 < len(domains) <= 1000
    assert isinstance(auth, str) and auth.startswith("Basic ")
    import aiohttp
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    body = [{"targets": domains}]
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.post(
            "https://api.dataforseo.com/v3/backlinks/bulk_ranks/live", json=body,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"  ERROR bulk_ranks: {resp.status} {text[:200]}", file=sys.stderr)
                return {}
            data = await resp.json()
    task = data.get("tasks", [{}])[0]
    cost = data.get("cost", 0)
    print(f"  bulk_ranks: status={task.get('status_code')}, cost=${cost}", file=sys.stderr)
    result: dict[str, int] = {}
    for item in (task.get("result", None) or []):
        result[item.get("target", "")] = item.get("rank", 0)
    return result


async def _fetch_bulk_summary(domains: list[str], auth: str) -> dict[str, dict[str, int]]:
    """Call DataForSEO bulk_pages_summary. Returns {domain: {refs, backlinks, rank}}."""
    assert 0 < len(domains) <= 1000
    assert isinstance(auth, str) and auth.startswith("Basic ")
    import aiohttp
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    body = [{"targets": domains}]
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.post(
            "https://api.dataforseo.com/v3/backlinks/bulk_pages_summary/live", json=body,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"  ERROR bulk_summary: {resp.status} {text[:200]}", file=sys.stderr)
                return {}
            data = await resp.json()
    task = data.get("tasks", [{}])[0]
    cost = data.get("cost", 0)
    print(f"  bulk_pages_summary: status={task.get('status_code')}, cost=${cost}", file=sys.stderr)
    result: dict[str, dict[str, int]] = {}
    for item in (task.get("result", None) or []):
        target = item.get("target", "")
        result[target] = {
            "referring_domains": item.get("referring_domains", 0) or 0,
            "backlinks": item.get("backlinks", 0) or 0,
            "rank": item.get("rank", 0) or 0,
            "broken_backlinks": item.get("broken_backlinks", 0) or 0,
            "spam_score": item.get("spam_score", 0) or 0,
        }
    return result


# ── Reclassification logic ──────────────────────────────────────────


def _reclassify_competition(domain_rank: int, editorial_count: int) -> str:
    """Reclassify competition tier with real DR data."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert isinstance(editorial_count, int) and editorial_count >= 0
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


def _competition_penalty(domain_rank: int) -> float:
    """Return multiplier based on real DR."""
    assert isinstance(domain_rank, int) and domain_rank >= 0
    assert domain_rank <= 100_000_000, f"implausible rank: {domain_rank}"
    if domain_rank == 0:
        return 0.9
    if domain_rank >= 1_000_000:
        return 0.3
    if domain_rank >= 100_000:
        return 0.5
    if domain_rank >= 10_000:
        return 0.7
    if domain_rank >= 100:
        return 1.0
    return 0.8


def _compute_da_traffic(rank: int, refs: int) -> tuple[float, float]:
    """Compute domain authority and traffic scores from real metrics."""
    assert isinstance(rank, int) and rank >= 0
    assert isinstance(refs, int) and refs >= 0
    da_score = min(95.0, max(10.0, math.log10(rank + 1) * 12)) if rank > 0 else 0.0
    if refs == 0:
        traffic = 0.0
    elif refs < 10:
        traffic = 10.0
    elif refs < 50:
        traffic = 30.0
    elif refs < 100:
        traffic = 50.0
    elif refs < 500:
        traffic = 70.0
    else:
        traffic = 90.0
    return da_score, traffic


def _compute_weighted_score(scores: dict[str, float], rank: int) -> float:
    """Compute weighted reaper score with competition penalty."""
    assert isinstance(scores, dict) and len(scores) > 0
    assert isinstance(rank, int) and rank >= 0
    weights = {
        "funding": 0.15, "domain_authority": 0.10, "drop_certainty": 0.15,
        "editorial_links": 0.25, "domain_age": 0.05, "niche_fit": 0.10,
        "domain_name_value": 0.10, "traffic_value": 0.05, "trademark_safety": 0.05,
    }
    raw = sum(scores.get(k, 0) * weights[k] for k in weights)
    penalty = _competition_penalty(rank)
    return round(min(100.0, max(0.0, raw * penalty)), 1)


def _rescore(entry: dict[str, Any], rank: int, refs: int, backlinks: int) -> dict[str, Any]:
    """Rescore a domain entry with real DataForSEO data."""
    assert isinstance(entry, dict) and "domain" in entry
    assert isinstance(rank, int) and rank >= 0
    old_score = entry.get("reaper_score", 0)
    old_tier = entry.get("competition_tier", "junk")

    da_score, traffic = _compute_da_traffic(rank, refs)
    scores = dict(entry.get("score_breakdown", {}))
    scores["domain_authority"] = da_score
    scores["traffic_value"] = traffic
    new_score = _compute_weighted_score(scores, rank)

    editorial_count = len(entry.get("press_mentions", [])) + len(entry.get("editorial_sources", []))
    new_comp = _reclassify_competition(rank, editorial_count)

    if new_score >= 75:
        new_tier_label = "critical"
    elif new_score >= 55:
        new_tier_label = "high"
    elif new_score >= 35:
        new_tier_label = "medium"
    else:
        new_tier_label = "low"

    return {
        **entry,
        "domain_rank": rank, "referring_domains": refs, "total_backlinks": backlinks,
        "reaper_score_old": old_score, "reaper_score": new_score,
        "score_delta": round(new_score - old_score, 1),
        "competition_tier_old": old_tier, "competition_tier": new_comp,
        "tier": new_tier_label,
        "score_breakdown": {**scores, "domain_authority": da_score, "traffic_value": traffic},
        "validated": True,
    }


# ── Output ──────────────────────────────────────────────────────────


def _format_validation_table(results: list[dict[str, Any]]) -> str:
    """Format validation results as ASCII table."""
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results[:10])
    hdr = (f"{'#':>3}  {'Domain':<28} {'Old':>5} {'New':>5} {'Delta':>6}  "
           f"{'OldComp':<11} {'NewComp':<11} {'DR':>7}  {'Refs':>6}  {'BL':>8}  "
           f"{'Funding':>9}  {'Press':>5}")
    sep = "-" * len(hdr)
    lines: list[str] = [sep, hdr, sep]
    for i, r in enumerate(results, 1):
        fund = r.get("funding_usd", 0)
        fund_str = f"${fund / 1e6:.0f}M" if fund >= 1e6 else f"${fund / 1e3:.0f}K" if fund >= 1e3 else "$0"
        delta = r.get("score_delta", 0)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(
            f"{i:>3}  {r['domain']:<28} {r.get('reaper_score_old', 0):>5.1f} "
            f"{r['reaper_score']:>5.1f} {delta_str:>6}  "
            f"{r.get('competition_tier_old', '?'):<11} {r['competition_tier']:<11} "
            f"{r.get('domain_rank', 0):>7}  {r.get('referring_domains', 0):>6}  "
            f"{r.get('total_backlinks', 0):>8}  {fund_str:>9}  "
            f"{len(r.get('press_mentions', [])):>5}"
        )
    lines.append(sep)
    return "\n".join(lines)


def _format_summary(results: list[dict[str, Any]]) -> str:
    """Format validation summary statistics."""
    assert isinstance(results, list)
    assert all("reaper_score" in r for r in results[:10])
    total = len(results)
    still_sweet = sum(1 for r in results if r["competition_tier"] == "sweet_spot")
    promoted = sum(1 for r in results if r.get("score_delta", 0) > 5)
    demoted = sum(1 for r in results if r.get("score_delta", 0) < -5)
    new_tiers: dict[str, int] = {}
    for r in results:
        t = r["competition_tier"]
        new_tiers[t] = new_tiers.get(t, 0) + 1

    avg_rank = sum(r.get("domain_rank", 0) for r in results) / max(1, total)
    avg_refs = sum(r.get("referring_domains", 0) for r in results) / max(1, total)

    lines = [
        f"\n  VALIDATION SUMMARY",
        f"  ─────────────────",
        f"  Total validated:    {total}",
        f"  Still sweet_spot:   {still_sweet}",
        f"  Score increased:    {promoted} (>5pt)",
        f"  Score decreased:    {demoted} (>5pt)",
        f"  New tier breakdown: {new_tiers}",
        f"  Avg domain rank:    {avg_rank:.0f}",
        f"  Avg referring doms: {avg_refs:.0f}",
    ]
    # Top 5 by new score
    top5 = sorted(results, key=lambda x: -x["reaper_score"])[:5]
    lines.append(f"\n  TOP 5 (post-validation):")
    for i, r in enumerate(top5, 1):
        lines.append(f"    {i}. {r['domain']} — score={r['reaper_score']}, "
                      f"DR={r.get('domain_rank', 0)}, refs={r.get('referring_domains', 0)}, "
                      f"tier={r['competition_tier']}")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────


def _load_env_settings(env_path: str) -> dict[str, str]:
    """Parse .env file into lowercase key dict."""
    assert isinstance(env_path, str)
    settings: dict[str, str] = {}
    if not os.path.isfile(env_path):
        return settings
    with open(env_path, encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            if idx > 200:
                break
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                settings[k.strip().lower()] = v.strip()
    assert isinstance(settings, dict)
    return settings


def _fetch_api_data(
    domains: list[str], login: str, password: str,
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Fetch ranks and summaries from DataForSEO. Returns (ranks, summaries)."""
    assert len(domains) > 0
    assert login and password
    auth = f"Basic {b64encode(f'{login}:{password}'.encode()).decode()}"
    print("\n  Calling DataForSEO bulk_ranks...", file=sys.stderr)
    ranks = asyncio.run(_fetch_bulk_ranks(domains, auth))
    print(f"  Got ranks for {len(ranks)} domains", file=sys.stderr)
    time.sleep(1)
    print("  Calling DataForSEO bulk_pages_summary...", file=sys.stderr)
    summaries = asyncio.run(_fetch_bulk_summary(domains, auth))
    print(f"  Got summaries for {len(summaries)} domains", file=sys.stderr)
    return ranks, summaries


def _reclassify_all(
    sweet_domains: list[dict[str, Any]],
    ranks: dict[str, int],
    summaries: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """Reclassify all sweet_spot domains with real data."""
    assert isinstance(sweet_domains, list) and len(sweet_domains) > 0
    assert isinstance(ranks, dict)
    validated: list[dict[str, Any]] = []
    for entry in sweet_domains:
        domain = entry["domain"]
        rank = ranks.get(domain, 0)
        summary = summaries.get(domain, {})
        refs = summary.get("referring_domains", 0)
        backlinks = summary.get("backlinks", 0)
        if rank == 0 and summary.get("rank", 0) > 0:
            rank = summary["rank"]
        validated.append(_rescore(entry, rank, refs, backlinks))
    validated.sort(key=lambda x: (-x["reaper_score"], x["domain"]))
    return validated


def _save_validation(validated: list[dict[str, Any]], input_path: str, out_path: str, api_called: bool) -> None:
    """Save validation results to JSON."""
    assert isinstance(validated, list) and len(validated) > 0
    assert isinstance(out_path, str) and len(out_path) > 0
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "sprint22_validation",
        "input_file": os.path.basename(input_path),
        "total_validated": len(validated),
        "api_called": api_called,
        "results": validated,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {out_path}", file=sys.stderr)


def main() -> None:
    """Run DataForSEO validation on sweet_spot domains."""
    import argparse
    parser = argparse.ArgumentParser(description="Sprint 22: Validate sweet_spot with real DataForSEO data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without API calls")
    parser.add_argument("--input", type=str, default=None, help="Custom input JSON path")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()
    assert isinstance(args.dry_run, bool)

    print("Sprint 22 — Agent 1: DataForSEO Validation Run", file=sys.stderr)
    input_path = args.input or _find_latest_reaper_json(_DATA_DIR)
    sweet_domains = _load_sweetspot_domains(input_path)
    assert sweet_domains, "No sweet_spot domains found"

    domains = [d["domain"] for d in sweet_domains if d.get("domain")]
    settings = _load_env_settings(os.path.join(_ROOT, ".env"))
    login = settings.get("dataforseo_login", "")
    password = settings.get("dataforseo_password", "")

    ranks: dict[str, int] = {}
    summaries: dict[str, dict[str, int]] = {}
    if not args.dry_run and login and password:
        ranks, summaries = _fetch_api_data(domains, login, password)
    else:
        print("  DRY RUN: Using mock data (domain_rank=0)", file=sys.stderr)

    validated = _reclassify_all(sweet_domains, ranks, summaries)
    print(f"\n{_format_validation_table(validated)}")
    print(_format_summary(validated), file=sys.stderr)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = args.output or os.path.join(_DATA_DIR, f"sprint22_validation_{date_str}.json")
    _save_validation(validated, input_path, out_path, not args.dry_run and bool(login))


if __name__ == "__main__":
    main()

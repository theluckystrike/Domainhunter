#!/usr/bin/env python3
"""Sprint 23 — LIVE DataForSEO Labs validation for all 38 sweet_spot domains.

Uses domain_rank_overview endpoint (works with current subscription, $0.01/domain).
Backlinks API returns 40204 (not subscribed), but Labs gives rank, ETV, keywords, backlinks.

Cost: 38 x $0.01 = $0.38
"""
from __future__ import annotations

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
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")

# Same scoring/classification as startup_reaper.py
_EDITORIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "techcrunch.com", "bloomberg.com", "forbes.com", "wsj.com", "nytimes.com",
    "cnbc.com", "reuters.com", "wired.com", "theverge.com", "bbc.com",
})


def _load_sweetspot() -> list[dict[str, Any]]:
    """Load sweet_spot domains from latest reaper output."""
    assert os.path.isdir(_DATA_DIR), f"data dir missing: {_DATA_DIR}"
    candidates = sorted(
        [f for f in os.listdir(_DATA_DIR)
         if f.startswith("startup_reaper_") and f.endswith(".json")
         and not f.startswith("startup_reaper_existing")],
        reverse=True,
    )
    assert len(candidates) > 0, "no reaper output found"
    path = os.path.join(_DATA_DIR, candidates[0])
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [r for r in data.get("results", []) if r.get("competition_tier") == "sweet_spot"]


def _fetch_domain_metrics(domain: str, headers: dict[str, str]) -> dict[str, Any]:
    """Fetch domain rank overview from DataForSEO Labs."""
    assert isinstance(domain, str) and "." in domain
    assert isinstance(headers, dict) and "Authorization" in headers
    import httpx
    body = [{"target": domain}]
    try:
        resp = httpx.post(
            "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live",
            headers=headers, json=body, timeout=20,
        )
        data = resp.json()
        task = data.get("tasks", [{}])[0]
        cost = data.get("cost", 0)
        result = (task.get("result", [{}])[0] or {})
        items = result.get("items", None)
        if items and len(items) > 0:
            item = items[0]
            organic = item.get("organic", {})
            return {
                "rank": item.get("rank", 0) or 0,
                "etv": organic.get("etv", 0) or 0,
                "keywords": organic.get("count", 0) or 0,
                "backlinks": item.get("backlinks", 0) or 0,
                "referring_domains": item.get("referring_domains", 0) or 0,
                "cost": cost,
                "has_data": True,
            }
        return {"rank": 0, "etv": 0, "keywords": 0, "backlinks": 0, "referring_domains": 0,
                "cost": cost, "has_data": False}
    except Exception as exc:
        print(f"  ERROR {domain}: {exc}", file=sys.stderr)
        return {"rank": 0, "etv": 0, "keywords": 0, "backlinks": 0, "referring_domains": 0,
                "cost": 0, "has_data": False}


def _competition_penalty(domain_rank: int) -> float:
    """Return score multiplier based on real domain rank."""
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


def _classify_competition(domain_rank: int, editorial_count: int) -> str:
    """Classify competition tier with real DR data."""
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


def _update_breakdown(breakdown: dict[str, float], rank: int, refs: int) -> dict[str, float]:
    """Update score breakdown with real DA and traffic data."""
    assert isinstance(breakdown, dict)
    assert isinstance(rank, int) and rank >= 0
    if rank > 0:
        breakdown["domain_authority"] = min(95.0, max(10.0, math.log10(rank + 1) * 12))
    if refs == 0:
        breakdown["traffic_value"] = 0.0
    elif refs < 10:
        breakdown["traffic_value"] = 10.0
    elif refs < 50:
        breakdown["traffic_value"] = 30.0
    elif refs < 100:
        breakdown["traffic_value"] = 50.0
    elif refs < 500:
        breakdown["traffic_value"] = 70.0
    else:
        breakdown["traffic_value"] = 90.0
    return breakdown


def _compute_weighted(breakdown: dict[str, float], rank: int) -> float:
    """Compute weighted score with competition penalty."""
    assert isinstance(breakdown, dict)
    assert isinstance(rank, int) and rank >= 0
    weights = {
        "funding": 0.15, "domain_authority": 0.10, "drop_certainty": 0.15,
        "editorial_links": 0.25, "domain_age": 0.05, "niche_fit": 0.10,
        "domain_name_value": 0.10, "traffic_value": 0.05, "trademark_safety": 0.05,
    }
    raw = sum(breakdown.get(k, 0) * weights[k] for k in weights)
    return round(min(100.0, max(0.0, raw * _competition_penalty(rank))), 1)


def _rescore(entry: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Rescore with real data."""
    assert isinstance(entry, dict) and "domain" in entry
    assert isinstance(metrics, dict)
    breakdown = _update_breakdown(
        dict(entry.get("score_breakdown", {})),
        metrics.get("rank", 0), metrics.get("referring_domains", 0),
    )
    old_score = entry.get("reaper_score", 0)
    rank = metrics.get("rank", 0)
    new_score = _compute_weighted(breakdown, rank)
    new_comp = _classify_competition(rank, len(entry.get("press_mentions", [])))

    if new_score >= 75:
        tier = "critical"
    elif new_score >= 55:
        tier = "high"
    elif new_score >= 35:
        tier = "medium"
    else:
        tier = "low"

    return {
        **entry,
        "domain_rank": rank, "referring_domains": metrics.get("referring_domains", 0),
        "total_backlinks": metrics.get("backlinks", 0),
        "etv_real": metrics.get("etv", 0), "keywords_real": metrics.get("keywords", 0),
        "reaper_score_old": old_score, "reaper_score": new_score,
        "score_delta": round(new_score - old_score, 1),
        "competition_tier_old": entry.get("competition_tier", "junk"),
        "competition_tier": new_comp, "tier": tier,
        "score_breakdown": breakdown, "validated": True,
        "has_data": metrics.get("has_data", False),
    }


def _load_credentials() -> tuple[str, str]:
    """Load DataForSEO credentials from .env. Returns (login, password)."""
    env_path = os.path.join(_ROOT, ".env")
    assert os.path.isfile(env_path), f".env not found: {env_path}"
    settings: dict[str, str] = {}
    with open(env_path, encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            if idx > 200:
                break
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip()
    login = settings.get("DATAFORSEO_LOGIN", "")
    password = settings.get("DATAFORSEO_PASSWORD", "")
    assert login and password, "DataForSEO credentials missing from .env"
    return login, password


def _fetch_all_metrics(
    sweet: list[dict[str, Any]], headers: dict[str, str],
) -> tuple[list[dict[str, Any]], float]:
    """Fetch and rescore all sweet_spot domains. Returns (validated, total_cost)."""
    assert len(sweet) > 0
    assert isinstance(headers, dict)
    total_cost = 0.0
    validated: list[dict[str, Any]] = []
    for i, entry in enumerate(sweet):
        domain = entry["domain"]
        metrics = _fetch_domain_metrics(domain, headers)
        total_cost += metrics.get("cost", 0)
        result = _rescore(entry, metrics)
        validated.append(result)
        status = "DATA" if metrics["has_data"] else "NONE"
        delta = result["score_delta"]
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"  [{i+1:>2}/{len(sweet)}] {domain:<28} {status:>4}  "
              f"rank={metrics.get('rank', 0):>8}  refs={metrics.get('referring_domains', 0):>6}  "
              f"score: {result['reaper_score_old']:.1f}->{result['reaper_score']:.1f} ({delta_str})  "
              f"{result['competition_tier_old']}->{result['competition_tier']}",
              file=sys.stderr)
        time.sleep(0.3)
    validated.sort(key=lambda x: (-x["reaper_score"], x["domain"]))
    return validated, total_cost


def _print_summary(validated: list[dict[str, Any]], total_cost: float) -> dict[str, int]:
    """Print validation summary to stderr. Returns stats dict."""
    assert isinstance(validated, list) and len(validated) > 0
    assert total_cost >= 0
    with_data = sum(1 for v in validated if v.get("has_data"))
    still_sweet = sum(1 for v in validated if v["competition_tier"] == "sweet_spot")
    to_stretch = sum(1 for v in validated if v["competition_tier_old"] == "sweet_spot" and v["competition_tier"] == "stretch")
    to_auction = sum(1 for v in validated if v["competition_tier_old"] == "sweet_spot" and v["competition_tier"] == "auction")
    to_junk = sum(1 for v in validated if v["competition_tier_old"] == "sweet_spot" and v["competition_tier"] == "junk")
    upgraded = sum(1 for v in validated if v["score_delta"] > 5)
    downgraded = sum(1 for v in validated if v["score_delta"] < -5)

    print(f"\n{'='*100}", file=sys.stderr)
    print(f"  VALIDATION RESULTS (LIVE API)", file=sys.stderr)
    print(f"  Total cost: ${total_cost:.2f}", file=sys.stderr)
    print(f"  Domains with data: {with_data}/{len(validated)}", file=sys.stderr)
    print(f"  VALIDATED sweet_spot: {still_sweet}", file=sys.stderr)
    print(f"  RECLASSIFIED: stretch={to_stretch}, auction={to_auction}, junk={to_junk}", file=sys.stderr)
    print(f"  Score changes: +5pt={upgraded}, -5pt={downgraded}", file=sys.stderr)

    print(f"\n  TOP 5 VALIDATED:", file=sys.stderr)
    for i, v in enumerate(validated[:5], 1):
        print(f"    {i}. {v['domain']} -- score={v['reaper_score']} (was {v['reaper_score_old']}), "
              f"rank={v.get('domain_rank', 0)}, tier={v['competition_tier']}", file=sys.stderr)
    print(f"{'='*100}", file=sys.stderr)

    return {"with_data": with_data, "still_sweet": still_sweet,
            "to_stretch": to_stretch, "to_auction": to_auction, "to_junk": to_junk}


def _print_table(validated: list[dict[str, Any]]) -> None:
    """Print ASCII results table to stdout."""
    assert isinstance(validated, list) and len(validated) > 0
    assert all("reaper_score" in v for v in validated[:5])
    hdr = (f"{'#':>3}  {'Domain':<28} {'Old':>5} {'New':>5} {'D':>5}  "
           f"{'OldComp':<11} {'NewComp':<11} {'Rank':>8}  {'Refs':>6}  {'BL':>8}  "
           f"{'ETV':>8}  {'KW':>5}  {'Fund':>8}")
    sep = "-" * len(hdr)
    print(sep)
    print(hdr)
    print(sep)
    for i, v in enumerate(validated, 1):
        fund = v.get("funding_usd", 0)
        fund_s = f"${fund/1e6:.0f}M" if fund >= 1e6 else "$0"
        d = v["score_delta"]
        d_s = f"+{d}" if d > 0 else str(d)
        print(f"{i:>3}  {v['domain']:<28} {v['reaper_score_old']:>5.1f} {v['reaper_score']:>5.1f} {d_s:>5}  "
              f"{v['competition_tier_old']:<11} {v['competition_tier']:<11} "
              f"{v.get('domain_rank', 0):>8}  {v.get('referring_domains', 0):>6}  "
              f"{v.get('total_backlinks', 0):>8}  "
              f"{v.get('etv_real', 0):>8.0f}  {v.get('keywords_real', 0):>5}  {fund_s:>8}")
    print(sep)


def _save_results(validated: list[dict[str, Any]], total_cost: float, stats: dict[str, int]) -> None:
    """Save validation results to JSON."""
    assert isinstance(validated, list) and len(validated) > 0
    assert total_cost >= 0
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(_DATA_DIR, f"sprint23_validation_{date_str}.json")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "sprint23_live_validation",
        "total_validated": len(validated),
        "api_cost": total_cost,
        **stats,
        "results": validated,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {out_path}", file=sys.stderr)


def main() -> None:
    """Run live validation."""
    print("Sprint 23 — LIVE DataForSEO Labs Validation", file=sys.stderr)
    assert os.path.isdir(_ROOT)

    login, password = _load_credentials()
    auth = f"Basic {b64encode(f'{login}:{password}'.encode()).decode()}"
    headers = {"Authorization": auth, "Content-Type": "application/json"}

    sweet = _load_sweetspot()
    assert len(sweet) > 0, "No sweet_spot domains found"
    print(f"  Loaded {len(sweet)} sweet_spot domains", file=sys.stderr)

    validated, total_cost = _fetch_all_metrics(sweet, headers)
    stats = _print_summary(validated, total_cost)
    _print_table(validated)
    _save_results(validated, total_cost, stats)


if __name__ == "__main__":
    main()

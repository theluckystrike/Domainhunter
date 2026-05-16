#!/usr/bin/env python3
"""Sprint 22 — Agent 4: Post-Catch Playbook Generator.

For each sweet_spot/stretch domain, generates a post-catch strategy:
  1. REDIRECT — park on expired domain, redirect traffic to new site
  2. REBUILD — rebuild as authority site in the niche
  3. FLIP — sell to end user, competitor, or on marketplace

Uses domain metadata (funding, sector, press, DA, backlinks) to recommend
the optimal strategy and estimate potential value.

Usage:
  python scripts/sprint22_playbook.py                  # All sweet_spot/stretch
  python scripts/sprint22_playbook.py --domain X.com   # Specific domain
  python scripts/sprint22_playbook.py --json            # JSON output

NASA P10: functions <60 lines, 2+ assertions, bounded loops, no global mutable.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")


def _load_candidates(domain_filter: str | None = None) -> list[dict[str, Any]]:
    """Load sweet_spot/stretch domains from latest reaper output."""
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
    results = data.get("results", [])
    filtered = [r for r in results if r.get("competition_tier") in ("sweet_spot", "stretch")]
    if domain_filter:
        filtered = [r for r in filtered if r["domain"].lower() == domain_filter.lower()]
    return filtered


def _estimate_value(entry: dict[str, Any]) -> dict[str, Any]:
    """Estimate domain value range based on metrics."""
    assert isinstance(entry, dict) and "domain" in entry
    assert entry.get("funding_usd", 0) >= 0
    funding = entry.get("funding_usd", 0)
    refs = entry.get("referring_domains", 0)
    rank = entry.get("domain_rank", 0)
    press = len(entry.get("press_mentions", []))
    score = entry.get("reaper_score", 0)
    tld = entry.get("tld", ".com")
    domain = entry.get("domain", "")
    name = domain.rsplit(".", 1)[0] if "." in domain else domain

    # Base value from funding (most funded startup domains attract end-user buyers)
    if funding >= 500_000_000:
        base_low, base_high = 5000, 50000
    elif funding >= 100_000_000:
        base_low, base_high = 2000, 20000
    elif funding >= 50_000_000:
        base_low, base_high = 1000, 10000
    elif funding >= 10_000_000:
        base_low, base_high = 500, 5000
    else:
        base_low, base_high = 100, 1000

    # TLD multiplier
    tld_mult = 1.0 if tld == ".com" else 0.5 if tld in (".io", ".ai", ".co") else 0.3

    # Name quality multiplier
    name_mult = 1.5 if len(name) <= 6 and name.isalpha() else 1.0 if name.isalpha() else 0.6

    # Press/brand recognition multiplier
    press_mult = 1.3 if press >= 3 else 1.1 if press >= 1 else 0.8

    low = int(base_low * tld_mult * name_mult * press_mult)
    high = int(base_high * tld_mult * name_mult * press_mult)

    return {"low": low, "high": high, "roi_low": round(low / 10.99, 0), "roi_high": round(high / 10.99, 0)}


def _build_strategies(
    domain: str, funding: int, refs: int, rank: int, press: int,
    sector: str, backlinks: int, tld: str, name: str,
) -> list[dict[str, Any]]:
    """Build list of candidate strategies for a domain."""
    assert isinstance(domain, str) and len(domain) > 0
    assert funding >= 0
    strategies: list[dict[str, Any]] = []
    if funding >= 50_000_000 or (press >= 3 and tld == ".com"):
        strategies.append({
            "strategy": "FLIP", "priority": 1,
            "description": f"Sell to end-user or competitor in {sector} space",
            "channels": ["Afternic", "Sedo", "Dan.com", f"direct outreach to {sector} companies"],
            "timeline": "1-6 months",
            "reasoning": f"${funding / 1e6:.0f}M funded brand with {press} press mentions = strong buyer interest",
        })
    if refs > 0 or rank > 0 or backlinks > 0:
        strategies.append({
            "strategy": "REDIRECT", "priority": 2 if strategies else 1,
            "description": f"301-redirect to affiliate/authority site in {sector} niche",
            "channels": ["Set up redirect immediately post-catch", "Build landing page within 48h"],
            "timeline": "Immediate (day 1)",
            "reasoning": f"DR={rank}, {refs} referring domains, {backlinks} backlinks = existing link equity to capture",
        })
    growing_niches = {"ai", "llm", "autonomous", "fintech", "crypto", "devtools", "saas"}
    if any(n in sector.lower() for n in growing_niches) or (len(name) <= 8 and name.isalpha()):
        strategies.append({
            "strategy": "REBUILD",
            "priority": 3 if len(strategies) >= 2 else 2 if strategies else 1,
            "description": f"Rebuild as micro-authority site in {sector}",
            "channels": ["WordPress/Ghost blog", "Monetize via ads/affiliates", "Build email list"],
            "timeline": "3-12 months to revenue",
            "reasoning": f"Brandable name '{name}' in growing {sector} niche = long-term asset",
        })
    if not strategies:
        strategies.append({
            "strategy": "FLIP", "priority": 1,
            "description": "List on domain marketplaces at markup",
            "channels": ["Afternic", "Sedo", "Dan.com"],
            "timeline": "1-12 months", "reasoning": "Default strategy: list and wait for buyer",
        })
    return strategies


def _recommend_strategy(entry: dict[str, Any]) -> dict[str, Any]:
    """Recommend post-catch strategy for a domain."""
    assert isinstance(entry, dict) and "domain" in entry
    assert entry.get("funding_usd", 0) >= 0
    domain = entry.get("domain", "")
    name = domain.rsplit(".", 1)[0] if "." in domain else domain
    strategies = _build_strategies(
        domain, entry.get("funding_usd", 0), entry.get("referring_domains", 0),
        entry.get("domain_rank", 0), len(entry.get("press_mentions", [])),
        entry.get("sector", ""), entry.get("total_backlinks", 0),
        entry.get("tld", ".com"), name,
    )
    return {
        "domain": domain,
        "strategies": sorted(strategies, key=lambda x: x["priority"]),
        "primary": strategies[0]["strategy"],
    }


def _format_playbook(entries: list[dict[str, Any]]) -> str:
    """Format post-catch playbooks as ASCII report."""
    assert isinstance(entries, list) and len(entries) > 0
    assert all(isinstance(e, dict) for e in entries[:10])
    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("  DOMAIN HUNTER — POST-CATCH PLAYBOOK (Sprint 22)")
    lines.append(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"  Domains: {len(entries)} sweet_spot/stretch candidates")
    lines.append("=" * 100)

    for i, e in enumerate(entries, 1):
        playbook = _recommend_strategy(e)
        value = _estimate_value(e)
        funding = e.get("funding_usd", 0)
        fund_str = f"${funding / 1e6:.0f}M" if funding >= 1e6 else f"${funding / 1e3:.0f}K" if funding >= 1e3 else "$0"

        lines.append(f"\n  {'─' * 96}")
        lines.append(f"  [{i}] {e['domain']}  |  {e.get('company_name', '?')}  |  "
                     f"Funded: {fund_str}  |  Score: {e.get('reaper_score', 0)}")
        lines.append(f"      Sector: {e.get('sector', '?')}  |  "
                     f"Press: {len(e.get('press_mentions', []))}  |  "
                     f"EPP: {e.get('epp_status', '?')}  |  "
                     f"Competition: {e.get('competition_tier', '?')}")
        lines.append(f"      Est. Value: ${value['low']:,}–${value['high']:,}  |  "
                     f"ROI: {value['roi_low']:.0f}x–{value['roi_high']:.0f}x (at $10.99 catch)")

        for s in playbook["strategies"]:
            marker = " ***" if s["priority"] == 1 else ""
            lines.append(f"      [{s['strategy']}]{marker} {s['description']}")
            lines.append(f"        Channels: {', '.join(s['channels'][:3])}")
            lines.append(f"        Timeline: {s['timeline']}")
            lines.append(f"        Why: {s['reasoning']}")

    # Summary
    total_low = sum(_estimate_value(e)["low"] for e in entries)
    total_high = sum(_estimate_value(e)["high"] for e in entries)
    lines.append(f"\n{'=' * 100}")
    lines.append(f"  PORTFOLIO VALUE ESTIMATE")
    lines.append(f"  Total catch cost: ${len(entries) * 10.99:.2f}")
    lines.append(f"  Est. portfolio value: ${total_low:,}–${total_high:,}")
    lines.append(f"  Est. portfolio ROI: {total_low / max(1, len(entries) * 10.99):.0f}x–"
                 f"{total_high / max(1, len(entries) * 10.99):.0f}x")
    lines.append("=" * 100)

    return "\n".join(lines)


def main() -> None:
    """Generate post-catch playbooks."""
    import argparse
    parser = argparse.ArgumentParser(description="Sprint 22: Post-Catch Playbook Generator")
    parser.add_argument("--domain", type=str, default=None, help="Specific domain to analyze")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()
    assert isinstance(args.json, bool)

    print("Sprint 22 — Agent 4: Post-Catch Playbook", file=sys.stderr)

    entries = _load_candidates(args.domain)
    assert isinstance(entries, list)
    print(f"  Loaded {len(entries)} candidates", file=sys.stderr)

    if not entries:
        print("  No sweet_spot/stretch domains found", file=sys.stderr)
        return

    if args.json:
        output = []
        for e in entries:
            playbook = _recommend_strategy(e)
            value = _estimate_value(e)
            output.append({**e, "playbook": playbook, "value_estimate": value})
        json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    else:
        print(f"\n{_format_playbook(entries)}")

    # Save
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(_DATA_DIR, f"sprint22_playbooks_{date_str}.json")
    output_data = []
    for e in entries:
        playbook = _recommend_strategy(e)
        value = _estimate_value(e)
        output_data.append({**e, "playbook": playbook, "value_estimate": value})
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output_data, fh, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

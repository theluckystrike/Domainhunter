#!/usr/bin/env python3
"""Sweet Spot Filter — Lane A of the Two-Lane Pipeline.

Filters daily drop feeds for DR 20-34 domains with low auction competition.
Uses competition predictor (pure name-based scoring, zero API calls) and
spam detection from longtail_drop_scanner.

Usage:
    python3 scripts/sweet_spot_filter.py                    # Full filter
    python3 scripts/sweet_spot_filter.py --dry-run          # Show plan only
    python3 scripts/sweet_spot_filter.py --max-results 20   # Cap output
    python3 scripts/sweet_spot_filter.py --input file.json  # From saved feed

NASA Power of 10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Project root setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    LANE_A_DEFAULT_MAX_RESULTS,
    LANE_A_DR_MAX,
    LANE_A_DR_MIN,
    LANE_A_MAX_SPAM,
    LANE_A_MIN_COMPETITION,
    MAX_LOOP_ITERATIONS,
)
from models.competition import (
    SweetSpotCandidate,
    build_sweet_spot_candidate,
    predict_competition,
)
from scripts.longtail_drop_scanner import (
    DropCandidate,
    compute_spam_score,
    parse_domain_parts,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ROOT: Final[str] = str(_PROJECT_ROOT)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_LOG = logging.getLogger("sweet_spot_filter")


# ---------------------------------------------------------------------------
# Core filter
# ---------------------------------------------------------------------------
def filter_sweet_spot(
    candidates: list[DropCandidate],
    max_results: int = LANE_A_DEFAULT_MAX_RESULTS,
    dr_min: int = LANE_A_DR_MIN,
    dr_max: int = LANE_A_DR_MAX,
    min_competition_score: float = LANE_A_MIN_COMPETITION,
    max_spam: float = LANE_A_MAX_SPAM,
) -> list[SweetSpotCandidate]:
    """Filter feed candidates through sweet spot gate.

    Applies: DR range → spam check → competition score → rank → cap.
    Returns sorted list of SweetSpotCandidate (best first).
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert max_results > 0, "max_results must be positive"
    assert dr_min <= dr_max, "dr_min must be <= dr_max"

    results: list[SweetSpotCandidate] = []

    for i, c in enumerate(candidates):
        if i >= MAX_LOOP_ITERATIONS:
            _LOG.warning("Hit loop bound at %d candidates", MAX_LOOP_ITERATIONS)
            break

        # Use trust_flow as DR proxy (TF correlates with DR at ~0.7)
        dr_estimate = c.trust_flow if c.trust_flow > 0 else 0

        # DR gate (fast reject)
        if dr_estimate < dr_min or dr_estimate > dr_max:
            continue

        # Spam gate
        spam = compute_spam_score(c)
        if spam > max_spam:
            continue

        # Competition gate
        comp = predict_competition(c.domain)
        if comp < min_competition_score:
            continue

        candidate = build_sweet_spot_candidate(
            domain=c.domain,
            sld=c.sld,
            tld=c.tld,
            source=c.source,
            dr_estimate=dr_estimate,
            referring_domains=max(c.referring_domains, c.semrush_rd),
            age_years=c.age_years,
            spam_score=spam,
            registrar_class="UNKNOWN",
            drop_date=c.drop_date,
        )
        if candidate is not None:
            results.append(candidate)

    ranked = rank_candidates(results)
    return ranked[:max_results]


def rank_candidates(
    candidates: list[SweetSpotCandidate],
) -> list[SweetSpotCandidate]:
    """Rank sweet spot candidates. Best opportunities first.

    Sort order: competition_score DESC, age DESC, referring_domains DESC.
    """
    assert isinstance(candidates, list), "candidates must be list"

    return sorted(
        candidates,
        key=lambda c: (c.competition_score, c.age_years, c.referring_domains),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_lane_a_output(
    candidates: list[SweetSpotCandidate],
    output_path: str,
) -> int:
    """Write Lane A candidates to JSON file.

    Returns number of candidates written.
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert isinstance(output_path, str) and len(output_path) > 0, "path required"

    records = []
    for c in candidates:
        records.append({
            "domain": c.domain,
            "sld": c.sld,
            "tld": c.tld,
            "source": c.source,
            "dr_estimate": c.dr_estimate,
            "referring_domains": c.referring_domains,
            "age_years": c.age_years,
            "competition_score": round(c.competition_score, 4),
            "spam_score": round(c.spam_score, 4),
            "registrar_class": c.registrar_class,
            "word_count": c.word_count,
            "char_count": c.char_count,
            "has_hyphens": c.has_hyphens,
            "has_numbers": c.has_numbers,
            "drop_date": c.drop_date,
            "lane": c.lane,
        })

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"candidates": records, "count": len(records)}, f, indent=2)

    return len(records)


def load_lane_a_output(path: str) -> list[dict[str, Any]]:
    """Load Lane A candidates from JSON file."""
    assert isinstance(path, str) and len(path) > 0, "path required"

    if not os.path.isfile(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, dict), "Lane A output must be a JSON object"
    return data.get("candidates", [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Sweet Spot Filter — Lane A of the Two-Lane Pipeline",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show filtered candidates without writing output",
    )
    parser.add_argument(
        "--max-results", type=int, default=LANE_A_DEFAULT_MAX_RESULTS,
        help=f"Maximum candidates to output (default: {LANE_A_DEFAULT_MAX_RESULTS})",
    )
    parser.add_argument(
        "--dr-min", type=int, default=LANE_A_DR_MIN,
        help=f"Minimum DR estimate (default: {LANE_A_DR_MIN})",
    )
    parser.add_argument(
        "--dr-max", type=int, default=LANE_A_DR_MAX,
        help=f"Maximum DR estimate (default: {LANE_A_DR_MAX})",
    )
    parser.add_argument(
        "--input", type=str, default="",
        help="Path to saved feed JSON (skips live download)",
    )
    parser.add_argument(
        "--output", type=str, default="",
        help="Output path for candidates JSON",
    )
    return parser


def main() -> None:
    """CLI entry point for sweet spot filter."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    args = _build_parser().parse_args()

    # Load candidates
    if args.input:
        print(f"Loading feed from {args.input}...", file=sys.stderr)
        with open(args.input, "r", encoding="utf-8") as f:
            raw = json.load(f)
        rows = raw if isinstance(raw, list) else raw.get("candidates", [])
        # Convert raw dicts to DropCandidate
        candidates: list[DropCandidate] = []
        for row in rows:
            sld, tld = parse_domain_parts(row.get("domain", ""))
            candidates.append(DropCandidate(
                domain=row.get("domain", ""),
                sld=sld, tld=tld,
                source=row.get("source", "file"),
                age_years=row.get("age_years", 0),
                trust_flow=row.get("trust_flow", row.get("dr_estimate", 0)),
                citation_flow=row.get("citation_flow", 0),
                referring_domains=row.get("referring_domains", 0),
                backlinks=row.get("backlinks", 0),
                drop_date=row.get("drop_date", ""),
                price=row.get("price", 0.0),
                valuation=row.get("valuation", 0.0),
                semrush_rd=row.get("semrush_rd", 0),
                semrush_traffic=row.get("semrush_traffic", 0),
            ))
    else:
        print("Fetching live feeds...", file=sys.stderr)
        from scripts.longtail_drop_scanner import (
            fetch_dropcatch_domains,
            fetch_godaddy_expiring,
            merge_sources,
        )
        dropcatch = fetch_dropcatch_domains()
        godaddy = fetch_godaddy_expiring()
        candidates = merge_sources(
            dropcatch, godaddy,
            allowed_tlds=frozenset({"com", "net"}),
            min_age=0,
        )

    print(f"Feed: {len(candidates):,} candidates", file=sys.stderr)

    # Filter
    t0 = time.monotonic()
    filtered = filter_sweet_spot(
        candidates,
        max_results=args.max_results,
        dr_min=args.dr_min,
        dr_max=args.dr_max,
    )
    elapsed = time.monotonic() - t0

    print(f"Sweet spot: {len(filtered)} candidates ({elapsed:.2f}s)", file=sys.stderr)

    # Display
    for i, c in enumerate(filtered):
        print(
            f"  {i + 1:3d}. {c.domain:<35s} "
            f"DR~{c.dr_estimate:2d}  comp={c.competition_score:.2f}  "
            f"spam={c.spam_score:.2f}  age={c.age_years}yr  "
            f"words={c.word_count}  {c.registrar_class}",
        )

    # Write output
    if not args.dry_run and filtered:
        output_path = args.output or os.path.join(
            _DATA_DIR, "lane_a_candidates.json",
        )
        count = write_lane_a_output(filtered, output_path)
        print(f"Wrote {count} candidates to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

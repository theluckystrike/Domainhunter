#!/usr/bin/env python3
"""Two-Lane Pipeline Runner — orchestrates Lane A + Lane B daily.

Fetches feeds ONCE, splits candidates by DR boundary, runs both lanes:
  Lane A (Sweet Spot Catcher): DR 20-34, auto-backorder, zero API cost
  Lane B (Whale Hunter): DR 35+, write candidates JSON, ntfy alert

Usage:
    python3 scripts/two_lane_runner.py                # Full run
    python3 scripts/two_lane_runner.py --dry-run      # No backorders
    python3 scripts/two_lane_runner.py --lane a       # Lane A only
    python3 scripts/two_lane_runner.py --lane b       # Lane B only

NASA Power of 10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Project root setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import LANE_A_DR_MAX, MAX_LOOP_ITERATIONS
from config.settings import Settings, load_settings
from scripts.authority_gate import enrich_with_authority_gate
from models.competition import SweetSpotCandidate
from scripts.longtail_drop_scanner import (
    DropCandidate,
    fetch_dropcatch_domains,
    fetch_godaddy_expiring,
    merge_sources,
)
from scripts.sweet_spot_filter import filter_sweet_spot, write_lane_a_output

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ROOT: Final[str] = str(_PROJECT_ROOT)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_LOG = logging.getLogger("two_lane_runner")
_DEFAULT_DR_BOUNDARY: Final[int] = 35
_DYNADOT_COST: Final[float] = 10.99
_DROPCATCH_COST: Final[float] = 59.00
_COMPETITION_STACK_THRESHOLD: Final[float] = 0.60


# ---------------------------------------------------------------------------
# Frozen result dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LaneResult:
    """Immutable result from running a single lane."""

    lane: str
    candidates_in: int
    candidates_out: int
    backorders_placed: int
    cost: float
    duration_seconds: float
    errors: tuple[str, ...]

    def __post_init__(self) -> None:
        assert self.lane in ("A", "B"), f"Invalid lane: {self.lane}"
        assert self.candidates_in >= 0, "candidates_in must be non-negative"
        assert self.cost >= 0.0, "cost must be non-negative"


@dataclass(frozen=True)
class TwoLaneResult:
    """Immutable result from running both lanes."""

    date: str
    lane_a: LaneResult
    lane_b: LaneResult
    total_feed_size: int
    total_backorders: int
    total_cost: float

    def __post_init__(self) -> None:
        assert len(self.date) >= 10, "date must be YYYY-MM-DD format"
        assert self.total_feed_size >= 0, "total_feed_size must be non-negative"


# ---------------------------------------------------------------------------
# Feed functions
# ---------------------------------------------------------------------------
def fetch_all_feeds() -> list[DropCandidate]:
    """Fetch DropCatch + GoDaddy feeds and merge. Single download."""
    dropcatch = fetch_dropcatch_domains()
    godaddy = fetch_godaddy_expiring()

    candidates = merge_sources(
        dropcatch, godaddy,
        allowed_tlds=frozenset({"com", "net"}),
        min_age=0,
    )

    _LOG.info("Fetched %d candidates (DC=%d, GD=%d)",
              len(candidates), len(dropcatch), len(godaddy))
    return candidates


def split_by_lane(
    candidates: list[DropCandidate],
    dr_boundary: int = _DEFAULT_DR_BOUNDARY,
) -> tuple[list[DropCandidate], list[DropCandidate]]:
    """Split candidates into Lane A (below boundary) and Lane B (at/above).

    Uses trust_flow as DR proxy (TF correlates with DR at ~0.7).
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert 0 < dr_boundary <= 100, "dr_boundary out of range"

    lane_a: list[DropCandidate] = []
    lane_b: list[DropCandidate] = []

    for i, c in enumerate(candidates):
        if i >= MAX_LOOP_ITERATIONS:
            break
        dr_est = c.trust_flow if c.trust_flow > 0 else 0
        if dr_est < dr_boundary:
            lane_a.append(c)
        else:
            lane_b.append(c)

    _LOG.info("Split: Lane A=%d, Lane B=%d", len(lane_a), len(lane_b))
    return lane_a, lane_b


# ---------------------------------------------------------------------------
# Budget tracking
# ---------------------------------------------------------------------------
def load_daily_budget(budget_path: str, daily_budget: float) -> dict[str, Any]:
    """Load or initialize daily budget tracker."""
    assert isinstance(budget_path, str) and len(budget_path) > 0, "path required"
    assert daily_budget > 0, "daily_budget must be positive"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if os.path.isfile(budget_path):
        with open(budget_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            return data

    return {"date": today, "spent": 0.0, "remaining": daily_budget, "orders": []}


def update_daily_budget(
    budget_path: str,
    cost: float,
    domain: str,
    platform: str,
    daily_budget: float,
) -> float:
    """Deduct cost from daily budget. Returns remaining budget."""
    assert cost >= 0, "cost must be non-negative"
    assert len(domain) > 0, "domain required"

    data = load_daily_budget(budget_path, daily_budget)
    data["spent"] = data["spent"] + cost
    data["remaining"] = daily_budget - data["spent"]
    data["orders"].append({
        "domain": domain, "platform": platform,
        "cost": cost, "time": datetime.now(timezone.utc).isoformat(),
    })

    os.makedirs(os.path.dirname(budget_path) or ".", exist_ok=True)
    with open(budget_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return data["remaining"]


# ---------------------------------------------------------------------------
# Lane A runner
# ---------------------------------------------------------------------------
def run_lane_a(
    candidates: list[DropCandidate],
    settings: Settings,
    dry_run: bool = False,
) -> LaneResult:
    """Run Lane A: filter sweet spot → place backorders."""
    assert isinstance(candidates, list), "candidates must be list"
    t0 = time.monotonic()
    errors: list[str] = []

    # Filter
    filtered = filter_sweet_spot(
        candidates,
        max_results=settings.lane_a_max_backorders_day,
        dr_min=settings.lane_a_dr_min,
        dr_max=settings.lane_a_dr_max,
        min_competition_score=settings.lane_a_min_competition_score,
        max_spam=settings.lane_a_max_spam,
    )

    _LOG.info("Lane A: %d/%d candidates passed filter",
              len(filtered), len(candidates))

    # Write output
    output_path = os.path.join(_DATA_DIR, "lane_a_candidates.json")
    write_lane_a_output(filtered, output_path)

    # Place backorders
    backorders_placed = 0
    total_cost = 0.0

    if not dry_run and filtered:
        budget_data = load_daily_budget(
            settings.lane_a_budget_path, settings.lane_a_daily_budget,
        )
        remaining = budget_data["remaining"]

        backorders_placed, total_cost, bo_errors = _place_lane_a_backorders(
            filtered, settings, remaining,
        )
        errors.extend(bo_errors)

    elapsed = time.monotonic() - t0
    return LaneResult(
        lane="A",
        candidates_in=len(candidates),
        candidates_out=len(filtered),
        backorders_placed=backorders_placed,
        cost=total_cost,
        duration_seconds=round(elapsed, 2),
        errors=tuple(errors),
    )


def _place_lane_a_backorders(
    candidates: list[SweetSpotCandidate],
    settings: Settings,
    remaining_budget: float,
) -> tuple[int, float, list[str]]:
    """Place backorders for Lane A candidates. Returns (count, cost, errors)."""
    assert isinstance(candidates, list), "candidates must be list"

    placed = 0
    cost = 0.0
    errors: list[str] = []

    for c in candidates:
        if remaining_budget < _DYNADOT_COST:
            _LOG.warning("Budget exhausted ($%.2f remaining)", remaining_budget)
            break

        # Always try Dynadot ($10.99)
        dynadot_ok = _backorder_dynadot(c.domain, settings)
        if dynadot_ok:
            order_cost = _DYNADOT_COST
        else:
            errors.append(f"Dynadot failed: {c.domain}")
            order_cost = 0.0

        # Stack DropCatch ($59) if competition is lower (more contested)
        if c.competition_score < _COMPETITION_STACK_THRESHOLD:
            if remaining_budget >= _DYNADOT_COST + _DROPCATCH_COST:
                dc_ok = _backorder_dropcatch(c.domain, settings)
                if dc_ok:
                    order_cost += _DROPCATCH_COST
                else:
                    errors.append(f"DropCatch failed: {c.domain}")

        if order_cost > 0:
            placed += 1
            cost += order_cost
            remaining_budget -= order_cost
            update_daily_budget(
                settings.lane_a_budget_path, order_cost, c.domain,
                "dynadot+dropcatch" if order_cost > _DYNADOT_COST else "dynadot",
                settings.lane_a_daily_budget,
            )

    return placed, cost, errors


def _backorder_dynadot(domain: str, settings: Settings) -> bool:
    """Place a Dynadot backorder. Returns True on success."""
    assert len(domain) > 0, "domain required"

    if not settings.dynadot_api_key:
        _LOG.warning("Dynadot API key not configured, skipping %s", domain)
        return False

    try:
        from clients.dynadot_client import DynadotClient
        client = DynadotClient(api_key=settings.dynadot_api_key)
        result = asyncio.run(client.backorder(domain))
        _LOG.info("Dynadot backorder %s: %s", domain, result.message)
        return result.success
    except Exception as exc:
        _LOG.error("Dynadot error for %s: %s", domain, exc)
        return False


def _backorder_dropcatch(domain: str, settings: Settings) -> bool:
    """Place a DropCatch backorder. Returns True on success."""
    assert len(domain) > 0, "domain required"

    if not settings.dropcatch_client_id or not settings.dropcatch_api_secret:
        _LOG.warning("DropCatch credentials not configured, skipping %s", domain)
        return False

    try:
        from clients.dropcatch_client import DropCatchClient
        with DropCatchClient(
            client_id=settings.dropcatch_client_id,
            client_secret=settings.dropcatch_api_secret,
        ) as client:
            result = client.place_backorders([domain])
            _LOG.info("DropCatch backorder %s: %d placed", domain, result.placed)
            return result.placed > 0
    except Exception as exc:
        _LOG.error("DropCatch error for %s: %s", domain, exc)
        return False


# ---------------------------------------------------------------------------
# Lane B runner
# ---------------------------------------------------------------------------
def run_lane_b(
    candidates: list[DropCandidate],
    settings: Settings,
    dry_run: bool = False,
) -> LaneResult:
    """Run Lane B: filter whales → write JSON → ntfy alert."""
    assert isinstance(candidates, list), "candidates must be list"
    t0 = time.monotonic()
    errors: list[str] = []

    # Filter: DR 35+ and RD 500+
    whales: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        if i >= MAX_LOOP_ITERATIONS:
            break
        dr_est = c.trust_flow if c.trust_flow > 0 else 0
        rd = max(c.referring_domains, c.semrush_rd)
        if dr_est >= settings.whale_min_dr and rd >= settings.whale_min_rd:
            whales.append({
                "domain": c.domain,
                "dr_estimate": dr_est,
                "referring_domains": rd,
                "age_years": c.age_years,
                "source": c.source,
                "drop_date": c.drop_date,
            })

    _LOG.info("Lane B: %d/%d whales found", len(whales), len(candidates))

    # Write output
    if whales:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_path = os.path.join(_DATA_DIR, f"whale_candidates_{today}.json")
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"whales": whales, "count": len(whales), "date": today}, f, indent=2)
        _LOG.info("Wrote %d whales to %s", len(whales), output_path)

    # Send ntfy alert
    if whales and not dry_run:
        _send_whale_alert(whales)

    elapsed = time.monotonic() - t0
    return LaneResult(
        lane="B",
        candidates_in=len(candidates),
        candidates_out=len(whales),
        backorders_placed=0,
        cost=0.0,
        duration_seconds=round(elapsed, 2),
        errors=tuple(errors),
    )


def _send_whale_alert(whales: list[dict[str, Any]]) -> None:
    """Send ntfy push notification for whale candidates."""
    assert isinstance(whales, list) and len(whales) > 0, "whales required"

    try:
        from clients.ntfy_client import send_alert
        top = whales[:5]
        lines = [f"  {w['domain']} (DR~{w['dr_estimate']}, RD={w['referring_domains']})"
                 for w in top]
        message = f"{len(whales)} whale candidates found:\n" + "\n".join(lines)
        send_alert(
            title="Lane B: Whale Alert",
            message=message,
            priority="high",
            tags="whale,domain",
        )
    except Exception as exc:
        _LOG.error("Failed to send whale alert: %s", exc)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_two_lane(
    dry_run: bool = False,
    lane: str = "both",
) -> TwoLaneResult:
    """Run the full two-lane pipeline. Fetches feeds once, splits, runs both."""
    assert lane in ("a", "b", "both"), f"Invalid lane: {lane}"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    settings = load_settings()

    # Fetch feeds once
    _LOG.info("=== Two-Lane Pipeline — %s ===", today)
    all_candidates = fetch_all_feeds()

    # Authority Gate enrichment (replaces TF proxy with composite DR)
    if settings.authority_gate_enabled:
        _LOG.info("Running Authority Gate on %d candidates...", len(all_candidates))
        all_candidates = asyncio.run(
            enrich_with_authority_gate(all_candidates, settings)
        )
        _LOG.info("Authority Gate: %d candidates survived", len(all_candidates))

    lane_a_cands, lane_b_cands = split_by_lane(all_candidates)

    # Run lanes
    empty_result = LaneResult(
        lane="A", candidates_in=0, candidates_out=0,
        backorders_placed=0, cost=0.0, duration_seconds=0.0, errors=(),
    )

    if lane in ("a", "both"):
        result_a = run_lane_a(lane_a_cands, settings, dry_run)
    else:
        result_a = empty_result

    if lane in ("b", "both"):
        result_b = run_lane_b(lane_b_cands, settings, dry_run)
    else:
        result_b = LaneResult(
            lane="B", candidates_in=0, candidates_out=0,
            backorders_placed=0, cost=0.0, duration_seconds=0.0, errors=(),
        )

    total = TwoLaneResult(
        date=today,
        lane_a=result_a,
        lane_b=result_b,
        total_feed_size=len(all_candidates),
        total_backorders=result_a.backorders_placed + result_b.backorders_placed,
        total_cost=result_a.cost + result_b.cost,
    )

    # Summary
    _LOG.info("=== Results ===")
    _LOG.info("Feed: %d total candidates", total.total_feed_size)
    _LOG.info("Lane A: %d→%d candidates, %d backorders, $%.2f",
              result_a.candidates_in, result_a.candidates_out,
              result_a.backorders_placed, result_a.cost)
    _LOG.info("Lane B: %d→%d whales", result_b.candidates_in, result_b.candidates_out)
    _LOG.info("Total: %d backorders, $%.2f", total.total_backorders, total.total_cost)

    if result_a.errors:
        _LOG.warning("Lane A errors: %s", result_a.errors)
    if result_b.errors:
        _LOG.warning("Lane B errors: %s", result_b.errors)

    # Send summary ntfy
    if not dry_run:
        _send_summary_alert(total)

    return total


def _send_summary_alert(result: TwoLaneResult) -> None:
    """Send ntfy summary notification."""
    assert isinstance(result, TwoLaneResult), "result required"

    try:
        from clients.ntfy_client import send_alert
        message = (
            f"Two-Lane Pipeline — {result.date}\n"
            f"Feed: {result.total_feed_size:,}\n"
            f"Lane A: {result.lane_a.candidates_out} sweet spots, "
            f"{result.lane_a.backorders_placed} backorders (${result.lane_a.cost:.0f})\n"
            f"Lane B: {result.lane_b.candidates_out} whales\n"
            f"Total: ${result.total_cost:.0f}"
        )
        send_alert(
            title="Two-Lane Pipeline Complete",
            message=message,
            priority="default",
            tags="pipeline,daily",
        )
    except Exception as exc:
        _LOG.error("Failed to send summary alert: %s", exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Two-Lane Pipeline Runner",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without placing backorders or sending alerts",
    )
    parser.add_argument(
        "--lane", type=str, default="both", choices=["a", "b", "both"],
        help="Which lane to run (default: both)",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    args = _build_parser().parse_args()
    result = run_two_lane(dry_run=args.dry_run, lane=args.lane)

    # Print summary to stdout
    print(f"\n{'='*60}")
    print(f"Two-Lane Pipeline — {result.date}")
    print(f"{'='*60}")
    print(f"Feed size:        {result.total_feed_size:,}")
    print(f"Lane A in:        {result.lane_a.candidates_in:,}")
    print(f"Lane A out:       {result.lane_a.candidates_out}")
    print(f"Lane A backorders:{result.lane_a.backorders_placed}")
    print(f"Lane A cost:      ${result.lane_a.cost:.2f}")
    print(f"Lane B in:        {result.lane_b.candidates_in:,}")
    print(f"Lane B whales:    {result.lane_b.candidates_out}")
    print(f"Total cost:       ${result.total_cost:.2f}")
    if result.lane_a.errors:
        print(f"Lane A errors:    {len(result.lane_a.errors)}")
    if result.lane_b.errors:
        print(f"Lane B errors:    {len(result.lane_b.errors)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

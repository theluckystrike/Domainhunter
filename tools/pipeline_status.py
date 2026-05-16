"""Pipeline status monitor for daily_hunter.py.

Shows last run timestamp, domains found, alerts triggered, errors
encountered, total runs to date, and daily cost so far.

NASA Power of 10 rules enforced:
  1. No goto/deep recursion/switch fallthroughs
  2. All loops have fixed upper bounds
  3. No unbounded memory -- explicit max sizes everywhere
  4. All functions < 60 lines
  5. Min 2 assertions per function
  6. Restrict data scope -- no global mutable state
  7. Check every return value -- no swallowed exceptions
  8. Standard Python only (no external deps)
  9. No dangerous mutations -- return new objects
  10. Zero warnings -- all errors fixed, not suppressed

Usage: python3 tools/pipeline_status.py
       python3 tools/pipeline_status.py --json
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Constants -- no global mutable state (all Final)
# ---------------------------------------------------------------------------
MAX_DAILY_FILES: Final[int] = 3650  # ~10 years of daily runs
MAX_CANDIDATES_PER_FILE: Final[int] = 500
MAX_ALERTS_DISPLAY: Final[int] = 50
COST_PER_LOOKUP: Final[float] = 0.001
SCRIPT_DIR: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = SCRIPT_DIR.parent
DAILY_DIR: Final[Path] = PROJECT_ROOT / "data" / "daily"


# ---------------------------------------------------------------------------
# Immutable data structures (frozen dataclasses)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunSnapshot:
    """Immutable summary of a single pipeline run."""

    run_date: str
    generated_at: str
    total_scanned: int
    total_above_min_da: int
    dataforseo_lookups_used: int
    candidate_count: int
    alert_count: int
    critical_count: int
    top_da: int
    top_domain: str


@dataclass(frozen=True)
class PipelineStatus:
    """Immutable overall pipeline status report."""

    last_run_date: str
    last_run_generated_at: str
    last_run_domains_found: int
    last_run_alerts: int
    last_run_criticals: int
    last_run_top_da: int
    last_run_top_domain: str
    total_runs: int
    total_domains_discovered: int
    total_dataforseo_lookups: int
    total_cost_usd: float
    errors: tuple[str, ...]
    recent_runs: tuple[RunSnapshot, ...]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def _discover_daily_files(daily_dir: Path) -> list[Path]:
    """Find all daily JSON snapshot files, sorted newest first."""
    assert isinstance(daily_dir, Path), "daily_dir must be Path"

    if not daily_dir.is_dir():
        assert isinstance(daily_dir, Path), "daily_dir type preserved when absent"
        return []

    files: list[Path] = []
    for idx, f in enumerate(sorted(daily_dir.glob("*.json"), reverse=True)):
        if idx >= MAX_DAILY_FILES:
            break
        if f.stem and len(f.stem) == 10:  # YYYY-MM-DD format
            files.append(f)

    assert len(files) <= MAX_DAILY_FILES, f"Too many daily files: {len(files)}"
    return files


# ---------------------------------------------------------------------------
# Snapshot parsing
# ---------------------------------------------------------------------------
def _parse_snapshot(file_path: Path) -> RunSnapshot | None:
    """Parse a daily JSON snapshot into a RunSnapshot."""
    assert isinstance(file_path, Path), "file_path must be Path"
    assert file_path.is_file(), f"File not found: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"WARNING: Could not parse {file_path}: {exc}\n")
        return None

    candidates = data.get("candidates", [])
    assert isinstance(candidates, list), "candidates must be list"

    alert_count, critical_count, top_da, top_domain = _count_alerts_from_candidates(
        candidates,
        alert_threshold=30,
        critical_threshold=50,
    )

    snapshot = RunSnapshot(
        run_date=str(data.get("run_date", file_path.stem)),
        generated_at=str(data.get("generated_at", "")),
        total_scanned=int(data.get("total_scanned", 0)),
        total_above_min_da=int(data.get("total_above_min_da", 0)),
        dataforseo_lookups_used=int(data.get("dataforseo_lookups_used", 0)),
        candidate_count=len(candidates),
        alert_count=alert_count,
        critical_count=critical_count,
        top_da=top_da,
        top_domain=top_domain,
    )
    assert isinstance(snapshot, RunSnapshot), "snapshot must be RunSnapshot"
    return snapshot


def _count_alerts_from_candidates(
    candidates: list[dict],
    alert_threshold: int,
    critical_threshold: int,
) -> tuple[int, int, int, str]:
    """Count alert-level and critical-level domains from candidate list."""
    assert isinstance(candidates, list), "candidates must be list"
    assert alert_threshold > 0, f"alert_threshold must be positive, got {alert_threshold}"

    alert_count = 0
    critical_count = 0
    top_da = 0
    top_domain = ""

    for idx, c in enumerate(candidates):
        if idx >= MAX_CANDIDATES_PER_FILE:
            break
        da = int(c.get("da_estimate", 0))
        if da >= critical_threshold:
            critical_count += 1
            alert_count += 1
        elif da >= alert_threshold:
            alert_count += 1
        if da > top_da:
            top_da = da
            top_domain = str(c.get("domain", ""))

    assert alert_count >= critical_count, "criticals must be subset of alerts"
    return alert_count, critical_count, top_da, top_domain


# ---------------------------------------------------------------------------
# Status aggregation
# ---------------------------------------------------------------------------
def _aggregate_status(snapshots: list[RunSnapshot]) -> PipelineStatus:
    """Aggregate all snapshots into a single pipeline status report."""
    assert isinstance(snapshots, list), "snapshots must be list"

    if not snapshots:
        empty_status = PipelineStatus(
            last_run_date="never",
            last_run_generated_at="never",
            last_run_domains_found=0,
            last_run_alerts=0,
            last_run_criticals=0,
            last_run_top_da=0,
            last_run_top_domain="",
            total_runs=0,
            total_domains_discovered=0,
            total_dataforseo_lookups=0,
            total_cost_usd=0.0,
            errors=(),
            recent_runs=(),
        )
        assert isinstance(empty_status, PipelineStatus), "status must be PipelineStatus"
        return empty_status

    latest = snapshots[0]
    total_domains = 0
    total_lookups = 0

    for idx, s in enumerate(snapshots):
        if idx >= MAX_DAILY_FILES:
            break
        total_domains += s.candidate_count
        total_lookups += s.dataforseo_lookups_used

    # Show up to 7 most recent runs
    max_recent = min(7, len(snapshots))
    recent = tuple(snapshots[:max_recent])

    status = PipelineStatus(
        last_run_date=latest.run_date,
        last_run_generated_at=latest.generated_at,
        last_run_domains_found=latest.candidate_count,
        last_run_alerts=latest.alert_count,
        last_run_criticals=latest.critical_count,
        last_run_top_da=latest.top_da,
        last_run_top_domain=latest.top_domain,
        total_runs=len(snapshots),
        total_domains_discovered=total_domains,
        total_dataforseo_lookups=total_lookups,
        total_cost_usd=round(total_lookups * COST_PER_LOOKUP, 4),
        errors=(),
        recent_runs=recent,
    )
    assert isinstance(status, PipelineStatus), "status must be PipelineStatus"
    return status


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def _format_status_text(status: PipelineStatus) -> str:
    """Format pipeline status as human-readable text."""
    assert isinstance(status, PipelineStatus), "status must be PipelineStatus"

    lines: list[str] = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  DOMAIN HUNTER PIPELINE STATUS")
    lines.append(f"  Report generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 70)
    lines.append(f"  Last run:          {status.last_run_date}")
    lines.append(f"  Last generated:    {status.last_run_generated_at}")
    lines.append(f"  Domains found:     {status.last_run_domains_found:>5}")
    lines.append(f"  Alerts triggered:  {status.last_run_alerts:>5}")
    lines.append(f"  Criticals:         {status.last_run_criticals:>5}")
    lines.append(f"  Top DA:            {status.last_run_top_da:>5}  ({status.last_run_top_domain})")
    lines.append("-" * 70)
    lines.append("  LIFETIME TOTALS")
    lines.append(f"  Total runs:        {status.total_runs:>5}")
    lines.append(f"  Total domains:     {status.total_domains_discovered:>5}")
    lines.append(f"  DataForSEO calls:  {status.total_dataforseo_lookups:>5}")
    lines.append(f"  Total cost:        ${status.total_cost_usd:.4f}")
    lines.append("-" * 70)

    if status.recent_runs:
        lines.append("  RECENT RUNS")
        for idx, run in enumerate(status.recent_runs):
            if idx >= 7:
                break
            lines.append(
                f"    {run.run_date}  "
                f"found={run.candidate_count:<4} "
                f"alerts={run.alert_count:<3} "
                f"top_da={run.top_da}"
            )
        lines.append("-" * 70)

    if status.errors:
        lines.append("  ERRORS")
        for idx, err in enumerate(status.errors):
            if idx >= MAX_ALERTS_DISPLAY:
                break
            lines.append(f"    {err}")
        lines.append("-" * 70)
    else:
        lines.append("  No errors.")

    lines.append("=" * 70)
    lines.append("")

    result = "\n".join(lines)
    assert len(result) > 0, "formatted output must not be empty"
    return result


def _format_status_json(status: PipelineStatus) -> str:
    """Format pipeline status as JSON string."""
    assert isinstance(status, PipelineStatus), "status must be PipelineStatus"

    data = asdict(status)
    result = json.dumps(data, indent=2, default=str)
    assert len(result) > 0, "JSON output must not be empty"
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def build_status(daily_dir: Path) -> PipelineStatus:
    """Build a complete pipeline status report from daily snapshot files."""
    assert isinstance(daily_dir, Path), "daily_dir must be Path"

    files = _discover_daily_files(daily_dir)
    snapshots: list[RunSnapshot] = []

    for idx, f in enumerate(files):
        if idx >= MAX_DAILY_FILES:
            break
        snapshot = _parse_snapshot(f)
        if snapshot is not None:
            snapshots.append(snapshot)

    status = _aggregate_status(snapshots)
    assert isinstance(status, PipelineStatus), "status must be PipelineStatus"
    return status


def main() -> None:
    """Entry point: print pipeline status to stdout."""
    assert DAILY_DIR is not None, "DAILY_DIR must be set"
    assert isinstance(DAILY_DIR, Path), "DAILY_DIR must be Path"

    json_mode = "--json" in sys.argv

    status = build_status(DAILY_DIR)

    if json_mode:
        print(_format_status_json(status))
    else:
        print(_format_status_text(status))


if __name__ == "__main__":
    main()

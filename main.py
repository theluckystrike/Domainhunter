"""Domain Hunter REVENANT — Main Pipeline Orchestrator.

Entry point. Chains all 5 agents sequentially:
  SCOUT -> SENTINEL -> ARCHIVIST -> SPECTRE -> ORACLE

Usage:
  python -m main                        # Full pipeline (live APIs)
  python -m main --dry-run              # Mock data only
  python -m main --from-stage sentinel  # Resume from specific stage

NASA Power of 10 rules enforced throughout.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from agents import archivist, oracle, scout, sentinel, spectre
from config.settings import Settings, load_settings
from models.candidate import DomainCandidate
from models.scored import ScoredDomain
from models.verdict import DomainVerdict, VerdictType
from models.verified import VerifiedDomain
from models.vetted import VettedDomain
from notifications.notifier import Notifier
from storage.database import Database

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Valid pipeline stages in execution order
# ---------------------------------------------------------------------------
_STAGES: tuple[str, ...] = ("scout", "sentinel", "archivist", "spectre", "oracle")
_MAX_PIPELINE_STAGES: int = 10


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list. Defaults to sys.argv[1:].

    Returns:
        Parsed namespace with dry_run and from_stage attributes.
    """
    assert _STAGES is not None and len(_STAGES) == 5, "invalid stage list"
    assert _MAX_PIPELINE_STAGES > 0, "max stages must be positive"

    parser = argparse.ArgumentParser(
        description="Domain Hunter REVENANT — 5-agent expired domain pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run pipeline with mock data only (no API calls)",
    )
    parser.add_argument(
        "--from-stage",
        type=str,
        default="scout",
        choices=list(_STAGES),
        help="Resume pipeline from a specific stage (default: scout)",
    )
    return parser.parse_args(argv)


async def _execute_stages(
    settings: Settings,
    run_id: str,
    db: Database,
    start_idx: int,
    counts: dict[str, int],
    *,
    mock: bool = False,
) -> list[DomainVerdict]:
    """Execute pipeline stages from start_idx onward.

    Args:
        settings: Pipeline settings.
        run_id: Current run ID.
        db: Database for persistence.
        start_idx: Index into _STAGES to begin from.
        counts: Mutable dict to record stage output counts.
        mock: Use mock data if True.

    Returns:
        List of final DomainVerdict results.
    """
    assert 0 <= start_idx <= 4, "start_idx must be 0-4"
    assert isinstance(counts, dict), "counts must be dict"

    candidates: list[DomainCandidate] = []
    vetted: list[VettedDomain] = []
    verified: list[VerifiedDomain] = []
    scored: list[ScoredDomain] = []
    verdicts: list[DomainVerdict] = []

    if start_idx <= 0:
        candidates = await _run_stage_scout(settings, run_id, db, mock=mock)
        counts["scout"] = len(candidates)
    if start_idx <= 1:
        vetted = await _run_stage_sentinel(settings, candidates, run_id, db, mock=mock)
        counts["sentinel"] = len(vetted)
    if start_idx <= 2:
        verified = await _run_stage_archivist(settings, vetted, run_id, db, mock=mock)
        counts["archivist"] = len(verified)
    if start_idx <= 3:
        scored = await _run_stage_spectre(settings, verified, run_id, db, mock=mock)
        counts["spectre"] = len(scored)
    if start_idx <= 4:
        verdicts = await _run_stage_oracle(settings, scored, run_id, db, mock=mock)
        counts["oracle"] = len(verdicts)

    return verdicts


async def _handle_pipeline_failure(
    db: Database,
    notifier: Notifier,
    run_id: str,
    error_msg: str,
) -> None:
    """Handle pipeline failure: persist error and notify.

    Args:
        db: Database connection.
        notifier: Notification client.
        run_id: Pipeline run ID.
        error_msg: Error description string.
    """
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"
    assert isinstance(error_msg, str), "error_msg must be string"

    try:
        await db.complete_run(run_id, "failed", error=error_msg)
    except Exception:
        logger.error("db_complete_run_failed", run_id=run_id)
    try:
        await notifier.send_slack(f"Pipeline FAILED: {error_msg}")
    except Exception:
        logger.error("failure_notification_failed", run_id=run_id)


async def run_pipeline(
    settings: Settings, *, mock: bool = False, from_stage: str = "scout",
) -> dict[str, Any]:
    """Execute the full 5-agent pipeline and return results dict."""
    assert isinstance(settings, Settings), "settings must be Settings"
    assert from_stage in _STAGES, f"invalid from_stage: {from_stage}"

    run_id: str = uuid4().hex[:12]
    start_time: float = time.monotonic()
    start_idx: int = _STAGES.index(from_stage)
    counts: dict[str, int] = {s: 0 for s in _STAGES}
    result: dict[str, Any] = {
        "run_id": run_id, "counts": counts, "verdicts": [],
        "status": "running", "error": None,
    }
    db = Database(_extract_db_path(settings.database_url))
    notifier = Notifier(settings)
    logger.info("pipeline_start", run_id=run_id, mock=mock, from_stage=from_stage)

    try:
        await db.connect()
        await db.create_run(run_id)
        verdicts = await _execute_stages(settings, run_id, db, start_idx, counts, mock=mock)
        await _send_alerts(notifier, run_id, counts, verdicts)
        elapsed = time.monotonic() - start_time
        await db.complete_run(run_id, "completed")
        result.update(verdicts=verdicts, status="completed", elapsed_seconds=round(elapsed, 2))
        logger.info("pipeline_complete", run_id=run_id, elapsed=f"{elapsed:.1f}s", counts=counts)
    except Exception as exc:
        elapsed = time.monotonic() - start_time
        error_msg = f"{type(exc).__name__}: {exc}"
        result.update(status="failed", error=error_msg, elapsed_seconds=round(elapsed, 2))
        logger.error("pipeline_failed", run_id=run_id, error=error_msg)
        await _handle_pipeline_failure(db, notifier, run_id, error_msg)
    finally:
        await _cleanup(db, notifier)

    return result


async def _send_alerts(
    notifier: Notifier, run_id: str, counts: dict[str, int], verdicts: list[DomainVerdict],
) -> None:
    """Send BUY_NOW alerts and pipeline summary notification.

    Args:
        notifier: Notification client.
        run_id: Pipeline run ID.
        counts: Stage result counts.
        verdicts: Final domain verdicts.
    """
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"
    assert isinstance(verdicts, list), "verdicts must be list"

    for v_idx, verdict in enumerate(verdicts):
        if v_idx >= _MAX_PIPELINE_STAGES:
            break
        if verdict.verdict == VerdictType.BUY_NOW:
            await notifier.send_buy_alert(verdict)
    await notifier.send_pipeline_summary(run_id, counts, verdicts)


async def _cleanup(db: Database, notifier: Notifier) -> None:
    """Close database and notifier connections gracefully.

    Args:
        db: Database instance.
        notifier: Notifier instance.
    """
    assert db is not None, "db must not be None"
    assert notifier is not None, "notifier must not be None"

    try:
        await db.close()
    except Exception:
        pass
    try:
        await notifier.close()
    except Exception:
        pass


async def _run_stage_scout(
    settings: Settings,
    run_id: str,
    db: Database,
    *,
    mock: bool = False,
) -> list[DomainCandidate]:
    """Execute SCOUT discovery stage.

    Args:
        settings: Pipeline settings.
        run_id: Current pipeline run ID.
        db: Database for persistence.
        mock: Use mock data.

    Returns:
        List of discovered domain candidates.
    """
    assert isinstance(settings, Settings), "settings required"
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

    logger.info("stage_start", stage="scout", run_id=run_id)
    try:
        candidates = await scout.run(settings, mock=mock)
        await db.update_run_stage(run_id, "scout", len(candidates))
        await db.save_candidates(run_id, "scout", candidates)
        logger.info("stage_complete", stage="scout", count=len(candidates))
        return candidates
    except Exception as exc:
        logger.error("stage_failed", stage="scout", error=str(exc))
        raise


async def _run_stage_sentinel(
    settings: Settings,
    candidates: list[DomainCandidate],
    run_id: str,
    db: Database,
    *,
    mock: bool = False,
) -> list[VettedDomain]:
    """Execute SENTINEL vetting stage.

    Args:
        settings: Pipeline settings.
        candidates: Input from SCOUT.
        run_id: Current pipeline run ID.
        db: Database for persistence.
        mock: Use mock data.

    Returns:
        List of vetted domains.
    """
    assert isinstance(settings, Settings), "settings required"
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

    logger.info("stage_start", stage="sentinel", run_id=run_id, input_count=len(candidates))
    try:
        vetted = await sentinel.run(settings, candidates, mock=mock)
        await db.update_run_stage(run_id, "sentinel", len(vetted))
        await db.save_candidates(run_id, "sentinel", vetted)
        logger.info("stage_complete", stage="sentinel", count=len(vetted))
        return vetted
    except Exception as exc:
        logger.error("stage_failed", stage="sentinel", error=str(exc))
        raise


async def _run_stage_archivist(
    settings: Settings,
    vetted: list[VettedDomain],
    run_id: str,
    db: Database,
    *,
    mock: bool = False,
) -> list[VerifiedDomain]:
    """Execute ARCHIVIST verification stage.

    Args:
        settings: Pipeline settings.
        vetted: Input from SENTINEL.
        run_id: Current pipeline run ID.
        db: Database for persistence.
        mock: Use mock data.

    Returns:
        List of verified domains.
    """
    assert isinstance(settings, Settings), "settings required"
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

    logger.info("stage_start", stage="archivist", run_id=run_id, input_count=len(vetted))
    try:
        verified = await archivist.run(settings, vetted, mock=mock)
        await db.update_run_stage(run_id, "archivist", len(verified))
        await db.save_candidates(run_id, "archivist", verified)
        logger.info("stage_complete", stage="archivist", count=len(verified))
        return verified
    except Exception as exc:
        logger.error("stage_failed", stage="archivist", error=str(exc))
        raise


async def _run_stage_spectre(
    settings: Settings,
    verified: list[VerifiedDomain],
    run_id: str,
    db: Database,
    *,
    mock: bool = False,
) -> list[ScoredDomain]:
    """Execute SPECTRE niche scoring stage.

    Args:
        settings: Pipeline settings.
        verified: Input from ARCHIVIST.
        run_id: Current pipeline run ID.
        db: Database for persistence.
        mock: Use mock data.

    Returns:
        List of scored domains.
    """
    assert isinstance(settings, Settings), "settings required"
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

    logger.info("stage_start", stage="spectre", run_id=run_id, input_count=len(verified))
    try:
        scored = await spectre.run(settings, verified, mock=mock)
        await db.update_run_stage(run_id, "spectre", len(scored))
        await db.save_candidates(run_id, "spectre", scored)
        logger.info("stage_complete", stage="spectre", count=len(scored))
        return scored
    except Exception as exc:
        logger.error("stage_failed", stage="spectre", error=str(exc))
        raise


async def _run_stage_oracle(
    settings: Settings,
    scored: list[ScoredDomain],
    run_id: str,
    db: Database,
    *,
    mock: bool = False,
) -> list[DomainVerdict]:
    """Execute ORACLE verdict stage.

    Args:
        settings: Pipeline settings.
        scored: Input from SPECTRE.
        run_id: Current pipeline run ID.
        db: Database for persistence.
        mock: Use mock data.

    Returns:
        List of domain verdicts.
    """
    assert isinstance(settings, Settings), "settings required"
    assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

    logger.info("stage_start", stage="oracle", run_id=run_id, input_count=len(scored))
    try:
        verdicts = await oracle.run(settings, scored, mock=mock)
        await db.update_run_stage(run_id, "oracle", len(verdicts))
        await db.save_candidates(run_id, "oracle", verdicts)
        logger.info("stage_complete", stage="oracle", count=len(verdicts))
        return verdicts
    except Exception as exc:
        logger.error("stage_failed", stage="oracle", error=str(exc))
        raise


def _extract_db_path(database_url: str) -> str:
    """Extract file path from SQLite database URL.

    Args:
        database_url: Database URL string (e.g. "sqlite:///domainhunter.db").

    Returns:
        File path string suitable for aiosqlite.
    """
    assert isinstance(database_url, str) and len(database_url) > 0, "database_url required"
    assert "sqlite" in database_url.lower() or database_url.endswith(".db"), "must be sqlite URL"

    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url


def main() -> None:
    """CLI entry point — parse args and run the pipeline."""
    args = parse_args()

    assert isinstance(args.dry_run, bool), "dry_run must be bool"
    assert args.from_stage in _STAGES, f"invalid from_stage: {args.from_stage}"

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    try:
        settings = load_settings()
    except Exception as exc:
        print(f"FATAL: Failed to load settings: {exc}", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(
        run_pipeline(
            settings,
            mock=args.dry_run,
            from_stage=args.from_stage,
        ),
    )

    status = result.get("status", "unknown")
    if status == "failed":
        logger.error("pipeline_exit_failure", error=result.get("error"))
        sys.exit(1)

    verdicts = result.get("verdicts", [])
    buy_count = sum(1 for v in verdicts if v.verdict == VerdictType.BUY_NOW)
    watch_count = sum(1 for v in verdicts if v.verdict == VerdictType.WATCH)

    _print_summary(result, buy_count, watch_count, verdicts)


def _print_summary(
    result: dict[str, Any],
    buy_count: int,
    watch_count: int,
    verdicts: list[DomainVerdict],
) -> None:
    """Print human-readable pipeline summary to stdout.

    Args:
        result: Pipeline result dict.
        buy_count: Number of BUY_NOW verdicts.
        watch_count: Number of WATCH verdicts.
        verdicts: Full verdict list for detail lines.
    """
    assert isinstance(result, dict), "result must be dict"
    assert buy_count >= 0 and watch_count >= 0, "counts must be non-negative"

    counts = result.get("counts", {})
    print("\n" + "=" * 60)
    print(f"  Domain Hunter REVENANT | Run: {result.get('run_id', '?')}")
    print(f"  Status: {result.get('status', '?')}")
    print(f"  Elapsed: {result.get('elapsed_seconds', 0):.1f}s")
    print("=" * 60)
    print(f"  SCOUT:     {counts.get('scout', 0):>5} candidates")
    print(f"  SENTINEL:  {counts.get('sentinel', 0):>5} vetted")
    print(f"  ARCHIVIST: {counts.get('archivist', 0):>5} verified")
    print(f"  SPECTRE:   {counts.get('spectre', 0):>5} scored")
    print(f"  ORACLE:    {counts.get('oracle', 0):>5} verdicts")
    print("-" * 60)
    print(f"  BUY NOW: {buy_count}  |  WATCH: {watch_count}")

    if verdicts:
        print("-" * 60)
        for v_idx, v in enumerate(verdicts):
            if v_idx >= 20:
                break
            print(f"  {v.summary}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

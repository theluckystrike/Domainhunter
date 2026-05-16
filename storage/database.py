"""SQLite database for persisting pipeline results across runs.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
NASA Rule 3: All loops bounded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import structlog

from config.constants import MAX_DB_BATCH_SIZE, MAX_LOOP_ITERATIONS

logger = structlog.get_logger(__name__)


class Database:
    """Async SQLite database for pipeline persistence."""

    def __init__(self, db_path: str) -> None:
        assert isinstance(db_path, str) and len(db_path) > 0, "db_path must be non-empty"
        assert db_path.endswith(".db") or ":memory:" in db_path, "db_path must end with .db"
        self._db_path: str = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and create tables."""
        assert self._db_path, "db_path must be set"
        assert self._conn is None, "already connected"
        self._conn = await aiosqlite.connect(self._db_path)
        await self._create_tables()

    async def _create_tables(self) -> None:
        """Create pipeline tables if they don't exist."""
        assert self._conn is not None, "must be connected"
        assert isinstance(self._conn, aiosqlite.Connection), "invalid connection type"

        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                scout_count INTEGER DEFAULT 0,
                sentinel_count INTEGER DEFAULT 0,
                archivist_count INTEGER DEFAULT 0,
                spectre_count INTEGER DEFAULT 0,
                oracle_count INTEGER DEFAULT 0,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                tld TEXT NOT NULL,
                source TEXT NOT NULL,
                stage TEXT NOT NULL,
                score REAL DEFAULT 0.0,
                verdict TEXT,
                data_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_run
                ON candidates(run_id, stage);
            CREATE INDEX IF NOT EXISTS idx_candidates_domain
                ON candidates(domain);
            CREATE INDEX IF NOT EXISTS idx_candidates_verdict
                ON candidates(verdict);
        """)
        await self._conn.commit()

    async def create_run(self, run_id: str) -> None:
        """Insert a new pipeline run record.

        Args:
            run_id: Unique identifier for this pipeline run.
        """
        assert self._conn is not None, "must be connected"
        assert isinstance(run_id, str) and len(run_id) > 0, "run_id must be non-empty"

        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, ?)",
            (run_id, now, "running"),
        )
        await self._conn.commit()

    async def update_run_stage(
        self,
        run_id: str,
        stage: str,
        count: int,
    ) -> None:
        """Update a pipeline run with stage completion count.

        Args:
            run_id: Pipeline run ID.
            stage: Stage name (scout, sentinel, archivist, spectre, oracle).
            count: Number of results from this stage.
        """
        assert self._conn is not None, "must be connected"
        assert stage in ("scout", "sentinel", "archivist", "spectre", "oracle"), (
            f"invalid stage: {stage}"
        )

        col = f"{stage}_count"
        await self._conn.execute(
            f"UPDATE pipeline_runs SET {col} = ? WHERE run_id = ?",
            (count, run_id),
        )
        await self._conn.commit()

    async def complete_run(self, run_id: str, status: str, error: str | None = None) -> None:
        """Mark a pipeline run as completed.

        Args:
            run_id: Pipeline run ID.
            status: Final status ('completed' or 'failed').
            error: Optional error message if failed.
        """
        assert self._conn is not None, "must be connected"
        assert status in ("completed", "failed"), f"invalid status: {status}"

        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "UPDATE pipeline_runs SET completed_at = ?, status = ?, error_message = ? "
            "WHERE run_id = ?",
            (now, status, error, run_id),
        )
        await self._conn.commit()

    async def save_candidates(
        self,
        run_id: str,
        stage: str,
        items: list[Any],
    ) -> int:
        """Save a batch of pipeline stage results.

        Args:
            run_id: Pipeline run ID.
            stage: Stage name.
            items: List of dataclass instances to save.

        Returns:
            Number of items saved.
        """
        assert self._conn is not None, "must be connected"
        assert isinstance(items, list), "items must be a list"

        saved: int = 0
        now = datetime.now(timezone.utc).isoformat()

        for idx, item in enumerate(items):
            if idx >= MAX_DB_BATCH_SIZE:
                logger.warning("batch_truncated", stage=stage, limit=MAX_DB_BATCH_SIZE)
                break
            try:
                domain = getattr(item, "domain", "unknown")
                tld = getattr(item, "tld", "")
                source = getattr(item, "source", stage)
                score = _extract_score(item)
                verdict = _extract_verdict(item)
                data_json = _serialize_item(item)

                await self._conn.execute(
                    "INSERT INTO candidates "
                    "(run_id, domain, tld, source, stage, score, verdict, data_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, domain, tld, source, stage, score, verdict, data_json, now),
                )
                saved += 1
            except Exception as exc:
                logger.error("save_candidate_failed", domain=getattr(item, "domain", "?"), error=str(exc))

        await self._conn.commit()
        return saved

    async def load_stage_data(
        self,
        run_id: str,
        stage: str,
    ) -> list[dict[str, Any]]:
        """Load all serialized records for a given stage.

        Args:
            run_id: Pipeline run ID.
            stage: Stage name to load from.

        Returns:
            List of deserialized JSON dicts.
        """
        assert self._conn is not None, "must be connected"
        assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

        cursor = await self._conn.execute(
            "SELECT data_json FROM candidates "
            "WHERE run_id = ? AND stage = ? ORDER BY id LIMIT ?",
            (run_id, stage, MAX_LOOP_ITERATIONS),
        )
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = json.loads(row[0])
            assert isinstance(data, dict), "data_json must deserialize to dict"
            results.append(data)
        assert len(results) <= MAX_LOOP_ITERATIONS, "result set too large"
        return results

    async def get_buy_now_count(self, run_id: str) -> int:
        """Count BUY_NOW verdicts for a pipeline run.

        Args:
            run_id: Pipeline run ID.

        Returns:
            Number of BUY_NOW verdicts.
        """
        assert self._conn is not None, "must be connected"
        assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM candidates "
            "WHERE run_id = ? AND stage = 'oracle' AND verdict = 'BUY_NOW' "
            "LIMIT ?",
            (run_id, MAX_LOOP_ITERATIONS),
        )
        row = await cursor.fetchone()
        count = int(row[0]) if row else 0
        assert count >= 0, "count must be non-negative"
        return count

    async def get_verdicts(self, run_id: str) -> list[dict[str, Any]]:
        """Load all ORACLE verdicts for a pipeline run.

        Args:
            run_id: Pipeline run ID.

        Returns:
            List of verdict dicts deserialized from JSON.
        """
        assert self._conn is not None, "must be connected"
        assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"

        cursor = await self._conn.execute(
            "SELECT data_json, verdict, score FROM candidates "
            "WHERE run_id = ? AND stage = 'oracle' "
            "ORDER BY score DESC LIMIT ?",
            (run_id, MAX_LOOP_ITERATIONS),
        )
        rows = await cursor.fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = json.loads(row[0])
            assert isinstance(data, dict), "data_json must deserialize to dict"
            results.append(data)
        assert len(results) <= MAX_LOOP_ITERATIONS, "result set too large"
        return results

    async def close(self) -> None:
        """Close the database connection."""
        assert self._conn is not None, "must be connected to close"
        assert isinstance(self._conn, aiosqlite.Connection), "invalid connection type"
        await self._conn.close()
        self._conn = None


def _extract_score(item: Any) -> float:
    """Extract the primary score from a pipeline dataclass.

    Args:
        item: A pipeline stage output dataclass.

    Returns:
        The primary score as a float, or 0.0.
    """
    assert item is not None, "item must not be None"
    for attr in ("final_score", "spectre_score", "niche_relevance_score", "domain_authority"):
        val = getattr(item, attr, None)
        if val is not None:
            assert isinstance(val, (int, float)), f"{attr} must be numeric"
            return float(val)
    return 0.0


def _extract_verdict(item: Any) -> str | None:
    """Extract verdict string from a domain verdict dataclass.

    Args:
        item: A pipeline stage output dataclass.

    Returns:
        Verdict string or None.
    """
    assert item is not None, "item must not be None"
    assert hasattr(item, "__dataclass_fields__") or hasattr(item, "__slots__"), "item must be a dataclass or __slots__ class"
    verdict = getattr(item, "verdict", None)
    if verdict is None:
        return None
    if hasattr(verdict, "value"):
        return str(verdict.value)
    return str(verdict)


def _serialize_item(item: Any) -> str:
    """Serialize a dataclass to JSON string for storage.

    Args:
        item: A frozen dataclass instance.

    Returns:
        JSON string representation.
    """
    assert item is not None, "item must not be None"
    assert hasattr(item, "__dataclass_fields__") or hasattr(item, "__slots__"), "item must be a dataclass or __slots__ class"

    if hasattr(item, "__dataclass_fields__"):
        from dataclasses import asdict
        data = asdict(item)
    else:
        to_dict_fn = getattr(item, "to_dict", None)
        assert callable(to_dict_fn), "__slots__ class must have to_dict()"
        data = to_dict_fn()
    return json.dumps(data, default=str, ensure_ascii=False)

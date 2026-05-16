#!/usr/bin/env python3
"""Sprint 26 -- End-to-end notification chain test.

Simulates a pendingDelete detection for a test domain and verifies
every link in the alert chain: desktop notification, log write, log read-back.

Run:  python scripts/sprint26_notification_test.py
      python scripts/sprint26_notification_test.py --domain guerrameats.com

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# ── Constants (immutable) ────────────────────────────────────────────
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
LOG_FILE: Final[Path] = LOG_DIR / "notification_test.log"
MAX_LOG_LINES: Final[int] = 500
TEST_DOMAIN_DEFAULT: Final[str] = "test-notification.example.com"


# ── Data Models (frozen) ────────────────────────────────────────────
@dataclass(frozen=True)
class TestResult:
    """Immutable test result for a single step."""
    step_name: str
    passed: bool
    detail: str
    timestamp: str

    def __post_init__(self) -> None:
        assert self.step_name, "Step name required"
        assert isinstance(self.passed, bool), "Passed must be bool"


@dataclass(frozen=True)
class SimulatedTransition:
    """Immutable simulated pendingDelete detection."""
    domain: str
    previous_status: str
    current_status: str
    urgency: str
    etv: int
    max_bid: int

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.current_status == "pendingDelete", "Must simulate pendingDelete"


# ── Desktop Notification ────────────────────────────────────────────
def send_test_notification(domain: str, urgency: str) -> TestResult:
    """Fire a macOS desktop notification and return pass/fail."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert urgency, "Urgency required"

    now = datetime.now(timezone.utc).isoformat()
    title = "Domain Hunter TEST"
    message = f"{domain}: {urgency}"

    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = (
        f'display notification "{safe_msg}" '
        f'with title "{safe_title}" sound name "Glass"'
    )

    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=10,
        )
        passed = proc.returncode == 0
        detail = "Notification sent" if passed else f"osascript exit {proc.returncode}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        passed = False
        detail = f"osascript error: {exc}"

    return TestResult(
        step_name="desktop_notification",
        passed=passed, detail=detail, timestamp=now,
    )


# ── Log Writer ──────────────────────────────────────────────────────
def write_test_log(transition: SimulatedTransition, log_path: Path) -> TestResult:
    """Write simulated transition to notification_test.log."""
    assert transition.domain, "Domain required"
    assert log_path.parent.exists(), f"Log dir missing: {log_path.parent}"

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "timestamp": now,
        "type": "notification_test",
        "domain": transition.domain,
        "previous_status": transition.previous_status,
        "current_status": transition.current_status,
        "urgency": transition.urgency,
        "etv": transition.etv,
        "max_bid": transition.max_bid,
        "test": True,
    }

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Append, but enforce max lines
        existing_lines: list[str] = []
        if log_path.exists():
            existing_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            if len(existing_lines) > MAX_LOG_LINES:
                existing_lines = existing_lines[-MAX_LOG_LINES:]

        line = json.dumps(entry, separators=(",", ":"))
        existing_lines.append(line)
        log_path.write_text(
            "\n".join(existing_lines) + "\n", encoding="utf-8",
        )
        passed = True
        detail = f"Logged to {log_path.name}"
    except OSError as exc:
        passed = False
        detail = f"Write failed: {exc}"

    return TestResult(
        step_name="log_write", passed=passed, detail=detail, timestamp=now,
    )


# ── Log Verify ──────────────────────────────────────────────────────
def verify_test_log(domain: str, log_path: Path) -> TestResult:
    """Read back the log and verify the test entry exists."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(log_path, Path), "log_path must be Path"

    now = datetime.now(timezone.utc).isoformat()

    if not log_path.exists():
        return TestResult(
            step_name="log_verify", passed=False,
            detail=f"Log file not found: {log_path}", timestamp=now,
        )

    try:
        content = log_path.read_text(encoding="utf-8").strip()
        lines = content.split("\n")
        found = False
        for i, line in enumerate(lines):
            if i >= MAX_LOG_LINES:
                break
            if not line.strip():
                continue
            entry = json.loads(line)
            if (entry.get("domain") == domain
                    and entry.get("type") == "notification_test"
                    and entry.get("current_status") == "pendingDelete"):
                found = True
                break

        detail = "Test entry found in log" if found else "Test entry NOT found"
    except (json.JSONDecodeError, OSError) as exc:
        found = False
        detail = f"Log parse error: {exc}"

    return TestResult(
        step_name="log_verify", passed=found, detail=detail, timestamp=now,
    )


# ── Backorder Queue Check ──────────────────────────────────────────
def verify_backorder_queue_readable() -> TestResult:
    """Verify backorder_queue.json is readable and well-formed."""
    now = datetime.now(timezone.utc).isoformat()
    queue_path = PROJECT_ROOT / "data" / "backorder_queue.json"

    assert isinstance(queue_path, Path), "queue_path must be Path"
    assert queue_path.suffix == ".json", "Must be .json"

    if not queue_path.exists():
        return TestResult(
            step_name="backorder_queue_check", passed=False,
            detail=f"File not found: {queue_path}", timestamp=now,
        )

    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
        queue_len = len(data.get("queue", []))
        balance = data.get("dynadot_balance", "unknown")
        detail = f"Queue OK: {queue_len} entries, balance=${balance}"
        passed = queue_len >= 0
    except (json.JSONDecodeError, OSError) as exc:
        passed = False
        detail = f"Parse error: {exc}"

    return TestResult(
        step_name="backorder_queue_check", passed=passed,
        detail=detail, timestamp=now,
    )


# ── Drop Monitor DB Check ──────────────────────────────────────────
def verify_drop_monitor_db() -> TestResult:
    """Verify drop_monitor.db exists and has the expected schema."""
    import sqlite3

    now = datetime.now(timezone.utc).isoformat()
    db_path = PROJECT_ROOT / "scripts" / "drop_monitor.db"

    assert isinstance(db_path, Path), "db_path must be Path"

    if not db_path.exists():
        return TestResult(
            step_name="drop_monitor_db_check", passed=False,
            detail=f"DB not found: {db_path}", timestamp=now,
        )

    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT COUNT(*) FROM domain_monitoring"
        ).fetchone()
        count = row[0] if row else 0
        conn.close()
        detail = f"DB OK: {count} monitoring records"
        passed = True
    except sqlite3.Error as exc:
        passed = False
        detail = f"DB error: {exc}"

    return TestResult(
        step_name="drop_monitor_db_check", passed=passed,
        detail=detail, timestamp=now,
    )


# ── Print Report ────────────────────────────────────────────────────
def print_report(results: tuple[TestResult, ...]) -> int:
    """Print PASS/FAIL report and return exit code (0=all pass)."""
    assert len(results) > 0, "No results to report"
    assert all(isinstance(r, TestResult) for r in results), "Invalid results"

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n" + "=" * 64)
    print("Sprint 26 -- Notification Chain Test Report")
    print("=" * 64)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.step_name}: {r.detail}")

    print("-" * 64)
    print(f"  Total: {total} | Passed: {passed} | Failed: {failed}")

    if failed == 0:
        print("  RESULT: ALL TESTS PASSED")
    else:
        print(f"  RESULT: {failed} TEST(S) FAILED")
    print("=" * 64)

    return 0 if failed == 0 else 1


# ── CLI Entry Point ─────────────────────────────────────────────────
def main() -> None:
    """Parse CLI args and run the full notification chain test."""
    parser = argparse.ArgumentParser(
        description="Sprint 26 -- Notification chain end-to-end test",
    )
    parser.add_argument(
        "--domain", type=str, default=TEST_DOMAIN_DEFAULT,
        help=f"Domain to simulate (default: {TEST_DOMAIN_DEFAULT})",
    )
    args = parser.parse_args()
    assert args.domain and "." in args.domain, f"Invalid domain: {args.domain}"

    # Build simulated transition
    transition = SimulatedTransition(
        domain=args.domain,
        previous_status="clientHold",
        current_status="pendingDelete",
        urgency="IMMEDIATE -- 5 days to drop",
        etv=11376,
        max_bid=200,
    )

    print(f"Simulating pendingDelete detection for: {transition.domain}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Run all test steps
    results: list[TestResult] = []

    # Step 1: Desktop notification
    r1 = send_test_notification(transition.domain, transition.urgency)
    results.append(r1)
    print(f"  [1/5] Desktop notification: {'PASS' if r1.passed else 'FAIL'}")

    # Step 2: Log write
    r2 = write_test_log(transition, LOG_FILE)
    results.append(r2)
    print(f"  [2/5] Log write: {'PASS' if r2.passed else 'FAIL'}")

    # Step 3: Log verify
    r3 = verify_test_log(transition.domain, LOG_FILE)
    results.append(r3)
    print(f"  [3/5] Log verify: {'PASS' if r3.passed else 'FAIL'}")

    # Step 4: Backorder queue readable
    r4 = verify_backorder_queue_readable()
    results.append(r4)
    print(f"  [4/5] Backorder queue: {'PASS' if r4.passed else 'FAIL'}")

    # Step 5: Drop monitor DB
    r5 = verify_drop_monitor_db()
    results.append(r5)
    print(f"  [5/5] Drop monitor DB: {'PASS' if r5.passed else 'FAIL'}")

    exit_code = print_report(tuple(results))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

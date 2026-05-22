#!/usr/bin/env python3
"""Domain Hunter Daemon Scheduler.

Replaces launchd agents that fail due to macOS TCC restrictions
on ~/Desktop/ directory access. Runs as a persistent background process
with proper UNIX daemonization (double-fork, setsid, fd redirect).

Usage:
    python3 scripts/daemon_scheduler.py start       # Start daemon (double-fork)
    python3 scripts/daemon_scheduler.py foreground   # Run in foreground (for launchd)
    python3 scripts/daemon_scheduler.py stop         # Stop daemon
    python3 scripts/daemon_scheduler.py status       # Check if running
    python3 scripts/daemon_scheduler.py run-once     # Run all tasks once (testing)
    python3 scripts/daemon_scheduler.py next         # Show next scheduled runs

Schedule:
    Every 6 hours:           drop_monitor.py --tier critical
    Every 24h at 03:00 UTC:  drop_monitor.py --tier all
    Every Monday 06:30 UTC:  startup_reaper.py
    Every day 09:00 UTC:     sprint26_daily_digest.py

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import io
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Final, List, Optional, Tuple

# Project root must be on sys.path before importing local clients
_PROJECT_ROOT_INIT: Path = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT_INIT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_INIT))

from clients.ntfy_client import send_alert as ntfy_alert

# ── Constants (immutable) ──────────────────────────────────────────────
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "scripts"
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
PID_FILE: Final[Path] = LOG_DIR / ".daemon.pid"
HEARTBEAT_FILE: Final[Path] = LOG_DIR / ".daemon_heartbeat"
LOG_FILE: Final[Path] = LOG_DIR / "daemon_scheduler.log"
VENV_PYTHON: Final[Path] = PROJECT_ROOT / ".venv" / "bin" / "python3"
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"
TICK_INTERVAL: Final[int] = 60  # seconds between scheduler ticks
MAX_LOG_LINES: Final[int] = 5000
MAX_TASK_RUNTIME: Final[int] = 300  # 5 minutes per task


# ── Data Models (frozen) ───────────────────────────────────────────────
@dataclass(frozen=True)
class ScheduledTask:
    """Immutable task definition."""
    name: str
    script: str
    args: Tuple[str, ...]
    interval_hours: Optional[float]   # None = use fixed_time
    fixed_hour: Optional[int]         # UTC hour (0-23)
    fixed_minute: Optional[int]       # UTC minute (0-59)
    weekday: Optional[int]            # 0=Mon, None=daily
    timeout: int = MAX_TASK_RUNTIME   # per-task timeout in seconds


# ── Task Schedule ──────────────────────────────────────────────────────
TASKS: Final[Tuple[ScheduledTask, ...]] = (
    ScheduledTask(
        name="drop-monitor-critical",
        script="drop_monitor.py",
        args=("--tier", "critical"),
        interval_hours=6.0,
        fixed_hour=None,
        fixed_minute=None,
        weekday=None,
    ),
    ScheduledTask(
        name="drop-monitor-all",
        script="drop_monitor.py",
        args=("--tier", "all"),
        interval_hours=None,
        fixed_hour=3,
        fixed_minute=0,
        weekday=None,
    ),
    ScheduledTask(
        name="startup-reaper",
        script="startup_reaper.py",
        args=("--sources", "existing"),
        interval_hours=None,
        fixed_hour=6,
        fixed_minute=30,
        weekday=0,  # Monday
        timeout=900,  # 15 minutes — processes large dataset
    ),
    ScheduledTask(
        name="daily-digest",
        script="sprint26_daily_digest.py",
        args=(),
        interval_hours=None,
        fixed_hour=9,
        fixed_minute=0,
        weekday=None,
    ),
)


# ── Logging Setup ──────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    """Configure file+console logger. Returns the daemon logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("daemon_scheduler")
    logger.setLevel(logging.INFO)
    # File handler
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S UTC",
    )
    fmt.converter = time.gmtime
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # Console handler (for run-once / status)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


def setup_daemon_logging() -> logging.Logger:
    """Configure file-only logger for daemon mode (no stdout)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("daemon_scheduler")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S UTC",
    )
    fmt.converter = time.gmtime
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


# ── Environment Loading ───────────────────────────────────────────────
def load_env() -> dict:
    """Load .env file into a dict. Returns env vars for subprocess."""
    env = dict(os.environ)
    assert ENV_FILE.parent.exists(), f"Project root missing: {ENV_FILE.parent}"
    if not ENV_FILE.exists():
        return env
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    assert isinstance(env, dict)
    return env


# ── Python Executable ─────────────────────────────────────────────────
def get_python() -> str:
    """Return venv python if available, else system python3."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return "python3"


# ── Task Execution ─────────────────────────────────────────────────────
def run_task(task: ScheduledTask, logger: logging.Logger, env: dict) -> int:
    """Execute a scheduled task. Returns exit code."""
    assert task.name, "Task must have a name"
    script_path = SCRIPTS_DIR / task.script
    assert script_path.exists(), f"Script not found: {script_path}"

    cmd = [get_python(), str(script_path)] + list(task.args)
    logger.info("EXEC [%s]: %s", task.name, " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=task.timeout,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
        # Log stdout (last 50 lines)
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            tail = lines[-50:] if len(lines) > 50 else lines
            for line in tail:
                logger.info("  [%s] %s", task.name, line)
        if result.stderr:
            err_lines = result.stderr.strip().split("\n")
            for line in err_lines[-20:]:
                logger.warning("  [%s] STDERR: %s", task.name, line)
        logger.info("DONE [%s]: exit=%d", task.name, result.returncode)
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error("TIMEOUT [%s]: killed after %ds", task.name, task.timeout)
        ntfy_alert(
            title=f"Daemon TIMEOUT: {task.name}",
            message=f"Task killed after {task.timeout}s\nScript: {task.script}",
            priority="high",
            tags="rotating_light,stopwatch",
        )
        return 1
    except Exception as exc:
        logger.error("FAIL [%s]: %s", task.name, exc)
        ntfy_alert(
            title=f"Daemon ERROR: {task.name}",
            message=f"Task failed: {exc}\nScript: {task.script}",
            priority="high",
            tags="rotating_light,x",
        )
        return 1


# ── Scheduling Logic ──────────────────────────────────────────────────
def should_run_interval(task: ScheduledTask, last_runs: dict, now: datetime) -> bool:
    """Check if an interval-based task is due."""
    assert task.interval_hours is not None
    assert task.interval_hours > 0
    last = last_runs.get(task.name)
    if last is None:
        return True
    elapsed = (now - last).total_seconds() / 3600.0
    return elapsed >= task.interval_hours


def should_run_fixed(task: ScheduledTask, last_runs: dict, now: datetime) -> bool:
    """Check if a fixed-time task is due (within 2-minute window)."""
    assert task.fixed_hour is not None
    assert task.fixed_minute is not None
    # Weekday check
    if task.weekday is not None and now.weekday() != task.weekday:
        return False
    # Time window check (run if within 2 min of target)
    target_min = task.fixed_hour * 60 + task.fixed_minute
    now_min = now.hour * 60 + now.minute
    if abs(now_min - target_min) > 1:
        return False
    # Already ran today?
    last = last_runs.get(task.name)
    if last is not None and (now - last).total_seconds() < 3600:
        return False
    return True


def check_due_tasks(last_runs: dict, now: datetime) -> List[ScheduledTask]:
    """Return list of tasks that should run now."""
    assert isinstance(last_runs, dict)
    due = []
    for task in TASKS:
        if task.interval_hours is not None:
            if should_run_interval(task, last_runs, now):
                due.append(task)
        else:
            if should_run_fixed(task, last_runs, now):
                due.append(task)
    assert isinstance(due, list)
    return due


# ── Heartbeat ─────────────────────────────────────────────────────────
def write_heartbeat(last_runs: dict) -> None:
    """Write heartbeat file with timestamp and last-run info."""
    assert isinstance(last_runs, dict)
    now = datetime.now(timezone.utc)
    lines = [
        f"daemon_alive: {now.isoformat()}",
        f"pid: {os.getpid()}",
    ]
    for name, ts in sorted(last_runs.items()):
        lines.append(f"last_run.{name}: {ts.isoformat()}")
    HEARTBEAT_FILE.write_text("\n".join(lines) + "\n")


# ── PID Management ────────────────────────────────────────────────────
def write_pid() -> None:
    """Write current PID to file."""
    PID_FILE.write_text(str(os.getpid()) + "\n")


def read_pid() -> Optional[int]:
    """Read PID from file. Returns None if not found or invalid."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        assert pid > 0
        return pid
    except (ValueError, AssertionError):
        return None


def is_running() -> Tuple[bool, Optional[int]]:
    """Check if daemon is running. Returns (running, pid)."""
    pid = read_pid()
    if pid is None:
        return False, None
    try:
        os.kill(pid, 0)  # signal 0 = existence check
        return True, pid
    except ProcessLookupError:
        return False, pid
    except PermissionError:
        return True, pid  # exists but owned by another user


# ── Log Rotation ──────────────────────────────────────────────────────
def rotate_log_if_needed() -> None:
    """Truncate log file if it exceeds MAX_LOG_LINES."""
    if not LOG_FILE.exists():
        return
    lines = LOG_FILE.read_text().split("\n")
    if len(lines) <= MAX_LOG_LINES:
        return
    # Keep last 80% of max
    keep = int(MAX_LOG_LINES * 0.8)
    trimmed = lines[-keep:]
    LOG_FILE.write_text(
        f"[LOG ROTATED: {len(lines)} -> {keep} lines]\n"
        + "\n".join(trimmed)
    )


# ── Daemon Loop ───────────────────────────────────────────────────────
def daemon_loop(logger: logging.Logger) -> None:
    """Main scheduler loop. Runs until SIGTERM/SIGINT."""
    assert logger is not None
    shutdown = {"flag": False}

    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        shutdown["flag"] = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    env = load_env()
    last_runs = {}  # type: dict[str, datetime]
    tick_count = 0
    max_ticks = 365 * 24 * 60  # ~1 year of 1-min ticks (bounded loop)

    write_pid()
    logger.info("Daemon started (pid=%d, python=%s)", os.getpid(), get_python())
    logger.info("Project root: %s", PROJECT_ROOT)
    logger.info("Tick interval: %ds", TICK_INTERVAL)
    for task in TASKS:
        logger.info("  Task: %s (script=%s)", task.name, task.script)

    # ntfy: notify on daemon (re)start so you know it's alive
    ntfy_alert(
        title="Domain Hunter daemon started",
        message=f"pid={os.getpid()} | {len(TASKS)} tasks scheduled",
        priority="default",
        tags="white_check_mark,gear",
    )

    # Run critical monitor immediately on start
    for task in TASKS:
        if task.name == "drop-monitor-critical":
            exit_code = run_task(task, logger, env)
            last_runs[task.name] = datetime.now(timezone.utc)
            break

    while tick_count < max_ticks and not shutdown["flag"]:
        tick_count += 1
        now = datetime.now(timezone.utc)
        write_heartbeat(last_runs)

        due = check_due_tasks(last_runs, now)
        for task in due:
            if shutdown["flag"]:
                break
            exit_code = run_task(task, logger, env)
            last_runs[task.name] = datetime.now(timezone.utc)

        # Rotate logs every 100 ticks (~1.5 hours)
        if tick_count % 100 == 0:
            rotate_log_if_needed()

        # Sleep in 5-second chunks for responsive shutdown
        for _ in range(TICK_INTERVAL // 5):
            if shutdown["flag"]:
                break
            time.sleep(5)

    logger.info("Daemon exiting (ticks=%d, shutdown=%s)", tick_count, shutdown["flag"])
    cleanup_pid()


def cleanup_pid() -> None:
    """Remove PID file on exit."""
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except OSError:
            pass


# ── Daemonize (UNIX double-fork) ──────────────────────────────────────
def daemonize() -> None:
    """Classic UNIX double-fork to detach from terminal."""
    # First fork
    pid = os.fork()
    if pid > 0:
        # Parent exits
        sys.exit(0)

    # Become session leader
    os.setsid()

    # Second fork (prevent re-acquiring terminal)
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect std file descriptors to /dev/null
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)  # stdin
    os.dup2(devnull, 1)  # stdout
    os.dup2(devnull, 2)  # stderr
    os.close(devnull)

    # Change working directory
    os.chdir(str(PROJECT_ROOT))


# ── Commands ──────────────────────────────────────────────────────────
def cmd_start() -> int:
    """Start the daemon. Returns exit code."""
    running, pid = is_running()
    if running:
        print(f"Daemon already running (pid={pid})")
        return 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Starting daemon (log={LOG_FILE})")
    print(f"  PID file: {PID_FILE}")
    print(f"  Heartbeat: {HEARTBEAT_FILE}")
    sys.stdout.flush()

    daemonize()

    # Now in daemon process
    logger = setup_daemon_logging()
    try:
        daemon_loop(logger)
    except Exception as exc:
        logger.error("Daemon crashed: %s", exc, exc_info=True)
        cleanup_pid()
        return 1
    return 0


def cmd_foreground() -> int:
    """Run daemon in foreground (for launchd KeepAlive). Returns exit code.

    Unlike 'start', this does NOT double-fork/daemonize. launchd manages
    the process lifecycle: KeepAlive restarts on crash, RunAtLoad starts
    on login. Stdout/stderr go to launchd log paths.
    """
    running, pid = is_running()
    if running:
        print(f"Daemon already running (pid={pid})")
        return 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = setup_logging()
    logger.info("Starting daemon in FOREGROUND mode (for launchd)")
    try:
        daemon_loop(logger)
    except Exception as exc:
        logger.error("Daemon crashed: %s", exc, exc_info=True)
        cleanup_pid()
        return 1
    return 0


def cmd_stop() -> int:
    """Stop the daemon. Returns exit code."""
    running, pid = is_running()
    if not running:
        print("Daemon is not running.")
        if pid is not None:
            print(f"  Stale PID file found (pid={pid}), cleaning up.")
            cleanup_pid()
        return 0

    print(f"Stopping daemon (pid={pid})...")
    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    # Wait up to 10 seconds for clean exit
    for _ in range(20):
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print("Daemon stopped.")
            cleanup_pid()
            return 0
    print("Daemon did not stop in time, sending SIGKILL...")
    os.kill(pid, signal.SIGKILL)
    cleanup_pid()
    return 0


def cmd_status() -> int:
    """Print daemon status. Returns 0 if running, 1 if not."""
    running, pid = is_running()
    if running:
        print(f"Daemon is RUNNING (pid={pid})")
        if HEARTBEAT_FILE.exists():
            print(f"\nHeartbeat ({HEARTBEAT_FILE}):")
            print(HEARTBEAT_FILE.read_text())
        return 0
    else:
        print("Daemon is NOT running.")
        if pid is not None:
            print(f"  Stale PID file references pid={pid}")
        if HEARTBEAT_FILE.exists():
            print(f"\nLast heartbeat:")
            print(HEARTBEAT_FILE.read_text())
        return 1


def cmd_run_once() -> int:
    """Run all tasks once (for testing). Returns max exit code."""
    logger = setup_logging()
    env = load_env()
    logger.info("=== RUN-ONCE: executing all %d tasks ===", len(TASKS))
    max_exit = 0
    for task in TASKS:
        exit_code = run_task(task, logger, env)
        max_exit = max(max_exit, exit_code)
    logger.info("=== RUN-ONCE complete (max_exit=%d) ===", max_exit)
    return max_exit


def cmd_next() -> int:
    """Show next scheduled run times."""
    now = datetime.now(timezone.utc)
    print(f"Current time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    for task in TASKS:
        if task.interval_hours is not None:
            print(f"  {task.name}: every {task.interval_hours}h")
        else:
            day_str = ""
            if task.weekday is not None:
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_str = f" ({days[task.weekday]})"
            assert task.fixed_hour is not None
            assert task.fixed_minute is not None
            print(
                f"  {task.name}: daily{day_str} at "
                f"{task.fixed_hour:02d}:{task.fixed_minute:02d} UTC"
            )
        print(f"    script: {task.script} {' '.join(task.args)}")
    return 0


# ── Main ──────────────────────────────────────────────────────────────
def main() -> int:
    """Parse command and dispatch."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1].lower().replace("_", "-")
    commands = {
        "start": cmd_start,
        "foreground": cmd_foreground,
        "stop": cmd_stop,
        "status": cmd_status,
        "run-once": cmd_run_once,
        "next": cmd_next,
    }
    handler = commands.get(command)
    if handler is None:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")
        return 1

    return handler()


if __name__ == "__main__":
    sys.exit(main())

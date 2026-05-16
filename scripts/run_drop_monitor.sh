#!/bin/bash
# Domain Hunter — Drop Monitor Manual Runner
# Activates venv, loads .env, runs drop_monitor.py, logs output, sends macOS notification.
# Usage: bash scripts/run_drop_monitor.sh [--tier critical|all] [--dry-run]

set -euo pipefail

PROJECT="/Users/mike/Desktop/domainhunter"
LOG_DIR="${PROJECT}/logs"
VENV="${PROJECT}/.venv"
SCRIPT="${PROJECT}/scripts/drop_monitor.py"

cd "$PROJECT"
mkdir -p "$LOG_DIR"

# Load environment
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# Activate venv if present
if [ -f "${VENV}/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${VENV}/bin/activate"
    echo "Activated venv: ${VENV}"
else
    echo "No venv found; using system Python: $(python3 --version 2>&1)"
fi

# Verify script exists
if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: ${SCRIPT} not found" >&2; exit 1
fi

# Run with logging
LOG_FILE="${LOG_DIR}/drop_monitor_$(date +%Y-%m-%d_%H%M%S).log"
echo "=== Drop Monitor: $(date -u) ===" | tee "$LOG_FILE"
echo "Args: $*" | tee -a "$LOG_FILE"

python3 "$SCRIPT" "$@" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
echo "=== Completed: $(date -u) | exit=${EXIT_CODE} ===" | tee -a "$LOG_FILE"

# Heartbeat: touch file on success so monitoring check can verify recency
if [ "$EXIT_CODE" -eq 0 ]; then
    touch "${LOG_DIR}/.drop_monitor_heartbeat"
    MSG="Drop monitor completed successfully."
else
    MSG="Drop monitor FAILED (exit ${EXIT_CODE}). See logs."
fi
osascript -e "display notification \"${MSG}\" with title \"Domain Hunter\"" 2>/dev/null || true

# Rotate logs older than 30 days
find "$LOG_DIR" -name "drop_monitor_*.log" -mtime +30 -delete 2>/dev/null || true
exit "$EXIT_CODE"

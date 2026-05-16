#!/bin/bash
# Startup Reaper — weekly scan for dead startup domains
# Sprint 22: Added logging, .env loading, auto-backorder, macOS notification.
# Sprint 23: Activated --dry-run-backorder in cron wrapper.
# Sprint 24: Promoted to --auto-backorder (live Dynadot backorders).
#
# Backorder activation progression (COMPLETE):
#   1. --dry-run-backorder  (done)    — logged what WOULD be backordered, no money spent
#   2. --auto-backorder     (active)  — places real Dynadot backorders ($12.99 each)
#
# Usage: bash scripts/run_startup_reaper.sh [--auto-backorder] [--dry-run]

set -euo pipefail

PROJECT="/Users/mike/Desktop/domainhunter"
LOG_DIR="${PROJECT}/logs"
VENV="${PROJECT}/.venv"
SCRIPT="${PROJECT}/scripts/startup_reaper.py"

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
LOG_FILE="${LOG_DIR}/startup_reaper_$(date +%Y-%m-%d_%H%M%S).log"
echo "=== Startup Reaper: $(date -u) ===" | tee "$LOG_FILE"
echo "Args: $*" | tee -a "$LOG_FILE"

# Sprint 24: --auto-backorder live. Dynadot backorders placed for qualifying domains.
python3 "$SCRIPT" --sources existing,deepseek,yc,kaggle --top 40 --auto-backorder "$@" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
echo "=== Completed: $(date -u) | exit=${EXIT_CODE} ===" | tee -a "$LOG_FILE"

# Heartbeat: touch file on success so monitoring check can verify recency
if [ "$EXIT_CODE" -eq 0 ]; then
    touch "${LOG_DIR}/.startup_reaper_heartbeat"
    MSG="Startup Reaper completed successfully."
else
    MSG="Startup Reaper FAILED (exit ${EXIT_CODE}). See logs."
fi
osascript -e "display notification \"${MSG}\" with title \"Domain Hunter\"" 2>/dev/null || true

# Rotate logs older than 30 days
find "$LOG_DIR" -name "startup_reaper_*.log" -mtime +30 -delete 2>/dev/null || true
exit "$EXIT_CODE"

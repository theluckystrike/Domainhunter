#!/bin/bash
# Domain Hunter — Daily Digest Runner
# Activates venv, loads .env, runs sprint26_daily_digest.py, sends macOS notification on failure.
# Usage: bash scripts/run_daily_digest.sh [--quiet]

set -euo pipefail

PROJECT="/Users/mike/Desktop/domainhunter"
LOG_DIR="${PROJECT}/logs"
VENV="${PROJECT}/.venv"
SCRIPT="${PROJECT}/scripts/sprint26_daily_digest.py"

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
fi

# Verify script exists
if [ ! -f "$SCRIPT" ]; then
    echo "ERROR: ${SCRIPT} not found" >&2; exit 1
fi

# Run digest
python3 "$SCRIPT" "$@"
EXIT_CODE=$?

# Heartbeat
if [ "$EXIT_CODE" -eq 0 ]; then
    touch "${LOG_DIR}/.daily_digest_heartbeat"
else
    osascript -e 'display notification "Daily digest FAILED. Check logs." with title "Domain Hunter"' 2>/dev/null || true
fi

exit "$EXIT_CODE"

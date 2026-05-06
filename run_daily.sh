#!/bin/bash
# Domain Hunter REVENANT — Daily cron wrapper
#
# Usage:
#   ./run_daily.sh              # Full pipeline
#   ./run_daily.sh --dry-run    # Mock data only
#
# Cron example (daily at 06:00 UTC):
#   0 6 * * * /path/to/domain-hunter-REVENANT/run_daily.sh >> /dev/null 2>&1

set -euo pipefail

cd "$(dirname "$0")"

# Source .env if exists
if [ -f .env ]; then
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
fi

LOG_DIR="./logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

echo "=== Domain Hunter starting: $(date -u) ===" >> "$LOG_FILE"
echo "Working directory: $(pwd)" >> "$LOG_FILE"
echo "Python: $(python3 --version 2>&1)" >> "$LOG_FILE"

# Run the pipeline, capturing exit code from python (not tee)
python3 -m main "$@" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "PIPELINE FAILED with exit $EXIT_CODE" >> "$LOG_FILE"

    # Send Slack failure notification if webhook is configured
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"Domain Hunter FAILED at $TIMESTAMP — exit code $EXIT_CODE\"}" \
            >> "$LOG_FILE" 2>&1 || true
    fi
fi

echo "=== Pipeline completed: $(date -u) | exit=$EXIT_CODE ===" >> "$LOG_FILE"

# Rotate logs older than 30 days
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE

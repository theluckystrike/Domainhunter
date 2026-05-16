#!/bin/bash
# Domain Hunter — Cron Job Installer
# Installs 3 cron jobs for domain monitoring. Idempotent (safe to re-run).
# Usage: bash scripts/setup_cron.sh

set -euo pipefail

PROJECT="/Users/mike/Desktop/domainhunter"
PY="/usr/bin/python3"
BACKUP_DIR="${PROJECT}/logs/cron_backups"

# Cron entries: critical every 6h, all daily 06:00 UTC, dashboard 06:30 UTC
CRON_CRITICAL="0 */6 * * * cd ${PROJECT} && ${PY} scripts/drop_monitor.py --tier critical >> logs/cron_critical.log 2>&1"
CRON_DAILY="0 6 * * * cd ${PROJECT} && ${PY} scripts/drop_monitor.py --tier all >> logs/cron_daily.log 2>&1"
CRON_DASHBOARD="30 6 * * * cd ${PROJECT} && ${PY} dashboard.py --generate >> logs/cron_dashboard.log 2>&1"
ENTRIES=("$CRON_CRITICAL" "$CRON_DAILY" "$CRON_DASHBOARD")

# Pre-flight
mkdir -p "${PROJECT}/logs" "$BACKUP_DIR"
if ! command -v crontab >/dev/null 2>&1; then
    echo "ERROR: crontab not found" >&2; exit 1
fi

CURRENT=$(crontab -l 2>/dev/null || true)
echo "=== BEFORE ==="
echo "${CURRENT:-<empty crontab>}"

# Back up existing crontab
if [ -n "$CURRENT" ]; then
    echo "$CURRENT" > "${BACKUP_DIR}/crontab_$(date +%Y%m%d_%H%M%S).bak"
    echo "Backup saved to ${BACKUP_DIR}/"
fi

# Install missing entries (skip duplicates)
ADDED=0
NEW_CRONTAB="$CURRENT"
for ENTRY in "${ENTRIES[@]}"; do
    MARKER=$(echo "$ENTRY" | sed 's/^[0-9*/  ]*//')
    if echo "$NEW_CRONTAB" | grep -qF "$MARKER"; then
        echo "SKIP (exists): ${ENTRY:0:70}..."
    else
        NEW_CRONTAB=$(printf '%s\n%s' "$NEW_CRONTAB" "$ENTRY")
        ADDED=$((ADDED + 1))
        echo "ADD: ${ENTRY:0:70}..."
    fi
done

if [ "$ADDED" -eq 0 ]; then
    echo "All 3 cron jobs already installed. Nothing to do."; exit 0
fi

echo "$NEW_CRONTAB" | crontab -

echo -e "\n=== AFTER ==="
crontab -l
echo "Installed ${ADDED} new cron job(s)."

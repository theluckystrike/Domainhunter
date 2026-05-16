#!/bin/bash
# Domain Hunter — launchd Agent Installer
# Replaces cron jobs with launchd plists (macOS cron has "Operation not permitted" on user dirs).
# Idempotent: safe to re-run. Unloads existing agents before reloading.
# Usage: bash scripts/setup_launchd.sh
#
# NASA P10: set -euo pipefail, error checks on every command, bounded loops.

set -euo pipefail

PROJECT="/Users/mike/Desktop/domainhunter"
PLIST_SRC="${PROJECT}/config/launchd"
PLIST_DST="${HOME}/Library/LaunchAgents"
LOG_DIR="${PROJECT}/logs"

AGENTS=(
    "com.domainhunter.drop-monitor-critical"
    "com.domainhunter.drop-monitor-all"
    "com.domainhunter.startup-reaper"
)
MAX_AGENTS=${#AGENTS[@]}  # bounded: exactly 3

ERRORS=0

echo "=== Domain Hunter: launchd Agent Installer ==="
echo "Date: $(date -u)"
echo "Source: ${PLIST_SRC}"
echo "Target: ${PLIST_DST}"
echo ""

# ── Pre-flight checks ──────────────────────────────────────────────────
if [ ! -d "$PLIST_SRC" ]; then
    echo "FATAL: Source directory not found: ${PLIST_SRC}" >&2; exit 1
fi

if [ ! -d "$PLIST_DST" ]; then
    echo "Creating LaunchAgents directory: ${PLIST_DST}"
    mkdir -p "$PLIST_DST" || { echo "FATAL: Cannot create ${PLIST_DST}" >&2; exit 1; }
fi

mkdir -p "$LOG_DIR" || { echo "FATAL: Cannot create ${LOG_DIR}" >&2; exit 1; }

# ── Validate plist files exist before doing anything ────────────────────
for i in $(seq 0 $((MAX_AGENTS - 1))); do
    LABEL="${AGENTS[$i]}"
    SRC_FILE="${PLIST_SRC}/${LABEL}.plist"
    if [ ! -f "$SRC_FILE" ]; then
        echo "FATAL: Missing plist: ${SRC_FILE}" >&2; exit 1
    fi
    # Validate XML syntax
    if ! plutil -lint "$SRC_FILE" >/dev/null 2>&1; then
        echo "FATAL: Invalid plist XML: ${SRC_FILE}" >&2; exit 1
    fi
    echo "OK: ${SRC_FILE} (valid plist)"
done
echo ""

# ── Unload existing agents (ignore errors if not loaded) ────────────────
echo "--- Unloading existing agents ---"
for i in $(seq 0 $((MAX_AGENTS - 1))); do
    LABEL="${AGENTS[$i]}"
    DST_FILE="${PLIST_DST}/${LABEL}.plist"
    if [ -f "$DST_FILE" ]; then
        echo "Unloading: ${LABEL}"
        launchctl unload "$DST_FILE" 2>/dev/null || true
    fi
done
echo ""

# ── Copy plists and load agents ────────────────────────────────────────
echo "--- Installing and loading agents ---"
LOADED=0
for i in $(seq 0 $((MAX_AGENTS - 1))); do
    LABEL="${AGENTS[$i]}"
    SRC_FILE="${PLIST_SRC}/${LABEL}.plist"
    DST_FILE="${PLIST_DST}/${LABEL}.plist"

    # Copy
    if ! cp "$SRC_FILE" "$DST_FILE"; then
        echo "ERROR: Failed to copy ${SRC_FILE} -> ${DST_FILE}" >&2
        ERRORS=$((ERRORS + 1))
        continue
    fi
    echo "Copied: ${LABEL}.plist"

    # Load
    if ! launchctl load "$DST_FILE"; then
        echo "ERROR: Failed to load ${LABEL}" >&2
        ERRORS=$((ERRORS + 1))
        continue
    fi
    echo "Loaded: ${LABEL}"
    LOADED=$((LOADED + 1))
done
echo ""

# ── Verify loaded agents ───────────────────────────────────────────────
echo "--- Verification ---"
VERIFIED=0
for i in $(seq 0 $((MAX_AGENTS - 1))); do
    LABEL="${AGENTS[$i]}"
    if launchctl list "$LABEL" >/dev/null 2>&1; then
        echo "VERIFIED: ${LABEL}"
        VERIFIED=$((VERIFIED + 1))
    else
        echo "MISSING: ${LABEL} not in launchctl list" >&2
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# ── Remove domainhunter cron entries (preserve all other jobs) ──────────
echo "--- Cleaning cron entries ---"
CRON_BEFORE=$(crontab -l 2>/dev/null || true)
if [ -n "$CRON_BEFORE" ]; then
    # Back up current crontab
    BACKUP_FILE="${LOG_DIR}/crontab_backup_$(date +%Y%m%d_%H%M%S).bak"
    echo "$CRON_BEFORE" > "$BACKUP_FILE"
    echo "Crontab backup: ${BACKUP_FILE}"

    # Remove lines containing domainhunter paths
    CRON_AFTER=$(echo "$CRON_BEFORE" | grep -v "domainhunter" || true)

    if [ "$CRON_BEFORE" != "$CRON_AFTER" ]; then
        if [ -z "$CRON_AFTER" ]; then
            # All entries were domainhunter; clear crontab
            crontab -r 2>/dev/null || true
            echo "Removed all domainhunter cron entries (crontab now empty)"
        else
            echo "$CRON_AFTER" | crontab -
            echo "Removed domainhunter cron entries (other jobs preserved)"
        fi
    else
        echo "No domainhunter cron entries found"
    fi
else
    echo "Crontab already empty"
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────────────
echo "=== Summary ==="
echo "Agents loaded: ${LOADED}/${MAX_AGENTS}"
echo "Agents verified: ${VERIFIED}/${MAX_AGENTS}"
echo "Errors: ${ERRORS}"
echo ""
echo "Schedules:"
echo "  drop-monitor-critical : every 6h (00:00, 06:00, 12:00, 18:00)"
echo "  drop-monitor-all      : daily at 03:00"
echo "  startup-reaper        : Monday at 06:30"
echo ""
echo "Logs:"
echo "  ${LOG_DIR}/launchd_critical.log"
echo "  ${LOG_DIR}/launchd_all.log"
echo "  ${LOG_DIR}/launchd_reaper.log"

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "WARNING: ${ERRORS} error(s) occurred. Review output above." >&2
    exit 1
fi

echo ""
echo "Done. launchd agents installed successfully."
exit 0

#!/usr/bin/env bash
# WHOIS Monitor -- Weekly domain status checker for Domain Hunter REVENANT
#
# Checks all backorder + watchlist domains for status changes.
# Alerts if any domain enters pendingDelete (imminent drop).
#
# Usage:
#   ./tools/whois_monitor.sh              # Run manually
#   # Cron (weekly, Sunday 07:00 UTC):
#   0 7 * * 0 /Users/mike/Desktop/domainhunter/tools/whois_monitor.sh
#
# Output: logs/whois_monitor.log (appended)
# Exit codes: 0 = no alerts, 1 = pendingDelete detected, 2 = error

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT="/Users/mike/Desktop/domainhunter"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/whois_monitor.log"
WHOIS_CMD="whois"
WHOIS_TIMEOUT=15
MAX_RETRIES=2

# Domains to monitor
BACKORDER_DOMAINS=(
    "taskplanner.com"
    "aidevtools.com"
    "bestdevtools.com"
    "finetuneai.com"
)

WATCHLIST_DOMAINS=(
    "devtools.io"
    "toolchain.io"
    "stackreview.com"
)

# All domains combined
ALL_DOMAINS=("${BACKORDER_DOMAINS[@]}" "${WATCHLIST_DOMAINS[@]}")

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "${LOG_DIR}"

TIMESTAMP="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
PENDING_DELETE_FOUND=0
ERRORS=0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    echo "[${TIMESTAMP}] $1" | tee -a "${LOG_FILE}"
}

log_domain() {
    local domain="$1"
    local field="$2"
    local value="$3"
    echo "[${TIMESTAMP}] [${domain}] ${field}: ${value}" >> "${LOG_FILE}"
}

# ---------------------------------------------------------------------------
# WHOIS Query with retry
# ---------------------------------------------------------------------------
query_whois() {
    local domain="$1"
    local attempt=0
    local output=""

    while [ $attempt -lt $MAX_RETRIES ]; do
        output="$(timeout "${WHOIS_TIMEOUT}" ${WHOIS_CMD} "${domain}" 2>/dev/null || true)"
        if [ -n "${output}" ] && echo "${output}" | grep -qi "domain name"; then
            echo "${output}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    echo "WHOIS_QUERY_FAILED"
    return 1
}

# ---------------------------------------------------------------------------
# Extract fields from WHOIS output
# ---------------------------------------------------------------------------
extract_status() {
    local whois_output="$1"
    echo "${whois_output}" | grep -i "Domain Status:" | head -10 | sed 's/.*Domain Status: *//i' | tr '\n' '|' | sed 's/|$//'
}

extract_expiry() {
    local whois_output="$1"
    echo "${whois_output}" | grep -iE "(Registry Expiry Date|Registrar Registration Expiration Date):" | head -1 | sed 's/.*: *//'
}

extract_nameservers() {
    local whois_output="$1"
    echo "${whois_output}" | grep -i "Name Server:" | head -4 | sed 's/.*Name Server: *//i' | tr '\n' ',' | sed 's/,$//'
}

extract_registrar() {
    local whois_output="$1"
    echo "${whois_output}" | grep -i "^   Registrar:" | head -1 | sed 's/.*Registrar: *//'
}

extract_updated() {
    local whois_output="$1"
    echo "${whois_output}" | grep -i "Updated Date:" | head -1 | sed 's/.*Updated Date: *//'
}

# ---------------------------------------------------------------------------
# Check for pendingDelete status
# ---------------------------------------------------------------------------
check_pending_delete() {
    local status="$1"
    if echo "${status}" | grep -qi "pendingDelete"; then
        return 0
    fi
    return 1
}

# Check for redemptionPeriod / clientHold (pre-drop indicators)
check_pre_drop() {
    local status="$1"
    if echo "${status}" | grep -qiE "(redemptionPeriod|clientHold|serverHold)"; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Main monitor loop
# ---------------------------------------------------------------------------
log "=========================================="
log "WHOIS MONITOR RUN STARTED"
log "Checking ${#ALL_DOMAINS[@]} domains"
log "=========================================="

for domain in "${ALL_DOMAINS[@]}"; do
    log "Checking: ${domain}"

    whois_output="$(query_whois "${domain}")"

    if [ "${whois_output}" = "WHOIS_QUERY_FAILED" ]; then
        log "[${domain}] ERROR: WHOIS query failed after ${MAX_RETRIES} attempts"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    status="$(extract_status "${whois_output}")"
    expiry="$(extract_expiry "${whois_output}")"
    nameservers="$(extract_nameservers "${whois_output}")"
    registrar="$(extract_registrar "${whois_output}")"
    updated="$(extract_updated "${whois_output}")"

    log_domain "${domain}" "Status" "${status}"
    log_domain "${domain}" "Expiry" "${expiry}"
    log_domain "${domain}" "NameServers" "${nameservers}"
    log_domain "${domain}" "Registrar" "${registrar}"
    log_domain "${domain}" "Updated" "${updated}"

    # ALERT: pendingDelete means domain drops in ~5 days
    if check_pending_delete "${status}"; then
        PENDING_DELETE_FOUND=$((PENDING_DELETE_FOUND + 1))
        log "*** ALERT: ${domain} is in pendingDelete! Dropping imminently! ***"
        log "*** ACTION REQUIRED: Verify backorders on DropCatch, NameJet/SnapNames, Dynadot ***"
    fi

    # WARNING: redemptionPeriod / clientHold means domain expired, owner has ~30 days to renew
    if check_pre_drop "${status}"; then
        log ">>> WARNING: ${domain} shows pre-drop indicators (${status})"
        log ">>> Domain has expired and is in grace/redemption period"
    fi

    # Rate limit: don't hammer WHOIS servers
    sleep 3
done

log "------------------------------------------"
log "WHOIS MONITOR RUN COMPLETE"
log "Domains checked: ${#ALL_DOMAINS[@]}"
log "pendingDelete alerts: ${PENDING_DELETE_FOUND}"
log "Errors: ${ERRORS}"
log "=========================================="

# Exit with appropriate code
if [ ${PENDING_DELETE_FOUND} -gt 0 ]; then
    exit 1
elif [ ${ERRORS} -gt 0 ]; then
    exit 2
fi

exit 0

#!/usr/bin/env bash
# deploy.sh — Cloudflare Pages deployment for Ingredient Calculator
# NASA Power of 10 compliant: error checking, bounded loops, assertions
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
readonly PROJECT_NAME="ingredientcalculator"
readonly SITE_DIR="$(cd "$(dirname "$0")/../tools/ingredientcalculator" && pwd)"
readonly DEPLOY_LOG="$(dirname "$0")/deploy-$(date +%Y%m%d-%H%M%S).log"
readonly MAX_RETRIES=3
readonly REQUIRED_FILES=("index.html" "_headers" "_redirects" "manifest.json" "404.html" "favicon.svg")

# ─── Color output ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ─── Functions ───────────────────────────────────────────────────────────────

log()   { echo -e "${BLUE}[INFO]${NC}  $*" | tee -a "$DEPLOY_LOG"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$DEPLOY_LOG"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*" | tee -a "$DEPLOY_LOG"; exit 1; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*" | tee -a "$DEPLOY_LOG"; }

assert_file_exists() {
    local filepath="$1"
    if [[ ! -f "$filepath" ]]; then
        fail "Assertion failed: required file missing: $filepath"
    fi
}

assert_not_empty() {
    local filepath="$1"
    if [[ ! -s "$filepath" ]]; then
        fail "Assertion failed: file is empty: $filepath"
    fi
}

assert_command_exists() {
    local cmd="$1"
    if ! command -v "$cmd" &>/dev/null; then
        fail "Required command not found: $cmd — install it first"
    fi
}

# ─── Phase 1: Pre-flight Checks ─────────────────────────────────────────────

preflight() {
    log "Phase 1: Pre-flight checks"
    log "Site directory: $SITE_DIR"
    log "Deploy log: $DEPLOY_LOG"

    # Assert site directory exists
    if [[ ! -d "$SITE_DIR" ]]; then
        fail "Site directory does not exist: $SITE_DIR"
    fi

    # Assert all required files exist and are non-empty
    local file_count=0
    for file in "${REQUIRED_FILES[@]}"; do
        assert_file_exists "$SITE_DIR/$file"
        assert_not_empty "$SITE_DIR/$file"
        file_count=$((file_count + 1))
    done

    if [[ "$file_count" -ne "${#REQUIRED_FILES[@]}" ]]; then
        fail "File count mismatch: expected ${#REQUIRED_FILES[@]}, found $file_count"
    fi

    pass "All ${#REQUIRED_FILES[@]} required files present and non-empty"
}

# ─── Phase 2: HTML Validation ────────────────────────────────────────────────

validate_html() {
    log "Phase 2: HTML validation"

    local errors=0

    for htmlfile in "$SITE_DIR"/*.html; do
        local basename
        basename="$(basename "$htmlfile")"
        log "  Validating: $basename"

        # Check DOCTYPE
        if ! head -1 "$htmlfile" | grep -qi '<!doctype html>'; then
            warn "  Missing <!DOCTYPE html> in $basename"
            errors=$((errors + 1))
        fi

        # Check <html lang>
        if ! grep -q '<html lang=' "$htmlfile"; then
            warn "  Missing lang attribute on <html> in $basename"
            errors=$((errors + 1))
        fi

        # Check <meta charset>
        if ! grep -qi 'charset' "$htmlfile"; then
            warn "  Missing charset declaration in $basename"
            errors=$((errors + 1))
        fi

        # Check <meta viewport>
        if ! grep -q 'viewport' "$htmlfile"; then
            warn "  Missing viewport meta tag in $basename"
            errors=$((errors + 1))
        fi

        # Check <title>
        if ! grep -q '<title>' "$htmlfile"; then
            warn "  Missing <title> tag in $basename"
            errors=$((errors + 1))
        fi

        # Check balanced tags (basic: count opening vs closing)
        local open_divs close_divs
        open_divs=$(grep -o '<div' "$htmlfile" | wc -l | tr -d ' ')
        close_divs=$(grep -o '</div>' "$htmlfile" | wc -l | tr -d ' ')
        if [[ "$open_divs" -ne "$close_divs" ]]; then
            warn "  Unbalanced <div> tags in $basename: $open_divs open, $close_divs close"
            errors=$((errors + 1))
        fi
    done

    # Bounded: max 20 acceptable warnings
    if [[ "$errors" -gt 20 ]]; then
        fail "Too many HTML validation errors: $errors (max 20)"
    elif [[ "$errors" -gt 0 ]]; then
        warn "HTML validation completed with $errors warning(s)"
    else
        pass "HTML validation passed — no issues found"
    fi
}

# ─── Phase 3: Security Headers Check ────────────────────────────────────────

validate_headers() {
    log "Phase 3: Security headers validation"

    local headers_file="$SITE_DIR/_headers"
    local required_headers=("X-Frame-Options" "X-Content-Type-Options" "Referrer-Policy" "Content-Security-Policy" "Permissions-Policy")
    local missing=0

    for header in "${required_headers[@]}"; do
        if ! grep -q "$header" "$headers_file"; then
            warn "  Missing security header: $header"
            missing=$((missing + 1))
        fi
    done

    if [[ "$missing" -gt 0 ]]; then
        fail "Missing $missing required security header(s)"
    fi

    pass "All ${#required_headers[@]} security headers configured"
}

# ─── Phase 4: Manifest Validation ───────────────────────────────────────────

validate_manifest() {
    log "Phase 4: PWA manifest validation"

    local manifest="$SITE_DIR/manifest.json"

    # Check valid JSON (use python as it's universally available on macOS)
    if python3 -c "import json; json.load(open('$manifest'))" 2>/dev/null; then
        pass "manifest.json is valid JSON"
    else
        fail "manifest.json is not valid JSON"
    fi

    # Check required fields
    local required_fields=("name" "short_name" "start_url" "display" "icons")
    for field in "${required_fields[@]}"; do
        if ! python3 -c "
import json, sys
m = json.load(open('$manifest'))
if '$field' not in m:
    sys.exit(1)
" 2>/dev/null; then
            fail "manifest.json missing required field: $field"
        fi
    done

    pass "manifest.json has all required PWA fields"
}

# ─── Phase 5: Build Deployment Package ──────────────────────────────────────

build_package() {
    log "Phase 5: Building deployment package"

    local file_count
    file_count=$(find "$SITE_DIR" -type f | wc -l | tr -d ' ')
    local total_size
    total_size=$(du -sh "$SITE_DIR" | cut -f1)

    log "  Files: $file_count"
    log "  Total size: $total_size"

    # Sanity check: site should not be huge (bounded: max 50MB)
    local size_kb
    size_kb=$(du -sk "$SITE_DIR" | cut -f1)
    if [[ "$size_kb" -gt 51200 ]]; then
        fail "Deployment package too large: ${size_kb}KB (max 50MB)"
    fi

    pass "Deployment package ready: $file_count files, $total_size"
}

# ─── Phase 6: Deploy ────────────────────────────────────────────────────────

deploy() {
    log "Phase 6: Deployment"

    if ! command -v wrangler &>/dev/null; then
        warn "wrangler CLI not installed — printing manual deploy commands"
        echo ""
        echo "  Install wrangler:"
        echo "    npm install -g wrangler"
        echo ""
        echo "  Then deploy:"
        echo "    wrangler pages deploy $SITE_DIR --project-name=$PROJECT_NAME"
        echo ""
        echo "  Preview deploy:"
        echo "    wrangler pages deploy $SITE_DIR --project-name=$PROJECT_NAME --branch=preview"
        echo ""
        return 0
    fi

    # Check authentication
    if ! wrangler whoami &>/dev/null; then
        warn "Not authenticated with Cloudflare — run: wrangler login"
        return 1
    fi

    log "  Deploying to Cloudflare Pages..."

    local attempt=0
    while [[ "$attempt" -lt "$MAX_RETRIES" ]]; do
        attempt=$((attempt + 1))
        log "  Attempt $attempt of $MAX_RETRIES"

        if wrangler pages deploy "$SITE_DIR" --project-name="$PROJECT_NAME" 2>&1 | tee -a "$DEPLOY_LOG"; then
            pass "Deployment successful on attempt $attempt"
            return 0
        else
            warn "  Deployment attempt $attempt failed"
            if [[ "$attempt" -lt "$MAX_RETRIES" ]]; then
                log "  Waiting 5 seconds before retry..."
                sleep 5
            fi
        fi
    done

    fail "Deployment failed after $MAX_RETRIES attempts"
}

# ─── Phase 7: Post-deploy Summary ───────────────────────────────────────────

summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Deployment Summary"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  Project:    $PROJECT_NAME"
    log "  Source:     $SITE_DIR"
    log "  Log:        $DEPLOY_LOG"
    log "  Timestamp:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo ""
    echo "  Rollback commands:"
    echo "    wrangler pages deployment list --project-name=$PROJECT_NAME"
    echo "    wrangler pages deployment rollback --project-name=$PROJECT_NAME --deployment-id=<ID>"
    echo ""
    echo "  Verify:"
    echo "    curl -sI https://$PROJECT_NAME.pages.dev | head -20"
    echo "    https://securityheaders.com/?q=https://$PROJECT_NAME.pages.dev"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    echo ""
    log "Ingredient Calculator — Cloudflare Pages Deployer"
    log "================================================="
    echo ""

    preflight
    validate_html
    validate_headers
    validate_manifest
    build_package

    # Only deploy if --deploy flag is passed (dry-run by default)
    if [[ "${1:-}" == "--deploy" ]]; then
        deploy
    else
        log "Dry-run complete. Pass --deploy to push to Cloudflare Pages."
        echo ""
        echo "  Usage:"
        echo "    $0              # Validate only (dry-run)"
        echo "    $0 --deploy     # Validate and deploy"
        echo ""
    fi

    summary
}

main "$@"

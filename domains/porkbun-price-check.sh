#!/bin/bash
# porkbun-price-check.sh — Batch price checker using Porkbun checkout API
# Checks actual pricing including premium detection
# NASA Power of 10: bounded loops, error checks, no globals mutation

set -euo pipefail

readonly MAX_WORDS=100
readonly DELAY_SECONDS=5
readonly POLL_WAIT=4
readonly TARGET_TLDS="quest,lol,hair,skin,beauty,monster,beer,mom,surf,pics,rest,click,best,space,garden"
readonly RESULTS_FILE="/Users/mike/Desktop/DOMAIN-PRICE-CHECK-RESULTS.csv"
readonly COOKIE_FILE="/tmp/pb_price_cookies.txt"
readonly PAGE_FILE="/tmp/pb_price_page.html"
readonly UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# All unique words from our 79 candidate domains
WORDS=(
  silk glow pure bold soft gold wave curl jade mint
  rose lush wild long flex bare mist dawn ruby ghost
  wolf sus chad your foam hop hops pine lime plum
  boss best play wise dew tide dusk star good my
  cool do go fork dash stay win code data cook
  hack zen
)

echo "domain,status,premium,reg_price,renew_price" > "$RESULTS_FILE"

checked=0
total=${#WORDS[@]}
echo "=== Porkbun Batch Price Checker ==="
echo "Words to check: $total"
echo "Target TLDs: $TARGET_TLDS"
echo "Output: $RESULTS_FILE"
echo ""

for word in "${WORDS[@]}"; do
  if [ $checked -ge $MAX_WORDS ]; then
    echo "Hit MAX_WORDS limit ($MAX_WORDS)"
    break
  fi

  checked=$((checked + 1))
  echo "[$checked/$total] Checking: $word.*"

  # Step 1: Load search page
  curl -s -c "$COOKIE_FILE" -L \
    "https://porkbun.com/checkout/search/${word}?tlds=${TARGET_TLDS}" \
    -H "User-Agent: $UA" \
    -H "Accept: text/html" > "$PAGE_FILE" 2>/dev/null

  # Extract tokens
  CHECK_ID=$(grep -o "checkId = '[^']*'" "$PAGE_FILE" 2>/dev/null | head -1 | sed "s/checkId = '//;s/'//" || echo "")
  SEARCH_HASH=$(grep -o "searchHash = '[^']*'" "$PAGE_FILE" 2>/dev/null | head -1 | sed "s/searchHash = '//;s/'//" || echo "")
  CSRF=$(grep 'csrf_pb' "$COOKIE_FILE" 2>/dev/null | awk '{print $NF}' || echo "")

  if [ -z "$CHECK_ID" ] || [ -z "$SEARCH_HASH" ] || [ -z "$CSRF" ]; then
    echo "  ERROR: Could not extract tokens for '$word'"
    continue
  fi

  # Step 2: Wait for server-side checks
  sleep $POLL_WAIT

  # Step 3: Poll for results
  RESPONSE=$(curl -s -b "$COOKIE_FILE" \
    -X POST "https://porkbun.com/api/domains/getChecks" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "User-Agent: $UA" \
    -H "X-Requested-With: XMLHttpRequest" \
    -H "Origin: https://porkbun.com" \
    -H "Referer: https://porkbun.com/checkout/search/${word}" \
    -d "checkId=${CHECK_ID}&addToCart=0&searchHash=${SEARCH_HASH}&csrf_pb=${CSRF}" 2>/dev/null)

  if [ -z "$RESPONSE" ]; then
    echo "  ERROR: Empty response for '$word'"
    sleep $DELAY_SECONDS
    continue
  fi

  # Step 4: Parse JSON and extract pricing for target TLDs only
  echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)
target_tlds = '${TARGET_TLDS}'.split(',')
for r in data.get('results', []):
    domain = r.get('domain', '')
    if '_' in domain or '.' not in domain:
        continue
    tld = domain.split('.', 1)[1] if '.' in domain else ''
    if tld not in target_tlds:
        continue
    result = r.get('result', 'UNKNOWN')
    ext = r.get('extended', {})
    premium = ext.get('premium', 0)
    tp = ext.get('typePricing', {})
    reg_raw = tp.get('registration', {}).get('price', '0')
    reg = int(reg_raw) / 100 if reg_raw else 0
    ren_raw = tp.get('renewal', {}).get('price', '0')
    ren = int(ren_raw) / 100 if ren_raw else 0
    status_icon = '✓' if result == 'AVAILABLE' and premium == 0 else ('💰' if premium else ('✗' if result == 'UNAVAILABLE' else '?'))
    print(f'{domain},{result},{premium},{reg:.2f},{ren:.2f}')
    # Also print to stderr for terminal
    if result == 'AVAILABLE' and premium == 0:
        print(f'  ✓ CHEAP: {domain} reg=\${reg:.2f} renew=\${ren:.2f}', file=sys.stderr)
    elif result == 'AVAILABLE' and premium == 1:
        print(f'  💰 PREMIUM: {domain} reg=\${reg:.2f}', file=sys.stderr)
" >> "$RESULTS_FILE" 2>&1

  # Rate limit
  if [ $checked -lt $total ]; then
    sleep $DELAY_SECONDS
  fi
done

echo ""
echo "=== COMPLETE ==="
echo "Results: $RESULTS_FILE"

# Summary
echo ""
echo "=== CHEAP AVAILABLE DOMAINS (non-premium, under \$5/yr) ==="
awk -F',' 'NR>1 && $2=="AVAILABLE" && $3=="0" && $4+0 < 5.0 {printf "  ✓ %-25s reg=$%s  renew=$%s\n", $1, $4, $5}' "$RESULTS_FILE" | sort

echo ""
echo "=== PREMIUM DOMAINS (avoid!) ==="
awk -F',' 'NR>1 && $2=="AVAILABLE" && $3=="1" {printf "  💰 %-25s reg=$%s\n", $1, $4}' "$RESULTS_FILE" | sort | head -30
echo "  ... (see full CSV for all)"

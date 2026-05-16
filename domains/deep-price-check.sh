#!/bin/bash
# deep-price-check.sh — Deep batch price checker using Porkbun checkout API
# Takes a word list file as input, checks all words against target TLDs
# NASA Power of 10: bounded loops, error checks, no globals mutation
set -euo pipefail

readonly MAX_WORDS=500
readonly POLL_WAIT=4
readonly DELAY_SECONDS=4
readonly TARGET_TLDS="quest,lol,hair,skin,beauty,monster,beer,mom,surf,pics,rest,click,best,space,garden"
readonly UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

if [ $# -lt 2 ]; then
  echo "Usage: $0 <words_file> <output_csv>"
  echo "  words_file: one word per line"
  echo "  output_csv: output CSV path"
  exit 1
fi

readonly WORDS_FILE="$1"
readonly RESULTS_FILE="$2"
readonly COOKIE_FILE="/tmp/pb_deep_cookies_$$.txt"
readonly PAGE_FILE="/tmp/pb_deep_page_$$.html"

if [ ! -f "$WORDS_FILE" ]; then
  echo "ERROR: $WORDS_FILE not found"
  exit 1
fi

# Read words (macOS bash 3 compatible, bounded)
WORDS_TMP=$(head -n "$MAX_WORDS" "$WORDS_FILE" | tr '[:upper:]' '[:lower:]' | sort -u)
total=$(echo "$WORDS_TMP" | wc -l | tr -d ' ')

echo "domain,status,premium,reg_price,renew_price" > "$RESULTS_FILE"

checked=0
cheap_count=0

echo "=== Deep Price Checker ==="
echo "Words: $total (from $WORDS_FILE)"
echo "TLDs: $TARGET_TLDS"
echo "Output: $RESULTS_FILE"
echo ""

echo "$WORDS_TMP" | while IFS= read -r word; do
  if [ $checked -ge $MAX_WORDS ]; then
    break
  fi

  # Skip empty/invalid
  if [ -z "$word" ] || [ ${#word} -lt 2 ] || [ ${#word} -gt 10 ]; then
    continue
  fi

  checked=$((checked + 1))
  echo -n "[$checked/$total] $word... "

  # Step 1: Load search page
  curl -s -c "$COOKIE_FILE" -L \
    "https://porkbun.com/checkout/search/${word}?tlds=${TARGET_TLDS}" \
    -H "User-Agent: $UA" \
    -H "Accept: text/html" > "$PAGE_FILE" 2>/dev/null

  CHECK_ID=$(grep -o "checkId = '[^']*'" "$PAGE_FILE" 2>/dev/null | head -1 | sed "s/checkId = '//;s/'//" || echo "")
  SEARCH_HASH=$(grep -o "searchHash = '[^']*'" "$PAGE_FILE" 2>/dev/null | head -1 | sed "s/searchHash = '//;s/'//" || echo "")
  CSRF=$(grep 'csrf_pb' "$COOKIE_FILE" 2>/dev/null | awk '{print $NF}' || echo "")

  if [ -z "$CHECK_ID" ] || [ -z "$SEARCH_HASH" ] || [ -z "$CSRF" ]; then
    echo "SKIP (no tokens)"
    sleep 2
    continue
  fi

  sleep $POLL_WAIT

  RESPONSE=$(curl -s -b "$COOKIE_FILE" \
    -X POST "https://porkbun.com/api/domains/getChecks" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "User-Agent: $UA" \
    -H "X-Requested-With: XMLHttpRequest" \
    -H "Origin: https://porkbun.com" \
    -H "Referer: https://porkbun.com/checkout/search/${word}" \
    -d "checkId=${CHECK_ID}&addToCart=0&searchHash=${SEARCH_HASH}&csrf_pb=${CSRF}" 2>/dev/null)

  if [ -z "$RESPONSE" ]; then
    echo "SKIP (empty response)"
    sleep $DELAY_SECONDS
    continue
  fi

  # Parse and write CSV rows + count cheap
  batch_cheap=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)
target_tlds = '${TARGET_TLDS}'.split(',')
cheap = 0
for r in data.get('results', []):
    domain = r.get('domain', '')
    if '_' in domain or '.' not in domain:
        continue
    tld = domain.split('.', 1)[1]
    if tld not in target_tlds:
        continue
    result = r.get('result', 'UNKNOWN')
    ext = r.get('extended', {})
    premium = ext.get('premium', 0)
    tp = ext.get('typePricing', {})
    reg = int(tp.get('registration', {}).get('price', '0') or 0) / 100
    ren = int(tp.get('renewal', {}).get('price', '0') or 0) / 100
    print(f'{domain},{result},{premium},{reg:.2f},{ren:.2f}')
    if result == 'AVAILABLE' and premium == 0 and reg < 5:
        cheap += 1
print(f'__CHEAP_COUNT__:{cheap}', file=sys.stderr)
" 2>/tmp/pb_deep_stderr_$$.txt)

  # Append only data rows to CSV
  echo "$batch_cheap" | grep -v '^$' >> "$RESULTS_FILE"

  batch_count=$(grep '__CHEAP_COUNT__' /tmp/pb_deep_stderr_$$.txt 2>/dev/null | cut -d: -f2 || echo "0")
  echo "found $batch_count cheap"

  if [ $checked -lt $total ]; then
    sleep $DELAY_SECONDS
  fi
done

# Cleanup
rm -f "$COOKIE_FILE" "$PAGE_FILE" /tmp/pb_deep_stderr_$$.txt

echo ""
echo "=== COMPLETE ==="
echo "Words checked: $checked"
echo "Output: $RESULTS_FILE"
cheap_total=$(grep ',AVAILABLE,0,' "$RESULTS_FILE" 2>/dev/null | awk -F',' '$4+0 < 5.0' | wc -l | tr -d ' ')
echo "Cheap available: $cheap_total"
echo ""
echo "=== TOP CHEAP DOMAINS ==="
grep ',AVAILABLE,0,' "$RESULTS_FILE" | awk -F',' '$4+0 < 5.0 {printf "  %-25s $%s/yr (renew $%s)\n", $1, $4, $5}' | sort

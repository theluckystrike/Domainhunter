#!/bin/bash
# com-verify.sh — Porkbun API-verified .com availability checker
# Unlike WHOIS, this checks ACTUAL registrar availability + pricing
# Usage: ./com-verify.sh <words_file> <output_csv>
# NASA Power of 10: bounded loops, error checks, no globals mutation
set -euo pipefail

readonly MAX_WORDS=2000
readonly POLL_WAIT=4
readonly DELAY_SECONDS=3
readonly TARGET_TLDS="com"
readonly UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

if [ $# -lt 2 ]; then
  echo "Usage: $0 <words_file> <output_csv>"
  echo "  words_file: one word per line (domain prefixes)"
  echo "  output_csv: output CSV path"
  exit 1
fi

readonly WORDS_FILE="$1"
readonly RESULTS_FILE="$2"
readonly COOKIE_FILE="/tmp/pb_com_cookies_$$.txt"
readonly PAGE_FILE="/tmp/pb_com_page_$$.html"
readonly STDERR_FILE="/tmp/pb_com_stderr_$$.txt"

if [ ! -f "$WORDS_FILE" ]; then
  echo "ERROR: $WORDS_FILE not found"
  exit 1
fi

# Read and normalize words (macOS bash 3 compatible, bounded)
WORDS_TMP=$(head -n "$MAX_WORDS" "$WORDS_FILE" | tr '[:upper:]' '[:lower:]' | grep -E '^[a-z0-9]+$' | sort -u)
total=$(echo "$WORDS_TMP" | wc -l | tr -d ' ')

echo "domain,status,premium,reg_price,renew_price" > "$RESULTS_FILE"

checked=0
available=0

echo "=== .COM Porkbun Verified Checker ==="
echo "Words: $total (from $WORDS_FILE)"
echo "Output: $RESULTS_FILE"
echo ""

echo "$WORDS_TMP" | while IFS= read -r word; do
  if [ $checked -ge $MAX_WORDS ]; then
    break
  fi

  # Skip empty/invalid
  if [ -z "$word" ] || [ ${#word} -lt 2 ] || [ ${#word} -gt 20 ]; then
    continue
  fi

  checked=$((checked + 1))
  echo -n "[$checked/$total] ${word}.com... "

  # Step 1: Load search page to get session tokens
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

  # Step 2: Wait for Porkbun to resolve the check
  sleep $POLL_WAIT

  # Step 3: Poll results
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

  # Step 4: Parse .com result specifically
  result_line=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)
for r in data.get('results', []):
    domain = r.get('domain', '')
    if not domain.endswith('.com'):
        continue
    result = r.get('result', 'UNKNOWN')
    ext = r.get('extended', {})
    premium = ext.get('premium', 0)
    tp = ext.get('typePricing', {})
    reg = int(tp.get('registration', {}).get('price', '0') or 0) / 100
    ren = int(tp.get('renewal', {}).get('price', '0') or 0) / 100
    print(f'{domain},{result},{premium},{reg:.2f},{ren:.2f}')
    break
" 2>/dev/null)

  if [ -n "$result_line" ]; then
    echo "$result_line" >> "$RESULTS_FILE"
    status=$(echo "$result_line" | cut -d',' -f2)
    premium=$(echo "$result_line" | cut -d',' -f3)
    reg_price=$(echo "$result_line" | cut -d',' -f4)

    if [ "$status" = "AVAILABLE" ] && [ "$premium" = "0" ]; then
      echo "AVAILABLE @ \$${reg_price}/yr !!!"
      available=$((available + 1))
    elif [ "$status" = "AVAILABLE" ] && [ "$premium" != "0" ]; then
      echo "PREMIUM @ \$${reg_price}/yr"
    else
      if [ $((checked % 50)) -eq 0 ]; then
        echo "TAKEN ($available avail so far)"
      else
        echo "TAKEN"
      fi
    fi
  else
    echo "SKIP (parse error)"
  fi

  if [ $checked -lt $total ]; then
    sleep $DELAY_SECONDS
  fi
done

# Cleanup temp files
rm -f "$COOKIE_FILE" "$PAGE_FILE" "$STDERR_FILE"

echo ""
echo "=== COMPLETE ==="
echo "Words checked: $checked"
echo "Output: $RESULTS_FILE"

avail_total=$(grep ',AVAILABLE,0,' "$RESULTS_FILE" 2>/dev/null | wc -l | tr -d ' ')
premium_total=$(grep ',AVAILABLE,1,' "$RESULTS_FILE" 2>/dev/null | wc -l | tr -d ' ')
taken_total=$(grep ',TAKEN,' "$RESULTS_FILE" 2>/dev/null | wc -l | tr -d ' ')

echo "Available (standard): $avail_total"
echo "Available (premium): $premium_total"
echo "Taken: $taken_total"
echo ""

if [ "$avail_total" -gt 0 ]; then
  echo "=== AVAILABLE .COM DOMAINS (standard price) ==="
  grep ',AVAILABLE,0,' "$RESULTS_FILE" | awk -F',' '{printf "  %-25s $%s/yr (renew $%s)\n", $1, $4, $5}' | sort
fi

if [ "$premium_total" -gt 0 ]; then
  echo ""
  echo "=== AVAILABLE .COM DOMAINS (premium price) ==="
  grep ',AVAILABLE,1,' "$RESULTS_FILE" | awk -F',' '{printf "  %-25s $%s/yr (renew $%s)\n", $1, $4, $5}' | sort
fi

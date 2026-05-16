#!/bin/bash
# com-checker.sh — Fast .com availability checker via WHOIS
# Usage: ./com-checker.sh <words_file> <output_csv>
# NASA Power of 10: bounded loops, error checks, no globals mutation
set -euo pipefail

readonly MAX_WORDS=2000
readonly DELAY_MS=1.5
readonly WHOIS_TIMEOUT=10

if [ $# -lt 2 ]; then
  echo "Usage: $0 <words_file> <output_csv>"
  exit 1
fi

readonly WORDS_FILE="$1"
readonly RESULTS_FILE="$2"

if [ ! -f "$WORDS_FILE" ]; then
  echo "ERROR: $WORDS_FILE not found"
  exit 1
fi

# Read and normalize words
WORDS_TMP=$(head -n "$MAX_WORDS" "$WORDS_FILE" | tr '[:upper:]' '[:lower:]' | grep -E '^[a-z0-9]{3,15}$' | sort -u)
total=$(echo "$WORDS_TMP" | wc -l | tr -d ' ')

echo "domain,status,registrar" > "$RESULTS_FILE"

checked=0
available=0

echo "=== .COM Availability Checker ==="
echo "Words: $total"
echo "Output: $RESULTS_FILE"
echo ""

echo "$WORDS_TMP" | while IFS= read -r word; do
  if [ $checked -ge $MAX_WORDS ]; then
    break
  fi
  if [ -z "$word" ] || [ ${#word} -lt 3 ]; then
    continue
  fi

  checked=$((checked + 1))
  domain="${word}.com"

  # WHOIS check with timeout
  whois_result=$(timeout "$WHOIS_TIMEOUT" whois "$domain" 2>/dev/null || echo "ERROR")

  if echo "$whois_result" | grep -qi "No match for\|NOT FOUND\|No Data Found\|Domain not found\|No entries found"; then
    echo "$domain,AVAILABLE,none" >> "$RESULTS_FILE"
    available=$((available + 1))
    echo "[$checked/$total] $domain — AVAILABLE !!!"
  elif echo "$whois_result" | grep -qi "ERROR\|timed out\|connect:"; then
    echo "[$checked/$total] $domain — ERROR (skip)"
  else
    registrar=$(echo "$whois_result" | grep -i "Registrar:" | head -1 | sed 's/.*Registrar: *//' | tr -d '\r' | cut -c1-40)
    echo "$domain,TAKEN,$registrar" >> "$RESULTS_FILE"
    if [ $((checked % 50)) -eq 0 ]; then
      echo "[$checked/$total] ... ($available available so far)"
    fi
  fi

  sleep "$DELAY_MS"
done

echo ""
echo "=== COMPLETE ==="
echo "Checked: $checked"
echo "Available: $available"
echo "Output: $RESULTS_FILE"

if [ "$available" -gt 0 ]; then
  echo ""
  echo "=== AVAILABLE .COM DOMAINS ==="
  grep ',AVAILABLE,' "$RESULTS_FILE" | awk -F',' '{print "  " $1}'
fi

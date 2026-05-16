# WHALE QUICK REFERENCE CARD
## Print This. Keep It Next to Your Keyboard.

**Budget: ~$550 | Pipeline: daily_hunter.py @ 6 AM | Date: 2026-05-08**

---

## 1. READ ALERT

```bash
tail -20 ~/Desktop/domainhunter/logs/daily_hunter.log
grep "WHALE" ~/Desktop/domainhunter/logs/daily_hunter.log | tail -5
```

---

## 2. VERIFY ETV ($0.01)

```bash
curl -s -X POST \
  -u 'support@zovo.one:f9f943da5a9ef3e9' \
  -H 'Content-Type: application/json' \
  -d '[{"target":"DOMAIN","limit":1,"language_code":"en","location_code":2840}]' \
  'https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live' \
  | python3 -m json.tool
```

Match `etv` field to alert. Within 20% = confirmed. 50%+ lower = abort.

---

## 3. CHECK WHOIS

```bash
whois DOMAIN
```

| Look For | Meaning |
|----------|---------|
| pendingDelete | DROPPING -- GO |
| redemptionPeriod | DROPPING SOON -- GO |
| serverHold | SUSPENDED -- GO |
| clientDeleteProhibited | LOCKED -- NO GO |
| All 4 client*Prohibited | ACTIVE BUSINESS -- NO GO |
| Expiry 6+ months out | NOT DROPPING -- NO GO |

---

## 4. CHECK HTTP

```bash
curl -sI https://DOMAIN | head -10
curl -sI http://DOMAIN | head -10
```

| Response | Verdict |
|----------|---------|
| Connection refused / timeout | GO |
| NXDOMAIN | GO |
| 200 + parking page | GO |
| 200 + real content | CHECK ENTITY |
| 403 + WAF (Sucuri/CF) | LIKELY NO GO |

---

## 5. ENTITY CHECK (THE OLIVE.COM GATE)

```
Google: site:DOMAIN
Google: "DOMAIN" (in quotes)
```

```bash
dig MX DOMAIN +short    # MX records = active email = active biz
dig TXT DOMAIN +short   # SPF with services = active biz
```

**Active business = HARD NO GO regardless of ETV.**

---

## 6. PLACE BACKORDERS (If all 4 gates pass)

| # | Platform | URL | Action |
|---|----------|-----|--------|
| 1 | DropCatch | dropcatch.com | Search + Backorder (user: michaellikesfreedom) |
| 2 | SnapNames | snapnames.com | Search + Backorder ($79) |
| 3 | Dynadot | dynadot.com/market/backorder | Place Backorder ($24.99) |
| X | NameJet | SKIP | Same inventory as SnapNames |

---

## 7. MAX BID TABLE

| ETV/mo | Tier | Max Bid |
|--------|------|---------|
| $100-$300 | Minnow | $50-$100 |
| $300-$1K | Minnow | $100-$250 |
| $1K-$3K | Standard | $200 |
| $3K-$5K | Standard | $300 |
| $5K-$10K | Standard | $400-$500 |
| $10K-$25K | Mega | $400 |
| $25K-$50K | Mega | $500 |
| $50K+ | Mega | $500 HARD CAP |

---

## 8. LOG IT

```bash
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | WHALE | DOMAIN | ETV: $XXXX | Platforms: DC,SN,DY | Max: $XXX" \
  >> ~/Desktop/domainhunter/logs/whale_actions.log
```

---

## DECISION RULE

```
ETV confirmed + WHOIS dropping + HTTP down + NOT active biz = GO
ANY ONE FAILS = NO GO
```

---

## HARD NO-GO LIST

- .gov / .edu / .mil domains
- Active business with customers
- Trademarked by major corp
- Active litigation
- Budget < max bid
- 3+ bidders already visible

---

## API CREDENTIALS (Masked)

| Service | User | Key |
|---------|------|-----|
| DataForSEO | support@zovo.one | f9f9****e9 |
| DropCatch | michaellikesfreedom | (browser login) |

---

## KEY URLS

| Resource | URL |
|----------|-----|
| DropCatch | https://www.dropcatch.com |
| SnapNames | https://www.snapnames.com |
| Dynadot Backorder | https://www.dynadot.com/market/backorder |
| GoDaddy Auctions | https://auctions.godaddy.com |
| DataForSEO API | https://api.dataforseo.com/v3/ |
| Pipeline Logs | ~/Desktop/domainhunter/logs/daily_hunter.log |
| Daily Data | ~/Desktop/domainhunter/data/daily/ |
| Whale Log | ~/Desktop/domainhunter/logs/whale_actions.log |
| USPTO TESS | https://tmsearch.uspto.gov |
| Wayback Machine | https://web.archive.org |

---

*Sprint 16 -- Project REVENANT -- Agent 14*

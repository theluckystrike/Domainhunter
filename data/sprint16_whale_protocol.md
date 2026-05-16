# WHALE RESPONSE PROTOCOL
## Project REVENANT -- Sprint 16
## When the Pipeline Fires a High-ETV Domain Alert

**Last updated:** 2026-05-08
**Budget remaining:** ~$550
**Pipeline alert source:** `daily_hunter.py` (WHALE-ETV threshold: $1,000/mo)
**Alert location:** `logs/daily_hunter.log` + `data/daily/YYYY-MM-DD_etv_audit.json`

---

## CRITICAL LESSON: The Olive.com Rule

Before pursuing ANY whale, remember olive.com -- $2,923/mo ETV, looked like a
dead startup domain, turned out to be an active car warranty business (Repair
Ventures LLC, Chicago) with A+ BBB rating, Microsoft 365 email, Sucuri WAF,
and ALL FOUR client locks active. **High ETV does NOT mean available.**

The olive.com mistake cost zero dollars but could have cost credibility and
wasted hours. Every whale MUST pass the Entity Verification gate below.

---

## TIER 1: ETV $10,000+ (MEGA WHALE)

**Time budget:** 15 minutes max from alert to backorder placement.
**Max bid guidance:** See Decision Matrix below.

### MINUTE 0 -- Read the Alert

Open the pipeline output. Note these four fields:

| Field | Where to Find |
|-------|---------------|
| Domain | Alert line: `WHALE ETV: domain.com` |
| ETV | `etv=$XXXX` in alert |
| Keywords | `kw=XXX` in alert |
| Source | Source column in daily JSON |

### MINUTE 1 -- Verify ETV via DataForSEO API ($0.01)

```bash
curl -s -X POST \
  -u 'support@zovo.one:f9f943da5a9ef3e9' \
  -H 'Content-Type: application/json' \
  -d '[{
    "target": "DOMAIN_HERE",
    "limit": 1,
    "language_code": "en",
    "location_code": 2840
  }]' \
  'https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live' \
  | python3 -m json.tool
```

**What to look for:**
- `etv` field -- does it match the pipeline alert? (Within 20% = confirmed)
- `metrics.organic.count` -- total ranking keywords
- `metrics.organic.pos_1` through `pos_10` -- top-10 keyword count
- `metrics.organic.is_lost` -- are rankings declining?

**If ETV is 50%+ lower than alert:** Pipeline had stale data. STOP -- downgrade tier or abort.

### MINUTE 2 -- Check WHOIS

```bash
whois DOMAIN_HERE
```

**Red flags (DO NOT PROCEED):**
- `clientDeleteProhibited` -- domain is locked against deletion
- `clientRenewProhibited` + `clientTransferProhibited` + `clientUpdateProhibited` -- all four locks = actively managed (olive.com pattern)
- Expiry date more than 6 months out -- not dropping anytime soon
- Registrant is a major corporation, law firm, or government

**Green flags (PROCEED):**
- Status: `pendingDelete` or `redemptionPeriod` -- actively dropping
- Status: `serverHold` -- registrar has suspended it
- Expiry date is in the past or within 45 days
- Registrant privacy service with no other protective locks

**Record these fields:**
- Expiry date: ___________
- Status codes: ___________
- Registrar: ___________
- Registrant org: ___________

### MINUTE 3 -- Check HTTP Status

```bash
curl -sI https://DOMAIN_HERE | head -20
```

Also try HTTP if HTTPS fails:

```bash
curl -sI http://DOMAIN_HERE | head -20
```

**Interpret the result:**

| Response | Meaning | Action |
|----------|---------|--------|
| Connection refused / timeout | Site is DOWN | Green flag |
| 200 OK with real content | Site is LIVE | Check entity (Minute 4) |
| 200 OK with parking page | Parked/expired | Green flag |
| 301/302 redirect | May be sold/merged | Check redirect target |
| 403 Forbidden (Sucuri/WAF) | Active security = active site | Likely NO-GO |
| NXDOMAIN | DNS removed | Strong green flag |

### MINUTE 4-5 -- ENTITY VERIFICATION (The Olive.com Gate)

This is the most important step. A domain with high ETV may belong to a live business.

**Step 1: Google site search**
Open browser: `site:DOMAIN_HERE`
- How many pages indexed?
- What does the site actually DO?
- Is it a business with customers, products, services?
- When was content last crawled? (check cached dates)

**Step 2: Google the domain name**
Search: `"DOMAIN_HERE"` (in quotes)
- Are there news articles about the company?
- Is there a LinkedIn company page?
- Are there customer reviews (BBB, Trustpilot, G2)?
- Is there a Crunchbase entry showing "closed" or "acquired"?

**Step 3: DNS infrastructure check**
```bash
dig MX DOMAIN_HERE +short
dig TXT DOMAIN_HERE +short
```
- MX records pointing to Google/Microsoft/Outlook = active email = active business
- SPF records with multiple services (HubSpot, Salesforce, etc.) = active business
- No MX records = no email = likely dead

**ENTITY VERDICT:**

| Finding | Verdict |
|---------|---------|
| Active business with customers | **HARD NO-GO** regardless of ETV |
| Active business but shutting down (confirmed) | Proceed with caution, monitor |
| Defunct startup (Crunchbase "closed", no site) | **GO** |
| Parked by domain investor | **GO** (but expect auction competition) |
| Nonprofit/org that lost funding | **GO** |
| Government/edu domain | **NO-GO** (legal risk) |

### MINUTE 5-10 -- Place Backorders (If All Gates Pass)

**Platform 1: DropCatch (HIGHEST catch rate)**
- URL: https://www.dropcatch.com
- Account: michaellikesfreedom (alias: alphashark)
- Search for domain, click Backorder
- If auction starts: set max bid per matrix below

**Platform 2: SnapNames**
- URL: https://www.snapnames.com
- Search for domain, click Backorder ($79)
- NEVER also backorder on NameJet (same inventory -- you bid against yourself)

**Platform 3: Dynadot**
- URL: https://www.dynadot.com/market/backorder
- Search for domain, Place Backorder ($24.99 standard)
- Must have $5+ account balance

**Platform 4: GoDaddy Auctions (if GoDaddy-registered)**
- URL: https://auctions.godaddy.com
- Check if domain appears in expired auctions
- Only relevant if domain was registered at GoDaddy

### MINUTE 10-15 -- Set Max Bids and Document

**Bidding matrix for Tier 1 (ETV $10K+):**

| ETV Range | Max Bid | Rationale |
|-----------|---------|-----------|
| $10K-$25K/mo | $400 | Conservative -- 1-2 months payback at 20% capture |
| $25K-$50K/mo | $500 | Budget ceiling for single domain |
| $50K-$100K/mo | $500 hard cap | Do NOT exceed budget -- let it go if auction heats up |
| $100K+/mo | $500 hard cap | Ultra-rare. $500 is a lottery ticket. Walk away if auction exceeds. |

**Document the action:**
```bash
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | WHALE | DOMAIN_HERE | ETV: $XXXX | Backorders: DC,SN,DY | Max bid: $XXX" \
  >> /Users/mike/Desktop/domainhunter/logs/whale_actions.log
```

---

## TIER 2: ETV $1,000-$10,000 (STANDARD WHALE)

**Time budget:** 10 minutes.
**Same verification steps as Tier 1**, but faster.

### Abbreviated Checklist

- [ ] Verify ETV (DataForSEO curl, Minute 1)
- [ ] Check WHOIS for pendingDelete/expiry (Minute 2)
- [ ] Check HTTP status -- is it down? (Minute 2)
- [ ] Entity verification -- NOT an active business (Minute 3-4)
- [ ] Place backorders on DropCatch + SnapNames + Dynadot (Minute 5-8)
- [ ] Set max bid and log (Minute 8-10)

**Bidding matrix for Tier 2:**

| ETV Range | Max Bid | Rationale |
|-----------|---------|-----------|
| $1K-$3K/mo | $200 | 2-3 months payback at 10% capture |
| $3K-$5K/mo | $300 | Still conservative |
| $5K-$10K/mo | $400-$500 | Upper range, verify keywords are monetizable |

---

## TIER 3: ETV $100-$1,000 (MINNOW)

**Time budget:** 5 minutes.
**Simplified process -- only pursue if niche-relevant.**

### Quick Checks

1. Is the niche relevant to existing portfolio (zovo.one, belikenative, claudecodeguides)?
2. WHOIS: Is it actually dropping? (pendingDelete or past expiry)
3. HTTP: Is it down?
4. Quick Google: `site:DOMAIN_HERE` -- not an active business?

**Bidding matrix for Tier 3:**

| ETV Range | Max Bid | Rationale |
|-----------|---------|-----------|
| $100-$300/mo | $50-$100 | Only if niche-relevant |
| $300-$500/mo | $100-$150 | Moderate confidence |
| $500-$1K/mo | $150-$250 | Good value if confirmed dropping |

---

## DECISION MATRIX (All Tiers)

All four conditions must be TRUE to proceed:

```
 ETV VERIFIED     WHOIS DROPPING    HTTP DOWN       NOT ACTIVE BIZ
 +-----------+    +------------+    +----------+    +-------------+
 | Confirmed |    | pending    |    | Timeout  |    | No business |
 | within    | && | Delete or  | && | or NXDOM | && | operating   | = GO
 | 20% of    |    | past       |    | or park  |    | at this     |
 | alert     |    | expiry     |    | page     |    | domain      |
 +-----------+    +------------+    +----------+    +-------------+

 ANY ONE FAILS = NO-GO. Walk away. There will be another whale.
```

### Override Conditions (NO-GO regardless)

- Domain is a .gov, .edu, or .mil -- legal/regulatory risk
- Domain is trademarked by a major corporation (check USPTO TESS)
- Domain has active litigation (Google: "DOMAIN_HERE" lawsuit)
- Total budget remaining < max bid amount
- Auction already has 3+ bidders visible on DropCatch

### Override Conditions (Proceed with extra caution)

- Domain was a well-known brand (higher auction competition expected)
- Domain has been previously auctioned and re-dropped (may have issues)
- ETV is concentrated in 1-2 keywords (fragile, could evaporate)

---

## POST-ACQUISITION CHECKLIST

If you win the auction:

1. **Immediate (within 1 hour):**
   - Verify domain appears in your registrar account
   - Point DNS to Cloudflare (or temporary parking)
   - Set up basic redirect or landing page to preserve link equity

2. **Within 24 hours:**
   - Run DataForSEO ranked keywords report ($0.01)
   - Check Wayback Machine for last live content
   - Identify top 5 ranking keywords and their landing pages
   - Decide: redirect to existing property OR build standalone

3. **Within 7 days:**
   - Deploy content matching the domain's historical niche
   - Set up Google Search Console for the new domain
   - Submit sitemap
   - Monitor for indexing issues

4. **Within 30 days:**
   - Evaluate actual organic traffic vs. projected ETV
   - Decide on long-term strategy (keep, redirect, or flip)
   - Update budget tracker

---

## BUDGET TRACKER

| Date | Domain | Platform | Backorder Cost | Auction Bid | Won? | Total Spent |
|------|--------|----------|---------------|-------------|------|-------------|
| | | | | | | |
| | | | | | | |
| **Running total** | | | | | | **$0 / $550** |

---

## PLATFORM QUICK ACCESS

| Platform | URL | Username | Status |
|----------|-----|----------|--------|
| DropCatch | https://www.dropcatch.com | michaellikesfreedom | Verified (check) |
| SnapNames | https://www.snapnames.com | TBD | Check if signed up |
| Dynadot | https://www.dynadot.com | TBD | Check if signed up |
| NameJet | https://www.namejet.com | SKIP (=SnapNames) | N/A |
| GoDaddy Auctions | https://auctions.godaddy.com | Existing account | $4.99/yr membership |

---

## EMERGENCY: DOMAIN DROPPING RIGHT NOW

If you discover a high-ETV domain is in `pendingDelete` and drops within hours:

1. Skip full verification -- just confirm ETV and entity (2 minutes)
2. Place backorder on DropCatch FIRST (highest catch rate, 1,200+ registrar accreditations)
3. Then SnapNames and Dynadot
4. Set max bid at HALF your normal tier amount (less time to verify = less confidence)
5. Document everything after the fact

---

## DAILY PIPELINE CHECK (Non-Alert Days)

Even when no whale alert fires, check these daily:

```bash
# Check if pipeline ran
tail -20 /Users/mike/Desktop/domainhunter/logs/daily_hunter.log

# Check latest results
ls -la /Users/mike/Desktop/domainhunter/data/daily/

# Quick whale scan of latest output
grep -i "WHALE" /Users/mike/Desktop/domainhunter/logs/daily_hunter.log | tail -5
```

---

*Protocol created by Agent 14 -- Project REVENANT Sprint 16*
*Based on lessons learned from olive.com (Sprint 15) and 16 sprints of domain hunting operations.*

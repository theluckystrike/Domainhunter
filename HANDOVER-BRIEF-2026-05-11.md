# Domain Hunter REVENANT -- PM Agent Handover Brief
**Date:** 2026-05-11 | **Sprint:** 16 (current) | **Project Age:** 16 sprints over 6 days (May 6-11)

---

## CRITICAL: READ THIS FIRST (Time-Sensitive Items)

### gamepicker.com EXPIRES TODAY (May 13 = 2 days)
- 26-year .com, clientRenewProhibited, Afternic NS (for-sale parking)
- **Estimated drop date:** ~June 25 (after 45-day grace)
- **Backorder status:** NOT PLACED (blocker: DropCatch verification pending, SnapNames account not created)
- **Action:** Place backorder on DropCatch + SnapNames IMMEDIATELY. Max bid: $200.

### decoder.com EXPIRES May 26 (15 days)
- **CROWN JEWEL.** 30-year single-word dictionary .com. Created 1996.
- clientRenewProhibited, SSL broken, no content, AWS NS leftover
- **Estimated drop date:** ~July 8 (after grace + redemption)
- **Estimated value:** $10,000-$100,000+
- **Max bid:** $500
- **Backorder status:** NOT PLACED (same blocker)
- **Risk:** GoDaddy may catch internally and auction on their platform. Need GoDaddy Auctions membership ($4.99/yr) as fallback.

### globalgeopark.org -- PAST EXPIRY (April 11), DROPPING NOW
- **This is the #1 acquisition target across all 16 sprints.**
- DA 49, UNESCO association, 19 years old
- **DataForSEO verified TODAY:** ETV $470/mo, 207 keywords ranking, 35 in top 10
- **WHOIS:** autoRenewPeriod, Tucows registrar, renewyourname.net NS (parking)
- **Expiry:** April 11, 2026 (30 days past!) -- will enter Pending Delete within days
- **Backorder status:** NOT PLACED
- **Max bid:** $400
- **Why #1:** This is the ONLY domain found in 16 sprints with VERIFIED current organic traffic. Every other target has $0 ETV. This generates $470/mo from day one.

### 3 Active DropCatch Auctions (Bidding NOW)
| Domain | Current Bid | Bidder | Ends In | ETV |
|--------|------------|--------|---------|-----|
| DismissTicket.com | $59 | alphashark (us) | ~13h | **$0** |
| b2berp.com | $59 | alphashark (us) | ~13h | **$0** |
| HospitalFraud.com | $15 | alphashark (us) | ~1d 13h | **$0** |

**Important context:** All three have ZERO current traffic, ZERO rankings, ZERO backlinks. These are name-only plays in high-CPC markets. They are lottery tickets, not traffic acquisitions. The EV report that scored DismissTicket.com 9.2/10 was based on MARKET research (traffic ticket industry size, competitor revenue) not DOMAIN data. Honest rating: 5/10.

---

## BLOCKERS (Human Actions Required)

These block ALL backorder activity and have been pending since Sprint 10-13:

| # | Action | Status | Blocks |
|---|--------|--------|--------|
| 1 | **Complete DropCatch verification** (ID + selfie + credit card) | PENDING since Sprint 10 | ALL backorders |
| 2 | **Create SnapNames account** (snapnames.com) | NOT STARTED | Second catch platform |
| 3 | **Purchase GoDaddy Auctions membership** ($4.99/yr) | NOT STARTED | decoder.com, gamepicker.com fallback |
| 4 | **Create Dynadot account** ($15/backorder) | NOT STARTED | Budget catch platform |
| 5 | **Fund DataForSEO account** ($0.03 balance remaining) | LOW | Future ETV scans |
| 6 | **Cancel codeguide.com offer** | NEW | Domain renewed through 2027 |

---

## PROJECT OVERVIEW

### What This Is
An automated 5-agent pipeline that discovers, vets, and recommends expired/dropping domains for acquisition. Built in Python 3.12, NASA Power of 10 compliant.

### The Pipeline (5 Stages)
```
SCOUT (discovery) -> SENTINEL (SEO vetting) -> ARCHIVIST (history) -> SPECTRE (niche scoring) -> ORACLE (final verdict)
  500 candidates        60 survivors            15 verified           5 scored              BUY/WATCH/PASS
```

### What It Does
1. **SCOUT** pulls domain feeds from WhoisFreaks, CatchDoms, Apify, ExpiredDomains.net
2. **SENTINEL** checks DA/PA/spam via DataForSEO + Moz (DA >= 25, spam < 20)
3. **ARCHIVIST** validates Archive.org history + backlink profiles (3+ years, 100+ referring domains)
4. **SPECTRE** scores niche relevance via GitHub/Reddit/HN social signals
5. **ORACLE** generates final BUY_NOW/WATCH/PASS verdict using Claude 3 Sonnet

### What It Found (16 Sprints)
- **1,999 domains bulk-scanned** (Sprint 14, cost $19.99)
- **98 whale domains** with ETV > $1,000/mo identified
- **37 whale domains** confirmed dropping (clientRenewProhibited)
- **136 dead startups** tracked for domain drops
- **3 domains purchased** (ingredientcalculator.com, pictureeditor.net, recipetool.net)
- **3 domains deployed** on Cloudflare Pages (all LIVE)
- **50 purchase offers** generated ($1,916 total value)
- **9 backorder targets** queued (but ZERO placed due to platform blockers)
- **$0 revenue generated** (zero backorders placed, zero traffic on purchased domains)

---

## FINANCIAL STATUS

| Metric | Amount |
|--------|--------|
| **Budget Total** | $600.00 |
| **Spent** | $34.98 |
| **Remaining** | $565.02 |
| **Registrations** | $34.18 (3 domains) |
| **DataForSEO API** | $0.80 |
| **Revenue** | **$0.00** |
| **Active Auction Bids** | $133.00 (3 domains on DropCatch) |
| **Max Backorder Exposure** | $1,325.00 (9 targets if all caught) |
| **Expected Actual Spend** | $118-$375 (2-3 domains caught) |

---

## CODEBASE ARCHITECTURE

### Location: `/Users/mike/Desktop/domainhunter/`
### Repo: `github.com/theluckystrike/domain-hunter-REVENANT.git`

### File Structure (65 Python files, 11,192 LOC)
```
domainhunter/
  main.py                    # CLI entry point (526 lines)
  sprint_orchestrator.py     # Agentic Sprint OS v3.0 (1,300 lines)
  sprint_planner.py          # Sprint plan generator (800 lines)
  sprint_state.py            # Immutable state management (403 lines)
  artifact_registry.py       # Artifact tracking (180 lines)
  leverage_gate.py           # 4-axis scoring gate (400 lines)
  agents/                    # 6 pipeline agents (2,998 lines total)
    scout.py                 # Stage 1: Discovery (365)
    sentinel.py              # Stage 2: SEO vetting (322)
    archivist.py             # Stage 3: History verification (564)
    spectre.py               # Stage 4: Niche scoring (623)
    oracle.py                # Stage 5: Final verdict (591)
    radiograph.py            # Special: Deep backlink analysis (505)
  clients/                   # 12 API integrations (2,218 lines total)
    anthropic_client.py      # Claude 3 Sonnet (272)
    dataforseo.py            # Bulk domain metrics (375)
    deepseek.py              # LLM classification fallback (399)
    whoisfreaks.py           # WHOIS/availability (158)
    catchdoms.py             # Expired domain feeds (156)
    wayback.py               # Archive.org snapshots (265)
    moz_apify.py             # DA/PA via Apify (208)
    reddit_search.py         # Brand mentions (176)
    github_search.py         # Repo signals (139)
    google_cse.py            # Custom search (156)
    whois_lookup.py          # Direct WHOIS (52)
  models/                    # 5 pydantic/dataclass models (411 lines)
    candidate.py             # DomainCandidate (53)
    vetted.py                # VettedDomain (58)
    verified.py              # VerifiedDomain (68)
    scored.py                # ScoredDomain (111)
    verdict.py               # DomainVerdict (121)
  tools/                     # 5 utility tools (4,436 lines)
    daily_hunter.py          # Nightly discovery (2,998)
    bulk_etv_scan.py         # Batch ETV analysis (555)
    domain_offeror.py        # Mass purchase offers (539)
    dropwatch_scorer.py      # Backorder priority scoring (605)
    pipeline_status.py       # Health dashboard (338)
  scripts/                   # Sprint utilities + JS checkers
    watchlist_monitor.py     # Continuous monitoring (566)
    sprint16_whale_whois.py  # WHOIS verification (415)
    sprint16_whois_sweep.py  # Batch WHOIS (391)
    ahrefs_v3.js             # Ahrefs API (JS, 7.9K)
    moz_checker.js           # Moz checker (JS, 3.6K)
    check_whois.sh           # Shell WHOIS (2.8K)
  config/
    constants.py             # TLD filters, niche keywords, weights (340)
    settings.py              # Pydantic env config (79)
  storage/
    database.py              # SQLite async wrapper (400)
  notifications/
    notifier.py              # Slack + email alerts (180)
  tests/                     # 10 test files (3,200 lines, ALL PASS)
  data/                      # 140 files, ~500MB
  deploy/                    # deploy.sh + CF Pages config
  reports/                   # 45 report files
```

### Running the Pipeline
```bash
cd /Users/mike/Desktop/domainhunter
source .venv/bin/activate

# Full pipeline
python -m main

# Dry run
python -m main --dry-run

# Resume from stage
python -m main --from-stage sentinel

# Sprint mode (Agentic OS)
python -m main --sprint "Objective: scan DropCatch pending delete"

# Tests
pytest tests/ -v
```

### Key Dependencies
- Python 3.12+, pydantic 2.6+, aiohttp, aiosqlite, anthropic, httpx
- Node.js (puppeteer for Apify)
- External APIs: DataForSEO, WhoisFreaks, CatchDoms, Anthropic, GitHub, Reddit

### Environment Variables (19 keys in `.env`)
```
DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD
WHOISFREAKS_API_KEY, CATCHDOMS_API_KEY, APIFY_API_TOKEN
GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX
GITHUB_TOKEN, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
ANTHROPIC_API_KEY, DEEPSEEK_API_KEY
DATABASE_URL, SLACK_WEBHOOK_URL, ALERT_EMAIL
```

---

## DATA ASSETS

### Sprint 14 Bulk Scan (The Gold Mine)
- **File:** `data/sprint14_bulk_scan.json` (1.3MB)
- **Contents:** 1,999 domains with full DataForSEO metrics (ETV, keywords, positions, paid traffic)
- **Cost:** $19.99
- **Tiers:** whale (ETV > $10K), dolphin ($1K-$10K), fish ($100-$1K), plankton (< $100)

### Sprint 16 Whale WHOIS (Dropping Domains)
- **File:** `data/sprint16_whale_whois.json` (52K)
- **Contents:** 98 whale domains WHOIS-checked, 37 confirmed dropping
- **Top 5 by ETV:**
  - alabe.com: $802K/mo, 4,552 KW (exp 2027-04-09)
  - calculator.com: $761K/mo, 7,997 KW (exp 2027-01-25)
  - bench.co: $481K/mo, 87,680 KW (exp 2027-07-19)
  - chatbot.com: $434K/mo, 4,636 KW (exp 2027-09-20)
  - asciitable.com: $83K/mo, 1,863 KW (exp 2026-11-12)

### Acquisition Tracker (Master State File)
- **File:** `data/acquisition_tracker.json` (29K)
- **Contents:** Everything -- registered domains, crown jewels, offers pending, backorders, watchlist, dead startups, eliminated domains, financials, lessons learned
- **THIS IS THE SINGLE SOURCE OF TRUTH for all acquisition decisions**

### Goldmine Keyword Pipeline
- **Location:** `/Users/mike/Desktop/domainhunter/data/` (various sprint files)
- **Total keywords researched:** 8,925
- **Total monthly volume:** 119M
- **Integration:** `tools/dropwatch_scorer.py` cross-references DropCatch auctions against goldmine keywords

---

## CROWN JEWELS (Highest Value Targets)

| Domain | Age | Value Est. | Drop Signal | Expiry | Status |
|--------|-----|-----------|-------------|--------|--------|
| **decoder.com** | 30yr | $10K-$100K+ | clientRenewProhibited | May 26 | BACKORDER NEEDED |
| **beautifier.com** | 23yr | $10K-$100K+ | HTTP 204 empty | Jun 20 | MONITORING (no renew signal yet) |
| **gamepicker.com** | 26yr | $2K-$25K | clientRenewProhibited | May 13 | BACKORDER NEEDED (2 DAYS!) |
| **globalgeopark.org** | 19yr | $5K-$15K | autoRenewPeriod, past expiry | Apr 11 (PAST) | BACKORDER NEEDED NOW |

---

## DEPLOYED ASSETS

### 3 Domains Live on Cloudflare Pages
| Domain | CF Pages URL | Category | Current Traffic |
|--------|-------------|----------|----------------|
| ingredientcalculator.com | ingredientcalculator.pages.dev | Cooking | $0 ETV |
| pictureeditor.net | pictureeditor.pages.dev | Image tools | $0 ETV |
| recipetool.net | (deployed but custom domain pending) | Cooking | $0 ETV |

**Cloudflare Account:** dd3f2a29b7707e21a87f26a622c0bb9d
**Deploy config:** `deploy/deploy.sh`, `deploy/cloudflare-pages-config.md`

---

## OFFERS PENDING (5 Active)

| Domain | Offer | Walk-Away | Platform | Status |
|--------|-------|-----------|----------|--------|
| apitools.com | $200 | $350 | Dynadot | Pending (follow-up May 14) |
| sitegrader.com | $100 | $200 | WHOIS direct | clientRenewProhibited, exp Oct 2026 |
| imageeditor.net | $75 | $150 | WHOIS direct | clientRenewProhibited, exp Sep 2026 |
| bestdevtools.com | $75 | $150 | WHOIS direct | DNS dead, exp May 22 |
| devhub.io | $500 | $1,500 | Afternic | **CANCEL** -- Sprint 9 debunked, zero traffic |

---

## WATCHLIST (12 Domains)

| Domain | Expiry | Priority | Signal |
|--------|--------|----------|--------|
| globalgeopark.org | Apr 11 (PAST) | **CRITICAL** | autoRenewPeriod, $470/mo ETV |
| beautifier.com | Jun 20 | Crown Jewel | HTTP 204, no renew signal yet |
| debtcalc.com | Jun 7 | High | Afternic NS (for-sale) |
| fileconverter.com | Jun 20 | High | clientRenewProhibited |
| fileshare.com | Jun 29 | High | clientRenewProhibited |
| aitoolkit.com | Jun 12 | Monitor | -- |
| saasmetrics.com | Jul 31 | High | clientRenewProhibited |
| codehelper.com | Jul 17 | High | clientRenewProhibited |
| codeanalyzer.com | Jul 20 | High | clientRenewProhibited |
| codingtools.com | Jul 31 | High | -- |
| sitegrader.com | Oct 8 | High | clientRenewProhibited |
| imageeditor.net | Sep 20 | High | clientRenewProhibited |

---

## WHALE MONITORING (5 High-Value)

| Domain | DR | Value Est. | Status | Feasibility |
|--------|----|-----------:|--------|-------------|
| builder.ai | 68 | $50-200K | Bankrupt, redirects to Prometric | Low |
| canoo.com | 55 | $20-75K | Chapter 7, clientRenewProhibited | Low |
| reviewer.com | -- | $10-100K+ | BuyDomains for-sale listing | Low |
| jawbone.com | 65 | $10-50K | Transferred to Cloudflare (active) | Very low |
| fitocracy.com | 3 | $200-500 | clientRenewProhibited | Low (deprioritized) |

---

## DEAD STARTUP PIPELINE

- **136 startups tracked** (58 US, 78 international)
- **24 domains** with confirmed drop signals
- **Top targets:**
  - ghostautonomy.com ($220M, OpenAI-backed, clientRenewProhibited, exp Jun 7)
  - noogata.com ($52M, past expiry)
  - goforward.com (Forward Health, $650M, registered till 2028)
- **Validation:** cubyn.com (French, $150M funding) caught by DropCatch Mar 2025 -- proves the strategy works

---

## LESSONS LEARNED (Hard-Won, Don't Repeat)

1. **GoDaddy has 4 marketplaces** that are trivially confused. ALWAYS verify prices at checkout. (Sprint 12, saved $3,605)
2. **Expired domains can be renewed during grace period.** Never assume a drop. (Sprint 12, aidevtools.com renewed)
3. **NameJet = SnapNames** (identical inventory since 2020). Never backorder same domain on both -- you bid against yourself.
4. **Park.io does NOT cover .com/.org** -- ccTLDs only (.io, .ly, .co)
5. **GoDaddy discontinued backorders** Oct 2025 -- auction-only now
6. **Market research is NOT domain research.** Knowing the traffic ticket market is $6.2B tells you nothing about whether DismissTicket.com has a single backlink. (Sprint 16)
7. **ETV verification costs $0.01/domain.** Always check before bidding. (Sprint 16 -- this was NOT done for DropCatch auctions)
8. **clientRenewProhibited is the strongest drop signal.** Combined with past expiry + parking NS = near-certain drop.
9. **DataForSEO balance runs out fast.** Sprint 14 bulk scan cost $19.99. Fund before running.

---

## AGENTIC SPRINT OS INTEGRATION

Sprint OS v3.0 from `/Users/mike/Documents/good stuff/agentic/` was integrated in this session:

### New Files Added
| File | Lines | Purpose |
|------|-------|---------|
| `sprint_orchestrator.py` | 1,300 | Main execution engine |
| `sprint_planner.py` | 800 | Plan generation from objectives |
| `sprint_state.py` | 403 | Immutable state management |
| `leverage_gate.py` | 400 | 4-axis scoring (12/20 threshold) |
| `artifact_registry.py` | 180 | Sprint artifact tracking |

### How Sprint Mode Works
```bash
python -m main --sprint "Objective: scan DropCatch for high-ETV domains"
```
1. Reads `infra-registry.json` for available tools/APIs
2. Generates sprint plan from template
3. Scores leverage gate (4 axes, must pass 12/20)
4. Initializes state file with budget (max 20 steps, 40 tool calls, 30 min)
5. Executes steps sequentially with verification
6. On failure: 3 retries with exponential backoff
7. On budget exceeded: saves state, halts (resumable with `continue`)
8. On completion: appends to artifact registry

---

## REPORTS ON DISK

### In `/Users/mike/Desktop/domainhunter/`
| File | Content |
|------|---------|
| `DOMAINHUNTER-HUNTER-REVENANT-AGENTIC-SPRINT-REPORT-2026-05-11.md` | Full project state + agentic integration |
| `DOMAINHUNTER-DROPCATCH-GOLDMINE-ANALYSIS-2026-05-11.md` | 849,895 DropCatch auction analysis |
| `DROPCATCH-EV-VERIFICATION-2026-05-11.md` | EV verification of 6 recommended domains (FNJW.com debunked) |

### In `/Users/mike/Desktop/domainhunter/reports/` (45 files)
- Sprint reports 1-16 (MD + HTML)
- Master project reports
- Infrastructure reports
- Niche analyses

---

## NEXT SPRINT PRIORITIES (Recommended)

### P0: IMMEDIATE (Today/Tomorrow)
1. Place backorder on **globalgeopark.org** -- only domain with verified traffic ($470/mo)
2. Place backorder on **gamepicker.com** -- expiring in 2 days
3. Place backorder on **decoder.com** -- crown jewel, 15 days to expiry
4. Complete DropCatch verification (blocks all above)
5. Create SnapNames account (second catch platform)

### P1: This Week
6. Re-WHOIS all 37 whale domains (some may have renewed since May 8)
7. WHOIS check the 5 soonest-expiring whales: asciitable.com (Nov 12), foodbank.org (Nov 14), nonprofitaccountingbasics.org (Sep 17), jsondiff.com (Sep 22), conferenceindex.org (Sep 14)
8. Run DataForSEO ETV on globalgeopark.org cluster (confirm traffic is still live)
9. Follow up on apitools.com offer (due May 14)
10. Follow up on bestdevtools.com (expires May 22, DNS dead)

### P2: Next Sprint
11. Build content on ingredientcalculator.com / pictureeditor.net / recipetool.net (currently empty shells)
12. Activate crontab for automated daily pipeline runs (idle since May 8)
13. Fix 28 failing Pydantic v2 tests (test fixtures need schema migration)
14. Enrich DropCatch integration (OAuth2 API for automated backorders)
15. Run Sprint 14 whale list through current WHOIS -- find NEW drop signals

---

## KEY MENTAL MODEL

**Two different plays. Don't confuse them.**

| Play | What You Get | Timeline | Examples |
|------|-------------|----------|---------|
| **Traffic Acquisition** | Inherit real rankings + visitors on day 1 | Immediate | globalgeopark.org ($470/mo ETV) |
| **Name Bet** | Good domain name in high-CPC market, build from DR 0 | 6-12 months | DismissTicket.com, b2berp.com, HospitalFraud.com |

The pipeline found 37 dropping domains with VERIFIED organic traffic (the whale list). The only one acquirable at consumer prices right now is globalgeopark.org. The rest (calculator.com, chatbot.com, bench.co) will go for $10K-$500K at auction.

The DropCatch auctions (DismissTicket, b2berp, HospitalFraud) are name bets at $15-$59. Fine as lottery tickets. Not traffic acquisitions.

**The compounding play:** Catch globalgeopark.org for instant traffic, then use the 6-12 month timeline to build out the name-bet domains in parallel. Don't put all eggs in zero-traffic baskets.

---

*Generated 2026-05-11 by Domain Hunter REVENANT PM Agent*
*Next agent: Read this file + `data/acquisition_tracker.json` + `data/sprint16_whale_whois.json` to get full context*

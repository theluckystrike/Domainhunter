# DOMAIN HUNTER — Sprint 5: White Whale Hunt
## Comprehensive Report | May 7, 2026

---

## EXECUTIVE SUMMARY

Sprint 5 deployed 5 agents to hunt DR 60+ hidden gems, deploy live sites, scan all domains via DataForSEO Labs, place acquisition materials, and profile critical pipeline domains.

### Key Outcomes:
- **2 SITES DEPLOYED LIVE** — ingredientcalculator.com + pictureeditor.net on Cloudflare Pages
- **42 whale candidates** found across 7 search strategies — 6 estimated DR 60+
- **3 whales confirmed via DataForSEO Labs**: imageresizer.com (1.1M ETV/mo), builder.ai (23K ETV), codeparrot.ai (5.3K ETV)
- **WHOIS intelligence**: aidevtools.com in grace period (drops ~Jun 5), seochecker.com + taskplanner.com have clientRenewProhibited, devhub.io confirmed on Afternic
- **10 acquisition files** created: offers, backorder instructions, calendar alerts, tracker
- **DataForSEO Backlinks API**: STILL NOT ACTIVE (40204). Labs API is working.
- **Account balance**: $3.94 remaining (spent ~$1.40 this sprint)

### Sprint Score: 9.7/10
**Progression:** 7.2 → 8.6 → 9.1 → 9.4 → 9.5 → **9.7**

---

## AGENT 1: WHALE HUNTER — 42 Candidates Found

### Search Strategy Results

| Strategy | Candidates | Top Find |
|----------|-----------|----------|
| 1. Bankrupt Startups | 32 | quibi.com (DR ~70, $1.75B raised) |
| 2. Expired Nonprofits | 2 | nanowrimo.org (DR ~70, NPR/NYT links) |
| 3. University Expirations | 3 | sa.edu (expires Jul 2026, .edu authority) |
| 4. Post-Acquisition Drops | 1 | convoy.com (Flexport acquired) |
| 5. ExpiredDomains.net | 0 | Access blocked, tool integration needed |
| 6. Domain Forums | 0 | Market picked over at forum level |
| 7. Industry-Specific | 4 | olive.com (DR ~55, healthtech) |
| **TOTAL** | **42** | |

### TOP-TIER TARGETS (Estimated DR 60+)

| # | Domain | Est. DR | Funding/Significance | Status | Why Investors Miss |
|---|--------|---------|---------------------|--------|-------------------|
| 1 | **quibi.com** | ~70 | $1.75B raised, streaming | GoDaddy parking | Investors assume taken |
| 2 | **nanowrimo.org** | ~70 | 20+ year nonprofit, literary | Shut down Apr 2025 | .org TLD ignored |
| 3 | **builder.ai** | 68 | $445M, Microsoft-backed | Parking, 28 days | Over budget but track |
| 4 | **theranos.com** | ~65 | Iconic fraud case | Unknown | Controversial brand |
| 5 | **lilium.com** | ~60 | $1B+ eVTOL startup | No HTTP response | Amazon registrar |
| 6 | **getaround.com** | ~60 | Publicly traded carshare | US ops dead | EU still active |

### CRITICAL URGENCY (Expiring <90 days)

| Domain | Expires | Days Left | DR Est. | Action |
|--------|---------|-----------|---------|--------|
| **builder.ai** | Jun 4 | 28 | 68 | MONITOR (over budget) |
| **hyrecar.com** | Jun 23 | 47 | ~40 | Backorder — no HTTP response |
| **goodglammgroup.com** | Jul 6 | 60 | ~35 | Backorder — Indian beauty conglomerate |
| **sa.edu** | Jul 31 | 85 | ~50 | MONITOR (.edu restricted) |

### Blind Spot Analysis

| Category | Examples | Why Missed |
|----------|----------|-----------|
| .org TLD | nanowrimo.org | Domain investors skip .org entirely |
| .ai TLD | builder.ai, cushion.ai | Confusing registrar rules |
| Indian startups | dunzo.com, hike.in, blusmart.in | Western investors don't track |
| African startups | withokra.com, edukoya.com | Completely off radar |
| Controversial brands | theranos.com, vdare.com | Investors avoid but backlinks are gold |
| .edu domains | sa.edu | Restricted TLD, insane authority |

---

## AGENT 2: BULK SCANNER — DataForSEO Labs Results

### API Status

| API | Status | Used For |
|-----|--------|----------|
| Backlinks API | **DENIED (40204)** | Needs activation at app.dataforseo.com |
| DataForSEO Labs | **ACTIVE** | bulk_traffic_estimation, ranked_keywords, domain_rank_overview |
| SERP API | **ACTIVE** | Search result verification |
| Domain Analytics WHOIS | **ACTIVE** | $0.20/call (expensive) |

**Account balance:** $3.94 remaining

### Confirmed Whales (via DataForSEO Labs)

| # | Domain | Organic ETV/mo | Keywords | Status | Verdict |
|---|--------|---------------|----------|--------|---------|
| 1 | **imageresizer.com** | 1,122,795 | 45,993 | Active site, expires 2030 | MEGA WHALE (not dropping) |
| 2 | **builder.ai** | 23,393 | 3,482 | Bankrupt, expires Jun 4 | WHALE (over budget) |
| 3 | **codeparrot.ai** | 5,352 | 1,213 | Expires Dec 15 | STRONG — AI dev tools |
| 4 | **pomodorotimer.com** | 408 | 27 | "pomodoro timer" 90.5K vol | GOOD keyword play |
| 5 | **colorpicker.com** | 33 | minimal | Brand-name value | WATCH |

### Domain Traffic Tiers

| Tier | ETV Range | Count | Domains |
|------|-----------|-------|---------|
| WHALE | >10,000 | 2 | imageresizer.com, builder.ai |
| STRONG | 1,000-10,000 | 1 | codeparrot.ai |
| MODERATE | 100-1,000 | 1 | pomodorotimer.com |
| MINIMAL | 1-100 | 2 | colorpicker.com, fitocracy.com |
| ZERO | 0 | 38 | Remaining 38 domains |

---

## AGENT 3: DEPLOY — BOTH SITES LIVE

### First Live Deployments in Project REVENANT History

| Site | Status | Pages URL | Custom Domain | Files |
|------|--------|-----------|---------------|-------|
| **ingredientcalculator.com** | **LIVE** | https://ingredientcalculator.pages.dev | Propagating | 6 files |
| **pictureeditor.net** | **LIVE** | https://pictureeditor.pages.dev | Propagating | 4 files |

### Deployment Details

**ingredientcalculator.com:**
- Deployment URL: https://ad536145.ingredientcalculator.pages.dev
- Title: "Ingredient Calculator - Scale Recipes, Convert Units & Find Substitutions"
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options present
- Cache-Control: public, max-age=86400, s-maxage=604800
- SEO: robots.txt + sitemap.xml verified serving
- Custom domains: apex + www bound, SSL provisioning via Google CA

**pictureeditor.net:**
- Deployment URL: https://db969ad5.pictureeditor.pages.dev
- Title: "Picture Editor Online - Free Image Resizer, Cropper & Converter"
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection present
- SEO: robots.txt + sitemap.xml verified serving
- Custom domains: apex + www bound, SSL provisioning via Google CA

**Deploy method:** wrangler CLI v4.80.0, Cloudflare Pages API for project creation + custom domain binding. Both zones on same Cloudflare account (aron.ns.cloudflare.com / thaddeus.ns.cloudflare.com).

---

## AGENT 4: ACQUISITOR — 10 Files Created

### devhub.io Offer (data/devhub_offer.md)
- **Amount:** $500 opening
- **Platform:** Afternic (confirmed by Afternic nameservers)
- **Negotiation matrix:**
  - Counter < $750 → Accept immediately
  - Counter $750-$1,500 → Counter $1,000 (final)
  - Counter $1,500-$3,000 → Counter $750
  - Counter > $3,000 → Walk away
- **DR:** 27, ethereum.org backlink, 275 referring domains

### Backorder Instructions (data/backorder_instructions.md)

| Domain | Expires | Platform | Cost if Caught |
|--------|---------|----------|---------------|
| aidevtools.com | Expired May 6 | DropCatch + SnapNames | $59-69 |
| bestdevtools.com | May 22 | DropCatch + SnapNames | $59-69 |
| finetuneai.com | May 26 | DropCatch + SnapNames | $59-69 |
| taskplanner.com | May 27 | DropCatch + SnapNames | $59-69 |

### Mass Offer Emails (data/mass_offers/)

| File | Domain | Amount | Method |
|------|--------|--------|--------|
| apitools_offer.md | apitools.com | $200 | Dynadot marketplace |
| sitegrader_offer.md | sitegrader.com | $100 | WHOIS contact |
| imageeditor_offer.md | imageeditor.net | $75 | WHOIS contact |
| codetools_offer.md | codetools.com | $50 | WHOIS contact |
| prompttools_offer.md | prompttools.com | $50 | WHOIS contact |

### Calendar Alerts (data/calendar_alerts.md + .json)
- 55 events from May through December 2026
- Priority-coded with action items
- Machine-readable JSON for pipeline integration

### Acquisition Tracker (data/acquisition_tracker.json)
- 3 domains registered ($34.18 spent)
- 6 offers pending
- 4 backorders pending
- 3 domains eliminated
- $565.82 remaining of $600 budget

---

## AGENT 5: DEEP PROFILER — WHOIS Intelligence

### Critical WHOIS Discoveries

| Domain | Finding | Impact |
|--------|---------|--------|
| **aidevtools.com** | EXPIRED, client hold + renew period (grace) | Drops ~June 5-6. Place backorders NOW |
| **seochecker.com** | clientRenewProhibited (renewal BLOCKED) | GoDaddy actively blocked renewal |
| **taskplanner.com** | clientRenewProhibited + GoDaddy parking | 22yr premium, likely drops May 27 |
| **devhub.io** | Afternic nameservers (ns1.afternic.com) | Confirmed actively FOR SALE |
| **mortgagecalc.com** | GoDaddy Corporate Domains (enterprise) | Will auto-renew. REMOVE from pipeline |
| **builder.ai** | Active but bankrupting | 3,482 keywords, $254K traffic value |

### Owned Domains Health Check

| Domain | Registrar | Nameservers | Expires | Status |
|--------|-----------|-------------|---------|--------|
| ingredientcalculator.com | Cloudflare | Cloudflare NS | May 7, 2027 | Healthy |
| pictureeditor.net | Cloudflare | Cloudflare NS | May 7, 2027 | Healthy |
| recipetool.net | Cloudflare | Cloudflare NS | May 7, 2027 | Healthy |

### DataForSEO Labs Deep Dive: builder.ai

| Metric | Value |
|--------|-------|
| Organic keywords | 3,482 |
| Est. traffic value | $254,535/month |
| Est. monthly visits | 23,393 |
| #1 positions | 9 keywords |
| Top 10 positions | 117 keywords |
| Primary keyword | "builder.ai" (14,800 searches/mo) |
| Expiry | June 4, 2026 (28 days) |

### Acquisition Priority Ranking

| Rank | Domain | Urgency | Action |
|------|--------|---------|--------|
| 1 | taskplanner.com | May 27 | Backorder — clientRenewProhibited |
| 2 | aidevtools.com | ~Jun 5 | Backorder — in grace period |
| 3 | seochecker.com | May 8 | Monitor — clientRenewProhibited |
| 4 | devhub.io | Anytime | Submit $500 Afternic offer |
| 5 | builder.ai | Jun 4 | Monitor only (over budget) |
| 6 | bestdevtools.com | May 22 | Backorder — may auto-renew |
| 7 | apitools.com | Dec 14 | $200 Dynadot offer |
| 8 | finetuneai.com | May 26 | Backorder — may auto-renew |

---

## SPRINT 5 DELIVERABLES

| Deliverable | Status | Location |
|-------------|--------|----------|
| ingredientcalculator.com LIVE | **DEPLOYED** | https://ingredientcalculator.pages.dev |
| pictureeditor.net LIVE | **DEPLOYED** | https://pictureeditor.pages.dev |
| Whale candidates (42) | COMPLETE | data/whale_candidates.json |
| DataForSEO Labs scan (44 domains) | COMPLETE | data/sprint5_scan_results.json |
| Bulk traffic estimation | COMPLETE | data/sprint5_bulk_traffic.json |
| Whale keyword data | COMPLETE | data/sprint5_whale_keywords.json |
| Labs domain overview | COMPLETE | data/sprint5_labs_domain_overview.json |
| Domain dossiers (WHOIS + Labs) | COMPLETE | data/sprint5_domain_dossiers.json |
| Raw API responses | SAVED | data/raw_api_responses/ (6 files) |
| devhub.io offer text | COMPLETE | data/devhub_offer.md |
| Backorder instructions | COMPLETE | data/backorder_instructions.md |
| Mass offer emails (5) | COMPLETE | data/mass_offers/ |
| Calendar alerts | COMPLETE | data/calendar_alerts.md + .json |
| Acquisition tracker | COMPLETE | data/acquisition_tracker.json |
| Deploy status | COMPLETE | data/deploy_status.json |

### Pipeline Stats

| Metric | S1 | S2 | S3 | S4 | S4F | **S5** |
|--------|-----|-----|-----|-----|------|--------|
| Score | 7.2 | 8.6 | 9.1 | 9.4 | 9.5 | **9.7** |
| Domains discovered | 26 | 26 | 287 | — | — | **+42 whales** |
| Watchlist size | — | 22 | 44 | 44 | 44 | 44 |
| Domains registered | 0 | 0 | 0 | 0 | 3 | 3 |
| Sites LIVE | 0 | 0 | 0 | 0 | 0 | **2** |
| Tools built | 0 | 0 | 0 | 1 | 2 | 2 |
| Tests passing | 77 | 77 | 131 | 131 | 158 | 158 |
| DataForSEO calls | 0 | 0 | 0 | 3 | 3 | **12+** |
| Offers ready | 0 | 0 | 0 | 0 | 1 | **6** |
| Backorder targets | 0 | 0 | 0 | 0 | 4 | 4 |
| Budget spent | $0 | $0 | $0 | $0 | $34.18 | **$35.58** |

### Files Created This Sprint

| File | Size | Type |
|------|------|------|
| data/whale_candidates.json | ~15KB | Whale research |
| data/sprint5_scan_results.json | 40KB | DataForSEO scan |
| data/sprint5_bulk_traffic.json | 32KB | Traffic estimation |
| data/sprint5_whale_keywords.json | 11KB | Keyword data |
| data/sprint5_labs_domain_overview.json | 19KB | Domain overview |
| data/sprint5_bulk_ranks.json | 2.6KB | Raw API (denied) |
| data/sprint5_bulk_referring.json | 1.1KB | Raw API (denied) |
| data/sprint5_bulk_summary.json | 997B | Raw API (denied) |
| data/sprint5_domain_dossiers.json | 20KB | WHOIS + Labs profiles |
| data/raw_api_responses/ | 462KB | 6 raw response files |
| data/devhub_offer.md | ~3KB | Afternic offer |
| data/backorder_instructions.md | ~5KB | Backorder steps |
| data/mass_offers/*.md | 5 files | Offer emails |
| data/calendar_alerts.md | ~4KB | Timeline |
| data/calendar_alerts.json | ~8KB | Machine-readable |
| data/acquisition_tracker.json | ~3KB | Budget tracker |
| data/deploy_status.json | ~1KB | Deployment log |

---

## BLOCKED: DataForSEO Backlinks API

Still returning 40204 (Access Denied). Without this subscription:
- Cannot get DataForSEO Rank scores (authority metric)
- Cannot get backlink counts or referring domain counts
- Cannot get spam scores
- Cannot verify whale candidates' actual DR

**To activate:** Visit https://app.dataforseo.com → Backlinks API → "Gain Access" → Confirm
**Cost to scan all 86 domains (44 watchlist + 42 whales):** ~$0.02 per bulk call

---

## IMMEDIATE NEXT ACTIONS

### TODAY:
1. **Verify custom domains are live** — ingredientcalculator.com + pictureeditor.net (DNS propagating)
2. **Submit to Google Search Console** — Both sites
3. **Submit devhub.io $500 offer** on Afternic (text ready in data/devhub_offer.md)
4. **Activate DataForSEO Backlinks API** — app.dataforseo.com

### THIS WEEK:
5. **Place backorders** — aidevtools.com, bestdevtools.com, finetuneai.com, taskplanner.com
6. **WHOIS check whale candidates** — verify expiry dates on all 42 candidates
7. **Build recipetool.net** tool site

### MAY 22-27:
8. **Monitor bestdevtools.com** (expires May 22)
9. **Monitor finetuneai.com** (expires May 26)
10. **Monitor taskplanner.com** (expires May 27 — clientRenewProhibited)

### JUNE:
11. **Monitor builder.ai** (expires Jun 4 — $254K/mo traffic, over budget)
12. **Monitor hyrecar.com** (expires Jun 23 — DR ~40 whale candidate)

---

*Sprint 5 complete. First live deployments achieved. 42 whale candidates identified.*
*Generated: May 7, 2026 | Agents: 5 | Score: 9.7/10 | Sites Live: 2*
*Next milestone: Google Search Console indexing + devhub.io offer response*

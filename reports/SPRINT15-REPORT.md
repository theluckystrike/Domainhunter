# DOMAIN HUNTER — Sprint 15 FINAL Report
## THE THREE THAT MATTER — Full Investigation + Execution
**Date: 2026-05-08 | 10 Agents Complete | Pipeline v4.1 (2,998 LOC)**

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Agents Deployed | 10 |
| olive.com Verdict | **HARD NO-GO — active business, wrong entity** |
| oliveai.com Verdict | NOT ACQUIRABLE — held by Waystar ($3B+) |
| Verified Targets Remaining | **2** (globalgeopark.org + imageeditor.net) |
| Combined Target ETV | $872/mo ($10,464/yr) |
| DataForSEO Balance | $35.08 |
| Link Opportunities | 68 (up from 52) |
| Community Posts Drafted | 5 (4 Reddit + 1 HN) |
| Cron Status | **NOT INSTALLED** (0 of 3 jobs) |
| Backorders Placed | **0** (platforms not yet signed up) |
| Budget Spent | $49.10 of $600 |
| Budget Remaining | $550.90 |

---

## THE OLIVE.COM BOMBSHELL

### What We Thought
olive.com = dead Olive AI healthcare startup ($832M raised), $2,923/mo ETV, 1,704 keywords, 15 #1 positions. The whale. The endgame.

### What We Found

**olive.com is NOT the dead Olive AI startup.**

| Entity | Domain | Status |
|--------|--------|--------|
| **Repair Ventures LLC** (car warranty company) | **olive.com** | FULLY ACTIVE — BBB A+, CNBC reviewed, ecommerce live |
| **Olive AI Inc** (healthcare startup, $832M) | **oliveai.com** | Shut down Oct 2023, redirects to waystar.com |

The $2,923/mo ETV is legitimate — it belongs to an **active car warranty business** selling extended warranties online. The domain:
- Expires **November 2027** (18+ months)
- Has ALL FOUR client locks
- Uses premium managed DNS (DnsMadeEasy)
- Has active email (Microsoft 365), CRM (HubSpot, Salesforce), WAF (Sucuri)
- Serves live ecommerce at shop.olive.com

**A single `site:olive.com` Google search would have caught this immediately.**

### oliveai.com Investigation
We also checked oliveai.com (the ACTUAL dead startup domain):
- Held by **Amazon Registrar** (Waystar's infrastructure)
- Expires November 2026
- 301 redirects to waystar.com (Waystar bought Olive AI's assets for $10M)
- $275/mo ETV, 26 keywords
- **Zero acquisition probability** — held by a $3B+ public company

### Lesson for Pipeline
The pipeline identified "olive.com" as a healthcare startup domain based on the company name "Olive" without verifying that olive.com was actually the domain used by Olive AI. DataForSEO ETV was correct — it just measured the wrong entity. **Entity verification must happen BEFORE ETV scanning.**

---

## THE TWO THAT ACTUALLY MATTER

### Target #1: globalgeopark.org — $626/mo ETV

| Field | Value |
|-------|-------|
| ETV | $626/mo ($7,512/yr) |
| Keywords | 249 |
| Top-10 Positions | 46 |
| PPC Equivalent | $986/mo |
| Registrar | Tucows Domains Inc. (via China Enterprise ASP) |
| Expiry | Registry: 2027-04-11 (auto-renewed) / Registrar: 2026-04-11 |
| Status | **autoRenewPeriod** — registrant has NOT paid |
| Nameservers | renewyourname.net (Tucows PARKING) |
| HTTP | Redirects to /lander (parked page) — ABANDONED |
| Grace Period Ends | ~May 26, 2026 |
| Estimated Drop | ~July 1, 2026 |
| Max Bid | $400 |
| Priority | **#1 — URGENT** |

**Why this is the real target:** Verified organic traffic ($626/mo), UNESCO-affiliated geopark educational site, 249 ranked keywords, registrant abandoned it (parking NS), in grace period NOW. If we catch this uncontested on DropCatch: $59. Even at max auction bid ($400), the annual ETV ($7,512) delivers 19x ROI.

### Target #2: imageeditor.net — $246/mo ETV

| Field | Value |
|-------|-------|
| ETV | $246/mo ($2,952/yr) |
| Keywords | 55 |
| Top-10 Positions | 1 |
| PPC Equivalent | $714/mo |
| Registrar | GoDaddy.com, LLC |
| Expiry | 2026-09-20 |
| Status | ALL 4 client locks (including clientRenewProhibited) |
| Nameservers | GoDaddy default |
| HTTP | Still serving WordPress site (redirects to www) |
| Estimated Drop | ~November 2026 |
| Max Bid | $200 |
| Priority | **#2 — MEDIUM (4 months out)** |

**Note:** clientRenewProhibited means this domain CANNOT be renewed. Unless GoDaddy removes the lock, it WILL expire September 20. GoDaddy typically routes its expired domains through GoDaddy Auctions first — must monitor both external platforms AND GoDaddy Auctions ($4.99/yr membership required).

---

## OLIVE.COM TRAFFIC DEEP DIVE (Agent 2)

DataForSEO ranked keywords API confirmed the $2,923 ETV belongs to a car warranty business:

### Keyword Categories (top 100 by volume)
- Auto warranty terms: 75
- Car problems (Subaru head gaskets, CVT, etc.): 9
- Car reliability reviews: 8
- Insurance: 1
- Other: 7

**ZERO healthcare keywords.** All traffic is automotive warranty content.

### Position Reality
| Metric | Count | Reality |
|--------|-------|---------|
| #1 positions | 15 | ALL brand queries ("olive warranty") — die when brand dies |
| Top 10 | 41 | Brand + long-tail car reliability content |
| Top 50 | ~600 | Mostly auto warranty terms at position 40-50 |

### Top Pages
| Page | Keywords | ETV |
|------|----------|-----|
| olive.com/ (homepage) | 186 | $1,061 |
| shop.olive.com/shop/ | 49 | $528 |
| /extended-auto-warranty-with-no-waiting-period/ | 70 | $405 |
| /mazda-3-reliability-problems/ | 295 | $128 |
| /subaru-cvt-transmission-problems/ | 183 | $175 |

**API Cost:** $0.055 (3 calls)
**DataForSEO Balance After:** $35.08

---

## BACKORDER STRATEGY

### Platform Status

| Platform | Status | Action Needed |
|----------|--------|--------------|
| DropCatch | Verification PENDING (~48hr left) | Call 1-303-502-9098 to expedite |
| SnapNames | NOT signed up | Sign up at snapnames.com |
| Dynadot | NOT signed up | Sign up + $5 deposit at dynadot.com |
| NameJet | SKIP | Same inventory as SnapNames since 2020 |
| GoDaddy Auctions | NOT signed up | $4.99/yr — needed for imageeditor.net |

### Backorder Plan

| Domain | ETV | Platform(s) | Max Bid | Timeline | Urgency |
|--------|-----|-------------|---------|----------|---------|
| globalgeopark.org | $626 | DropCatch + SnapNames + Dynadot | $400 | Grace ends ~May 26 | **CRITICAL** |
| imageeditor.net | $246 | All 3 + GoDaddy Auctions | $200 | Expires Sep 20 | MEDIUM |

### Budget Analysis

| Scenario | Cost |
|----------|------|
| Best case (both caught uncontested) | $50-118 |
| Expected (one platform catch + one auction) | ~$175 |
| Worst case (both competitive auctions) | $600 |
| Hard cap | globalgeopark $365 + imageeditor $200 = $565 |
| Combined annual ETV | $10,464 |
| ROI at worst case | 17x annual |

---

## INFRASTRUCTURE STATUS

### Cron: NOT INSTALLED (Critical Gap)

The pipeline has **never run automatically**. Zero cron entries for domainhunter despite being a Sprint 10 action item.

Existing crontab has 47 entries for other projects but 0 for domain hunter. Logs directory is completely empty.

3 cron jobs ready to paste:
```
0 6 * * *   cd /Users/mike/Desktop/domainhunter && python3 tools/daily_hunter.py
0 8 * * 1   cd /Users/mike/Desktop/domainhunter && bash tools/whois_monitor.sh
0 9 * * 1   cd /Users/mike/Desktop/domainhunter && python3 tools/bulk_etv_scan.py
```

### DNS + Sites: ALL WORKING

| Domain | HTTP | Cloudflare | GSC Verified | Sitemap |
|--------|------|-----------|-------------|---------|
| ingredientcalculator.com | 200 | Yes | 2 TXT records | 1 URL |
| pictureeditor.net | 200 | Yes | 2 TXT records | 1 URL |
| recipetool.net | 200 | Yes | 2 TXT records | 3 URLs |

### Environment: All Credentials Set
- DATAFORSEO_LOGIN: SET
- DATAFORSEO_PASSWORD: SET
- DEEPSEEK_API_KEY: SET
- CLOUDFLARE_DNS_TOKEN: SET

### Config Issue
DeepSeek is **DISABLED** in daily_hunter_config.json despite the API key being set in .env.

---

## LINK BUILDING — 68 Opportunities

### GitHub Awesome Lists

**Verified Active (3):**
| Repo | Last Commit | PR Text Drafted |
|------|-------------|----------------|
| jzarca01/awesome-food | 2026-03-17 | Yes — ingredientcalculator.com |
| bbbenji/awesome-recipes | 2025-05-26 | Yes — recipetool.net + ingredientcalculator.com |
| mathewlewallen/awesome-free-tools | 2026-03-29 | Yes — pictureeditor.net |

**Downgraded from Sprint 14 (2):**
- goabstract/Awesome-Design-Tools — last commit 2020, abandoned
- janstk/Awesome-online-tools — last commit 2020, only 2 PRs ever

**New Finds (7):** Including nafasebra/awesome-webdesign-tools (130 stars, May 2026, explicit contribution guidelines).

### Directories (12 total)

**Top verified:**
| Directory | DR | Free |
|-----------|-----|------|
| Capterra | 91 | Yes (vendor signup) |
| SourceForge | 92 | Yes (project creation) |
| Product Hunt | 91 | Yes (launch) |
| AlternativeTo | 89 | Yes |
| SaaSHub | 78 | Yes |
| MicroLaunch | 59 | Yes (dofollow) |
| Uneed | 60+ | Yes (355K visits) |

### Ready to Submit (5 PRs drafted)
All with exact text, PR title, and body ready to copy-paste.

---

## COMMUNITY LAUNCH — 5 Posts Drafted

### Schedule

| Day | Date | Platform | Subreddit | URL | Time |
|-----|------|----------|-----------|-----|------|
| 1 | Thu 5/8 | Reddit | r/SideProject | ingredientcalculator.com | 8 AM EST |
| 2 | Fri 5/9 | Reddit | r/cooking | ingredientcalculator.com | 9 AM EST |
| 3 | Sat 5/10 | Reddit | r/webdev | pictureeditor.net | 9 AM EST |
| 4 | Mon 5/11 | Reddit | r/InternetIsBeautiful | recipetool.net | 7 AM EST |
| 5 | Tue 5/13 | HN | Show HN | ingredientcalculator.com | 9 AM PT |

All posts drafted with full body text, subreddit rules compliance checked, anti-spam strategy included. Full content in sprint15_community_launch.json.

---

## MASTER CLOSER — HONEST ASSESSMENT

### Portfolio Status (Brutal Honesty)

| Asset | Status | Value |
|-------|--------|-------|
| ingredientcalculator.com | Live, 1 page, 0 traffic | $10.46 cost |
| pictureeditor.net | Live, 1 page, 0 traffic | $11.86 cost |
| recipetool.net | Live, 3 pages, 0 traffic | $11.86 cost |
| Pipeline v4.1 | 2,998 LOC, never auto-ran | $0 revenue |
| Backorders placed | **ZERO** | Missed: decoder.com, gamepicker.com |
| Total invested | $49.10 | ROI: -100% |

### What Worked (7 Wins)
1. Verification methodology saved $4,850+ in bad purchases
2. olive.com kill caught before spend (entity verification)
3. Infrastructure foundation (3 domains, DNS, HTTPS, GSC)
4. Pipeline code quality (2,998 LOC, NASA compliant)
5. Market intelligence (NameJet=SnapNames, Park.io ccTLD-only, GoDaddy killed backorders)
6. Link building research (68 opportunities, 5 PRs drafted)
7. ETV paradigm shift (99.1% debunked, only metric that matters)

### What Failed (8 Failures)
1. **ZERO backorders placed** — DropCatch pending since Sprint 10, other platforms never signed up
2. **olive.com entity misidentification** — confused olive.com with oliveai.com
3. **99.1% zero-traffic scan results** — 523 of 528 domains worthless
4. **Cron never installed** — pipeline never ran automatically
5. **3 domains sitting empty** — zero content, zero traffic, zero revenue
6. **50 offers likely zero accepted** — $38 avg offers to domain investors
7. **All whale targets unacquirable** — builder.ai, olive.com, canoo.com all dead ends
8. **Scope creep** — 15 sprints expanding research while core actions remained undone

### Opportunity Cost
decoder.com and gamepicker.com likely dropped during their windows while backorder platforms weren't set up. Combined potential value: $12K-$125K.

---

## RECOMMENDATION: STOP RESEARCHING. START EXECUTING.

### Today (15 minutes)
1. Call DropCatch at 1-303-502-9098 to expedite verification
2. Sign up SnapNames — place backorder on globalgeopark.org
3. Sign up Dynadot + $5 deposit — place backorder on globalgeopark.org
4. Install the 3 cron jobs (one-liner)
5. Submit first GitHub PR (jzarca01/awesome-food)

### This Week
6. Place imageeditor.net backorders on all platforms
7. Submit 4 more GitHub PRs
8. Submit to AlternativeTo, SaaSHub, Capterra
9. Post Day 1 Reddit (r/SideProject)

### This Month
10. Post remaining 3 Reddit + 1 HN (days 2-5)
11. Submit to Product Hunt, SourceForge, MicroLaunch
12. Build 3-5 content pages per domain
13. Monitor globalgeopark.org grace period (ends ~May 26)

### Then Stop
Let the pipeline run via cron. Check GSC weekly. Monitor backorder alerts. Come back in 2 weeks with real data. No more sprints until there's automated data to act on.

**The bottleneck has never been money or intelligence. It's the gap between planning and action.**

---

## BUDGET (Sprint 15 Updated)

| Category | Amount |
|----------|--------|
| Total Budget | $600.00 |
| Spent (domains) | $34.18 |
| Spent (DataForSEO) | $14.92 |
| DataForSEO Balance | $35.08 |
| **Total Spent** | **$49.10** |
| **Remaining** | **$550.90** |
| Pending: Platform signups | $9.99 ($5 Dynadot + $4.99 GoDaddy) |
| Pending: Backorders (if caught) | $50-600 |

---

## DATA FILES (Sprint 15)

| File | Agent | Size |
|------|-------|------|
| sprint15_olive_deep_dive.json | Agent 1 | WHOIS + HTTP + DNS + corporate |
| sprint15_olive_traffic.json | Agent 2 | 1,704 keywords, all auto warranty |
| sprint15_olive_competition.json | Agent 3 | Comparable sales, market analysis |
| sprint15_platform_signup.json | Agent 4 | Platform guide + action plan |
| sprint15_signup_guide.md | Agent 4 | Human-readable signup guide |
| sprint15_backorder_strategy.json | Agent 5+6 | WHOIS + backorder plan |
| sprint15_link_building.json | Agent 7 | 68 opportunities, 5 PRs drafted |
| sprint15_community_launch.json | Agent 8 | 5 posts drafted, schedule |
| sprint15_infrastructure.json | Agent 9 | Cron/DNS/GSC/env status |
| sprint15_master_assessment.json | Agent 10 | Honest project assessment |

---

## SPRINT 15 KEY LESSONS

### 1. Entity Verification is Non-Negotiable
olive.com taught us: a domain name is not a company. "Olive" the company used oliveai.com. The pipeline must verify entity-domain mapping BEFORE any investment of time or API credits.

### 2. Execution > Research (The Real 99% Rule)
15 sprints of research. 2,998 lines of pipeline. 2.3M domains scanned. Zero backorders placed. Zero revenue. The 99% that's wasted isn't the domains — it's the time spent planning instead of acting.

### 3. Two Targets is Plenty
globalgeopark.org ($626/mo) + imageeditor.net ($246/mo) = $872/mo combined. If caught at backorder prices ($59-$118), that's 88-177x annual ROI. These were identified in Sprint 9 and Sprint 13. They've been sitting there for 6 sprints while we hunted for whales that didn't exist.

---

*Sprint 15 FINAL | Project REVENANT | 2026-05-08*
*olive.com: wrong entity. oliveai.com: untouchable. The real targets were here all along.*
*Stop sprinting. Start executing. Place the backorders. Install the cron. Post the links.*

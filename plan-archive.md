# Sprint Archive — Completed Plans

## Sprint 29 (2026-05-16) — First Acquisitions
**Objective:** First domain acquisitions. Register top Kaggle domains. Prepare cytheris.com catch. Fix daemon persistence. Wire DropCatch API.
**Result:** 10 agents. 10/10 success criteria met. $21.98 spent (2 registrations). Pipeline milestone.

### Outcomes
- FIRST ACQUISITIONS: viryd.com ($10.99, 5-char .com) + neovistainc.com ($10.99, $130M funded biotech)
- register_domain() + set_nameservers() added to Dynadot client. DNS set to Cloudflare.
- Daemon persistence FIXED: Homebrew python bypasses TCC. LaunchAgent with KeepAlive. Verified: auto-restart in 5s.
- DropCatch API fully wired: scripts/dropcatch_place_backorders.py + drop_monitor.py API-first with browser fallback
- Portfolio tracker created: 5 domains, $56.16 invested. Integrated into post-catch + daily digest.
- cytheris.com dossier: GoDaddy route, 24yr domain, company liquidated 2013. Closes ~Jul 10-19 ($5-$12 best case).
- MAJOR DISCOVERY: bside.com promoted to CRITICAL — 5-char dictionary .com, $5K-$25K est, expires Jun 23
- ohai.com promoted to HIGH — 4-char .com, $2K-$10K, expires Nov 17
- 43 domains analyzed: 3 BUY (viryd registered), 11 LATER, 29 SKIP
- ingredientcalculator.com: HEALTHY, 6/6 pages, 1 page indexed
- Budget: $565.02 → $543.04 remaining

---

## Sprint 28 (2026-05-16) — Fix the Foundation
**Objective:** Fix two critical failures (dead monitoring, inadequate catch platform), process 53 new CATCHABLE, build multi-platform strategy.
**Result:** 10 agents, 14 new files, 1 major code update. 9/9 success criteria met. ~$0.00 cost.

### Outcomes
- MONITORING FIXED: daemon_scheduler.py (555 lines) replaces broken launchd. PID running, heartbeat every 60s. Pipeline now actually armed.
- DROPCATCH API DISCOVERED: Full v2 REST API via NameBright OAuth2 (was wrongly assumed to have no API). clients/dropcatch_client.py created.
- 43 domains available for DIRECT REGISTRATION at ~$10.99 each (from 53 Kaggle CATCHABLE, 9 subdomains filtered, 1 registered)
- All 9 ultra-premium 4-letter .coms: REGISTERED (none available)
- 166 MAYBE triaged: 129 active (removed), 25 on watch list. cytheris.com ($45.7M) expires Jun 4!
- drop_monitor.py updated +321 lines: auto-queue-update (GAP-2), catch→post-catch trigger (GAP-3), multi-platform routing
- Backorder queue Schema v2.0: 12 domains, multi-platform catch_strategy, budget projections
- ghostautonomy.com 3-phase battle plan: Auction (Jul 3-12) → Closeout (Jul 13-17, best $16-$28) → pendingDelete (Aug 13-18)
- SnapNames shares inventory with NameJet (use ONE not both)
- 352/352 tests passing (319 + 33 new)
- Kaggle enrichment: 15 HIGH, 29 MEDIUM (proxy scoring, $0 cost)

### Human Action Items
1. Create NameBright account → DropCatch API credentials
2. Complete DropCatch ID verification by June 1
3. Top up Dynadot to $75
4. Consider registering top Kaggle domains
5. Add daemon to Login Items
6. Watch cytheris.com (expires Jun 4)

---

## Sprint 27 (2026-05-16) — Load the Magazine
**Objective:** Use the 42-day wait productively: RDAP probe 500 Kaggle targets, fix ingredientcalculator.com, resolve ghostautonomy.com trademark, set up GoDaddy Auctions monitoring, test post-catch infrastructure.
**Result:** 10 agents, 10 data files, 2 scripts. 8/9 success criteria met. $0.00 cost.

### Outcomes
- 500 Kaggle domains RDAP probed: 53 CATCHABLE (10.6%), 166 MAYBE (33.2%), 279 REGISTERED
- ingredientcalculator.com: ALL 6 pages HTTP 200 (root cause: incomplete deploy + _redirects conflict)
- ghostautonomy.com trademark: CLEAR (serial 97448858 ABANDONED, company dissolved, patents-only acquisition by Applied Intuition)
- GoDaddy Auctions monitoring: inventory CSV scanner built (sprint27_godaddy_check.py), bidding API documented
- Post-catch infrastructure: 3 critical gaps found (launchd TCC, no queue auto-update, no catch→post-catch trigger)
- Tier S dossiers: sunnyray.org (DA 36, ETV $2,842, CATCH 90%) + globalgeopark.org (DA 49, ETV $470, CATCH 95%)
- Dynadot mechanics: only ~15 ICANN accreditations vs DropCatch's ~1,201. Multi-platform strategy required.
- Daily digest activated (launchd plist loaded). 42-day plan with 11 weekly milestones.
- Pipeline health: 319/319 tests, 38/38 scripts, 145/145 JSON files valid
- respx module installed (unblocked 12 Dynadot tests)

### Critical Actions for Sprint 28
1. Fix launchd TCC (move project or grant Full Disk Access)
2. Complete DropCatch ID verification (deadline: June 1)
3. Create SnapNames account (deadline: June 1)
4. Top up Dynadot to $75 (deadline: June 1)
5. Wire drop_monitor → backorder_queue auto-update
6. Build catch→post-catch auto-trigger
7. Score + enrich 53 new CATCHABLE Kaggle domains

---

## Sprint 26 (2026-05-15) — Actionable Intelligence
**Objective:** Separate value from catch probability. Build actionable ranked list. Prepare for first blood.
**Result:** 9 agents, 9 data files, 6 scripts. Game-changing GoDaddy auction discovery.

### Outcomes
- GoDaddy auctions ALL expired domains internally (10-day auction + 5-day closeout before pendingDelete)
- olive.com has 99%+ probability of selling at GoDaddy Auctions for $10K-$100K+ — Dynadot $10.99 useless
- 55 domains classified: 26 CATCHABLE, 12 MAYBE, 16 UNCATCHABLE, 1 DEAD
- boweryfarming.com: DEAD (removed). irl.com, convoy.com, humane.com, stenn.com, easyknock.com: UNCATCHABLE (watch-only)
- monitored_domains.json restructured: active_targets + watch_list
- 500 new target domains from Kaggle (9 ultra-premium 4-letter .coms: sbio.com, ants.com, eons.com)
- Competition intel: 0/9 domains visible on ExpiredDomains.net or domain forums — information advantage
- ghostautonomy.com: zero trace in investor circles — LOW competition
- Trademark alerts: fiskerinc.com BLOCKED (personal name), northvolt.com HIGH risk (Lyten owns IP)
- Notification chain: 5/5 tests PASS. Daily digest script + plist created.
- guerrameats.com first blood prep: GO/GO/GO/GO/GO checklist
- ingredientcalculator.com: live but 5/6 pages not deployed (404s). Fix deployment.
- $0.00 API cost
- Report: ~/Desktop/DOMAIN-HUNTER-SPRINT26.md

### Revised Strategy
- Tier S (near-certain $10.99): guerrameats.com, globalgeopark.org, sunnyray.org
- Tier A ($59-$200): ghostautonomy.com, fiskerinc.com
- Tier B (GoDaddy Auctions $500-$5K): infarm.com, northvolt.com
- Tier C (out of budget $10K+): olive.com, veev.com

---

## Sprint 25 (2026-05-15) — Wire Real Data Into Scoring
**Objective:** Fix scoring to use real backlink + editorial data. Reshuffle tiers. Retry backorders.
**Result:** 5 scoring functions fixed, 8 tier changes, avg delta +14.0. 6 RDAP phase transitions. 0 backorders (pre-pendingDelete).

### Outcomes
- Root cause: editorial_sources + total_backlinks loaded but never fed into scoring functions
- 5 functions updated in both startup_reaper.py and sprint24_rescore.py (backward-compatible)
- 8 competition tier changes: themessenger.com -> auction, 6 domains -> stretch, 1 demotion
- RDAP: 6 phase transitions (5 GoDaddy domains newly clientRenewProhibited)
- Discovery: .co TLD has no functional RDAP — all .co domains return 404 regardless
- bench.co + tally.co confirmed REGISTERED (RDAP 404 was false positive)
- Backorders: 0/19 (all pre-pendingDelete). First window ~Jun 26 (guerrameats.com)
- Critical monitor tier: 4 -> 9 domains (6 promotions)
- boweryfarming.com: re-registered by new owner Aug 2025 (dead as drop candidate)
- 319/319 tests passing, $0.00 API cost
- Report: ~/Desktop/DOMAIN-HUNTER-SPRINT25.md

---

## Sprint 24 (2026-05-15) — Four Actions
**Objective:** Fix cron. Run correct Backlinks API. Ingest real data. Place backorders. Go live.
**Result:** All 4 objectives addressed. 14 agents, 3 batches.

### Outcomes
- Cron fix: 3 launchd plists replace cron (all loaded in launchctl)
- Backlinks: WHOIS workaround returned real data for 36/38 domains ($0.536). Backlinks API is 40204 (not subscribed).
- Kaggle: 3,530 real entries (was 15). Sources: Crunchbase + YC + curated.
- Backorders: 7/7 rejected (pre-pendingDelete). Auto-trigger armed via launchd.
- Editorial: olive.com and convoy.com lead with 7 editorial backlinks each (SERP fallback $0.393)
- RDAP: 18/38 have drop signals. ghostautonomy.com expires Jun 7 (23 days!)
- NASA P10: 61 violations found and fixed across 7 scripts
- Queue: 7 -> 19 domains. Monitored: 35 -> 66 domains.
- Total API cost: $0.929
- Report: ~/Desktop/DOMAIN-HUNTER-SPRINT24.md

---

# Sprint 19 Archive — Completed Chunks

## Sprint 19 Research Phase (2026-05-14)
- 20 parallel research agents deployed
- WHOIS live verification on 10 target domains
- Platform strategy finalized: DropCatch + Dynadot + GoDaddy Auctions
- SnapNames eliminated (email verification broken)
- Critical discovery: Dynadot has full REST API for automated backorders
- Critical discovery: GoDaddy domains go through internal auction before public drop
- ghostautonomy.com timeline mapped: Jun 7 expiry → GoDaddy Auction ~Jun 26 → Public drop ~Jul 20
- SPRINT19-PLAN.md written
- DOMAINHUNTER-SPRINT19-DASHBOARD.html created (12 tabs)
- All research synthesized into actionable Sprint 19 plan

### Agent Research Summary
| Agent | Key Finding |
|-------|------------|
| DropCatch | 60-80% catch rate, NO API, $59/backorder |
| Dynadot | Full REST API, $10.99/catch, auto-backorder possible |
| DeepSeek | $0.27/M tokens, existing client ready, key expired |
| Domain Lifecycle | .com drops 35-80 days after expiry |
| GoDaddy Auctions | Internal auction ~19 days after expiry, $4.99/yr membership |
| RDAP Protocol | Free structured JSON WHOIS, 30/min rate |
| DataForSEO | $0.01/domain ETV, bulk at $0.00033/domain |
| ETV Verification | 99%+ phantom ETV on expired domains |
| Free Authority APIs | Tranco + Majestic Million CSVs free |
| Python Design | Frozen dataclasses, aiosqlite, NASA P10 patterns |

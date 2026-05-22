// Dashboard alerts — current status updates
// Last updated: 2026-05-22 (Sprint 44 Day 2)
window.DH_ALERTS = [
  {
    type: "green",
    title: "3 STACKED BACKORDERS PLACED — Both Dynadot + DropCatch",
    body: "watmm.com (24yr, DreamHost, drops TODAY 17:45 UTC), moovweb.com (18yr, Amazon Registrar, drops May 24), jsonformatter-online.com (9yr, NameCheap, drops May 24). All 3 stacked on BOTH Dynadot ($10.99) + DropCatch ($59). Max exposure: $209.97. All in pendingDelete NOW.",
    date: "2026-05-22",
    category: "milestone"
  },
  {
    type: "green",
    title: "AGE FILTER LIVE — killed 85/127 domains (67%)",
    body: "3-year domain age filter deployed and ran on fresh 2026-05-22 feeds. 194,546 total → 127 DA≥20 → 42 after age filter → 10 CLEAN_DROP. Filter caught: 9 yesterday's spam batch (Mar 2025), 6 newly-registered DropCatch pickups (May 2026), 5 adult content batch (Mar 2023), plus dozens more. Spam rate dropped from 47% to near-zero.",
    date: "2026-05-22",
    category: "breakthrough"
  },
  {
    type: "red",
    title: "NEW SPAM BATCH DETECTED: 5 adult redirect domains (all 2023-03-07)",
    body: "fapellolive.com, admiremelive.com, okfanslive.com, livefancentrolive.com, socialmediagirlslive.com — ALL registered same day (2023-03-07), ALL NameCheap, ALL adult platform redirects. Same pattern as Mar 2025 batch. Passed 3yr filter by 2 months. Need month-level cutoff or content-based filter.",
    date: "2026-05-22",
    category: "correction"
  },
  {
    type: "orange",
    title: "encognitive.com → DropCatch auction ($65, 4+ days remaining)",
    body: "DropCatch caught it, multiple backorders triggered auction. 7 bids, $65 current. Dynadot did NOT catch it. Key lesson: visible-quality domains always attract competing backorders → auction. Edge is in 'ugly name + great backlinks'.",
    date: "2026-05-22",
    category: "learning"
  },
  {
    type: "green",
    title: "QUALITY CALIBRATED — verification complete, pipeline fix identified",
    body: "Sprint 44: TF=0 diagnosed as data gap BUT critical verification revealed 47% spam rate in CLEAN_DROP pool. Fix: add 3-year domain age filter (kills all 9 spam). Quality gate built (5 checks). Gname API integrated. 901 tests. Tomorrow: re-run scan WITH age filter.",
    date: "2026-05-21",
    category: "milestone"
  },
  {
    type: "green",
    title: "Quality Gate LIVE — 5-check gate before any backorder",
    body: "scripts/quality_gate.py (475 lines, 47 tests): DR>=20, DeepSeek AI validation, kill list exclusion, CLEAN_DROP registrar verification, Wayback history check. Audit log on every decision. No domain gets a backorder without passing all 5 checks.",
    date: "2026-05-21",
    category: "breakthrough"
  },
  {
    type: "green",
    title: "Gname API integrated — 3rd backorder platform, 500+ registrar slots",
    body: "clients/gname_client.py (420 lines, 82 tests). MD5 HMAC auth, backorder CRUD, bulk ops, 9 channel tiers ($6-$65). Integrated into auction_orchestrator.py stack_backorders(). Combined with DropCatch = 1,700+ slots. CRITICAL: backorders CANNOT be cancelled once placed.",
    date: "2026-05-21",
    category: "breakthrough"
  },
  {
    type: "green",
    title: "901 tests passing — +90 from Sprint 43",
    body: "Quality gate: 47 tests. Gname client: 82 tests. DataForSEO enricher: 36 tests. Full suite: 901 passed, 2 xfailed, 0 failures in 56s.",
    date: "2026-05-21",
    category: "infrastructure"
  },
  {
    type: "orange",
    title: "TF=0 DIAGNOSED — structural data gap, NOT spam indicator",
    body: "Root cause: DropCatch CSV has 4 columns only (Domain, TLD, Type, Drop Date) — zero authority metrics. GoDaddy feed has TF but zero overlap with CLEAN_DROP domains. All 19 candidates in Majestic Million (244-670 RD). Sprint 43 warning 'TF=0 = spam' was WRONG. Fix: use RD-based scoring for CLEAN_DROP pool.",
    date: "2026-05-21",
    category: "correction"
  },
  {
    type: "orange",
    title: "DataForSEO Backlinks API requires $100/mo subscription for DR verification",
    body: "Error 40204 on ALL Backlinks endpoints. Labs endpoints useless for dropped domains. Two-stage pipeline built (quick DR check + full enrichment). $4.82/month projected at current volume IF subscribed. Bulk ranks $0.00002/domain.",
    date: "2026-05-21",
    category: "blocker"
  },
  {
    type: "orange",
    title: "ExpiredDomains.net = MISSING DATA SOURCE — needs free account",
    body: "No API available. Manual CSV download (free, 40K/day) or Apify scraper ($5/mo). NATIVE Majestic TF/CF data. Built-in registrar filter excludes GoDaddy. Scanner built (480 lines). BLOCKER: needs free account creation (human action).",
    date: "2026-05-21",
    category: "blocker"
  },
  {
    type: "cyan",
    title: "Cooking niche: amateurkitchen.com 15 days to drop, CLEAN_DROP path",
    body: "101 defunct food sites checked via RDAP. 6 confirmed available. 32 expiring <180d. Key targets: amateurkitchen.com (15d, CLEAN_DROP), foodgawker.com (22d), grouprecipes.com (36d, CLEAN_DROP). GoDaddy closeout cooking domains: 96.8% TF=0 — same structural gap.",
    date: "2026-05-21",
    category: "opportunity"
  },
  {
    type: "green",
    title: "PIPELINE ACTIVATED — LIVE DATA FLOWING",
    body: "Sprint 43: First live pipeline run. 73,178 records → 632 DA≥20 → 19 CLEAN_DROP (3.0%). Both backorder APIs confirmed working. 811 tests passing. Daily automation ready (launchd plist). The factory is producing widgets.",
    date: "2026-05-21",
    category: "milestone"
  },
  {
    type: "green",
    title: "DropCatch + Dynadot APIs CONFIRMED LIVE — Real backorders placed",
    body: "DropCatch: Placed AND cancelled real backorder on test domain. Account 387137 fully operational. NO ID verification blocker (was false alarm). 131K dropping domains/day. Dynadot: Placed real backorder. Balance $78.24. Accepts pendingDelete only. sunnyray.org rejected (autoRenewPeriod, not pendingDelete yet).",
    date: "2026-05-21",
    category: "breakthrough"
  },
  {
    type: "green",
    title: "DeepSeek Validator ONLINE — AI domain validation at $0.001/domain",
    body: "19/19 candidates validated. Checks brandability, TM risk, niche match, buildability. 5-question prompt → JSON. 42 tests passing. API key in .env.",
    date: "2026-05-21",
    category: "breakthrough"
  },
  {
    type: "green",
    title: "ghostautonomy.com catch plan COMPLETE — 78-85% probability",
    body: "Expected cost $28-41. Trademark ABANDONED (USPTO serial 97448858). Wild West Domains registrar (GoDaddy pipeline). Expires Jun 7. Auction ~Jul 13. Closeout ~Jul 18. Stacked backorder on both platforms if auction fails.",
    date: "2026-05-21",
    category: "strategy"
  },
  {
    type: "orange",
    title: "DataForSEO Backlinks API requires $100/mo subscription — NOT just balance",
    body: "Error 40204: subscription not activated. $49.97 balance exists but Backlinks endpoint blocked. Labs API works ($0.06 spent on whale enrichment). FREE ALTERNATIVE: GoDaddy feed already has Majestic TF/CF/RD. Zero-cost MVP recommended.",
    date: "2026-05-21",
    category: "discovery"
  },
  {
    type: "red",
    title: "CORRECTED: TF=0 is data gap BUT 47% of candidates are SPAM anyway",
    body: "Sprint 43 said 'TF=0 = spam' — WRONG, it's a data gap. Sprint 44 initial pass said 'all 19 are authority' — ALSO WRONG. Verification found 9/19 are spam/PBN (young domains with inflated RefSubNets). Fix: domain age >= 3 years filter. encognitive.com (20yr, DR 50 Ahrefs-verified) is the model of what a REAL candidate looks like.",
    date: "2026-05-21",
    category: "correction"
  },
  {
    type: "cyan",
    title: "Whale metrics overestimated — proxy DA inflates by 7-27 points",
    body: "ghostautonomy.com: proxy DA 52 → real DR 35-45 (overestimates by 7-17 pts). rocketfuel.com: claimed DR 72-78 → actual ~45-55 (overestimates by 17-27 pts). Use DataForSEO Labs for real DR on high-value targets.",
    date: "2026-05-21",
    category: "discovery"
  },
  {
    type: "green",
    title: "Daily pipeline automation READY — 9-step orchestrator + launchd",
    body: "scripts/daily_pipeline.py: download feeds → classify registrars → enrich → score → kill list gate → whale alert → report → ntfy. Dry-run passed. macOS launchd plist at 06:00 UTC. Just needs: launchctl load.",
    date: "2026-05-21",
    category: "infrastructure"
  },
  {
    type: "green",
    title: "9-AGENT SPRINT COMPLETE — 5 whales found, 3 A+ kills, Cooking/Food wins",
    body: "Whale scan: purenz.com ($6, TF 31, BBC+CNN), balconytv.com ($11, Guardian+Wikipedia), inspect-ny.com ($41, 28K RD, NYTimes). Backlink audit killed 3/5 A+ picks (active spam). Fleet analysis: Cooking/Food 2.9x more imp/page than AI/ML. Niche scorer fixed (39 keywords, 96% true positive). 593 tests passing.",
    date: "2026-05-20",
    category: "milestone"
  },
  {
    type: "red",
    title: "ZERO REVENUE after 43 sprints",
    body: "5 domains owned, $56.16 invested, 0 sales, 0 revenue. Priority #1: Drop neovistainc.com to $800 and get first sale. Everything else is theory until proven.",
    date: "2026-05-21",
    category: "critical"
  },
  {
    type: "red",
    title: "GoDaddy Aftermarket API BLOCKED — 403",
    body: "API key authenticates for orders/subscriptions but returns 403 USER_NOT_ALLOWED on aftermarket endpoints. Root cause: key generated without Aftermarket scope. FIX: Regenerate at developer.godaddy.com/keys → Production env → enable Aftermarket + Domains scopes.",
    date: "2026-05-21",
    category: "blocker"
  },
  {
    type: "orange",
    title: "2 RENEWALS detected — kitchenunited.com + avegant.com",
    body: "Both renewed May 20. Expiries moved to 2027. Removed from pipeline. montrealmartialarts.com also GONE (acquired/renewed May 18). ~20% renewal attrition rate confirmed.",
    date: "2026-05-20",
    category: "renewal"
  },
  {
    type: "cyan",
    title: "rocketfuel.com — TM RISK DECLINING",
    body: "Major finding: domain serves DIYAutoTune/MegaSquirtPNP (automotive), NOT Zeta Global. SSL broken. 2/5 Zeta trademarks confirmed dead. TM risk declining to 25-35% drop probability. Still monitor — Jun 25 expiry is key.",
    date: "2026-05-20",
    category: "watch"
  },
  {
    type: "yellow",
    title: "RDAP: All 11 pipeline targets STABLE — zero EPP changes",
    body: "632 live RDAP queries ran in 15.5 min (5 concurrent). decoder.com 5 days to expiry. sunnyray.org/globalgeopark.org still autoRenewPeriod — check daily through May 26.",
    date: "2026-05-21",
    category: "monitoring"
  }
];

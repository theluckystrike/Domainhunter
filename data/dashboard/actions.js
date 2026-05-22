// Human action items
// Last updated: 2026-05-22 (Sprint 44 Day 2)
window.DH_ACTIONS = {
  blocking: [
    {
      id: 24,
      action: "Create ExpiredDomains.net free account",
      detail: "Go to expireddomains.net → Register (free). Unlocks 40K domain CSV/day with native Majestic TF/CF. Scanner already built (scripts/expireddomains_scanner.py). This is the MISSING DATA SOURCE that solves TF=0 for CLEAN_DROP candidates.",
      priority: "critical",
      effort: "5 min",
      status: "pending",
      category: "data_source"
    },
    {
      id: 25,
      action: "Decision: Activate DataForSEO $100/mo Backlinks subscription",
      detail: "ALL Backlinks API endpoints blocked (error 40204). $49.97 balance exists but useless without subscription. Two-stage enricher built (quick_dr_check + full_enrichment). $4.82/month projected at current volume. ALTERNATIVE: ExpiredDomains.net free CSV has Majestic TF/CF natively — may eliminate need entirely.",
      priority: "high",
      effort: "Decision + 5 min",
      status: "pending",
      category: "subscription"
    },
    {
      id: 26,
      action: "Create Gname account + fund balance",
      detail: "Go to gname.com → Register → Fund account. Client built (clients/gname_client.py, 82 tests). 9 channel tiers ($6-$65). Adds 500+ registrar slots to backorder stack (total 1,700+ with DropCatch). WARNING: backorders CANNOT be cancelled once placed.",
      priority: "high",
      effort: "10 min",
      status: "pending",
      category: "platform"
    },
    {
      id: 27,
      action: "Place amateurkitchen.com backorder when pendingDelete",
      detail: "15 days to drop. CLEAN_DROP path (non-GoDaddy registrar). Cooking/Food niche = 2.9x best imp/page. Run quality gate first, then stack Dynadot + DropCatch + Gname.",
      priority: "high",
      effort: "5 min",
      status: "pending",
      category: "acquisition"
    },
    {
      id: 28,
      action: "Run quality gate on Sprint 43 CLEAN_DROP candidates",
      detail: "python3 scripts/quality_gate.py — Run all 19 CLEAN_DROP candidates through 5-check gate (DR>=20, DeepSeek, kill list, registrar, Wayback). With TF=0 diagnosed as data gap (not spam), these may be legitimate targets.",
      priority: "high",
      effort: "10 min",
      status: "pending",
      category: "validation"
    },
    {
      id: 33,
      action: "Monitor watmm.com drop — TODAY 17:45 UTC",
      detail: "24yr domain (2002). Stacked backorder: Dynadot ($10.99) + DropCatch ($59). Drops TODAY. Check DropCatch for auction notification, Dynadot for catch confirmation.",
      priority: "critical",
      effort: "2 min",
      status: "pending",
      category: "monitoring"
    },
    {
      id: 34,
      action: "Monitor encognitive.com DropCatch auction — set max bid",
      detail: "7 bids, $65 current, 4+ days remaining. DR 50 domain. Decide max bid based on flip value ($500-$2K). Currently at $59 standard backorder — will need manual bid if auction escalates.",
      priority: "high",
      effort: "5 min",
      status: "pending",
      category: "acquisition"
    },
    {
      id: 35,
      action: "Add content-based spam filter for adult redirect domains",
      detail: "5 adult redirect domains (fapello, admireme, okfans, fancentro, socialmediagirls) passed 3yr age filter. All registered 2023-03-07 (same-day batch). Need keyword blocklist or Wayback content check to catch these.",
      priority: "medium",
      effort: "1 hr",
      status: "pending",
      category: "pipeline"
    },
    {
      id: 14,
      action: "Regenerate GoDaddy API key with Aftermarket scope",
      detail: "Current key returns 403 on aftermarket endpoints. Go to developer.godaddy.com/keys → Delete old key → Create new → select Production environment → enable Aftermarket + Domains scopes. Update .env GODADDY_API_KEY + GODADDY_API_SECRET.",
      priority: "critical",
      effort: "5 min",
      status: "pending",
      category: "api"
    },
    {
      id: 20,
      action: "Install daily pipeline launchd plist",
      detail: "Run: launchctl load ~/Library/LaunchAgents/com.revenant.daily-pipeline.plist — Activates 9-step daily pipeline at 06:00 UTC. Dry-run already passed.",
      priority: "critical",
      effort: "2 min",
      status: "pending",
      category: "automation"
    },
    {
      id: 21,
      action: "Place ghostautonomy.com stacked backorders",
      detail: "78-85% catch probability. Expected cost $28-41. TM ABANDONED. Place on BOTH Dynadot ($10.99) + DropCatch ($59) when pendingDelete detected. Jun 7 expiry → ~Jul 13 auction → Jul 18 closeout → Aug 6 drop.",
      priority: "high",
      effort: "5 min",
      status: "pending",
      category: "acquisition"
    },
    {
      id: 17,
      action: "Buy purenz.com ($6) — WHALE, TF 31, BBC+CNN",
      detail: "27yr .com, 613 RD, 100% editorial. Best value in today's feed. Travel/NZ niche. GoDaddy closeout — buy NOW before auction ends.",
      priority: "critical",
      effort: "2 min",
      status: "pending",
      category: "acquisition"
    },
    {
      id: 3,
      action: "Find GoDaddy Customer ID from browser login",
      detail: "TESTED: BuyNow API endpoint exists and accepts POST. Auth works. BUT customer ID 778556874 returns 404. Log into godaddy.com → Account Settings → find real Customer #. Then update .env.",
      priority: "medium",
      effort: "5 min",
      status: "pending",
      category: "api"
    }
  ],
  scheduled: [
    { id: 4, action: "Daily RDAP: sunnyray.org + globalgeopark.org", date: "2026-05-26", status: "scheduled", priority: "high", detail: "autoRenewPeriod NOW — check daily through May 26 for EPP transition to pendingDelete" },
    { id: 5, action: "decoder.com EXPIRES — watch only", date: "2026-05-26", status: "scheduled", priority: "low", detail: "Do NOT bid. Log final sale price as market intel." },
    { id: 6, action: "taskplanner.com EXPIRES", date: "2026-05-27", status: "scheduled", priority: "medium", detail: "Monitor. Closeout play at ~Jul 2 ($31)." },
    { id: 7, action: "Dynadot top-up $50", date: "2026-06-01", status: "scheduled", priority: "medium", detail: "Current $78.24 → target $128.24 for backorder coverage" },
    { id: 8, action: "cytheris.com EXPIRES", date: "2026-06-04", status: "scheduled", priority: "medium", detail: "Safest catch. Closeout play at ~Jul 10 ($31)." },
    { id: 9, action: "ghostautonomy.com EXPIRES — #1 TARGET", date: "2026-06-07", status: "scheduled", priority: "critical", detail: "#1 target. 78-85% catch probability. Stacked backorder both platforms. $28-41 expected cost." },
    { id: 10, action: "ingredientcalculator.com GSC checkpoint", date: "2026-06-15", status: "scheduled", priority: "medium", detail: "30-day GSC analysis. Determines REBUILD vs FLIP strategy." },
    { id: 12, action: "bside.com EXPIRES", date: "2026-06-23", status: "scheduled", priority: "high", detail: "27K bl, .edu links. Expected auction $3K-$15K. Max $500." }
  ],
  completed: [
    { id: 29, action: "Add 3-year domain age filter to CLEAN_DROP pipeline", date: "2026-05-22", status: "done", detail: "Filter deployed. Killed 85/127 (67%). All yesterday's spam batch rejected. Added registration_date extraction from RDAP." },
    { id: 30, action: "Re-run pipeline scan (2026-05-22) with age filter", date: "2026-05-22", status: "done", detail: "194,546 → 127 DA≥20 → 42 age-filtered → 10 CLEAN_DROP. 3 legit + 5 adult spam + 2 needs research." },
    { id: 36, action: "STACKED BACKORDERS: watmm.com + moovweb.com + jsonformatter-online.com", date: "2026-05-22", status: "done", detail: "All 3 on Dynadot ($10.99 each) + DropCatch ($59 each). watmm.com drops TODAY. Max exposure $209.97." },
    { id: 1, action: "Drop neovistainc.com price to $800", date: "2026-05-21", status: "done" },
    { id: 31, action: "FIRST STACKED BACKORDER: encognitive.com — Dynadot ($10.99) + DropCatch ($59)", date: "2026-05-21", status: "done", detail: "Ahrefs DR 50, 3.1K BL, 945 LW, 20yr domain. Drops today. Total exposure $69.99, charged only if caught." },
    { id: 32, action: "Critical verification audit — 3 agents, zero-trust", date: "2026-05-21", status: "done", detail: "Found 47% spam in CLEAN_DROP pool. Identified 4 legitimate candidates. Fixed pipeline interpretation." },
    { id: 2, action: "Fix DropCatch .env secret key", date: "2026-05-20", status: "done" },
    { id: 22, action: "Confirm DropCatch API works — NO ID blocker", date: "2026-05-21", status: "done" },
    { id: 23, action: "Confirm Dynadot API works — real backorder placed", date: "2026-05-21", status: "done" },
    { id: 19, action: "montrealmartialarts.com — GONE (acquired/renewed May 18)", date: "2026-05-21", status: "done" },
    { id: 100, action: "GoDaddy SMS alerts + watchlist", date: "2026-05-17", status: "done" },
    { id: 101, action: "Enable GoDaddy auction membership", date: "2026-05-10", status: "done" },
    { id: 102, action: "List viryd.com + neovistainc.com on Afternic", date: "2026-04-20", status: "done" },
    { id: 103, action: "List viryd.com + neovistainc.com on Dan.com", date: "2026-04-20", status: "done" },
    { id: 104, action: "Fund Dynadot account", date: "2026-04-15", status: "done" },
    { id: 105, action: "Fund NameBright account", date: "2026-04-15", status: "done" }
  ],
  contingency: [
    { scenario: "Auction end while sleeping", response: "Set proxy bid at TRUE MAX before bed. GoDaddy proxy handles it. If you lose, you lose — don't watch.", priority: "plan" },
    { scenario: "Credit card declined on GoDaddy win", response: "48hr grace period. Update card IMMEDIATELY. Add backup payment method NOW.", priority: "critical" },
    { scenario: "Domain unexpectedly renewed (RDAP shows ok)", response: "Remove from ALL backorder queues. Update monitored_domains.json to DEAD. Reallocate budget.", priority: "plan" },
    { scenario: "ghostautonomy.com auction price exceeds $200", response: "Let it go to closeout ($5-$11). If closeout sells, backorders catch on drop. Expected $28-41 total.", priority: "plan" },
    { scenario: "Pipeline daily_pipeline.py fails", response: "Check logs at data/pipeline_log_{date}.json. Individual steps are idempotent — re-run failed step only.", priority: "plan" }
  ]
};

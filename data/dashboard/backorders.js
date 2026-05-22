// Backorder placements log
// Last updated: 2026-05-22 (Sprint 44 Day 2)
// Ahrefs data added 2026-05-22
// jsonformatter-online.com CANCELLED 2026-05-22 — TOXIC (Turkish gambling 301 spam)
window.DH_BACKORDERS = {
  summary: {
    total_placements: 7,
    total_domains: 5,
    platforms_active: 2,
    max_exposure: 268.97,
    cancelled: 1,
    date: "2026-05-22"
  },
  placements: [
    {
      domain: "watmm.com",
      age: "24yr (2002)",
      refsubnets: 326,
      registrar: "DreamHost",
      classification: "CLEAN_DROP",
      drop_date: "2026-05-22",
      drop_time: "17:45 UTC",
      status: "DROPPING TODAY",
      dynadot: { placed: true, cost: 10.99, status: "confirmed", api_response: "success=True status=200" },
      dropcatch: { placed: true, cost: 59.00, status: "confirmed", api_response: "success, dropDate=2026-05-22T17:45:00Z" },
      max_exposure: 69.99,
      ahrefs: {
        dr: 28,
        backlinks: 4000000,
        dofollow_pct: 92,
        linking_websites: 628,
        lw_dofollow_pct: 66
      },
      quality: "CLEAN",
      quality_notes: "24yr domain. DR 28 with 4M backlinks and 628 linking websites. 92% dofollow. Massive link count relative to LW = sitewide links from forums/communities (expected for WATMM — We Are The Music Makers, electronic music forum). Organic profile.",
      notes: "Oldest domain in batch. Electronic music community forum since 2002. 4M backlinks = sitewide forum links across thousands of threads. DR 28 is real organic authority."
    },
    {
      domain: "moovweb.com",
      age: "18yr (2008)",
      refsubnets: 389,
      registrar: "Amazon Registrar",
      classification: "CLEAN_DROP",
      drop_date: "2026-05-24",
      drop_time: "17:45 UTC",
      status: "PENDING",
      dynadot: { placed: true, cost: 10.99, status: "confirmed", api_response: "success=True status=200" },
      dropcatch: { placed: true, cost: 59.00, status: "confirmed", api_response: "success, dropDate=2026-05-24T17:45:00Z" },
      max_exposure: 69.99,
      ahrefs: {
        dr: 64,
        backlinks: 33000,
        dofollow_pct: 98,
        linking_websites: 772,
        lw_dofollow_pct: 70
      },
      quality: "EXCELLENT",
      quality_notes: "DR 64 — strongest in batch by far. Known tech company (Edgio/Moovweb — web performance/edge computing platform). 772 linking websites with 70% dofollow. 98% dofollow backlinks = industry/tech editorial links. High organic authority. Will likely trigger DropCatch auction due to DR 64 visibility.",
      notes: "BEST CANDIDATE. DR 64, 33K BL, 772 LW. Edgio/Moovweb tech company. Expect DropCatch auction competition at this DR level."
    },
    {
      domain: "jsonformatter-online.com",
      age: "9yr (2017)",
      refsubnets: 256,
      registrar: "NameCheap",
      classification: "TOXIC_DROP",
      drop_date: "2026-05-24",
      drop_time: "17:45 UTC",
      status: "CANCELLED",
      cancelled_date: "2026-05-22",
      cancelled_reason: "TOXIC -- Turkish gambling 301 redirect spam, pharma anchors, blog comment spam. DR 37 inflated. Only 1 real editorial link.",
      dynadot: { placed: true, cost: 10.99, status: "cancelled", api_response: "delete_backorder_request success=True" },
      dropcatch: { placed: true, cost: 59.00, status: "cancelled", api_response: "DELETE /v2/backorders success, failures=[]" },
      max_exposure: 0,
      ahrefs: {
        dr: 37,
        backlinks: 36000,
        dofollow_pct: 69,
        linking_websites: 1100,
        lw_dofollow_pct: 41
      },
      quality: "TOXIC",
      quality_notes: "DR 37 looks decent but backlink profile is HEAVILY CONTAMINATED. Turkish gambling spam via 301 redirect chains (askalexww.com → tacosmexigo.com → thewonderingalchemist.com → westpasco.com → jsonformatter-online.com). Anchors include: 'deneme bonusu', 'almanbahis', 'betovis', 'depobola', plus pharma spam ('Achat Viagra', 'Cialis Generique'). Some legitimate links exist (DigitalOcean DR 91 editorial mention, foodiecrush DR 72, loveandlemons DR 80) but these are old blog comment spam from ~2017 with 'json formatter' anchors. 41% dofollow on linking websites = red flag for spam dilution.",
      spam_signals: [
        "301 redirect chain from Turkish gambling domains",
        "Pharma spam anchors (Viagra, Cialis, Kamagra)",
        "Turkish gambling anchors (deneme bonusu, almanbahis, betovis)",
        "Blog comment spam on food/lifestyle sites (~2017 era)",
        "Only 41% dofollow linking websites (spam diluted)"
      ],
      legit_links: [
        { domain: "digitalocean.com", dr: 91, anchor: "find this tool pretty useful to format and validate JSON: JSON formatter", type: "editorial" },
        { domain: "loveandlemons.com", dr: 80, anchor: "Depo Bola (301 chain)", type: "spam redirect" },
        { domain: "autostraddle.com", dr: 76, anchor: "json converter", type: "blog comment spam" },
        { domain: "stylebyemilyhenderson.com", dr: 75, anchor: "json formatter", type: "blog comment spam" },
        { domain: "yogawithadriene.com", dr: 72, anchor: "Depobola (301 chain)", type: "spam redirect" },
        { domain: "foodiecrush.com", dr: 72, anchor: "json formatter", type: "blog comment spam" },
        { domain: "onegoodthingbyjillee.com", dr: 71, anchor: "Json Formatter", type: "blog comment spam" },
        { domain: "repeatcrafterme.com", dr: 62, anchor: "json formatter online", type: "blog comment spam" },
        { domain: "jadlonomia.com", dr: 57, anchor: "json formatter online", type: "blog comment spam" }
      ],
      notes: "CANCELLED 2026-05-22. DR 37 is misleading. Profile is 301 redirect spam (Turkish gambling) + blog comment spam (~2017). Only 1 real editorial link (DigitalOcean). Backorders cancelled on both DropCatch and Dynadot. Exposure reduced by $69.99."
    },
    {
      domain: "encognitive.com",
      age: "20yr (2006)",
      refsubnets: 450,
      registrar: "DropCatch.com 1165 LLC",
      classification: "CLEAN_DROP (caught by DropCatch)",
      drop_date: "2026-05-21",
      drop_time: "—",
      status: "AUCTION",
      dynadot: { placed: true, cost: 10.99, status: "missed", api_response: "Dynadot did NOT catch" },
      dropcatch: { placed: true, cost: 59.00, status: "auction", api_response: "7 bids, $65 current, 4+ days remaining" },
      max_exposure: 59.00,
      ahrefs: {
        dr: 50,
        backlinks: 3100,
        dofollow_pct: null,
        linking_websites: 945,
        lw_dofollow_pct: null
      },
      quality: "CLEAN",
      quality_notes: "DR 50, 3.1K BL, 945 LW. Known from prior verification. DropCatch caught it — now in auction at $65 with 7 bids. DR 50 attracted competition as predicted.",
      notes: "DR 50. DropCatch caught → auction. 7 bids, $65 current, 4+ days left. Lesson: DR 50+ domains always attract competing backorders."
    },
    {
      domain: "buffalo-technology.com",
      age: "26yr (2000)",
      refsubnets: 712,
      registrar: "Total Web Solutions Limited",
      classification: "CLEAN_DROP",
      drop_date: "2026-05-22",
      drop_time: "17:45 UTC",
      status: "PENDING",
      dynadot: { placed: true, cost: 10.99, status: "confirmed", api_response: "success=True status=200" },
      dropcatch: { placed: true, cost: 59.00, status: "confirmed", api_response: "success, dropDate=2026-05-22T17:45:00Z" },
      max_exposure: 69.99,
      ahrefs: {
        dr: 56,
        backlinks: 24000,
        dofollow_pct: 86,
        linking_websites: 1600,
        lw_dofollow_pct: 66
      },
      quality: "EXCELLENT",
      quality_notes: "DR 56 — second strongest in pipeline. Known hardware company (Buffalo Technology — NAS, routers, external drives). Wikipedia backlink from DD-WRT article. 1,600 linking websites with 66% dofollow. 86% dofollow backlinks = organic editorial profile. 26 years of domain age.",
      notes: "#2 CANDIDATE. DR 56, 24K BL, 1.6K LW. Wikipedia BL. Real hardware company. Expect DropCatch auction at DR 56."
    }
  ],
  ranking: [
    { rank: 1, domain: "moovweb.com", dr: 64, verdict: "EXCELLENT — Best candidate. Real tech company, DR 64, TechCrunch+VentureBeat BL. TM risk zero." },
    { rank: 2, domain: "buffalo-technology.com", dr: 56, verdict: "EXCELLENT — DR 56, Wikipedia BL, 1.6K LW. Real hardware company. BACKORDER PLACED." },
    { rank: 3, domain: "encognitive.com", dr: 50, verdict: "CLEAN but IN AUCTION — DR 50, YMYL risk. Flip-only, max bid $175." },
    { rank: 4, domain: "watmm.com", dr: 28, verdict: "CLEAN — 24yr electronic music forum. DR 28 organic. Drops TODAY 17:45 UTC." },
    { rank: 5, domain: "jsonformatter-online.com", dr: 37, verdict: "CANCELLED — TOXIC. 301 gambling spam. Backorders cancelled 2026-05-22." },
    { rank: 6, domain: "apksos.com", dr: 38, verdict: "BORDERLINE — DR 38 decent but APK download niche = malware reputation risk. Skip." },
    { rank: 7, domain: "seven10solutions.com", dr: 0.9, verdict: "REJECTED — DR 0.9, zero authority. 97% dofollow = spam. Not worth $69.99." }
  ],
  ahrefs_verified: [
    { domain: "buffalo-technology.com", dr: 56, backlinks: 24000, dofollow_pct: 86, linking_websites: 1600, lw_dofollow_pct: 66, quality: "EXCELLENT", status: "BACKORDER_PLACED", key_links: "Wikipedia (DD-WRT article), Buffalo forums. Real networking/storage hardware company.", action: "STACKED BACKORDER CONFIRMED — Dynadot + DropCatch" },
    { domain: "seven10solutions.com", dr: 0.9, backlinks: 3700, dofollow_pct: 97, linking_websites: 567, lw_dofollow_pct: 79, quality: "REJECTED", status: "KILLED", key_links: "None valuable. 97% dofollow = purchased/spam links.", action: "SKIP — DR 0.9 is worthless" },
    { domain: "apksos.com", dr: 38, backlinks: 4800, dofollow_pct: 54, linking_websites: 833, lw_dofollow_pct: 49, quality: "BORDERLINE", status: "SKIPPED", key_links: "Unknown — APK download niche carries malware reputation risk.", action: "SKIP — niche risk outweighs DR 38 value" }
  ],
  platforms: {
    dynadot: {
      api_status: "LIVE",
      balance: 67.25,
      active_backorders: ["watmm.com", "moovweb.com", "buffalo-technology.com"],
      cost_per_backorder: 10.99,
      total_exposure: 32.97,
      catch_method: "Registry-level backorder. Charged only if caught.",
      notes: "jsonformatter-online.com cancelled 2026-05-22 (TOXIC). list_backorder API returns empty but placements confirmed via success=True response."
    },
    dropcatch: {
      api_status: "LIVE",
      balance: "N/A (charged on catch)",
      active_backorders: ["encognitive.com", "watmm.com", "moovweb.com", "buffalo-technology.com"],
      cost_per_backorder: 59.00,
      total_exposure: 236.00,
      catch_method: "1,200+ registrar slots via NameBright network. Auction if multiple backorders.",
      notes: "jsonformatter-online.com cancelled 2026-05-22 (TOXIC). All placements confirmed via PUT /v2/backorders API. OAuth2 auth working."
    }
  },
  rejected: [
    { domain: "fapellolive.com", refsubnets: 297, reason: "Adult spam batch (fapello redirect)", registered: "2023-03-07" },
    { domain: "okfanslive.com", refsubnets: 270, reason: "Adult spam batch (okfans redirect)", registered: "2023-03-07" },
    { domain: "livefancentrolive.com", refsubnets: 265, reason: "Adult spam batch (fancentro redirect)", registered: "2023-03-07" },
    { domain: "socialmediagirlslive.com", refsubnets: 245, reason: "Adult spam batch (forum redirect)", registered: "2023-03-07" },
    { domain: "admiremelive.com", refsubnets: 231, reason: "Adult spam batch (admireme redirect)", registered: "2023-03-07" },
    { domain: "apksos.com", refsubnets: 323, reason: "Needs research — potential malware reputation risk", registered: "2022-05-15" },
    { domain: "seven10solutions.com", refsubnets: 314, reason: "Needs research — business name, needs Wayback check", registered: "2019-08-12" }
  ],
  history: [
    { date: "2026-05-21", action: "First stacked backorder", domain: "encognitive.com", platforms: "Dynadot + DropCatch", result: "DropCatch caught → auction (7 bids, $65)" },
    { date: "2026-05-22", action: "Stacked backorder x3", domain: "watmm.com", platforms: "Dynadot + DropCatch", result: "Confirmed. Drops TODAY 17:45 UTC" },
    { date: "2026-05-22", action: "Stacked backorder x3", domain: "moovweb.com", platforms: "Dynadot + DropCatch", result: "Confirmed. Drops May 24" },
    { date: "2026-05-22", action: "Stacked backorder x3", domain: "jsonformatter-online.com", platforms: "Dynadot + DropCatch", result: "Confirmed. Drops May 24" },
    { date: "2026-05-22", action: "Ahrefs backlink audit", domain: "all 3 + encognitive", platforms: "—", result: "moovweb DR 64 (best), watmm DR 28 (clean), jsonformatter DR 37 (TOXIC — gambling spam)" },
    { date: "2026-05-22", action: "CANCELLED backorders", domain: "jsonformatter-online.com", platforms: "Dynadot + DropCatch", result: "Both cancelled. TOXIC — Turkish gambling 301 redirect spam, pharma anchors. Exposure reduced by $69.99." },
    { date: "2026-05-22", action: "Ahrefs verified 3 candidates", domain: "buffalo-tech / seven10 / apksos", platforms: "—", result: "buffalo-technology DR 56 EXCELLENT, seven10solutions DR 0.9 REJECTED, apksos DR 38 SKIPPED" },
    { date: "2026-05-22", action: "Stacked backorder", domain: "buffalo-technology.com", platforms: "Dynadot + DropCatch", result: "Confirmed. DR 56, Wikipedia BL, 26yr. dropDate=2026-05-22T17:45:00Z" }
  ]
};

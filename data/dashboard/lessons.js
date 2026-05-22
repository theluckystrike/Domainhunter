// Lessons & Strategy — institutional knowledge from 44 sprints
// This is authored content, not auto-generated from scans
// Last updated: 2026-05-21 (Sprint 44)
window.DH_LESSONS = {
  bottom_line: "44 sprints. 5 domains owned. $56.16 invested. 0 sales. 0 revenue. FIRST REAL BACKORDER PLACED: encognitive.com (DR 50 Ahrefs-verified, 3.1K BL, 20yr domain, $10.99 Dynadot). CRITICAL VERIFICATION: 47% of CLEAN_DROP candidates were SPAM — 9/19 registered in a 4-day batch (Mar 2025), inflated RefSubNets. Only 4 of 19 legitimate. Fix: domain age >= 3yr filter. 'RD' was mislabeled (actually RefSubNets). 'DA' was synthetic. neovistainc.com dropped to $800. Re-scan tomorrow with age filter.",

  hard_truths: [
    { num: 1, color: "red", truth: "Sniping is dead.", evidence: "GoDaddy soft close: any bid changing price with <5 min left extends auction 5 minutes, indefinitely. Proxy auto-responds in <1 second.", implication: "T-30s bot = dead code. T-305s proxy bid (outside anti-snipe window). Only closeout BuyNow is first-come-first-served." },
    { num: 2, color: "red", truth: "Bots own the auction floor.", evidence: "HugeDomains bot '913932' wins 47% of contested auctions. PerfectDomain brings combined win rate to 64%. ~$500 ceiling on dictionary .com. API access closed to new applicants since 2020.", implication: "Dictionary .com domains under $500 are bot food. Don't compete. Any recognizable English-word .com will be auto-bid." },
    { num: 3, color: "red", truth: "Good domains never reach backorder.", evidence: "8/8 bid targets SOLD at auction (100% loss rate). Every domain with TF >= 10 or age 20+ sold. Zero made it to pendingDelete.", implication: "Authority domains must be won at auction or closeout. Backorder is for leftovers only, except .org (near-zero auction competition)." },
    { num: 4, color: "orange", truth: "97.7% of auctions get zero bids.", evidence: "95,539 of 97,814 domains = zero bids. Only 2,275 (2.3%) attracted ANY activity. Only 870 had 2+ bids.", implication: "The opportunity is in the long tail, not contested auctions. 200K+ closeouts/day, 75K uncaught drops/day. Volume beats precision." },
    { num: 5, color: "orange", truth: "GoDaddy is a monopoly.", evidence: "29 registrars feed GoDaddy Auctions (Tucows since 2016, Squarespace since Aug 2025). 77-day pipeline: expiry → 18d grace → 10d auction → 5d closeout → 30d RGP → 5d pendingDelete → drop.", implication: "Nearly all expired domains pass through GoDaddy before dropping. Clean-drop registrars (Cloudflare, Gandi, DreamHost) are rare." },
    { num: 6, color: "orange", truth: "Renewals kill 1 in 5 targets.", evidence: "bestdevtools.com, purenz.com, kitchenunited.com, avegant.com, guerrameats.com — all renewed despite expiry locks. clientRenewProhibited does NOT prevent renewal.", implication: "~20% attrition rate on pipeline. Always run RDAP the day before action. Never invest emotionally in a single target." },
    { num: 7, color: "green", truth: "Closeout = best ROI path.", evidence: "11.8% of successfully flipped domains were acquired at closeout ($5-$11). Median ROI: 400% for TF >= 15 closeouts. montrealmartialarts.com: $6, TF 37. No anti-snipe on BuyNow.", implication: "Focus here. Filter GoDaddy closeout feed daily for TF 15+, $5-$11. Buy 2-3/week at $15-$33 total. Flip at $200-$500 each." },
    { num: 8, color: "green", truth: ".org is the blind spot.", evidence: "Near-zero auction competition for .org. globalgeopark.org (DA 49, UNESCO backlinks) appeared in GoDaddy feed with 0 bids. Dynadot has 'great success' with .org catch rate (~30%).", implication: "Focus Dynadot backorders exclusively on .org targets. Don't waste Dynadot's 15 registrar slots on .com (80:1 odds vs DropCatch)." },
    { num: 9, color: "green", truth: "Free data beats paid APIs.", evidence: "GoDaddy Inventory Protocol: 41 free JSON/CSV/XML feeds, no auth, 300K+ closeouts with Majestic TF + Semrush RD. Updated daily 7-8am PST. Replaces DataForSEO.", implication: "Kill the DataForSEO spend. Inventory Protocol + RDAP + DropCatch CSV = complete data stack at near-zero cost." },
    { num: 10, color: "cyan", truth: "The flip thesis is unproven.", evidence: "43 sprints. $56.16 invested. 5 domains owned. 2 listed (viryd.com $2,500 + neovistainc.com $1,500). Zero sales. Zero revenue.", implication: "Priority #1: Get one sale. Drop neovistainc.com to $800. Prove the model before scaling. One $800 sale validates the entire pipeline." },
    { num: 11, color: "green", truth: "Clean-drop registrars are rare but real.", evidence: "Live POC: 632 DA≥20 domains → only 19 (3.0%) at clean-drop registrars (NameCheap 12, Cloudflare 4, DreamHost 2, Porkbun 1). 75.6% at GoDaddy-pipeline registrars.", implication: "Clean-drop rate is LOW but these domains skip auction entirely. 60-70% catch probability vs 5-10% at GoDaddy pipeline. Worth scanning at scale." },
    { num: 12, color: "orange", truth: "Proxy metrics overestimate by 7-27 points.", evidence: "ghostautonomy.com: proxy DA 52 → real DR 35-45. rocketfuel.com: proxy DR 72-78 → actual ~45-55. DataForSEO Labs confirms.", implication: "Never trust feed metrics for high-value decisions. Verify with DataForSEO Labs ($0.06/domain) before committing >$50." },
    { num: 13, color: "green", truth: "Both backorder APIs work. No ID blocker.", evidence: "DropCatch: placed AND cancelled real backorder. Account 387137 fully operational. Dynadot: placed real backorder. $78.24 balance. Zero verification issues.", implication: "The 'ID verification blocker' was a false alarm. Both platforms ready for live backorders TODAY." },
    { num: 14, color: "green", truth: "TF=0 does NOT mean no authority.", evidence: "All 19 CLEAN_DROP candidates are in Majestic Million with 244-670 RD. DropCatch CSV has only 4 fields (Domain, TLD, Type, Drop Date) — zero metrics. GoDaddy feed has TF but zero overlap with CLEAN_DROP domains. TF=0 is a data gap, not a quality signal.", implication: "Sprint 43 warning 'TF=0 = spam' was WRONG. Use RD-based scoring for CLEAN_DROP pool. Don't discard candidates based on missing data." },
    { num: 15, color: "orange", truth: "Free data has structural gaps.", evidence: "DropCatch CSV: 524,957 unique .com but only 4 columns (zero authority metrics). GoDaddy feed: 300K+ with Majestic TF/CF but only covers GoDaddy-pipeline registrars. ExpiredDomains.net: native TF/CF but needs account + manual CSV download. No single free source covers everything.", implication: "Must layer multiple free sources (GoDaddy feed + DropCatch CSV + ExpiredDomains.net) to get complete coverage. Or pay DataForSEO $100/mo for DR on demand." },
    { num: 16, color: "red", truth: "47% of CLEAN_DROP candidates are spam/PBN.", evidence: "3-agent verification: 9/19 domains registered in last 15 months with 244-670 RefSubNets. 7 registered in 4-day batch (Mar 4-7 2025). 2 are OVH abuse takedowns (future expiry + pendingDelete). These are link networks designed to inflate metrics, not authority sites.", implication: "High RefSubNets ≠ high quality. Domain age is the REAL quality signal. Add 3-year minimum age filter. Kills all 9 spam, preserves all 4 legitimate candidates." },
    { num: 17, color: "green", truth: "Domain age is the ultimate spam filter.", evidence: "All 4 legitimate CLEAN_DROP candidates are 9-24 years old. All 9 spam candidates are <15 months old. Zero false positives with 3-year cutoff. encognitive.com: 20yr, DR 50 (Ahrefs verified) — the template.", implication: "Age >= 3 years before any backorder. Combined with Ahrefs spot-check on high-value targets ($0 with free toolbar). This is the filter we were missing." },
    { num: 18, color: "orange", truth: "Pipeline data labels were wrong.", evidence: "'RD' in pipeline = actually RefSubNets (Majestic Million column 5, referring subnets, NOT referring domains). 'DA' = int(log10(RefSubNets+1)*10) — synthetic formula, NOT real Moz DA. floresdelicadas.com 'cooking niche' = matched substring 'deli' inside the word. Agent outputs need verification.", implication: "Never trust pipeline labels without checking the source column. Rename fields. Label synthetic metrics clearly. Verify agent claims independently." }
  ],

  works: [
    { label: "Closeout speed-buy ($5-$11)", detail: "First-come-first-served, no anti-snipe, 400% median ROI on TF 15+" },
    { label: "GoDaddy Inventory Protocol", detail: "Free daily 300K+ domain feed with Majestic/Semrush metrics. Zero cost." },
    { label: ".org Dynadot backorder", detail: "~30% catch rate, $10.99, near-zero competition. Best TLD for backorder." },
    { label: "Multi-platform backorder stack", detail: "DropCatch ($59) + Gname ($65) = 1,700 registrar slots. Pay only if caught." },
    { label: "RDAP monitoring for EPP transitions", detail: "Catches renewals, redemption periods, pendingDelete entry. ~20% save rate." },
    { label: "12-signal validation scoring", detail: "Catches fraud (bluemaxcapital), far-right (whiteoutpress), gambling spam. 24% kill rate." },
    { label: "Startup failure monitoring", detail: "2.6x closure rate in 2026. AI wrapper wave coming Q3-Q4. Source of future targets." },
    { label: "Niche relevance filtering", detail: "Semrush keyword data from Inventory Protocol identifies topical clusters. Auto-flags domains matching AI/ML, cooking, dev tools, etc." },
    { label: "Build vs Flip classification", detail: "Second scoring pass answers 'would I build on this?' vs 'is this just a brand name?'. TF/CF ratio, niche match, age, content history." }
  ],

  doesnt_work: [
    { label: "T-30s sniping", detail: "Dead. Soft close anti-snipe extensions. Structurally impossible." },
    { label: "$5 bids on authority domains", detail: "8/8 loss rate. Feeds the proxy system. Bot auto-escalates every raise." },
    { label: "GoDaddy Auctions API (bidding)", detail: "Closed to new applicants since ~2020. Two-tier system: API insiders vs everyone else." },
    { label: "Dynadot backorder for .com", detail: "15 registrar slots vs DropCatch's 1,200. 80:1 odds. Near-zero catch rate on competitive .com." },
    { label: "Contested auction bidding (<$500)", detail: "HugeDomains bot wins 47% under $500. You're paying the bot tax on every English-word .com." },
    { label: "DataForSEO Backlinks API", detail: "Requires $100/mo subscription (error 40204). $49.97 balance exists but endpoint blocked. Labs API works. Use free GoDaddy feed Majestic data instead." },
    { label: "Emotional attachment to TIER 0 targets", detail: "rocketfuel.com has LIVE trademark (Zeta Global). decoder.com will auction at $5K-$100K. Set max proxy, walk away." },
    { label: "Generic authority scoring alone", detail: "A domain with TF 22 from cooking blogs = 9/10 for building but 4/10 as flip. Need niche-aware scoring." }
  ],

  playbook: [
    { priority: 0, strategy: "GET FIRST SALE", cost: "$0", roi: "∞", effort: "1 hour", how: "Drop neovistainc.com to $800. List on Dan.com + Afternic + Sedo simultaneously." },
    { priority: 1, strategy: "Closeout volume play", cost: "$5-$11", roi: "400% median", effort: "30 min/day", how: "Run closeout_monitor.py 3x/day. Filter TF >= 15, $5-$11. Buy 2-3/week. Flip at $200-$500." },
    { priority: 2, strategy: ".org backorder pipeline", cost: "$10.99", roi: "500%+ potential", effort: "10 min/day", how: "Daily RDAP on .org targets. Dynadot backorder at pendingDelete. globalgeopark.org is test case." },
    { priority: 3, strategy: "Long-tail drop scanning", cost: "$8-$12", roi: "200-400%", effort: "20 min/day", how: "Run longtail_drop_scanner.py daily. 75K uncaught drops/day. DA 15-25 sweet spot." },
    { priority: 4, strategy: "Whale targets (passive)", cost: "$59-$124", roi: "Variable", effort: "5 min/week", how: "Set proxy bids at true max. Place DropCatch + Gname backorders. Walk away." },
    { priority: 5, strategy: "Niche fleet building", cost: "$5-$31/domain", roi: "100x authority multiplier (unproven)", effort: "2-3 domains/month", how: "Closeout scanner + niche_match filter. Deploy 50 pages of topical content on authority domains. Start at position 10-20 instead of 50+ like fresh domains." },
    { priority: 6, strategy: "Whale catch (passive)", cost: "$31-$124", roi: "Build or flip $5K-$50K", effort: "Automatic (scanner + backorder)", how: "ghostautonomy.com is the template. DR 45+, editorial links. Either build content empire OR flip. Let scanner find them, backorder auto." }
  ],

  attrition: [
    { domain: "bestdevtools.com", what_happened: "Renewed May 17 (expiry → 2027)", category: "RENEWED", lesson: "clientRenewProhibited does NOT prevent renewal" },
    { domain: "purenz.com", what_happened: "Sold at GoDaddy auction to Tucows, Apr 24", category: "SOLD AT AUCTION", lesson: "TF 31, NZ tourism — exactly what pros target" },
    { domain: "kitchenunited.com", what_happened: "Renewed May 20 (expiry → 2027)", category: "RENEWED", lesson: "$100M funded companies often auto-renew" },
    { domain: "avegant.com", what_happened: "Renewed May 20 (expiry → 2027)", category: "RENEWED", lesson: "Even dead startups with lock flags can renew" },
    { domain: "guerrameats.com", what_happened: "Confirmed renewed, expiry → 2027", category: "RENEWED", lesson: "1 bid at auction suggests manual renewal triggered" },
    { domain: "cosmeticimplantdentist.com", what_happened: "Sold to 1API GmbH, May 15", category: "SOLD AT AUCTION", lesson: "CPC keyword domains = pro investor targets" },
    { domain: "prolificprogrammer.com", what_happened: "$1→$6→$11→$21 in 3 bids", category: "PROXY TRAPPED", lesson: "Raising bids feeds the proxy. Every dollar goes to the ceiling." },
    { domain: "magellanpetroleum.com", what_happened: "Sold, transfer pending, May 14", category: "SOLD AT AUCTION", lesson: "NASDAQ ticker domains = high-value targets" },
    { domain: "balconytv.com", what_happened: "Sold, transfer pending, May 17", category: "SOLD AT AUCTION", lesson: "1,066 RD, 20yr music platform — exactly what TF filter catches" },
    { domain: "tepilo.com", what_happened: "Sold, transfer pending, May 17", category: "SOLD AT AUCTION", lesson: "3 bids, 2 bidders = proxy war unwinnable at $16" },
    { domain: "swaptree.com", what_happened: "Listed on Afternic for $50K asking price", category: "PRICED OUT", lesson: "Aftermarket asking prices ($50K) disconnected from estimated values ($2K-$10K)" },
    { domain: "bluemaxcapital.com", what_happened: "Forex fraud site, contaminated backlinks", category: "KILLED (FRAUD)", lesson: "12-signal validator caught it. Always check site content." },
    { domain: "whiteoutpress.com", what_happened: "Far-right content, toxic association", category: "KILLED (CONTENT)", lesson: "Backlinks alone don't tell the story. Check Wayback Machine." }
  ],

  attrition_rates: {
    renewed: 20,
    sold_at_auction: 30,
    killed_validation: 24,
    survives_to_action: 26,
    note: "Only ~26% of researched targets survive to actionable status. Build a wide funnel."
  },

  landscape: [
    { player: "HugeDomains (bot 913932)", advantage: "API access, $500 ceiling, 5.1M portfolio, 200-350 closeout buys/day", weakness: "Keyword/brandability focused. Misses niche verticals, .org, long compounds.", our_edge: "We target what their algorithm doesn't score: niche authority, editorial backlinks, non-brandable high-TF." },
    { player: "DropCatch", advantage: "1,200+ registrar slots, ~50% catch on competitive .com", weakness: "Discount Club ($13) deprioritized vs Standard ($59).", our_edge: "Use Standard $59 tier. Stack with Gname for 1,700 combined slots." },
    { player: "Pro domainers", advantage: "Experience, GoDaddy API access (grandfathered), marketplace relationships", weakness: "Focus on short brandable .com. Don't do deep backlink analysis.", our_edge: "Automated 300K+ daily scan with TF/RD filtering. Speed + depth." },
    { player: "SEO operators", advantage: "Know backlink value. Willing to pay $500+ for DA 40+.", weakness: "Google's expired domain abuse update penalizes off-topic reuse.", our_edge: "We buy and flip, not build PBNs. Clean marketplace listings." }
  ],

  edge: [
    { name: "Automated Scanning", detail: "300K+ closeouts scanned daily with TF/RD filtering at zero marginal cost." },
    { name: "Niche Targeting", detail: "HugeDomains misses .org authority, editorial backlinks, long compounds with high TF." },
    { name: "Multi-Platform Stack", detail: "DropCatch + Gname + Dynadot + GoDaddy closeout + long-tail. Five channels, 1,700+ registrar slots." },
    { name: "Niche Content Deployment", detail: "Deploy 50 pages of topical content on authority domains. Backlinks give head start that fresh domains can't match." }
  ]
};

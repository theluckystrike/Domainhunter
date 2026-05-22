// Competition intelligence — curated from 16 research agents + 41 sprints
// Last updated: 2026-05-20
window.DH_COMPETITION = {
  headline_stats: {
    zero_bid_rate: 97.7,
    zero_bid_detail: "95,539 of 97,814 domains = zero bids. Only 2,275 (2.3%) attracted ANY activity.",
    bot_ceiling_usd: 500,
    daily_drops_uncaught: 75000,
    daily_closeouts: 200000,
    daily_auctions_active: 97814
  },

  proxy_mechanics: {
    how_it_works: "GoDaddy proxy bidding: bidder sets hidden maximum. System auto-responds to any incoming bid up to that ceiling in <1 second. You never see the real max until you exceed it.",
    soft_close: "Any bid that changes the price with <5 minutes remaining extends the auction by 5 minutes. This extension repeats indefinitely. A single proxy bidder creates an infinite extension loop.",
    implication: "T-30s sniping is structurally impossible. Even T-5min fails. Only T-305s (outside anti-snipe window) or closeout BuyNow works.",
    evidence: "prolificprogrammer.com: $1→$6→$11→$21 in 3 bids, 2 bidders. Each bid fed the proxy. HugeDomains proxy set at ~$50 for a TF 26 domain."
  },

  godaddy_pipeline: {
    description: "77-day journey from expiry to drop",
    stages: [
      { name: "Grace Period", days: 18, detail: "Owner can still renew. clientRenewProhibited doesn't prevent this." },
      { name: "Auction", days: 10, detail: "GoDaddy Expired Domain Auction. 97.7% get zero bids." },
      { name: "Closeout", days: 5, detail: "BuyNow at $5-$50. First-come-first-served. No anti-snipe." },
      { name: "Redemption (RGP)", days: 30, detail: "Registrar can still recover at premium price." },
      { name: "Pending Delete", days: 5, detail: "ICANN deletion queue. Backorder window." },
      { name: "Drop", days: 0, detail: "Domain released. DropCatch/Gname/Dynadot compete." }
    ],
    feeder_registrars: "29 registrars feed GoDaddy: Tucows (since 2016), Squarespace (since Aug 2025), DreamHost, etc."
  },

  key_players: [
    {
      name: "HugeDomains (bot 913932)",
      type: "bot",
      win_rate: 47,
      ceiling_usd: 500,
      detail: "5.1M portfolio. Sister company of DropCatch. 200-350 closeout buys/day. API access (closed to new applicants since ~2020). Algorithm targets short brandable .com. Misses niche verticals, .org, long compounds.",
      weakness: "Keyword/brandability focused. Doesn't score editorial backlinks, niche authority, or non-English domains."
    },
    {
      name: "PerfectDomain",
      type: "bot",
      win_rate: 17,
      ceiling_usd: 300,
      detail: "Combined with HugeDomains = 64% of contested auctions. Similar algorithmic approach.",
      weakness: "Same blindspot as HugeDomains — misses non-brandable authority domains."
    },
    {
      name: "DropCatch",
      type: "registrar",
      win_rate: 0,
      ceiling_usd: 0,
      detail: "1,200+ ICANN registrar accreditations. ~50% catch rate on competitive .com. Discount Club ($13) deprioritized vs Standard ($59).",
      weakness: "HugeDomains gets corporate partner priority. Discount tier is second-class."
    },
    {
      name: "Gname",
      type: "registrar",
      win_rate: 0,
      ceiling_usd: 0,
      detail: "501 registrar accreditations. $65/catch. Chinese registrar with bulk API. Growing fast.",
      weakness: "Fewer slots than DropCatch. Interface in Chinese."
    },
    {
      name: "Dynadot",
      type: "registrar",
      win_rate: 0,
      ceiling_usd: 0,
      detail: "~15 accreditations. $10.99/catch. 'Great success' with .org (~30% catch rate).",
      weakness: "Only 15 slots. Near-zero catch rate on competitive .com. .org only realistic."
    }
  ],

  auction_outcomes: {
    our_bids: [
      { domain: "cosmeticimplantdentist.com", bid: 5, result: "SOLD to 1API GmbH", lesson: "CPC keyword = pro target" },
      { domain: "prolificprogrammer.com", bid: 5, result: "$1→$6→$11→$21, proxy trapped", lesson: "Raising bids feeds proxy" },
      { domain: "purenz.com", bid: 5, result: "SOLD to Tucows", lesson: "TF 31 NZ tourism = pro target" },
      { domain: "magellanpetroleum.com", bid: 5, result: "SOLD, transfer pending", lesson: "NASDAQ ticker = high value" },
      { domain: "balconytv.com", bid: 5, result: "SOLD, transfer pending", lesson: "1,066 RD visible to scanners" },
      { domain: "tepilo.com", bid: 16, result: "SOLD, 3 bids 2 bidders", lesson: "Proxy war unwinnable at $16" },
      { domain: "violadamore.com", bid: 5, result: "SOLD", lesson: "26yr niche = pro target" }
    ],
    total_bids: 7,
    total_wins: 0,
    loss_rate: 100,
    lesson: "Every domain with TF >= 10 or age 20+ sells at auction. Good domains never reach backorder."
  },

  our_edge: [
    { name: "Automated Scanning", detail: "300K+ closeouts scanned daily with TF/RD filtering at zero cost. Pros scan manually." },
    { name: "Niche Targeting", detail: "HugeDomains misses .org authority, editorial backlink domains, long compounds with high TF." },
    { name: "Multi-Platform Stack", detail: "DropCatch + Gname + Dynadot + GoDaddy closeout + long-tail. 5 channels, 1,700+ registrar slots." },
    { name: "Cost Discipline", detail: "GoDaddy Inventory Protocol = free daily data. No DataForSEO dependency. Near-zero scanning cost." }
  ],

  long_tail_opportunity: {
    daily_drops: 75000,
    uncaught_rate: 88,
    sweet_spot: "DA 15-25 domains that nobody is scanning for. $8-$12 registration, $200-$500 flip.",
    detail: "75,000 .com domains/day go unregistered after dropping. Most have zero value. But ~1% have DA 15+ with clean history. That's 750 domains/day nobody is competing for."
  }
};

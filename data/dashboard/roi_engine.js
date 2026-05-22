// ROI Engine Data — Sprint 46 Validation
// Generated 2026-05-22 from 6,746 Dropped auctions + 40 validation agents
window.DH_ROI_ENGINE = {
  date: "2026-05-22",
  data_sources: {
    full_dropped_pull: { count: 6746, file: "all_dropped_auctions.json" },
    mixed_pull: { count: 1425, file: "dropcatch_live_auctions_2026-05-22.json" },
    bid_histories: { count: 521, file: "bid_histories_sample.json" },
    external_sources: 10
  },

  // THE FUNNEL
  funnel: {
    daily_com_deletions: 103798,
    dropcatch_catches: 3864,
    catch_rate_pct: 3.72,
    uncontested_pct: 95.6,
    uncontested_daily: 3694,
    contested_daily: 170,
    contested_under_100: 95,
    contested_100_500: 54,
    contested_500_plus: 20,
    contested_1k_plus: 2
  },

  // COMPETITION PROFILES
  competition: {
    by_word_count: [
      { words: "1 word", avg_bidders: 7.8, example: "Livery.com" },
      { words: "2 words", avg_bidders: 7.0, example: "AgentIndex.com" },
      { words: "3 words", avg_bidders: 1.5, example: "CleanTechCamp.com" },
      { words: "4+ words", avg_bidders: 0.9, example: "BabyEagleIsMissing.com" }
    ],
    by_length: [
      { range: "<=5 chars", avg_bidders: 11.2, pct_low_comp: 3.7 },
      { range: "6-8 chars", avg_bidders: 7.1, pct_low_comp: 27.7 },
      { range: "9-12 chars", avg_bidders: 6.6, pct_low_comp: 35.1 },
      { range: "13-15 chars", avg_bidders: 2.4, pct_low_comp: 47.4 },
      { range: "16-20 chars", avg_bidders: 1.6, pct_low_comp: 42.9 },
      { range: "21+ chars", avg_bidders: 2.1, pct_low_comp: 42.9 }
    ],
    by_feature: [
      { feature: "Hyphenated", avg_bidders: 1.4, multiplier: "4.4x less" },
      { feature: "No hyphens", avg_bidders: 6.2, multiplier: "baseline" },
      { feature: "With numbers", avg_bidders: 3.0, multiplier: "2x less" },
      { feature: "No numbers", avg_bidders: 5.9, multiplier: "baseline" }
    ],
    by_day: [
      { day: "Monday", avg_bidders: 8.15, verdict: "AVOID" },
      { day: "Tuesday", avg_bidders: 5.20, verdict: "OK" },
      { day: "Wednesday", avg_bidders: 4.80, verdict: "OK" },
      { day: "Thursday", avg_bidders: 4.60, verdict: "GOOD" },
      { day: "Friday", avg_bidders: 4.35, verdict: "OPTIMAL" }
    ],
    bidder_types: [
      { type: "Spray (floor $59)", pct_bids: 46, pct_wins: 0 },
      { type: "Manual selective", pct_bids: 34, pct_wins: 30 },
      { type: "Proxy (hidden max)", pct_bids: 20, pct_wins: 70 }
    ]
  },

  // DR-SEGMENTED ROI
  dr_roi: [
    { range: "0-19", acq_cost: 59, flip_price: "50-100", flip_rate: 5, ev: -56, roi: -95, verdict: "SKIP" },
    { range: "20-29", acq_cost: 72, flip_price: "200-400", flip_rate: 25, ev: 15, roi: 21, verdict: "BUY" },
    { range: "30-39", acq_cost: 243, flip_price: "500-2K", flip_rate: 30, ev: 117, roi: 48, verdict: "MONITOR" },
    { range: "40-49", acq_cost: 4199, flip_price: "2K-5K", flip_rate: 35, ev: -2599, roi: -62, verdict: "SKIP" },
    { range: "50+", acq_cost: 13509, flip_price: "5K-20K", flip_rate: 40, ev: -1659, roi: -44, verdict: "SKIP" }
  ],

  // ECONOMICS
  economics: {
    cost_per_domain: 60,
    clean_catch_cost: 59,
    auction_cost_median: 78,
    clean_catch_rate: 95.6,
    stacked_catch_rate: 63.5,
    breakeven: [
      { flip_price: 200, rate: 32.1 },
      { flip_price: 300, rate: 21.5 },
      { flip_price: 500, rate: 13.0 },
      { flip_price: 750, rate: 8.7 },
      { flip_price: 1000, rate: 6.5 }
    ],
    monthly_cost_10: 609,
    monthly_cost_20: 1140,
    minimum_viable_flip_rate: 9,
    working_capital_required: 1770,
    budget_remaining: 5337
  },

  // SWEET SPOT PROFILE
  sweet_spot: {
    dr_range: "20-34",
    word_count: "3-4",
    min_length: 13,
    prefer_hyphenated: true,
    prefer_descriptive: true,
    avoid: ["single-word .com", "<=6 chars", ".org", "DR 40+", "Monday auctions"],
    target_keywords: ["tech", "health", "finance", "education", "digital", "smart", "bio"],
    examples: [
      "SmartTechEnergy.net",
      "best-tech-reviews.com",
      "CleanTechCamp.com",
      "AliveTechies.com",
      "SystechUniversity.com",
      "ArabBiotech.net"
    ]
  },

  // TWO-LANE STRATEGY
  lanes: {
    a: {
      name: "Sweet Spot Catcher",
      target: "DR 20-34, 3+ words, 13+ chars",
      volume: "10-20/month",
      cost: "$590-$1,140/month",
      expected_clean: "95.6%",
      gate: "Ahrefs spam check only"
    },
    b: {
      name: "Whale Hunter",
      target: "DR 35+, RD 500+, editorial backlinks",
      volume: "1-3/month",
      cost: "$150-$500/month",
      expected_clean: "5-20%",
      gate: "Full 5-stage pipeline + manual review"
    }
  },

  // PRICE STRATEGY
  pricing: [
    { dr_range: "20-24", initial: 200, day60: 100, day90: "DROP" },
    { dr_range: "25-29", initial: 400, day60: 200, day90: 100 },
    { dr_range: "30-34", initial: 800, day60: 400, day90: 200 },
    { dr_range: "35+", initial: 1500, day60: 1000, day90: 500 }
  ],

  // 12-MONTH PROJECTIONS
  projections: [
    { scenario: "Conservative", backorders: 10, flip_rate: 15, flip_price: 300, breakeven: "Never", year1_pl: -1908 },
    { scenario: "Moderate", backorders: 10, flip_rate: 20, flip_price: 500, breakeven: "Month 8", year1_pl: 1780 },
    { scenario: "Optimistic", backorders: 20, flip_rate: 25, flip_price: 500, breakeven: "Month 6", year1_pl: 8820 }
  ],

  // FEED SOURCES
  feeds: [
    { name: "DropCatch CSV", domains_day: 3864, cost: "Free", quality: "High", priority: "P1", status: "LIVE" },
    { name: "Gname dropcatch", domains_day: "500-2K", cost: "Free", quality: "High", priority: "P1", status: "READY" },
    { name: "Dynadot closeout", domains_day: "1K-5K", cost: "Free", quality: "High", priority: "P1", status: "READY" },
    { name: "Whoxy drop list", domains_day: "166K+", cost: "Free", quality: "Low", priority: "P2", status: "PLANNED" },
    { name: "NameSilo auctions", domains_day: "500-2K", cost: "Free", quality: "Medium", priority: "P2", status: "PLANNED" },
    { name: "WhoisFreaks", domains_day: "200K+", cost: "$50/mo", quality: "Low", priority: "P3", status: "LIVE" },
    { name: "CatchDoms Pro", domains_day: "50K+", cost: "$49/mo", quality: "Medium", priority: "P3", status: "OPTIONAL" }
  ],

  // 10 RULES
  rules: {
    catching: [
      "ONLY target DR 20-34. DR 0-19 has no flip market. DR 40+ has institutional competition.",
      "Prefer 3-4 word descriptive names. 8.7x less competition than single-word brands.",
      "Prefer 13+ character domains. 47% have 0-1 bidders vs 3.7% for <=5 chars.",
      "Love hyphens. 4.4x lower competition.",
      "Avoid short single-word .coms. 91% of high-competition auctions.",
      "Stack backorders. DropCatch ($59) + Dynadot ($10.99) = 63.5% catch rate.",
      "Bid on Fridays. 1.87x less competition than Mondays.",
      "Walk from 6+ bidder auctions. Median settles at $111+.",
      "Cap auction spend at $150. Above this, proxy bidders dominate.",
      "List on Day 1, not Day 30."
    ],
    selling: [
      "Price by DR band. DR 20-29 = $200-$400. DR 30-34 = $500-$1,000.",
      "Cut prices at 60 days. 50% reduction if zero inquiries.",
      "Kill at 90 days. Don't renew domains with zero interest.",
      "Target content builders, not brand buyers.",
      "Multi-platform distribution: Afternic + Sedo + Dan.com."
    ]
  },

  // KILL SIGNALS
  kill_signals: [
    "Zero inquiries after 30 days + 50% price cut",
    "Flip rate confirmed < 8% after 20+ catches",
    "Budget drops below $500",
    "3 consecutive domains auction above $150"
  ]
};

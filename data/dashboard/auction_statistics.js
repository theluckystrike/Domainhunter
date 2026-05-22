// Auction Statistics — Sprint 46 Validation (CORRECTED with full 6,746-auction pull)
// Last updated: 2026-05-22
window.DH_AUCTION_STATS = {
  source: "DropCatch API v2 — FULL PULL",
  date: "2026-05-22",

  // FULL DATASET (6,746 Dropped auctions via Types[]=Dropped&sort=EndTimeAsc)
  total_dropped: 6746,
  total_mixed: 1425,

  by_type: {
    Dropped: {
      count_full: 6746,
      count_sample: 261,
      pct_zero_bidders_full: 95.6,
      pct_zero_one_bidders_sample: 33.72,
      median_price: 16,
      mean_price_full: 23.13,
      mean_price_sample: 185.95,
      mean_bidders_full: 0.27,
      mean_bidders_sample: 5.65,
      note: "Sample was biased by HighBidDesc sort. Full pull is the truth."
    },
    PreRelease: {
      count: 244,
      pct_zero_one_bidders: 98.77,
      median_price: 13,
      mean_bidders: 0.14
    },
    PrivateSeller: {
      count: 920,
      pct_zero_one_bidders: 94.13,
      median_price: 59,
      mean_bidders: 0.21
    }
  },

  // FULL PULL bidder distribution (6,746 Dropped auctions)
  bidder_distribution_full: {
    zero: 6452,
    one: 6,
    two_five: 224,
    six_ten: 33,
    eleven_twentyfive: 17,
    twentysix_fifty: 10,
    fiftyone_plus: 4
  },

  // SAMPLE bidder distribution (261 Dropped from mixed pull — BIASED)
  bidder_distribution_sample: {
    zero: 88,
    one: 0,
    two_three: 88,
    four_five: 30,
    six_ten: 25,
    eleven_plus: 30
  },

  // PRICE DISTRIBUTION (full pull)
  price_distribution: {
    tier_10_50: { count: 6513, pct: 96.5 },
    tier_50_69: { count: 174, pct: 2.6 },
    tier_69_100: { count: 28, pct: 0.4 },
    tier_100_250: { count: 18, pct: 0.3 },
    tier_250_500: { count: 7, pct: 0.1 },
    tier_1000_5000: { count: 4, pct: 0.1 },
    tier_5000_plus: { count: 2, pct: 0.0 }
  },

  // AUCTION PRICING by bidder count (261 sample — only contested auctions)
  auction_pricing: [
    { bidders: "2", count: 88, median: 64, mean: 63, max: 304 },
    { bidders: "3", count: 35, median: 60, mean: 61, max: 350 },
    { bidders: "4", count: 18, median: 64, mean: 83, max: 393 },
    { bidders: "5", count: 20, median: 95, mean: 101, max: 300 },
    { bidders: "6", count: 15, median: 111, mean: 146, max: 480 },
    { bidders: "7", count: 8, median: 111, mean: 95, max: 160 },
    { bidders: "8+", count: 46, median: 88, mean: 650, max: 1016 }
  ],

  key_finding: "95.6% of ALL 6,746 Dropped auctions have ZERO bidders (full API pull). Only 294 (4.4%) have any competition. The prior 261-sample was biased by HighBidDesc sort.",
  confirmed: true,

  price_stats: {
    dropped_full: {
      min: 13,
      max: 15500,
      median: 16,
      mean: 23.13,
      total_volume: 156022
    },
    dropped_sample: {
      min: 13,
      max: 15500,
      median: 20,
      mean: 185.95,
      at_59: 6,
      pct_at_59: 2.3
    }
  },

  our_positions: [
    {
      domain: "EnCognitive.com",
      auction_id: 7908358,
      high_bid: 65,
      our_max: 175,
      winning: true,
      bidders: 6,
      end_time: "2026-05-26T19:00:00Z"
    }
  ],

  // COMPETITION SIGNALS
  competition_signals: {
    strongest: "word_count",
    word_count: { one_word: 7.8, two_word: 7.0, three_word: 1.5, four_plus: 0.9 },
    hyphens: { with: 1.4, without: 6.2, multiplier: 4.4 },
    length: { under_6: 11.2, chars_13_15: 2.4, sweet_spot_pct: 47.4 },
    day_of_week: { monday: 8.15, friday: 4.35, multiplier: 1.87 }
  },

  // BIDDER BEHAVIOR (from 521 bid histories)
  bidder_behavior: {
    total_bids_analyzed: 521,
    manual_pct: 80,
    proxy_pct: 20,
    proxy_win_pct: 70,
    spray_bidders_pct: 46,
    real_competition_discount: 0.3,
    peak_hour_utc: 17,
    avg_proxy_bid: 2056,
    avg_manual_bid: 596
  },

  validation: {
    sample_size_full: 6746,
    sample_size_mixed: 1425,
    confidence_level: "95%",
    confidence_interval_full: [94.8, 96.4],
    confidence_interval_sample: [27.98, 39.45],
    note: "Full pull CI is much tighter due to 25.8x larger sample"
  }
};

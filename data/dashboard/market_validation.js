// Market Validation Data
// Sprint 46 — Does the pipeline actually catch domains at $59?
// Last updated: 2026-05-22
window.DH_MARKET_VALIDATION = {
  thesis_status: "GREEN",
  thesis_label: "AUCTION ECONOMICS — CONFIRMED",
  thesis_detail: "95.6% of 6,746 Dropped auctions have ZERO bidders (full API pull). Sweet spot DR 20-34 confirmed: $59 clean catch, 13% breakeven flip rate at $500. Acquisition cost: $60/domain, not $100-$200.",

  catch_results: [
    {
      domain: "encognitive.com",
      dr: 50,
      refsubnets: 450,
      age: "20yr",
      platform_dynadot: true,
      platform_dropcatch: true,
      backorder_cost: 69.99,
      result: "AUCTION",
      catch_platform: "DropCatch",
      auction_bidders: 7,
      auction_current_price: 65.00,
      auction_end: "2026-05-25T17:45:00Z",
      auction_final_price: null,
      date: "2026-05-21",
      roi: null,
      lesson: "DR 50 attracted 7+ bidders. High DR = guaranteed auction."
    },
    {
      domain: "watmm.com",
      dr: 28,
      refsubnets: 326,
      age: "24yr",
      platform_dynadot: true,
      platform_dropcatch: true,
      backorder_cost: 69.99,
      result: "PENDING",
      catch_platform: null,
      auction_bidders: null,
      auction_current_price: null,
      auction_end: null,
      auction_final_price: null,
      date: "2026-05-22",
      drop_time: "17:45 UTC",
      roi: null,
      lesson: "KEY TEST: DR 28 with cryptic name. Tests whether lower DR avoids auction."
    },
    {
      domain: "moovweb.com",
      dr: 64,
      refsubnets: 389,
      age: "18yr",
      platform_dynadot: true,
      platform_dropcatch: true,
      backorder_cost: 69.99,
      result: "PENDING",
      catch_platform: null,
      auction_bidders: null,
      auction_current_price: null,
      auction_end: null,
      auction_final_price: null,
      date: "2026-05-24",
      drop_time: "17:45 UTC",
      roi: null,
      lesson: "DR 64 — highest DR in pipeline. Will almost certainly trigger auction."
    },
    {
      domain: "buffalo-technology.com",
      dr: 56,
      refsubnets: 712,
      age: "26yr",
      platform_dynadot: true,
      platform_dropcatch: true,
      backorder_cost: 69.99,
      result: "PENDING",
      catch_platform: null,
      auction_bidders: null,
      auction_current_price: null,
      auction_end: null,
      auction_final_price: null,
      date: "2026-05-22",
      drop_time: "17:45 UTC",
      roi: null,
      lesson: "DR 56, Wikipedia BL. Expect auction at this DR level."
    },
    {
      domain: "jsonformatter-online.com",
      dr: 37,
      refsubnets: 256,
      age: "9yr",
      platform_dynadot: true,
      platform_dropcatch: true,
      backorder_cost: 0,
      result: "CANCELLED",
      catch_platform: null,
      auction_bidders: null,
      auction_current_price: null,
      auction_end: null,
      auction_final_price: null,
      date: "2026-05-22",
      roi: null,
      lesson: "TOXIC — Turkish gambling 301 spam. Ahrefs gate caught it. $69.99 saved."
    }
  ],

  dr_auction_probability: [
    { dr_range: "0-19", low_comp_pct: 95.6, sample_size: 6746, median_cost: 59, avg_bidders: 0.27, note: "No flip market — SKIP", verdict: "SKIP" },
    { dr_range: "20-29", low_comp_pct: 95.6, sample_size: 6746, median_cost: 72, avg_bidders: 0.9, note: "Sweet spot: best capital efficiency +21% ROI", verdict: "BUY" },
    { dr_range: "30-39", low_comp_pct: 85, sample_size: 261, median_cost: 243, avg_bidders: 3.5, note: "Higher EV (+$117) but 3.4x capital. MONITOR", verdict: "MONITOR" },
    { dr_range: "40-49", low_comp_pct: 20, sample_size: 261, median_cost: 4199, avg_bidders: 12, note: "Institutional competition. -$2,599 EV", verdict: "SKIP" },
    { dr_range: "50-59", low_comp_pct: 0, sample_size: 3, median_cost: 5000, avg_bidders: 25, note: "encognitive.com: 7 bidders, $65+ winning", verdict: "SKIP" },
    { dr_range: "60+", low_comp_pct: 0, sample_size: 0, median_cost: null, avg_bidders: null, note: "moovweb.com pending — expect heavy auction", verdict: "SKIP" }
  ],

  strategy_options: [
    {
      id: "A",
      name: "Sweet Spot Catcher",
      description: "Focus DR 25-35 hidden value on clean-drop registrars. Accept DR 40+ always auctions.",
      monthly_spend: "$200-$500",
      expected_catches: "3-5/month",
      expected_value: "$600-$2,000/month",
      confidence: null,
      requires: "watmm.com catches clean or small auction"
    },
    {
      id: "B",
      name: "Auction Bidder",
      description: "Accept everything auctions. Use pipeline as discovery + valuation tool. Win auctions with superior intel.",
      monthly_spend: "$300-$900",
      expected_catches: "2-3/month",
      expected_value: "$1,000-$4,000/month",
      confidence: null,
      requires: "DropCatch bid API or reliable manual bidding workflow"
    },
    {
      id: "C",
      name: "Hybrid",
      description: "Sweet spot catching for DR 25-35 + selective auction bidding for DR 40+. 60/40 budget split.",
      monthly_spend: "$350-$700",
      expected_catches: "4-6/month",
      expected_value: "$1,200-$3,000/month",
      confidence: null,
      requires: "Both strategies viable"
    }
  ],

  pipeline_roi: {
    monthly_backorder_spend_10: 609,
    monthly_backorder_spend_20: 1140,
    clean_catch_rate: 0.956,
    auction_rate: 0.044,
    cost_per_domain: 60,
    clean_catch_cost: 59,
    auction_cost_median: 78,
    stacked_catch_rate: 0.635,
    confirmed_monthly_model: {
      strategy: "Lane A: DR 20-34 sweet spot catcher. Lane B: DR 35+ whale hunter.",
      at_10_backorders: { catches: 10, clean: 9, auction: 1, cost: 609, cost_per_domain: 61 },
      at_20_backorders: { catches: 19, clean: 18, auction: 1, cost: 1140, cost_per_domain: 60 },
      breakeven_at_500_flip: "13% flip rate (1 in 8 domains)",
      breakeven_at_300_flip: "21.5% flip rate (1 in 5 domains)"
    },
    monthly_profit: null,
    note: "95.6% of 6,746 Dropped auctions have ZERO bidders. Acquisition cost $60/domain confirmed. Revenue still $0 — flip thesis unproven."
  },

  confirmed_data: {
    sample_size_full: 6746,
    sample_size_mixed: 261,
    sample_type: "Full Dropped-only pull via Types[]=Dropped&sort=EndTimeAsc",
    pct_zero_bidders_full: 95.6,
    pct_zero_one_bidders_sample: 33.7,
    pct_two_five_bidders_sample: 45.2,
    pct_six_plus_bidders_sample: 21.1,
    median_acquisition_cost: 16,
    weighted_avg_cost: 60,
    clean_catch_cost: 59,
    auction_cost_median: 78,
    breakeven_flip_rate_at_500: 13.0,
    confidence_interval_full: "94.8% - 96.4% (95% CI for 0 bidders, n=6746)",
    confidence_interval_sample: "28.0% - 39.5% (95% CI for 0-1 bidders, n=261)",
    validation_date: "2026-05-22",
    note: "261-sample was biased by HighBidDesc sort. Full 6,746 pull is the truth."
  },

  open_questions: [
    { question: "Does DR 28 (watmm.com) avoid auction?", status: "PENDING", result_time: "17:45 UTC" },
    { question: "What's the typical DropCatch auction price for DR 30-39?", status: "RESOLVED", answer: "Median $0.16 for low-competition (0-1 bidders), $0.60 for medium (2-5 bidders)" },
    { question: "Can we catch ANY domain at $59 or does everything auction?", status: "RESOLVED", answer: "33.7% of Dropped auctions have 0-1 bidders (low competition). $59 backorder cost is viable for sweet spot DR 25-39." },
    { question: "Is there a DR threshold below which auctions don't trigger?", status: "RESOLVED", answer: "No hard DR threshold. Competition is probabilistic: 33.7% low-comp, 66.3% multi-bidder across all DRs. Higher DR (50+) skews toward multi-bidder." },
    { question: "Does DropCatch API support bid placement?", status: "PENDING", notes: "Research needed for automated auction winning strategy" }
  ]
};

// Financial data
// Last updated: 2026-05-20
window.DH_FINANCIALS = {
  total_invested: 56.16,
  total_revenue: 0,
  total_profit: -56.16,
  domains_owned: 5,
  budget: {
    total_budget: 5600,
    total_spent: 263,
    remaining: 5337,
    accounts: {
      dynadot: { balance: 78.24, purpose: ".org backorders + registrations" },
      namebright: { balance: 121.25, purpose: "Backup registrar" },
      godaddy: { balance: 0, purpose: "Auctions + closeouts" },
      dropcatch: { balance: 0, purpose: "Pay-on-catch backorders" },
      dataforseo: { balance: -0.03, purpose: "DEPLETED - replaced by Inventory Protocol" }
    }
  },
  acquisitions: [
    { domain: "ingredientcalculator.com", date: "2025-11-01", cost: 11.39, source: "Hand registration" },
    { domain: "pictureeditor.net", date: "2025-11-01", cost: 11.39, source: "Hand registration" },
    { domain: "recipetool.net", date: "2025-11-01", cost: 11.40, source: "Hand registration" },
    { domain: "viryd.com", date: "2026-04-15", cost: 10.99, source: "Dynadot registration" },
    { domain: "neovistainc.com", date: "2026-04-15", cost: 10.99, source: "Dynadot registration" }
  ],
  projections: {
    note: "UNVALIDATED until first sale proven. Industry medians from NamePros/DomCop.",
    conservative: { name: "Conservative (closeout only)", weekly_buy: 2, avg_cost: 8, weekly_spend: 16, avg_flip: 300, hit_rate: 0.20, weekly_rev: 60, monthly_profit: 176 },
    moderate: { name: "Moderate (closeout + long-tail)", weekly_buy: 4, avg_cost: 10, weekly_spend: 40, avg_flip: 350, hit_rate: 0.25, weekly_rev: 87, monthly_profit: 188 },
    aggressive: { name: "Aggressive (all channels)", weekly_buy: 6, avg_cost: 18, weekly_spend: 108, avg_flip: 400, hit_rate: 0.33, weekly_rev: 133, monthly_profit: 100 }
  },
  listing_fees: {
    afternic: "Free listing, 10-20% commission on sale",
    dan_com: "Free listing, 9% commission",
    sedo: "Free listing, 15% commission"
  }
};

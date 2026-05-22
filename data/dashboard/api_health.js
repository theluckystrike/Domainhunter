// API integration health status
// Last updated: 2026-05-21 (Sprint 43 — live API tests)
window.DH_API_HEALTH = [
  {
    name: "GoDaddy Inventory Protocol",
    status: "working",
    detail: "41 free feeds, no auth required. Primary data source. 309K closeouts daily. Whale scan: 370K records across 5 feeds.",
    last_checked: "2026-05-21",
    endpoint: "inventory.auctions.godaddy.com",
    cost: "Free"
  },
  {
    name: "RDAP/WHOIS monitoring",
    status: "working",
    detail: "All 11 pipeline targets STABLE. 632 live RDAP queries ran in 15.5 min (5 concurrent). Zero EPP changes. decoder.com 5 days. sunnyray.org/globalgeopark.org still autoRenewPeriod.",
    last_checked: "2026-05-21",
    endpoint: "rdap.verisign.com + rdap.org",
    cost: "Free"
  },
  {
    name: "DropCatch API (backorder)",
    status: "working",
    detail: "CONFIRMED LIVE: Placed and cancelled real backorder on test domain. Account 387137 fully operational. NO ID verification blocker (false alarm). 131K dropping domains in today's feed. JWT auth OK.",
    last_checked: "2026-05-21",
    endpoint: "api.dropcatch.com",
    cost: "$59/catch (standard), $13/catch (discount)"
  },
  {
    name: "Dynadot API (backorder)",
    status: "working",
    detail: "CONFIRMED LIVE: Placed real backorder on test domain. Balance: $78.24 (7 backorders). Accepts pendingDelete domains only. sunnyray.org rejected (autoRenewPeriod, not pendingDelete).",
    last_checked: "2026-05-21",
    endpoint: "api.dynadot.com/api3.json",
    cost: "$10.99/backorder catch"
  },
  {
    name: "DeepSeek Validator",
    status: "working",
    detail: "NEW: AI domain validation at $0.001/domain. 19/19 candidates validated. Checks brandability, TM risk, niche match, buildability. API key in .env.",
    last_checked: "2026-05-21",
    endpoint: "api.deepseek.com/chat/completions",
    cost: "$0.001/domain"
  },
  {
    name: "ntfy push alerts",
    status: "working",
    detail: "Closeout monitor, whale alerts (priority 5), RDAP change alerts, pipeline summary notifications all functional.",
    last_checked: "2026-05-21",
    endpoint: "ntfy.sh/dh-revenant-alerts",
    cost: "Free"
  },
  {
    name: "GoDaddy Auctions API (bidding)",
    status: "blocked",
    detail: "403 USER_NOT_ALLOWED. Key has zero scopes. FIX: Regenerate at developer.godaddy.com/keys → Production → Aftermarket + Domains scopes.",
    last_checked: "2026-05-21",
    endpoint: "api.godaddy.com/v1/aftermarket",
    cost: "N/A"
  },
  {
    name: "GoDaddy Closeout BuyNow API",
    status: "blocked",
    detail: "Same root cause as Auctions API — key scope issue. Will unblock when key is regenerated.",
    last_checked: "2026-05-21",
    endpoint: "api.godaddy.com/v1/aftermarket/listings",
    cost: "$5-$50/domain"
  },
  {
    name: "DataForSEO",
    status: "restricted",
    detail: "Balance: $49.97. BUT Backlinks API requires $100/mo subscription (not activated). Labs API works ($0.06 spent on whale enrichment). Recommendation: use free feed Majestic data instead.",
    last_checked: "2026-05-21",
    endpoint: "api.dataforseo.com",
    cost: "$100/mo subscription required"
  },
  {
    name: "Dynadot Auction API",
    status: "restricted",
    detail: "Account restricted from auction APIs. Low priority — backorder API works.",
    last_checked: "2026-05-21",
    endpoint: "api.dynadot.com/api3.json (auction commands)",
    cost: "Varies"
  }
];

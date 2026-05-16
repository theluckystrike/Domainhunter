# Expired & Dropping Domain APIs -- Research Report

**Date:** 2026-05-02
**Goal:** Find .com domains that are EXPIRING SOON or JUST DROPPED via programmatic APIs

---

## TL;DR Comparison Matrix

| Service | Has API? | Free Tier | .com Filter | Drop/Expire Data | Backlink Data | Price Entry Point |
|---------|----------|-----------|-------------|-------------------|---------------|-------------------|
| **WhoisFreaks** | YES (REST) | 500 credits | YES (JSON endpoint) | YES (daily CSV+JSON) | YES ($234/mo tier) | $70/mo (no WHOIS) |
| **ExpiredDomains.net** | NO | N/A | N/A | Web only | Web only | Free (web) |
| **WhoisXML API** | YES (file feed) | No | YES | YES (daily feeds) | No | Quote-based (~$100+/mo) |
| **Domainr/Fastly** | YES (REST) | No | N/A | NO (availability only) | No | Quote-based |
| **GoDaddy Auctions** | YES (REST) | Free (20K calls/mo) | YES | YES (auction listings) | No | Free API + $4.99/yr membership |
| **Whoxy** | YES (file download) | No | YES | YES (daily files) | No | $95/mo (expiring) |
| **Dynadot** | YES (REST) | Free | YES | YES (auctions+closeouts) | No | Free API, pay per domain |
| **CatchDoms** | YES (REST) | No | YES | YES (scored+filtered) | YES | 468 EUR/yr |
| **DropCatch** | YES (REST) | No | YES | Backorder only | No | $10.99/domain |
| **NameSilo** | Partial | Free | Limited | Marketplace only | No | Free API, pay per domain |

---

## 1. WhoisFreaks API -- BEST FOR PROGRAMMATIC BULK ACCESS

**Verdict:** The strongest general-purpose expired domains API. Daily feeds, JSON with TLD filtering, WHOIS + backlinks.

### Base URL
```
https://api.whoisfreaks.com/v3/
```

### Authentication
- **Method:** API Key as query parameter
- **Parameter:** `apiKey=YOUR_API_KEY`
- **Obtain:** Register at https://billing.whoisfreaks.com/

### Endpoints

#### 1a. Expiring Domains (CSV with WHOIS)
```
GET /expiring-domains?apiKey=YOUR_KEY
GET /expiring-domains?apiKey=YOUR_KEY&date=2026-05-02
```

#### 1b. Expiring Domains (CSV without WHOIS)
```
GET /expiring-domains?apiKey=YOUR_KEY&whois=false
GET /expiring-domains?apiKey=YOUR_KEY&whois=false&date=2026-05-02
```

#### 1c. Expiring Domains (Cleaned WHOIS -- no REDACTED entries)
```
GET /expiring-domains-cleaned?apiKey=YOUR_KEY
GET /expiring-domains-cleaned?apiKey=YOUR_KEY&date=2026-05-02
```

#### 1d. Dropped Domains (CSV with WHOIS)
```
GET /dropped-domains?apiKey=YOUR_KEY&whois=true
GET /dropped-domains?apiKey=YOUR_KEY&whois=true&date=2026-05-02
```

#### 1e. Dropped Domains (CSV without WHOIS)
```
GET /dropped-domains?apiKey=YOUR_KEY&whois=false
```

#### 1f. Dropped Domains (JSON -- SUPPORTS TLD FILTERING)
```
GET /dropped-domains-json?apiKey=YOUR_KEY
GET /dropped-domains-json?apiKey=YOUR_KEY&tlds=com
GET /dropped-domains-json?apiKey=YOUR_KEY&tlds=com,net&date=2026-05-02
```

### Example curl Commands
```bash
# Get today's dropped .com domains as JSON
curl "https://api.whoisfreaks.com/v3/dropped-domains-json?apiKey=YOUR_KEY&tlds=com"

# Get expiring domains with WHOIS as CSV
curl "https://api.whoisfreaks.com/v3/expiring-domains?apiKey=YOUR_KEY&date=2026-05-02" -o expiring.csv

# Get dropped domains without WHOIS as CSV
curl "https://api.whoisfreaks.com/v3/dropped-domains?apiKey=YOUR_KEY&whois=false" -o dropped.csv
```

### Data Returned
| Field | Available |
|-------|-----------|
| Domain name | YES |
| Create date | YES |
| Update date | YES |
| Expiry date | YES |
| Registrar info | YES (WHOIS tiers) |
| Registrant contact | YES (WHOIS tiers) |
| Admin/Tech/Billing contacts | YES (WHOIS tiers) |
| Name servers | YES (WHOIS tiers) |
| Domain status flags | YES (WHOIS tiers) |
| Backlink count | YES ($234/mo tier) |
| Outgoing links | YES ($234/mo tier) |
| Previous traffic | NO |
| Domain age | Derivable from create_date |

### TLD Filtering
- **JSON endpoint only** (`/dropped-domains-json`): Use `tlds=com` parameter
- **CSV endpoints:** No TLD filter -- returns all TLDs, filter locally

### Pricing
| Plan | Price/mo | Billed Yearly | Details |
|------|----------|---------------|---------|
| **Expired w/o WHOIS** | $70 | $59/mo | Domain names only (CSV) |
| **Expired w/ WHOIS** | $100 | $84/mo | + registrant, registrar, dates, NS |
| **Expired w/ Cleaned WHOIS** | $200 | $167/mo | WHOIS minus REDACTED entries |
| **Dropped w/o WHOIS** | $100 | $84/mo | Recently dropped domains |
| **Dropped w/ WHOIS** | $150 | $125/mo | + full WHOIS |
| **Dropped w/ WHOIS + Backlinks** | $234 | $209/mo | + backlink counts |
| **Dropped w/ Backlinks Only** | $200 | $167/mo | Domain + backlink counts only |

### Free Tier
- 500 API credits on signup (for WHOIS lookups, NOT the data feed subscriptions)
- Data feed subscriptions require paid plans

### Rate Limits
- API credits measured per requests-per-minute (RPM)
- 50K credit tier: 80 RPM (live), 20 RPM (bulk), 10 RPM (historical/reverse)
- Enterprise: custom RPM

### Update Schedule
- Daily at 03:00 UTC

---

## 2. ExpiredDomains.net -- NO API

**Verdict:** No API exists. Period. Web-only interface.

### Official Statement
ExpiredDomains.net FAQ explicitly states: "Can I have access to your API? No." There is no public or private API, free or paid.

### What It Offers (Web Only)
- Massive database of expired, deleted, and pending-delete domains
- Filters by TLD, age, backlinks (Majestic), Archive.org snapshots, etc.
- Free to use via web interface (account required)
- Manual CSV export

### Programmatic Alternatives
1. **Apify Scraper:** Third-party scraping actor at https://apify.com/easyapi/expireddomains-net-scraper/api
   - Sends HTTP POST to Apify API
   - Apify pricing applies (~$49/mo for basic plan)
   - Legal risk: violates ExpiredDomains.net ToS
2. **ScrapingBee Scraper:** https://www.scrapingbee.com/scrapers/expireddomains-scraper-api/

### Recommendation
Skip this for programmatic use. Use WhoisFreaks or CatchDoms instead.

---

## 3. WhoisXML API -- ENTERPRISE-GRADE DATA FEEDS

**Verdict:** High-quality data but enterprise pricing. File-based downloads, not a REST query API.

### Access Method
**File download service** (not a traditional REST API for querying)

### Base URLs
```
HTTPS: https://newly-registered-domains.whoisxmlapi.com/datafeeds/
FTP:   ftp://datafeeds.whoisxmlapi.com:21210/
FTPS:  ftps://datafeeds.whoisxmlapi.com:21210/  (explicit TLS)
```

### Authentication
- **HTTPS:** API key as username AND password (HTTP Basic Auth)
- **FTP/FTPS:** Username `user`, Password = your API key

### Data Structure
Files organized in directories:
```
Newly_Registered_Domains_2.0/[subscription_tier]/daily/[YYYY-MM-DD]/
```
Files are `.csv.gz` or `.json.gz` (compressed)

### Example curl
```bash
# Download daily just-expired domains feed
curl -u "YOUR_API_KEY:YOUR_API_KEY" \
  "https://newly-registered-domains.whoisxmlapi.com/datafeeds/Newly_Registered_Domains_2.0/basic/daily/2026-05-02/" \
  -o expired-2026-05-02.csv.gz
```

### Supplementary REST API: Domain Availability Check
```
GET https://domain-availability.whoisxmlapi.com/api/v1?apiKey=YOUR_KEY&domainName=example.com&credits=DA
```

### Domain Availability Example curl
```bash
curl "https://domain-availability.whoisxmlapi.com/api/v1?apiKey=YOUR_KEY&domainName=example.com&credits=DA&outputFormat=JSON"
```

### Data Returned
| Field | Basic | Professional+ |
|-------|-------|---------------|
| Domain name | YES | YES |
| Registration date | YES | YES |
| Expiration date | YES | YES |
| Reason (expired/registered) | YES | YES |
| WHOIS (90+ fields) | NO | YES |

### TLD Filtering
- Filter locally after download (files organized by data, not TLD)
- Domain Availability API: checks single domain at a time

### Pricing
- **Quote-based** -- must request pricing
- 5 tiers: Lite, Basic, Professional, Enterprise, Ultimate
- 3 license types: Educational, Internal Business, Commercial
- Lite tier does NOT include expired domains data
- **Free tier:** 500 WHOIS lookups (for the separate WHOIS API), 100 domain availability checks

### Rate Limits
- Domain Availability API: **30 requests/second**
- Data feed downloads: not rate-limited (daily file access)

### Update Schedule
- Daily at 02:00 UTC
- Covers 1M+ records daily across all TLDs

---

## 4. Domainr / Fastly Domain Research API

**Verdict:** NOT useful for expired domain hunting. This is a domain SUGGESTION + AVAILABILITY tool, not an expired domain feed.

### Status
- Original Domainr API: **DEPRECATED** (acquired by Fastly in 2023)
- Replacement: Fastly Domain Research API

### Base URLs
```
# Legacy (deprecated, still functional)
https://api.domainr.com/v2/
https://domainr.p.rapidapi.com/v2/   (via RapidAPI)

# Current (Fastly)
https://api.fastly.com/domain-management/v1/tools/
```

### Endpoints

#### Suggest (domain name ideas)
```
GET /domain-management/v1/tools/suggest?query=startup
```
Parameters: `query` (required), `defaults`, `keywords`, `location`, `vendor`

#### Status (availability check)
```
GET /domain-management/v1/tools/status?domain=example.com
GET /domain-management/v1/tools/status?domain=example.com&scope=estimate
```

### Authentication
- **Legacy Domainr:** `mashape-key` (RapidAPI) or `client_id` query param
- **Fastly:** Fastly API token (must enable Domain Research API product in account)

### Example curl (Legacy)
```bash
curl "https://domainr.p.rapidapi.com/v2/search?query=startup" \
  -H "X-RapidAPI-Key: YOUR_RAPIDAPI_KEY"
```

### Why It's NOT Useful for This Use Case
- No expired domain feed or list
- Single-domain availability checks only
- Status endpoint accepts ONE domain per request
- No backlink, age, or traffic data
- No drop date information
- 30-second timeout per request

### Pricing
- Fastly: quote-based, no public pricing
- RapidAPI legacy: varies by plan

### Recommendation
Skip for expired domain hunting. Only useful if you already have a candidate domain name and want to check if it's available.

---

## 5. GoDaddy Auctions API

**Verdict:** Free API access but RESTRICTED to existing API-approved accounts. New users may be blocked. Covers GoDaddy expired domain auctions only.

### Base URLs
```
Production: https://api.godaddy.com
OTE (test): https://api.ote-godaddy.com
```

### Authentication
```
Authorization: sso-key API_KEY:API_SECRET
```
- Obtain keys at https://developer.godaddy.com/keys
- First key = test (OTE), second key = production

### Endpoints (from Swagger spec)

#### Auctions API
```
GET /v1/auctions                    # List current auctions
GET /v1/auctions/{auctionId}        # Get auction details
```

#### Aftermarket API
```
GET /v1/aftermarket/listings        # List aftermarket domains
POST /v1/aftermarket/listings       # Create listing
```

### Example curl
```bash
# List active auctions
curl -X GET "https://api.godaddy.com/v1/auctions" \
  -H "Authorization: sso-key YOUR_KEY:YOUR_SECRET" \
  -H "Accept: application/json"

# Check domain availability
curl -X GET "https://api.godaddy.com/v1/domains/available?domain=example.com" \
  -H "Authorization: sso-key YOUR_KEY:YOUR_SECRET"
```

### Data Returned
- Domain name
- Current bid / price
- Auction end date
- Auction type (expired, closeout, user-listed)
- Domain age (limited)
- No backlink data

### TLD Filtering
- Likely filterable via query parameters (full Swagger spec at `/swagger/swagger_auctions.json`)

### Pricing
- **API access:** Free (20,000 calls/month with active domain in account)
- **Auctions membership:** $4.99/year
- **Domain purchase:** Market price (auction winning bid)

### Rate Limits
- 20,000 API calls/month (general domains API)
- Auction-specific limits undocumented

### CRITICAL LIMITATION
GoDaddy stopped granting NEW Auctions API access ~3 years ago. Existing users retain access. New users must email auctions@godaddy.com to request access (not guaranteed).

### Alternative: Inventory Download
```
https://inventory.auctions.godaddy.com/
```
Browse and download CSV inventory files directly (manual or scripted).

---

## 6. Additional APIs Discovered

### 6a. Whoxy -- DAILY FILE DOWNLOADS

**Verdict:** Solid data, file-download model (not REST query). Cheaper than WhoisFreaks for basic feeds.

#### Access Method
Subscription-based file downloads via direct URL (curl-compatible)

#### WHOIS Lookup API Base URL
```
https://api.whoxy.com/?key=YOUR_KEY&whois=example.com
```

#### Data Feeds (subscriptions, not per-query API)
| Feed | Monthly | Yearly |
|------|---------|--------|
| Expiring Domains (next 30 days + WHOIS) | $95/mo | $950/yr |
| Dropped/Deleted Domains + WHOIS | $195/mo | $1,950/yr |
| Newly Registered Domains + WHOIS | $495/mo | $4,950/yr |
| All-in-One | $695/mo | $6,950/yr |

#### Data Returned
- Domain name, create/update/expiry dates
- Full parsed WHOIS (registrant, admin, tech, billing contacts)
- Name servers, domain status
- ~5.86M deleted domains/month in feed
- 1,596 TLDs supported

#### TLD Filtering
- Filter locally after download (files contain all TLDs)

#### Example curl
```bash
# WHOIS lookup (per-query API, separate from feeds)
curl "https://api.whoxy.com/?key=YOUR_KEY&whois=coolstartup.com"

# Data feed files -- download URL provided after subscription
curl -u "USERNAME:PASSWORD" "https://[download-url-provided-after-signup]" -o dropped.csv
```

#### Free Tier
- None for data feeds
- WHOIS API: pay-per-query starting at $2/1,000 queries

---

### 6b. CatchDoms -- BEST FOR SCORED/FILTERED EXPIRED DOMAINS

**Verdict:** Excellent REST API with rich filtering. Returns scored domains with SEO metrics. Best for finding quality drops.

#### Base URL
```
https://catchdoms.com/api
```

#### Authentication
```
Authorization: Bearer YOUR_API_KEY
```
Obtain after Pro subscription at https://catchdoms.com/api-access

#### Endpoints

```
GET /api/domains                    # List domains (paginated, filterable)
GET /api/domains/{id}               # Single domain details
GET /api/user                       # Account info
```

#### Query Parameters (extensive filtering)
| Parameter | Description |
|-----------|-------------|
| `tld` | Filter by TLD (e.g., `com`) |
| `source` | Domain source/marketplace |
| `score_min` | Minimum quality score |
| `age_min` | Minimum domain age |
| `type` | Domain type |
| `has_backlinks` | Boolean -- has backlinks? |
| `has_gmb` | Has Google My Business listing? |
| `da_min` | Minimum Domain Authority |
| `rd_min` | Minimum Referring Domains |
| `tf_min` | Minimum Trust Flow (Majestic) |
| `cf_min` | Minimum Citation Flow (Majestic) |
| `language` | Content language |
| `contains` | Domain name contains string |
| `has_edu_gov` | Has .edu/.gov backlinks? |
| `categories` | Topic categories |
| `price_min` / `price_max` | Price range |
| `snapshots_min` | Min Archive.org snapshots |
| `per_page` | Results per page (default 50) |
| `page` | Page number |

#### Example curl
```bash
# Find high-quality .com drops with backlinks and min score of 50
curl "https://catchdoms.com/api/domains?tld=com&score_min=50&has_backlinks=1&da_min=20&per_page=50" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/json"

# Find .com domains with .edu/.gov backlinks
curl "https://catchdoms.com/api/domains?tld=com&has_edu_gov=1&tf_min=15" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/json"
```

#### Response Format
```json
{
  "data": [
    {
      "id": 12345,
      "domain": "example.com",
      "score": 72,
      "da": 35,
      "rd": 128,
      "tf": 22,
      "cf": 30,
      "backlinks": true,
      "age": 12,
      "snapshots": 45,
      "...": "..."
    }
  ],
  "links": { "next": "...", "prev": "..." },
  "meta": { "current_page": 1, "total": 500 }
}
```

#### Pricing
- **Pro:** 468 EUR/year (~$510 USD) -- 15 requests/minute
- **Authority:** Higher tier -- 60 requests/minute

#### Rate Limits
- Pro: 15 req/min
- Authority: 60 req/min
- 429 returned on limit; headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

#### Data Returned
Domain name, quality score, Domain Authority, referring domains, Trust Flow, Citation Flow, backlink presence, .edu/.gov links, Google My Business, Archive.org snapshots, domain age, language, categories, price -- **richest data of any API reviewed**.

---

### 6c. Dynadot API -- FREE API WITH AUCTION + CLOSEOUT ACCESS

**Verdict:** Free REST API with expired domain auctions and closeout inventory. Can bid and buy programmatically.

#### Base URLs
```
Production: https://api.dynadot.com/api3.json
Sandbox:    https://api-sandbox.dynadot.com/api3.json
```
(Also available as `.xml` for XML responses)

#### Authentication
```
key=YOUR_API_KEY  (query parameter)
```
Obtain from Dynadot account settings.

#### Key Endpoints for Expired Domains

```bash
# List open expired domain auctions
GET /api3.json?key=YOUR_KEY&command=get_open_auctions&count_per_page=100&page_index=0

# Get auction details
GET /api3.json?key=YOUR_KEY&command=get_auction_details&auction_id=12345

# Place a bid
GET /api3.json?key=YOUR_KEY&command=place_auction_bid&auction_id=12345&bid_amount=50

# Get expired closeout domains (buy-now pricing)
GET /api3.json?key=YOUR_KEY&command=get_expired_closeout_domains&count_per_page=100&page_index=0

# Buy a closeout domain immediately
GET /api3.json?key=YOUR_KEY&command=buy_expired_closeout_domain&domain=example.com

# Place a backorder for a domain about to drop
GET /api3.json?key=YOUR_KEY&command=add_backorder_request&domain=example.com

# List your backorders
GET /api3.json?key=YOUR_KEY&command=backorder_request_list

# View closed auctions (historical)
GET /api3.json?key=YOUR_KEY&command=get_closed_auctions&count_per_page=100&page_index=0
```

#### Example curl
```bash
# List open expired domain auctions (JSON)
curl "https://api.dynadot.com/api3.json?key=YOUR_KEY&command=get_open_auctions&count_per_page=50&page_index=0"

# Get closeout domains available for immediate purchase
curl "https://api.dynadot.com/api3.json?key=YOUR_KEY&command=get_expired_closeout_domains&count_per_page=100&page_index=0"

# Backorder a specific domain
curl "https://api.dynadot.com/api3.json?key=YOUR_KEY&command=add_backorder_request&domain=targetdomain.com"
```

#### Data Returned
- Domain name
- Auction ID
- Current bid / buy price
- Auction end time
- Bid history
- ResponseCode (0 = success, -1 = failure)

#### TLD Filtering
- No explicit TLD filter parameter -- filter results locally

#### Pricing
- **API access:** FREE
- **Auction domains:** Pay winning bid
- **Closeout domains:** Fixed price (typically $5-15)
- **Backorders:** $10.99 if caught, $0 if not

#### Rate Limits
- Not explicitly documented; standard API fair-use policies

---

### 6d. DropCatch.com API -- BACKORDER-ONLY

**Verdict:** Backorder API only. You specify domains to catch; no browse/search endpoint. Uses NameBright authentication.

#### Authentication
- Bearer token from NameBright.com Auth endpoint
- Requires NameBright API account with "Register Domains" permission
- IP whitelist required

#### Endpoints
```
POST [dropcatch-api-url]/backorder     # Backorder one or more domains
POST [dropcatch-api-url]/cancel        # Cancel backorder(s)
```

#### Pricing
- **Backorder:** Free to place
- **If caught (sole bidder):** $10.99
- **If caught (multiple bidders):** Goes to auction

#### Example (conceptual)
```bash
# Get bearer token from NameBright
TOKEN=$(curl -X POST "https://api.namebright.com/auth/token" \
  -d '{"username":"you","password":"pass"}' | jq -r '.token')

# Place backorder
curl -X POST "https://api.dropcatch.com/backorder" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domains":["example.com","another.com"]}'
```

#### Limitation
- No search/browse API -- you must already know which domains to backorder
- See GitHub examples: https://github.com/NameBright/DropCatchBackorderExamples

---

### 6e. Park.io -- ccTLD BACKORDERS (NOT .com)

**Verdict:** Skip for .com. Only supports ccTLDs (.io, .ly, .me, .sh, .ac, etc.)

- JSON endpoints and RSS feeds available
- $99/domain if caught
- Auction if multiple bidders
- Supports: .io, .ly, .to, .me, .sh, .ac, .vc, .gg, .je, .mn, .bz, .ag, .sc, .lc
- **Does NOT support .com**

---

## Recommended Stack for .com Drop Hunting

### Budget: Free / Minimal
1. **Dynadot API** (free) -- Browse open auctions + closeout domains + place backorders
2. **GoDaddy inventory CSV** (free, $4.99/yr membership) -- Download auction lists
3. **WhoisFreaks free tier** (500 credits) -- Spot-check WHOIS on candidates

### Budget: ~$100/mo
1. **WhoisFreaks Dropped w/o WHOIS** ($100/mo) -- Daily full dropped domains feed, filter to .com locally
2. **Dynadot API** (free) -- Closeout + auction hunting
3. **WhoisXML Domain Availability** (100 free checks) -- Verify registration status

### Budget: ~$500/mo (Serious Operation)
1. **WhoisFreaks Dropped w/ WHOIS + Backlinks** ($234/mo) -- Full data including link profile
2. **CatchDoms Pro** (468 EUR/yr = ~$42/mo) -- Scored, filtered, SEO-metric-rich API
3. **Dynadot API** (free) -- Execute purchases/bids/backorders
4. **DropCatch API** (free + $10.99/catch) -- Backorder high-value targets

### Optimal Workflow
```
1. WhoisFreaks daily feed (03:00 UTC) → filter .com → rank by domain age
2. CatchDoms API → cross-reference with DA/TF/backlinks scoring
3. Dynadot get_expired_closeout_domains → find bargains
4. DropCatch backorder → pre-order high-value targets before they drop
5. Dynadot place_auction_bid → bid on auction targets
```

---

## Key Timing Notes

- **Expiring (pre-drop):** Domains in `redemptionPeriod` or `pendingDelete` status. 5-day window before actual deletion.
- **Dropped (just released):** Available for immediate registration. WhoisFreaks publishes at 03:00 UTC daily.
- **Closeout:** Registrar-specific discounted expired domains before full deletion. Dynadot offers these via API.
- **Auction:** Competitive bidding on expired domains. GoDaddy + Dynadot both have API-accessible auctions.

The gems (recently dropped .com with existing backlinks/traffic) typically get grabbed within minutes of dropping. To compete:
- Pull WhoisFreaks feed immediately at 03:00 UTC
- Cross-reference backlink data
- Register via registrar API (Dynadot, NameSilo, Namecheap) within minutes

---

## Sources

- [WhoisFreaks Expired Domains API Documentation](https://whoisfreaks.com/documentation/expiring-dropped-domains)
- [WhoisFreaks Products - Expiring & Dropped Domains](https://whoisfreaks.com/products/expiring-dropped-domains)
- [WhoisFreaks Pricing](https://whoisfreaks.com/pricing/api-plans)
- [WhoisXML API - Getting Started with NRD Database](https://www.whoisxmlapi.com/blog/getting-started-with-whoisxml-api-newly-registered-just-expired-domains-database)
- [WhoisXML Domain Availability API](https://domain-availability.whoisxmlapi.com/api/documentation/making-requests)
- [WhoisXML NRD Pricing](https://newly-registered-domains.whoisxmlapi.com/pricing)
- [Domainr API (Deprecated)](https://domainr.com/docs/api)
- [Fastly Domain Research API](https://docs.fastly.com/products/domain-research-api)
- [GoDaddy Auctions API](https://developer.godaddy.com/doc/endpoint/auctions)
- [GoDaddy Aftermarket API](https://developer.godaddy.com/doc/endpoint/aftermarket)
- [GoDaddy API Getting Started](https://developer.godaddy.com/getstarted)
- [GoDaddy Auctions Inventory](https://inventory.auctions.godaddy.com/)
- [Whoxy Expiring Domains](https://www.whoxy.com/expiring-domain-names/)
- [Whoxy Dropped Domains](https://www.whoxy.com/dropped-deleted-domains/)
- [Whoxy Pricing](https://www.whoxy.com/pricing.php)
- [CatchDoms REST API Documentation](https://catchdoms.com/docs)
- [Dynadot API Commands](https://www.dynadot.com/domain/api-commands)
- [DropCatch Backorder API Examples (GitHub)](https://github.com/NameBright/DropCatchBackorderExamples)
- [ExpiredDomains.net FAQ (No API)](https://www.expireddomains.net/faq/)
- [Park.io](https://park.io/)
- [NameSilo API Reference](https://www.namesilo.com/api-reference)

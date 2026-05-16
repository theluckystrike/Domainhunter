# Domain Aftermarket & Auction API Research

**Goal:** Find .com domains listed for sale or at auction for UNDER $500 with good brandability (short, real words, memorable).

**Date:** 2026-05-02

---

## Executive Summary

| Platform | Public Search API? | Price Filter? | Auth Method | Free Tier? | Best For |
|----------|-------------------|---------------|-------------|------------|----------|
| **GoDaddy Auctions** | Limited (bid-only endpoints public; search restricted) | Via SOAP only (legacy) | sso-key header | Yes (API free, $4.99/yr auction membership) | Largest auction inventory, closeouts |
| **Sedo** | YES (SOAP) | No direct filter, but price returned | Partner ID + Sign Key | Free with partner account | 18M+ listed domains, keyword search |
| **Dan.com** | Seller-only (CRUD) | N/A (no buyer search) | Token header | Free | Managing your own listings |
| **Afternic** | YES (Partner XML) | Yes (price range) | Partner credentials | Free (partner program) | DLS network, 100+ registrar integration |
| **NameJet** | NO (restricted) | N/A | N/A | N/A | Expired domain auctions (manual only) |
| **DropCatch** | YES (OAuth2/Bearer) | Likely (Swagger docs) | OAuth2 via NameBright | Free with account | Drop-catching expired domains |
| **Dynadot** | YES (REST) | Yes (via auction params) | Bearer + HMAC-SHA256 | Free with account | Closeout domains, auctions |
| **Namecheap** | YES (REST) | Yes (auction filters) | Separate Auctions API key | Free with account | Budget closeout auctions |
| **Park.io** | JSON feeds only | No | None (public feeds) | Free | ccTLD backorders (.io, .co, etc.) |
| **SnapNames** | NO (restricted) | N/A | N/A | N/A | Expired domain auctions (manual only) |

**Top 4 for programmatic sub-$500 .com hunting: GoDaddy (via inventory files), Sedo (SOAP search), Dynadot (REST auctions/closeouts), Afternic (partner search API).**

---

## 1. GoDaddy Aftermarket / Auctions API

### Base URLs
- **Production:** `https://api.godaddy.com`
- **Test (OTE):** `https://api.ote-godaddy.com`
- **Swagger specs:** `/swagger/swagger_aftermarket.json`, `/swagger/swagger_auctions.json`

### Authentication
- **Method:** API Key + Secret in Authorization header
- **Format:** `Authorization: sso-key {API_KEY}:{API_SECRET}`
- **Key generation:** GoDaddy Developer Portal > My Account > API Keys
- **Auction membership required:** $4.99/year for auction access

### Endpoints

#### Aftermarket API (v1) -- For Sellers/Registrars
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/aftermarket/listings` | Add expiry listings into GoDaddy Auction |
| DELETE | `/v1/aftermarket/listings` | Remove listings from GoDaddy Auction |

**Limitation:** The current public Aftermarket API only supports adding/removing listings. It does NOT expose a search endpoint.

#### Auctions API -- For Buyers
The public REST API currently exposes **bid placement only**, not search/browse. However, there are two workarounds:

**Option A: Inventory File Download (Recommended)**
GoDaddy provides downloadable inventory files:
- URL: `https://auctions.godaddy.com/beta` > Export/Download
- Contains: domain name, auction type, price, end date, traffic, bids
- Updated frequently; can be parsed programmatically

**Option B: Legacy SOAP API (GdAuctionsBiddingWS_v2)**
- **Endpoint:** `https://auctions.godaddy.com/GdAuctionsBiddingWS_v2/service.asmx`
- **Method:** `GetAuctionListByAuctionType2`
- **Note:** ACCESS RESTRICTED -- GoDaddy is no longer issuing new access credentials

Parameters for legacy SOAP:
| Parameter | Values |
|-----------|--------|
| pageNumber | Numeric (1, 2, 3...) |
| rowsPerPage | 15, 25, 50, 100, 200, 300, 500 |
| keyword | Search term (no spaces/special chars, hyphens OK) |
| auctionType | "auction", "buy now" |
| searchType | "most active", "featured", "expiring", "ending soon", "buy now", "closeouts", "bargainbin", "a-z listings" |

### Search / Filter Capabilities
- **Keyword search:** Only via legacy SOAP or inventory file parsing
- **TLD filter:** Only via inventory file parsing
- **Price filter:** Only via inventory file parsing
- **Sort by:** Via inventory file (price, expiry, traffic, bids)
- **Domain metadata:** Traffic (monthly page views), revenue estimates, age (via WHOIS), bids count

### Rate Limits
- **60 requests/minute** per endpoint

### Pricing
- API key creation: **Free**
- Auction membership: **$4.99/year**
- Commission on purchase: **15-20%**

### Example: curl (check domain availability -- related but not auction-specific)
```bash
curl -X GET "https://api.godaddy.com/v1/domains/available?domain=example.com" \
  -H "Authorization: sso-key YOUR_KEY:YOUR_SECRET" \
  -H "Accept: application/json"
```

### Practical Strategy for Sub-$500 .com Domains
1. Download the auction inventory file daily
2. Parse for .com, price < $500, sort by traffic/bids
3. Use the API to place bids on targets
4. Focus on "closeouts" and "bargainbin" search types

---

## 2. Sedo API

### Base URL
- **SOAP Endpoint:** `https://api.sedo.com/api/v1/`
- **WSDL:** `https://api.sedo.com/api/v1/?wsdl`
- **Legacy (deprecated but supported):** `/api/sedointerface.php`
- **Protocol:** SOAP 1.1 (RPC/Encoded, UTF-8)

### Authentication
- **partnerid** (integer): Your Sedo Partner ID
- **signkey** (string): Your API sign key
- **Obtain:** Register for Sedo Partner Program (free)

### Key Endpoints (Functions)

#### DomainSearch -- PRIMARY FOR BUYER DISCOVERY
```
public array DomainSearch( array $searchquery )
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| partnerid | integer | YES | Partner ID |
| signkey | string | YES | Sign key |
| keyword | string | YES | Search keyword (UTF-8) |
| tld | string | NO | TLD filter (e.g., "com") |
| kwtype | string | NO | B=Begins with, C=Contains, E=Ends with |
| no_hyphen | boolean | NO | true = exclude hyphenated domains |
| no_numeral | boolean | NO | true = exclude domains with numbers |
| no_idn | boolean | NO | true = exclude IDN domains |
| resultsize | integer | NO | Max results (up to 1000) |
| language | string | NO | ISO 639-1 code (e.g., "en") |

**Return fields:**
| Field | Type | Description |
|-------|------|-------------|
| domain | string | Domain name (ACE format) |
| type | string | D=Domain, W=Website |
| price | double | Price (0.00 = no price set, Make Offer) |
| currency | integer | 0=EUR, 1=USD, 2=GBP |
| rank | integer | 1=Exact, 2=Begins, 3=Ends, 4=Contains |
| url | string | Sedo detail page URL |

#### Other Useful Functions
| Function | Description |
|----------|-------------|
| DomainList | List your own portfolio |
| DomainListExtended | Extended listing with more metadata |
| DomainStatus | Check status of a specific domain |
| DomainInsert | Add domain to your Sedo portfolio |
| DomainEdit | Update listing price/settings |
| DomainPreview | Preview domain details |
| CheckBlacklist | Check if domain is blacklisted |

### Search / Filter Capabilities
- **Keyword search:** YES (begins with, contains, ends with)
- **TLD filter:** YES
- **Price filter:** NOT directly; price returned in results, filter client-side
- **Exclude hyphens/numbers/IDN:** YES
- **Sort:** By rank (relevance); client-side sort by price
- **Max results:** 1,000 per query

### Domain Metadata
- Price and currency
- Type (domain vs website with content)
- No direct backlink/traffic data (use Ahrefs/Semrush for enrichment)

### Rate Limits
- Not officially documented; reasonable usage expected
- Partner program terms apply

### Pricing
- Partner account: **Free**
- Commission on sale: **15-20%**
- 18M+ domains listed

### Example: PHP SOAP Call
```php
$client = new SoapClient(null, [
    'location'     => 'https://api.sedo.com/api/v1/',
    'soap_version' => SOAP_1_1,
    'encoding'     => 'UTF-8',
    'uri'          => 'urn:SedoInterface',
    'style'        => SOAP_RPC,
    'use'          => SOAP_ENCODED,
]);

$params = [
    'partnerid'  => 1234,
    'signkey'    => 'your_sign_key_here',
    'keyword'    => 'brand',
    'tld'        => 'com',
    'kwtype'     => 'C',       // Contains
    'no_hyphen'  => true,
    'no_numeral' => true,
    'no_idn'     => true,
    'resultsize' => 500,
    'language'   => 'en',
];

$results = $client->DomainSearch($params);
foreach ($results as $domain) {
    if ($domain['price'] > 0 && $domain['price'] <= 500) {
        echo $domain['domain'] . ' - $' . $domain['price'] . "\n";
    }
}
```

### Example: curl (SOAP envelope)
```bash
curl -X POST "https://api.sedo.com/api/v1/" \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H "SOAPAction: urn:SedoInterface#DomainSearch" \
  -d '<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <SOAP-ENV:Body>
    <DomainSearch xmlns="urn:SedoInterface">
      <partnerid xsi:type="xsd:int">1234</partnerid>
      <signkey xsi:type="xsd:string">your_sign_key</signkey>
      <keyword xsi:type="xsd:string">brand</keyword>
      <tld xsi:type="xsd:string">com</tld>
      <kwtype xsi:type="xsd:string">C</kwtype>
      <no_hyphen xsi:type="xsd:boolean">true</no_hyphen>
      <no_numeral xsi:type="xsd:boolean">true</no_numeral>
      <no_idn xsi:type="xsd:boolean">true</no_idn>
      <resultsize xsi:type="xsd:int">500</resultsize>
      <language xsi:type="xsd:string">en</language>
    </DomainSearch>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>'
```

---

## 3. Dan.com API

### Important Note
Dan.com was acquired by GoDaddy in 2021 and integrated with Afternic. The API is **seller-focused** -- it manages YOUR domain listings, not buyer search.

### Base URL
```
https://dan.com/api/v1/domains
```

### Authentication
- **Header:** `Authorization: Token YOUR_TOKEN`
- **Obtain:** Dan.com account > Settings > API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/domains/` | List all YOUR domains |
| GET | `/api/v1/domains/{id}` | Get single domain (by ID or name) |
| POST | `/api/v1/domains` | Create/add domain listing |
| PUT | `/api/v1/domains/{id}` | Update domain (price, settings) |
| DELETE | `/api/v1/domains/{id}` | Remove domain listing |

### Domain Object Fields
```json
{
  "domain": {
    "id": 12345,
    "name": "example.com",
    "buy_now_price": 499,
    "starting_offer": 100
  }
}
```

### Search / Filter Capabilities
- **Keyword search:** NO (cannot search marketplace)
- **Price filter:** NO
- **TLD filter:** NO
- **This is a seller portfolio management API only**

### Rate Limits
- Not documented

### Pricing
- Account: **Free**
- Commission: **9-15%** (lowest in the market)

### Example: curl
```bash
# List your domains
curl -X GET "https://dan.com/api/v1/domains/" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json"

# Add a domain listing
curl -X POST "https://dan.com/api/v1/domains" \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain": {"name": "example.com", "buy_now_price": 299, "starting_offer": 50}}'
```

### Verdict for Sub-$500 Hunting
**NOT USEFUL for buying.** Dan.com has no buyer search API. Use the Dan.com website directly to browse, or use Afternic's partner API instead (Dan.com inventory feeds into Afternic/GoDaddy).

---

## 4. Afternic API (GoDaddy Company)

### Base URL
- **Search API:** Partner-specific URL provided upon enrollment
- **General format:** `https://api.afternic.com/` (partner portal)
- **Documentation:** `partnerportaldocs.afternic.com` (may require partner login)

### Authentication
- **Method:** Partner credentials (account ID + API key)
- **Obtain:** Apply for Afternic DLS (Domain Listing Service) Partner Program

### Key Capabilities

#### Search API
- Real-time search against DLS Network inventory
- XML response format
- Can also download full inventory file for local hosting

#### Search Parameters (from partner docs)
| Parameter | Description |
|-----------|-------------|
| keyword | Search term |
| tld | Filter by TLD |
| minprice | Minimum price filter |
| maxprice | Maximum price filter |
| exact | Exact match only |
| sort | Sort field |
| order | Sort direction |
| limit | Results per page |
| offset | Pagination offset |

### Search / Filter Capabilities
- **Keyword search:** YES
- **TLD filter:** YES
- **Price range filter:** YES (minprice/maxprice)
- **Sort:** YES (price, relevance)
- **Inventory download:** YES (full DLS inventory file)

### Domain Metadata
- Domain name, price, category
- Fast Transfer availability
- No direct traffic/backlink data

### Rate Limits
- Partner-specific; not publicly documented

### Pricing
- Partner enrollment: **Free**
- Commission on sale: **15-20%**
- Network reach: 100+ registrar checkout flows

### Example: Search Request
```
GET https://api.afternic.com/search?keyword=brand&tld=com&maxprice=500&limit=100
```
(Exact URL format varies by partner integration; XML response)

### Verdict for Sub-$500 Hunting
**EXCELLENT.** Afternic has the best price filtering for a buyer search API. The DLS inventory file download is the most reliable method. Apply for partner access. Afternic also aggregates Dan.com inventory.

---

## 5. NameJet API

### Status: RESTRICTED / NOT PUBLICLY AVAILABLE

### Key Facts
- NameJet merged with SnapNames (both owned by Web.com/Newfold Digital)
- Combined auction engine since 2016
- API access reportedly limited to high-volume partners
- No public developer portal or documentation

### Alternative Approach
- Use the NameJet website: `https://www.namejet.com/`
- Search expiring and auction domains manually
- Backorder domains for $69-$99 (charged only if acquired)
- Set maximum bid for auctions

### Pricing
- Backorder: Free to place; charged $69-$99 on acquisition
- Auction: Standard auction bidding

### Verdict for Sub-$500 Hunting
**MANUAL ONLY.** No programmatic access. Good inventory of expired .com domains. Check daily via website. Many domains go for $69-$200 in auctions.

---

## 6. DropCatch API

### Base URLs
- **API:** `https://api.dropcatch.com/`
- **Documentation (Swagger UI):** `https://api.dropcatch.com/documentation`
- **API specs:** `/documentation/v2/doc.json` and `/documentation/v1/doc.json`
- **Credential management:** `https://www.dropcatch.com/account/api-management`

### Authentication
- **Method:** OAuth 2.0 Bearer Token
- **Flow:** Obtain bearer token from NameBright.com Auth endpoint
- **Requirements:**
  - Active NameBright.com account with API activation
  - "Register Domains" permission enabled
  - IP whitelist configured
  - Prior login to DropCatch.com using NameBright credentials
- **Header:** `Authorization: Bearer YOUR_TOKEN`

### Key Capabilities
- Backorder one or more domain names
- Cancel backorders
- Search current auctions
- Place bids on auctions

### Response Format
```json
{
  "someErrors": false,
  "results": [
    {
      "domainName": "example.com",
      "success": true,
      "maxBid": 100,
      "message": "",
      "statusCode": 200
    }
  ]
}
```

### Search / Filter Capabilities
- Full Swagger documentation available at the API docs URL
- Auction search with filtering likely supported (v2 endpoints)
- Exact parameter list requires accessing Swagger UI directly

### Rate Limits
- Not publicly documented

### Pricing
- Account: **Free**
- Backorder: Free to place; minimum $59 if won
- Auction: Standard auction format; 3-5 day auctions

### Example: curl (Backorder)
```bash
# Get bearer token from NameBright
TOKEN=$(curl -X POST "https://api.namebright.com/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "YOUR_CLIENT_ID", "clientSecret": "YOUR_CLIENT_SECRET"}' \
  | jq -r '.token')

# Place backorder on DropCatch
curl -X POST "https://api.dropcatch.com/v2/backorders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"domainName": "example.com", "maxBid": 200}]'
```

### Verdict for Sub-$500 Hunting
**GOOD for expired/dropping domains.** Many expired .com domains go for $59-$300 in DropCatch auctions. API enables automated backordering of targets.

---

## 7. Dynadot API (Aftermarket)

### Base URLs
- **REST (JSON):** `https://api.dynadot.com/api3.json`
- **REST (XML):** `https://api.dynadot.com/api3.xml`
- **Sandbox:** `https://api-sandbox.dynadot.com/api3.json`

### Authentication
- **Header:** `Authorization: Bearer YOUR_API_KEY`
- **Signature Header:** `X-Signature: HMAC-SHA256(API_KEY + path + X-Request-ID + body, API_SECRET)`
- **Content-Type:** `application/json`
- **Obtain:** Dynadot account > Account Settings > API

### Key Aftermarket Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/get_open_auctions` | List all active auctions |
| GET | `/get_auction_details` | Details for specific auction |
| GET | `/get_auction_bids` | View bids on an auction |
| POST | `/place_auction_bid` | Submit auction bid |
| GET | `/get_closed_auctions` | View completed auctions |
| GET | `/get_expired_closeout_domains` | Browse closeout inventory (GREAT for cheap domains) |
| POST | `/buy_expired_closeout_domain` | Purchase closeout domain |
| POST | `/buy_it_now` | Instant purchase of listed domain |
| GET | `/get_listings` | View all aftermarket listings |
| GET | `/get_listing_item` | Specific listing details |
| PUT | `/set_for_sale` | Configure domain for sale |
| POST | `/add_backorder_request` | Create domain backorder |
| DELETE | `/delete_backorder_request` | Cancel backorder |
| GET | `/backorder_request_list` | List active backorders |
| POST | `/listing_on_afternic` | Cross-list to Afternic |
| POST | `/listing_on_sedo` | Cross-list to Sedo |

### Search / Filter Capabilities
- **Keyword search:** Via open auctions and closeout listings
- **TLD filter:** Via parameters (command-specific)
- **Price range:** Client-side filtering from returned results
- **Sort:** By auction end time, price
- **Currency support:** USD, EUR, CNY, CAD, etc.

### Domain Metadata
- Domain name, price, currency
- Auction end time, current bid, bid count
- Closeout price (typically $5-$20 for .com domains!)
- WHOIS stats available via `/get_whois_stats`

### Rate Limits
| Tier | Limit |
|------|-------|
| Regular | 60 requests/minute |
| Bulk | 600 requests/minute |
| Super Bulk | 6,000 requests/minute |

### Pricing
- API access: **Free** with Dynadot account
- Expired closeout domains: **$5-$20** (incredibly cheap!)
- Auction wins: Varies (many under $100)
- No listing fee

### Example: curl
```bash
# Get all open auctions
curl -X GET "https://api.dynadot.com/api3.json?key=YOUR_API_KEY&command=get_open_auctions" \
  -H "Accept: application/json"

# Get expired closeout domains (BEST for cheap .com)
curl -X GET "https://api.dynadot.com/api3.json?key=YOUR_API_KEY&command=get_expired_closeout_domains" \
  -H "Accept: application/json"

# Place auction bid
curl -X GET "https://api.dynadot.com/api3.json?key=YOUR_API_KEY&command=place_auction_bid&domain=example.com&bid_amount=150&currency=USD" \
  -H "Accept: application/json"

# Buy expired closeout domain
curl -X GET "https://api.dynadot.com/api3.json?key=YOUR_API_KEY&command=buy_expired_closeout_domain&domain=example.com" \
  -H "Accept: application/json"
```

### Verdict for Sub-$500 Hunting
**BEST VALUE.** Dynadot's expired closeout domains are $5-$20 each. The API is fully featured with REST/JSON. Open auctions frequently have .com domains under $100. This should be your primary source for cheap domains.

---

## 8. Namecheap Marketplace / Auctions API

### Base URL
- **Auctions API:** `https://aftermarketapi.namecheap.com/`
- **Docs (Swagger):** `https://aftermarketapi.namecheap.com/client/docs/`
- **Regular API:** `https://api.namecheap.com/xml.response` (domain management only)

### Authentication
- **Auctions API:** Separate API key from regular Namecheap API
- **Obtain:** Namecheap Market Dashboard > API Settings
- **Regular API:** `ApiUser`, `ApiKey`, `UserName`, `ClientIp` parameters
- **IP Whitelist:** Required for all API access

### Key Endpoints

#### Regular Namecheap API (Domain Registration/Management)
| Command | Description |
|---------|-------------|
| `namecheap.domains.check` | Check domain availability |
| `namecheap.domains.getList` | List your domains |
| `namecheap.domains.getInfo` | Domain details |
| `namecheap.domains.getTldList` | Available TLDs |

#### Auctions API (Separate System)
- Search listed auction domains
- Place bids
- Get auction details
- Filter by keyword, extension, auction type
- GET and POST request methods

### Search / Filter Capabilities
- **Keyword search:** YES
- **TLD filter:** YES (extension filter)
- **Auction type filter:** YES
- **Price filter:** YES (within auction parameters)
- **Sort:** YES

### Rate Limits
- Regular API: **50 requests/minute** (20 for sandbox)
- Auctions API: Not publicly documented

### Pricing
- API access: **Free** with Namecheap account (min $50 balance or 20+ domains)
- Auctions: Many domains at $1-$50 starting bids
- No separate auction membership fee
- Commission: Included in pricing

### Example: curl (Regular API)
```bash
curl -X GET "https://api.namecheap.com/xml.response?\
ApiUser=YOUR_USER&\
ApiKey=YOUR_KEY&\
UserName=YOUR_USER&\
Command=namecheap.domains.check&\
ClientIp=YOUR_IP&\
DomainList=example.com,brand.com"
```

### Verdict for Sub-$500 Hunting
**GOOD.** Namecheap auctions have many low-cost domains. The dedicated Auctions API at `aftermarketapi.namecheap.com` supports search and filtering. Many expired/closeout domains available for $1-$50.

---

## 9. Park.io

### Base URL
- **Website:** `https://park.io/`
- **JSON feeds:** `https://park.io/domains.json` (public, read-only)
- **RSS feeds:** Available for listings and auctions
- **CSV export:** Last 50 sales

### Authentication
- **None required** for public feeds

### Capabilities
- JSON endpoints for domain listings and auctions
- RSS feeds for monitoring
- CSV export of recent sales
- **READ-ONLY** -- no bidding, no backordering via API

### Search / Filter Capabilities
- **Keyword search:** NO (browse only)
- **TLD filter:** Browse by TLD on website
- **Price filter:** NO
- **Sort:** NO

### Supported TLDs
.io, .co, .me, .to, .ly, .sh, .ac, .vc, .je, .gg, .cc

### Pricing
- Backorder (via website): **$99** per domain (charged only if acquired)
- If multiple backorders: Goes to 10-day auction
- **.com NOT supported** -- Park.io focuses on ccTLDs only

### Verdict for Sub-$500 Hunting
**NOT USEFUL for .com domains.** Park.io only handles ccTLDs. Good if you want .io or .co domains at $99/each. No real API for programmatic access.

---

## 10. SnapNames

### Status: NO PUBLIC API

### Key Facts
- Owned by Newfold Digital (same parent as NameJet, Web.com)
- Combined backorder/auction engine with NameJet since 2016
- No public developer portal
- API access reportedly limited to select high-volume partners
- No documentation available

### Platform Features (Website Only)
- Search expired/deleting domain names
- Place backorders
- Bid in auctions
- "Buy Now" instant purchase
- 25M+ domains annually processed

### Pricing
- Backorder: Free to place, **$69** minimum if won
- Auction: Standard bidding (many domains $69-$200)

### Verdict for Sub-$500 Hunting
**MANUAL ONLY.** No API. Use `snapnames.com` website directly. Many .com domains go for $69-$200 at auction. Check daily for new expiring inventory.

---

## Bonus: Additional Programmatic Data Sources

### WhoisFreaks API
- **URL:** `https://whoisfreaks.com/`
- **Provides:** Daily feeds of expired/dropped domains across 1,528 TLDs
- **Includes:** WHOIS records, DNS data, backlink counts
- **Pricing:** Paid plans starting ~$19/month
- **Best for:** Enriching domain data found on other platforms

### ICANN CZDS (Zone File Access)
- **URL:** `https://czds.icann.org/`
- **Provides:** Complete TLD zone files (all registered domains)
- **Free** for research purposes
- **Best for:** Building your own expired domain detection pipeline

### Ahrefs / Semrush APIs (Enrichment)
- Use to check Domain Rating, backlinks, organic traffic for candidate domains
- Ahrefs: ~$99/month; Semrush: ~$119/month
- Essential for evaluating brandability and SEO value

---

## Recommended Pipeline for Sub-$500 Brandable .com Domains

### Step 1: Source Candidates (Daily)
```
Priority 1: Dynadot get_expired_closeout_domains  ($5-$20 each)
Priority 2: GoDaddy Auctions inventory file       (filter < $500)
Priority 3: Sedo DomainSearch (keyword=brand terms, tld=com)
Priority 4: Namecheap Auctions API search          (filter < $500)
Priority 5: DropCatch API open auctions             (filter < $500)
```

### Step 2: Filter for Brandability
```
- Length: 4-8 characters preferred
- No hyphens, no numbers
- Real English words or pronounceable made-up words
- .com only
- Price: < $500
```

### Step 3: Enrich with Metadata
```
- Ahrefs: Domain Rating, backlinks, referring domains
- WHOIS: Registration age, history
- Archive.org: Previous site content (avoid spam history)
- Google: Existing indexed pages, brand conflicts
```

### Step 4: Acquire
```
- Dynadot closeouts: Instant buy ($5-$20)
- Auctions: Set max bid, wait
- Fixed price: Purchase via platform
```

### Estimated Monthly Cost
| Item | Cost |
|------|------|
| Dynadot account | Free |
| GoDaddy Auction membership | $4.99/yr |
| Sedo partner account | Free |
| Namecheap account | Free (need $50 balance) |
| DropCatch/NameBright account | Free |
| Domain acquisitions (5-10/mo) | $50-$500 |
| Ahrefs (optional enrichment) | $99/mo |
| **Total** | **$50-$600/month** |

---

## Quick Reference: API Authentication Setup

| Platform | Sign Up URL | Auth Type |
|----------|-------------|-----------|
| GoDaddy | `developer.godaddy.com` | sso-key header |
| Sedo | `sedo.com/us/partner-program/` | Partner ID + Sign Key (SOAP) |
| Afternic | `afternic.com/partner` | Partner credentials |
| Dynadot | `dynadot.com` > API Settings | API Key (Bearer + HMAC) |
| Namecheap | `namecheap.com` > API Settings | API Key + IP whitelist |
| DropCatch | `dropcatch.com/account/api-management` | OAuth2 Bearer (via NameBright) |
| Dan.com | `dan.com` > Settings > API | Token header |

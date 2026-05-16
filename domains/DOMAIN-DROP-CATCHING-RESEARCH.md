# Domain Drop-Catching Ecosystem Research

**Date:** 2026-05-02
**Focus:** .com domain expiration lifecycle, drop-catching APIs, pending delete data sources

---

## 1. The .com Domain Expiration Lifecycle (Verisign Registry)

When a .com domain registration expires and the registrant fails to renew, it passes through a strict sequence of phases before becoming available for re-registration. The exact timeline:

### Phase 1: Auto-Renew Grace Period (0-45 days after expiry)
- **Duration:** Up to 45 days (registrar-dependent, typically 30-40 days)
- **What happens:** The registrar may auto-renew on behalf of the registrant. The registrant can renew at normal price. Most registrars park the domain or show a "this domain has expired" page.
- **Cost to recover:** Standard renewal fee (e.g., $10-15 for .com)
- **Registry status:** `autoRenewPeriod`

### Phase 2: Redemption Grace Period (30 days)
- **Duration:** Exactly 30 days (set by Verisign for .com)
- **What happens:** The registrar has deleted the domain from its records, but Verisign still holds it in a "redemption" state. The original registrant can still recover it, but at a steep penalty fee.
- **Cost to recover:** $80-200+ (Verisign charges registrars ~$80 restore fee, registrars mark up to $150-200)
- **Registry status:** `redemptionPeriod`
- **Zone file:** Domain is REMOVED from the .com zone (no DNS resolution)

### Phase 3: Pending Delete (5 days)
- **Duration:** Exactly 5 days
- **What happens:** The domain is queued for permanent deletion. NO ONE can recover it during this phase -- not even the original registrant. This is the point of no return.
- **Registry status:** `pendingDelete`
- **Zone file:** Not in zone

### Phase 4: Drop (Day 0 -- Domain Released)
- **When:** After the 5-day pending delete completes
- **Drop time:** Approximately 2:00 PM Eastern Time (18:00-19:00 UTC depending on DST)
- **Duration of drop window:** Verisign processes deletions over approximately 2 hours
- **Pattern:** No fixed order; the exact second a specific domain drops varies daily
- **What happens:** The domain is purged from Verisign's registry and becomes available for first-come-first-served registration

### Total Timeline: ~71-80 days from expiry to drop
```
Day 0:        Registration expires
Day 0-45:     Auto-Renew Grace Period (registrar sets exact length)
Day 45-75:    Redemption Grace Period (exactly 30 days)
Day 75-80:    Pending Delete (exactly 5 days)
Day 80:       DOMAIN DROPS -- available for registration
```

**Important note:** The 45-day grace period varies by registrar. GoDaddy uses ~42 days, Namecheap uses ~30 days, etc. The redemption (30 days) and pending delete (5 days) are fixed by Verisign.

---

## 2. Drop-Catching Services with APIs

### 2A. DropCatch.com (BEST API -- Recommended)

**Owner:** NameBright (Donuts/Identity Digital ecosystem)
**Market position:** Dominant drop-catcher with 1,200+ ICANN-accredited registrars (highest in the industry)
**Estimated catch share:** ~50%+ of all competitively caught .com domains

#### API Details

**Authentication:**
- OAuth2 client_credentials flow via NameBright
- Auth endpoint: `https://api.namebright.com/auth/token`
- Tokens valid for 30 minutes
- Requires: NameBright account with API access + "Register Domains" permission + IP whitelist

**Setup steps:**
1. Create account at `namebright.com/NewAccount`
2. Activate API at `namebright.com/Settings#Api`
3. Enable "Register Domains" permission
4. Configure IP whitelist
5. Log into DropCatch.com once with NameBright credentials
6. Generate API credentials at `dropcatch.com/account/api-management`

**Interactive API docs:** `https://api.dropcatch.com/documentation` (Swagger UI, v1 + v2)

#### API v2 Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/Authorize` | Get bearer token (ClientId + ClientSecret) |
| `PUT` | `/v2/backorders` | Place backorders (bulk, array of domains) |
| `GET` | `/v2/backorders` | List your backorders (searchTerm, tld, type filters) |
| `DELETE` | `/v2/backorders` | Cancel backorders (array of domain strings) |
| `GET` | `/v2/auctions` | Search active auctions (filters: TLD, bid range, end time, has bids) |
| `GET` | `/v2/auctions/{id}` | Get single auction details |
| `GET` | `/v2/auctions/{id}/bids` | Get bid history for an auction |
| `POST` | `/v2/bids` | Place bids (bulk, array of PlaceBid objects) |
| `GET` | `/v2/bids` | List your bids (winning filter available) |
| `GET` | `/v2/downloads/dropping/{type}` | **Download dropping domain lists** (zip file) |
| `GET` | `/v2/downloads/auctions/{downloadType}` | Download auction data (zip file) |
| `GET` | `/v2/history/auctions` | Your auction history |
| `GET` | `/v2/history/backorders` | Your backorder history |

#### Example: Place a Backorder (curl)

```bash
# Step 1: Get bearer token
TOKEN=$(curl -s -X POST https://api.namebright.com/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET" \
  | jq -r '.access_token')

# Step 2: Place backorder
curl -X PUT https://api.dropcatch.com/v2/backorders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"domainName": "example.com", "maxBid": 59.00}]'
```

#### Response Format
```json
{
  "someErrors": false,
  "results": [
    {
      "domainName": "example.com",
      "success": true,
      "maxBid": "59.00",
      "message": "Backorder Accepted",
      "statusCode": "200.1"
    }
  ]
}
```

#### Pricing
- **Backorder placement:** FREE
- **If caught (sole backorder):** $59 for .com
- **If caught (multiple backorders):** Goes to 3-day PUBLIC auction, minimum bid $59
- **You only pay if you win**
- **2025 median auction price:** Rose 18% year-over-year due to increased competition

#### Success Rate
- Solo backorders on non-competitive domains: 60-80%
- Competitive/premium domains: Much lower (multiple catchers racing)
- Overall market dominance: Catches more domains than any other service

---

### 2B. NameJet / SnapNames (Combined Platform)

**Owner:** Newfold Digital (formerly Web.com/Endurance)
**Market position:** #2 drop-catcher, exclusive access to Network Solutions and Register.com expired inventory
**Combined since:** 2016 (shared inventory, shared auction engine)

#### API Access
- **No public API documented.** These platforms are web-interface only for individual users.
- **Reseller/Partner program exists:** The "Backorder Service Partner Program" allows partners to place orders on clients' behalf, but this requires a business relationship/contract with Newfold Digital.
- **Affiliate widget:** HTML/JS embed that lets visitors search/backorder from your website (not a REST API).
- Contact: Reseller inquiry through `snapnames.com/domain-reseller-solutions.action` or `namejet.com/domain-reseller-solutions.action`

#### Pricing
- **Backorder placement:** FREE
- **If caught (sole backorder):** $69-79 for .com
- **If caught (multiple backorders):** 3-day PRIVATE auction (only backorder holders can bid)
- **Seller commission:** 15%

#### Key Difference from DropCatch
NameJet/SnapNames auctions are **private** (restricted to users who placed backorders). DropCatch auctions are **public** (anyone can bid). This means NameJet private auctions may have less bidding competition but no API means no automation.

---

### 2C. Dynadot

**Owner:** Dynadot LLC (independent registrar)
**Market position:** Mid-tier drop-catcher, good for budget catches

#### API Details

**Authentication:** API key from Dynadot control panel (Tools > API)
**Base URL (production):** `https://api.dynadot.com`
**Base URL (sandbox):** `https://api-sandbox.dynadot.com`
**Format:** XML or JSON (choose via endpoint path: `api3.xml` or `api3.json`)

#### Backorder API Endpoints

| Command | URL | Purpose |
|---------|-----|---------|
| `add_backorder_request` | `GET/POST https://api.dynadot.com/api3.json?key=KEY&command=add_backorder_request&domain=DOMAIN` | Place a backorder |
| `delete_backorder_request` | `GET/POST https://api.dynadot.com/api3.json?key=KEY&command=delete_backorder_request&domain=DOMAIN` | Cancel a backorder |
| `backorder_request_list` | `GET https://api.dynadot.com/api3.json?key=KEY&command=backorder_request_list` | List all your backorders |
| `get_open_backorder_auctions` | `GET https://api.dynadot.com/api3.json?key=KEY&command=get_open_backorder_auctions` | View active backorder auctions |
| `get_backorder_auction_details` | `GET https://api.dynadot.com/api3.json?key=KEY&command=get_backorder_auction_details&auction_id=ID` | Get auction detail |
| `place_backorder_auction_bid` | `POST https://api.dynadot.com/api3.json?key=KEY&command=place_backorder_auction_bid&auction_id=ID&amount=AMT` | Bid on auction |
| `get_closed_backorder_auctions` | `GET https://api.dynadot.com/api3.json?key=KEY&command=get_closed_backorder_auctions` | View completed auctions |

**RESTful v2 endpoints (newer):**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/restful/v2/aftermarkets/backorder-requests` | Create backorder |
| `DELETE` | `/restful/v2/aftermarkets/backorder-requests/{request_id}` | Delete backorder |
| `GET` | `/restful/v2/aftermarkets/backorder-requests` | List backorders |
| `GET` | `/restful/v2/aftermarkets/backorder-auctions` | List backorder auctions |

#### Pricing
- **Backorder placement:** FREE (requires $5 minimum account balance or $5+ order in last 365 days)
- **If caught (sole backorder):** Registration fee only (~$10-12 for .com)
- **If caught (multiple backorders):** Backorder auction, starting bid $5 over backorder price
- **Afilias TLDs:** Two pricing tiers (high priority = attempt before release, low priority = attempt at release)

#### Advantage
Cheapest option if you win without competition. $10-12 vs $59-79 at DropCatch/NameJet. Downside: lower catch rate since they have fewer registrar accreditations.

---

### 2D. GoDaddy Auctions (Backorders RETIRED)

**Status:** GoDaddy retired its backorder service on October 7, 2025. Credits were removed.
**Current model:** Expired GoDaddy-registered domains go through GoDaddy Auctions, then Closeouts.

#### API Details

**API exists but restricted:**
- Production: `https://api.godaddy.com`
- OTE (testing): `https://api.ote-godaddy.com`
- Swagger spec: `/swagger/swagger_aftermarket.json`
- Authentication: API Key + Secret

**Critical limitation:** GoDaddy stopped granting NEW API access ~2022. If you do not already have access, you cannot get it. The API only has a bid endpoint -- no endpoint to search/filter auction listings programmatically.

#### Closeout Pricing
- Domains that receive no auction bids enter 5-day "Closeout"
- Reverse-price auction: starts at ~$20-30 and declines daily to minimum $5
- These are GoDaddy-registered domains only (not drops from the general registry)

#### Verdict
Not useful for drop-catching. GoDaddy only auctions domains that expired at GoDaddy itself. No general .com drop-catching. API access closed to new users.

---

### 2E. Park.io

**Owner:** Mike Carson (indie operator)
**Supported TLDs:** .IO, .LY, .ME only (NO .com support)

#### Pricing
- **$99 per caught domain**
- Card only charged on successful catch
- Some backorders allow setting a max price threshold

#### API
- No public REST API documented
- Web interface only

#### Verdict
**Not applicable for .com drop-catching.** Park.io specializes in ccTLDs (.io, .ly, .me). Included here for completeness since it is frequently mentioned in drop-catching discussions.

---

### 2F. Pheenix.com (DEFUNCT)

**Status:** ICANN terminated Pheenix's registrar accreditation. All domains transferred to EnCirca.com.
**Verdict:** No longer operational. Do not use. Historical reference only.

---

### 2G. Namecheap

**Status:** Namecheap does NOT offer a backorder/drop-catch service.
**What they do:** Auction expired Namecheap-registered domains on their marketplace (similar to GoDaddy).
**API:** Namecheap has a registration API but no backorder API.
**Verdict:** Not a drop-catching option. You can buy expired Namecheap domains at auction, but cannot catch general .com drops.

---

### 2H. Sav.com (Budget Alternative)

**Market position:** Budget-friendly, no-fee backorder service
**Supported TLDs:** 350+

#### Pricing
- **Backorder placement:** FREE (unlimited backorders)
- **If caught (sole backorder):** Registration cost only (~$9-12 for .com)
- **If caught (multiple backorders):** 10-day private auction starting at $1 + registration cost

#### API
- No public API documented
- Web interface only

#### Verdict
Cheapest possible option. No backorder fee, no catch fee beyond registration. Lower catch rate than DropCatch but worth using as a supplementary service.

---

## 3. Pending Delete Lists -- Where to Get Them

### 3A. DropCatch API (BEST for actionable data)

**Endpoint:** `GET /v2/downloads/dropping/{type}`
**Returns:** ZIP file with dropping domain lists
**Advantage:** Already filtered for domains DropCatch is tracking; you can immediately backorder via the same API
**Cost:** Free with DropCatch account

---

### 3B. ExpiredDomains.net (FREE, Web-Based)

**URL:** `https://www.expireddomains.net/expired-domains/`
**Coverage:** 677 TLDs including .com
**Features:**
- Daily updated pending delete lists
- Filter by: TLD, age, backlinks (Majestic), Archive.org history, length, keywords
- Export: CSV (up to 2,000 domains per export, requires free account login)
- .com specific: `https://www.expireddomains.net/expired-com-domains/`

**Limitations:**
- NO API (explicitly stated by the site)
- Max 2,000 domain CSV export
- Web scraping is prohibited by ToS
- Manual process only

---

### 3C. ICANN CZDS / Verisign Zone Files (DIY Method)

**How it works:** Download the daily .com zone file (all active .com domains), compare yesterday's zone to today's zone. Domains that disappear from the zone have entered redemption or pending delete.

**Access:**
1. Apply at `https://czds.icann.org/`
2. Must represent a legitimate organization with legal/ethical use case
3. Approval takes days to weeks (90%+ approval rate)
4. Zone files available after 06:00 UTC daily

**Technical approach:**
```bash
# Conceptual: diff yesterday's and today's .com zone files
# Domains in yesterday but NOT in today = newly entered redemption/pending delete
comm -23 <(sort yesterday.zone) <(sort today.zone) > newly_removed.txt
```

**Important caveat:** The zone file does NOT include domains in `serverHold`, `clientHold`, `pendingDelete`, or `redemptionPeriod` status. So you detect removals by diffing, but you cannot distinguish between redemption (30 days away) and pending delete (5 days away) from the zone file alone. You need WHOIS lookups to determine the exact status.

**Zone file size:** The .com zone is ~10-15 GB compressed, containing 150M+ domain records. Processing requires significant compute/storage.

**Tools:**
- `https://github.com/pogzyb/czdsdump` -- Python tool to automate CZDS downloads
- `https://github.com/acidvegas/czds` -- Another CZDS automation tool
- `https://github.com/icann/czds-api-client-java` -- Official ICANN Java client

---

### 3D. DNSExit (FREE)

**URL:** `https://dnsexit.com/Direct.sv?cmd=exdomains`
**What:** Daily list of expired and pending-delete .com and .net domains
**Source:** Compiled from registry data
**Cost:** Free

---

### 3E. WhoisFreaks (PAID API)

**URL:** `https://whoisfreaks.com/products/expiring-dropped-domains`

**API Endpoints:**
```
Expired:  https://files.whoisfreaks.com/v3.1/download/domainer/expired?apiKey=KEY&whois=true&date=YYYY-MM-DD
Dropped:  https://files.whoisfreaks.com/v3.3/download/domainer/dropped?apiKey=KEY&whois=true&date=YYYY-MM-DD
Cleaned:  https://files.whoisfreaks.com/v3.1/download/domainer/expired/cleaned?apiKey=KEY
```

**Parameters:** `apiKey`, `whois` (true/false), `date` (YYYY-MM-DD)
**Coverage:** 1,528+ TLDs
**Update frequency:** Daily at 03:00 UTC
**Formats:** CSV, JSON

**Pricing:**

| Plan | Monthly | Annual (per mo) | Data |
|------|---------|-----------------|------|
| Expired (no WHOIS) | $70 | $59 | Domain names only |
| Expired (with WHOIS) | $100 | $84 | + registrant, registrar, dates, nameservers |
| Expired (cleaned WHOIS) | $200 | $167 | WHOIS minus privacy-redacted entries |
| Dropped (no WHOIS) | $100 | $84 | Recently dropped names only |
| Dropped (with WHOIS) | $150 | $125 | + WHOIS data |
| Dropped (WHOIS + backlinks) | $234 | $209 | + backlink counts |
| Dropped (backlinks only) | $200 | $167 | Names + backlink data |

**Free tier:** Up to 10,000 expired/dropped domains daily at `whoisfreaks.com/resources/blog/best-expired-domains-list-free-daily-expired-domain-names-available`

---

### 3F. DomainPunch / Domain Name Filter Pro (PAID)

**URL:** `https://domainpunch.com/kb/droplists.php`
**What:** Desktop software that downloads and filters pending delete lists
**Features:** Keyword filtering, bulk WHOIS, drop date tracking
**Cost:** Software license required

---

## 4. Comparison Matrix

| Service | API? | Backorder Cost | Catch Cost (.com) | Auction Type | Est. Catch Rate | Dropping List? |
|---------|------|---------------|-------------------|--------------|-----------------|----------------|
| **DropCatch** | YES (REST, full) | Free | $59 | Public (3-day) | 60-80% (solo), ~50% market share | YES (API download) |
| **NameJet/SnapNames** | NO (partner only) | Free | $69-79 | Private (3-day) | ~25-30% market share | No |
| **Dynadot** | YES (REST + legacy) | Free ($5 min bal) | ~$10-12 | Public (auction) | Low-moderate | No |
| **GoDaddy** | CLOSED to new users | N/A (retired) | $5-30 closeout | Public auction | GD-registered only | No |
| **Park.io** | No | N/A | $99 | N/A | .io/.ly/.me only | No |
| **Sav.com** | No | Free | ~$9-12 | Private (10-day) | Low | No |
| **Pheenix** | DEFUNCT | -- | -- | -- | -- | -- |
| **Namecheap** | No backorder API | N/A | N/A | NC-registered only | N/A | No |

---

## 5. Recommended Strategy

### For automated, API-driven drop-catching of .com domains:

**Primary:** DropCatch.com API
- Only service with a comprehensive REST API for backorders, auctions, bids, AND dropping domain downloads
- Highest catch rate in the industry
- $59/catch is competitive

**Secondary:** Dynadot API
- Cheapest catches ($10-12 if uncontested)
- Full API for backorders and auctions
- Lower catch rate but worth stacking with DropCatch

**Supplementary (manual):** NameJet/SnapNames
- Place backorders on high-value targets via web UI
- Private auctions mean less competition once caught
- No API but worth the manual effort for premium names

**Data pipeline for finding targets:**
1. Use DropCatch `/v2/downloads/dropping/{type}` API for the daily dropping list
2. Supplement with ExpiredDomains.net (free, manual CSV) for filtering by metrics
3. For full automation: WhoisFreaks API ($70-100/mo) for daily pending delete feeds with WHOIS data
4. Advanced: CZDS zone file diffs for earliest possible detection (domains entering redemption, 35 days before drop)

### Timing Checklist
```
Day -35:  Domain disappears from zone file (entered redemption) -- CZDS diff detects
Day -5:   Domain enters pendingDelete -- appears on dropping lists
Day 0:    ~2:00 PM ET / 18:00 UTC -- Verisign drops the domain
```

Place backorders at least 1-2 days before the drop date. DropCatch and NameJet begin their catch attempts the moment Verisign releases the domain.

---

## Sources

- [Domain Renewal Grace Periods (DomainDetails)](https://domaindetails.com/kb/getting-started/domain-renewal-grace-periods)
- [Domain Expiration Lifecycle (CaptainDNS)](https://www.captaindns.com/en/blog/domain-lifecycle-expiration-protection)
- [Lifecycle of .com/.net Domains (aeserver)](https://www.aeserver.com/the-lifecycle-of-a-gtld-com-net/)
- [Domain Expiration to Deletion Guide (TIGM)](https://tigm.com/guides/domain-expiration-grace-redemption-guide/)
- [DropCatch API Interactive Docs](https://api.dropcatch.com/documentation)
- [DropCatch Backorder API Examples (GitHub)](https://github.com/NameBright/DropCatchBackorderExamples)
- [DropCatch Backorder API Blog Post](https://dropcatch.wordpress.com/2014/08/26/backorder-api/)
- [DropCatch How Backordering Works](https://www.dropcatch.com/hiw/backorders)
- [NameBright OAuth2 Auth Endpoint](https://api.namebright.com/auth/help)
- [Dynadot API Command List](https://www.dynadot.com/domain/api-commands)
- [Dynadot Backorder Service](https://www.dynadot.com/market/backorder)
- [GoDaddy Phases Out Backorders](https://www.godaddy.com/resources/news/godaddy-phases-out-domain-backorders)
- [GoDaddy Aftermarket API Docs](https://developer.godaddy.com/doc/endpoint/aftermarket)
- [Park.io Pricing](https://park.io/pricing)
- [SnapNames Reseller Solutions](https://www.snapnames.com/domain-reseller-solutions.action)
- [NameJet/SnapNames Merge Announcement](https://www.prweb.com/releases/namejet_and_snapnames_combine_resources_to_dominate_drop_catch_segment_of_domain_name_aftermarket/prweb13330941.htm)
- [Expired Domain Auctions Comparison (DomainDetails)](https://domaindetails.com/kb/domain-investing/expired-domain-auctions-comparison)
- [ExpiredDomains.net](https://www.expireddomains.net/)
- [ICANN CZDS Portal](https://czds.icann.org/)
- [Verisign Zone File Info](https://www.verisign.com/resources/zone-file/)
- [WhoisFreaks Expired Domains API](https://whoisfreaks.com/products/expiring-dropped-domains)
- [DNSExit Pending Delete Lists](https://dnsexit.com/Direct.sv?cmd=exdomains)
- [DomainPunch Drop Lists](https://domainpunch.com/kb/droplists.php)
- [Verisign Drop Time (Quora)](https://www.quora.com/When-does-Verisign-release-com-domains-after-theyre-pending-delete-What-time-of-the-day-Is-it-the-same-or-does-it-vary-every-day)
- [Drop Catching 101 (Domavest)](https://www.domavest.com/2026/02/drop-catching-101-how-to-snap-up.html)
- [DropCatch for Domain Sellers 2025 Guide](https://powerdomaining.com/dropcatch-for-domain-sellers/)
- [Sav.com Backorder Service](https://www.sav.com/domains/domain-backorder)
- [CZDS Dump Tool (GitHub)](https://github.com/pogzyb/czdsdump)

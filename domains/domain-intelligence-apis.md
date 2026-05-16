# Domain Intelligence APIs — Research Reference

Compiled 2026-05-02. APIs and services for scoring domain quality, brandability, and value.

---

## Table of Contents

1. [Moz API (DA/PA)](#1-moz-api)
2. [Ahrefs API (DR/Backlinks)](#2-ahrefs-api)
3. [Majestic API (TF/CF)](#3-majestic-api)
4. [WhoisXML API (Domain Age/WHOIS)](#4-whoisxml-api)
5. [BuiltWith API (Tech History)](#5-builtwith-api)
6. [Wayback Machine / CDX API (Archive History)](#6-wayback-machine--cdx-api)
7. [Google Safe Browsing API (Blacklist Check)](#7-google-safe-browsing-api)
8. [Trademark / Brand Search APIs](#8-trademark--brand-search-apis)
9. [Dictionary / Word APIs](#9-dictionary--word-apis)
10. [Domain Valuation APIs](#10-domain-valuation-apis)
11. [Bonus: DataForSEO (Budget All-in-One)](#11-bonus-dataforseo)
12. [Cost Summary & Recommendations](#12-cost-summary--recommendations)

---

## 1. Moz API

**What it provides:** Domain Authority (DA), Page Authority (PA), spam score, linking root domains, top pages.

**Why it matters for domains:** DA is the most widely-recognized domain strength metric. A previously-used domain with DA > 20 is significantly more valuable than a fresh registration. Spam score flags toxic link profiles.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://lsapi.seomoz.org/v2/` |
| Auth | HTTP Basic Auth (`access_id:secret_key`) |
| Format | POST, JSON request/response |
| Free tier | 2,500 rows/month, 1 req/10 sec |
| Paid plans | Moz Pro: $49/mo (Starter) to $299/mo (Premium) |
| Docs | https://moz.com/help/links-api |

### Key Endpoints

| Endpoint | Purpose | Key Fields Returned |
|----------|---------|-------------------|
| `/v2/url_metrics` | DA, PA, spam score for a target | `domain_authority`, `page_authority`, `spam_score`, `root_domains_to_root_domain` |
| `/v2/linking_root_domains` | Domains linking to target | domain list, DA of each linker |
| `/v2/top_pages` | Most-linked pages on domain | page URL, PA, external links |
| `/v2/link_status` | Check if specific links exist | link status, anchor text |
| `/v2/anchor_text` | Anchor text distribution | anchor text, external pages |

### Example Request

```bash
curl -X POST "https://lsapi.seomoz.org/v2/url_metrics" \
  -u "mozscape-ACCESS_ID:SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["example.com"],
    "daily_history_values": false
  }'
```

### Example Response

```json
{
  "results": [{
    "page": "example.com",
    "domain_authority": 42,
    "page_authority": 38,
    "spam_score": 3,
    "root_domains_to_root_domain": 1247,
    "external_pages_to_root_domain": 58432
  }]
}
```

### Domain Scoring Use

- DA 0: Fresh/unused domain (neutral)
- DA 1-10: Minimal history
- DA 10-30: Some legitimate usage history (good sign)
- DA 30+: Significant authority (premium value)
- Spam score > 30%: RED FLAG, likely penalized

---

## 2. Ahrefs API

**What it provides:** Domain Rating (DR), Ahrefs Rank, backlink count, referring domains, organic traffic estimates.

**Why it matters for domains:** DR is arguably the most accurate backlink strength metric. High DR + clean backlink profile = premium expired domain value. Organic traffic data shows if a domain was actually ranking.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://api.ahrefs.com/v3/` |
| Auth | Bearer token in Authorization header |
| Format | GET, JSON response |
| Free tier | None (test queries on some plans) |
| Paid plans | API access starts at Enterprise ($999/mo); standalone API $500-$10,000/mo |
| Docs | https://docs.ahrefs.com/api |

### Key Endpoints

| Endpoint | Purpose | Key Fields |
|----------|---------|-----------|
| `/v3/site-explorer/domain-rating` | DR score | `domain_rating`, `ahrefs_rank` |
| `/v3/site-explorer/backlinks` | All backlinks to target | `url_from`, `anchor`, `dr_source` |
| `/v3/site-explorer/refdomains` | Referring domains | domain list, DR of each |
| `/v3/site-explorer/metrics` | Organic traffic estimate | `organic_traffic`, `organic_keywords` |

### Example Request

```bash
curl "https://api.ahrefs.com/v3/site-explorer/domain-rating?target=example.com&date=2026-05-01" \
  -H "Authorization: Bearer YOUR_AHREFS_API_KEY" \
  -H "Accept: application/json"
```

### Example Response

```json
{
  "domain_rating": {
    "domain_rating": 67.3,
    "ahrefs_rank": 28451
  }
}
```

### Domain Scoring Use

- DR 0-10: No meaningful backlinks
- DR 10-30: Some authority
- DR 30-60: Strong domain (valuable if clean)
- DR 60+: Extremely strong (rare, high value)
- Ahrefs Rank: Lower = stronger (top 100K is excellent)

### Cost Note

Ahrefs is the gold standard but prohibitively expensive for bulk domain checking. Consider DataForSEO (section 11) as a budget alternative that provides similar backlink metrics.

---

## 3. Majestic API

**What it provides:** Trust Flow (TF), Citation Flow (CF), Topical Trust Flow, backlink counts from both "Fresh" and "Historic" indices.

**Why it matters for domains:** TF/CF ratio reveals link quality vs. quantity. TF > CF means high-quality links. CF >> TF means spammy link profile. Topical Trust Flow categorizes what niche the domain was used in.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://api.majestic.com/api/json` |
| Auth | `api_key` parameter or `authentication_token` |
| Format | GET or POST, JSON/XML response |
| Free tier | Very limited: free lookups on own verified sites only |
| Paid plans | Lite $49.99/mo, Pro $99.99/mo (includes API), Full API $399.99/mo |
| Docs | https://developer-support.majestic.com/api/ |

### Key Endpoints (Commands)

| Command | Purpose | Key Fields |
|---------|---------|-----------|
| `GetIndexItemInfo` | TF, CF, backlinks for domain/URL | `TrustFlow`, `CitationFlow`, `ExtBackLinks`, `RefDomains` |
| `GetBackLinkData` | Detailed backlink list | source URL, anchor text, TF/CF of source |
| `GetTopics` | Topical categorization | topic category, TF per topic |
| `GetRefDomains` | Referring domains | domain, TF, CF per referring domain |

### Example Request

```bash
curl "https://api.majestic.com/api/json?app_api_key=YOUR_API_KEY&cmd=GetIndexItemInfo&items=1&item0=example.com&datasource=fresh"
```

### Example Response

```json
{
  "Code": "OK",
  "DataTables": {
    "Results": {
      "Data": [{
        "Item": "example.com",
        "TrustFlow": 45,
        "CitationFlow": 52,
        "ExtBackLinks": 234567,
        "RefDomains": 8901,
        "TopicalTrustFlow_Topic_0": "Business",
        "TopicalTrustFlow_Value_0": 38
      }]
    }
  }
}
```

### Domain Scoring Use

- TF 0: No trust signals
- TF 10-20: Moderate trust
- TF 20-40: Good trust (valuable)
- TF 40+: Excellent (premium)
- TF/CF ratio > 0.8: Clean profile
- TF/CF ratio < 0.3: Spammy (red flag)
- Topical Trust Flow: Match domain name to niche = ideal

---

## 4. WhoisXML API

**What it provides:** WHOIS records, domain age (creation/expiry dates), registrant history, DNS history, domain reputation score.

**Why it matters for domains:** Domain age is a ranking factor. A domain registered in 2005 that expired is worth more than a brand-new registration. Registration history reveals if it changed hands frequently (churn = red flag).

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://www.whoisxmlapi.com/whoisserver/WhoisService` |
| Auth | `apiKey` query parameter |
| Format | GET or POST, JSON/XML response |
| Free tier | 500 credits on signup (WhoisXML); Alternative: WhoisFreaks gives 500 free credits |
| Paid plans | Starts ~$29/mo for 1,000 queries; bulk discounts available |
| Docs | https://whois.whoisxmlapi.com/documentation/making-requests |

### Key API Products

| API | Purpose | Key Fields |
|-----|---------|-----------|
| WHOIS Lookup | Current registration data | `createdDate`, `expiresDate`, `registrant`, `registrar` |
| WHOIS History | Historical registration records | array of past WHOIS records with dates |
| Domain Reputation | Safety/trust score 0-100 | `reputationScore`, `testResults` |
| DNS Lookup | Current/historical DNS | A records, MX records, nameservers |

### Example Request — WHOIS Lookup

```bash
curl "https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey=YOUR_API_KEY&domainName=example.com&outputFormat=json"
```

### Example Response

```json
{
  "WhoisRecord": {
    "domainName": "example.com",
    "createdDate": "1995-08-14T04:00:00Z",
    "updatedDate": "2024-08-14T07:01:38Z",
    "expiresDate": "2025-08-13T04:00:00Z",
    "registrarName": "RESERVED-Internet Assigned Numbers Authority",
    "estimatedDomainAge": 11217,
    "registrant": {
      "organization": "IANA",
      "country": "US"
    }
  }
}
```

### Alternative: Whoxy.com

| Item | Value |
|------|-------|
| Base URL | `https://api.whoxy.com/` |
| Pricing | $2 per 1,000 WHOIS lookups (very cheap) |
| Free tier | None, but $2 minimum |

```bash
curl "https://api.whoxy.com/?key=YOUR_KEY&whois=example.com"
```

### Domain Scoring Use

- Age > 10 years: Premium (established trust)
- Age 5-10 years: Good
- Age 1-5 years: Moderate
- Never registered before: Neutral (brandable but no SEO head start)
- Many ownership changes: Suspicious
- Privacy-protected WHOIS: Neutral (common practice)

---

## 5. BuiltWith API

**What it provides:** Current and historical technology stack for any domain — CMS, analytics, hosting, frameworks, e-commerce platforms, advertising, etc.

**Why it matters for domains:** Reveals whether a domain was used for a real business (WordPress + Stripe + Google Analytics = legitimate) vs. a parked/spam site (no tech detected). Technology history going back 41 years.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://api.builtwith.com/` |
| Auth | `KEY` query parameter |
| Format | GET, JSON/XML response |
| Free tier | Free API: 1 req/sec, basic counts only (no history) |
| Paid plans | Basic $295/mo, Pro $495/mo, Enterprise custom |
| Free API URL | `https://api.builtwith.com/free1/api.json` |
| Docs | https://api.builtwith.com/ |

### Endpoints

| Endpoint | Purpose | Access Level |
|----------|---------|-------------|
| `/free1/api.json` | Tech group counts | Free |
| `/v21/api.json` | Full current tech stack | Paid (Basic+) |
| `/v21/api.json` (with `HIDETEXT=no`) | Include tech descriptions | Paid |
| Domain Live API | Real-time scan | Paid (Pro+) |

### Example Request — Free API

```bash
curl "https://api.builtwith.com/free1/api.json?KEY=YOUR_FREE_KEY&LOOKUP=example.com"
```

### Example Response (Free)

```json
{
  "Results": [{
    "Lookup": "example.com",
    "LastUpdated": "2026-04-15",
    "Groups": [
      {"name": "analytics", "count": 3},
      {"name": "cms", "count": 1},
      {"name": "framework", "count": 2},
      {"name": "hosting", "count": 1}
    ]
  }]
}
```

### Example Request — Paid Domain API

```bash
curl "https://api.builtwith.com/v21/api.json?KEY=YOUR_PAID_KEY&LOOKUP=example.com"
```

### Domain Scoring Use

- Has CMS + Analytics + real tech: Legitimate site history (good)
- Has e-commerce platform: Was a real business (premium)
- Only parking page tech: Was parked/unused (neutral)
- No tech detected at all: Never used or long-expired (neutral)
- Had SSL + CDN + email: Professional operation (good sign)

---

## 6. Wayback Machine / CDX API

**What it provides:** Historical snapshots of any domain — when it was active, what content it had, how it changed over time. Completely free, no auth required.

**Why it matters for domains:** The single best way to check if a domain was used for a real site, spam, or adult content. Number of snapshots correlates with how seriously the domain was used. This is the MOST IMPORTANT free check for domain quality.

### API Details

| Item | Value |
|------|-------|
| Availability API URL | `https://archive.org/wayback/available` |
| CDX API URL | `https://web.archive.org/cdx/search/cdx` |
| Auth | **None required** |
| Format | GET, JSON or plain text |
| Free tier | **Completely free, unlimited** |
| Rate limits | Be polite; no hard limit but throttled if abusive |
| Docs | https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server |

### Availability API — Quick Check

```bash
# Check if any snapshot exists
curl "https://archive.org/wayback/available?url=example.com"
```

Response:
```json
{
  "url": "example.com",
  "archived_snapshots": {
    "closest": {
      "status": "200",
      "available": true,
      "url": "http://web.archive.org/web/20240101120000/http://example.com",
      "timestamp": "20240101120000"
    }
  }
}
```

### CDX API — Full History (The Power Tool)

#### Count total snapshots for a domain
```bash
curl "https://web.archive.org/cdx/search/cdx?url=example.com&matchType=domain&output=json&limit=0&showNumPages=true"
```

#### Get first and last snapshots (domain age proxy)
```bash
# First snapshot ever
curl "https://web.archive.org/cdx/search/cdx?url=example.com&output=json&limit=1&fl=timestamp,original,statuscode"

# Last snapshot
curl "https://web.archive.org/cdx/search/cdx?url=example.com&output=json&limit=-1&fastLatest=true&fl=timestamp,original,statuscode"
```

#### Get one snapshot per year (activity timeline)
```bash
curl "https://web.archive.org/cdx/search/cdx?url=example.com&output=json&collapse=timestamp:4&fl=timestamp,statuscode,mimetype"
```

#### Get all unique pages ever crawled on domain
```bash
curl "https://web.archive.org/cdx/search/cdx?url=example.com/*&output=json&fl=original&collapse=urlkey&limit=100"
```

#### Filter only successful HTML pages
```bash
curl "https://web.archive.org/cdx/search/cdx?url=example.com&output=json&filter=statuscode:200&filter=mimetype:text/html&collapse=timestamp:6&fl=timestamp,original"
```

### CDX API Parameters Reference

| Parameter | Values | Purpose |
|-----------|--------|---------|
| `url` | domain or URL (required) | Target to search |
| `matchType` | exact, prefix, host, domain | Scope of matching |
| `output` | json, text | Response format |
| `fl` | comma-separated fields | Select fields: `urlkey`, `timestamp`, `original`, `mimetype`, `statuscode`, `digest`, `length` |
| `from` / `to` | yyyyMMddhhmmss (1-14 digits) | Date range filter |
| `filter` | field:regex or !field:regex | Filter results |
| `collapse` | field or field:N | Deduplicate (N=digit precision) |
| `limit` | N or -N | Max results (negative = from end) |
| `fastLatest` | true | Optimize for last-N queries |
| `showNumPages` | true | Return only page count |

### Domain Scoring Use

- 0 snapshots: Never had content (neutral for new brands, bad for "aged" domains)
- 1-50 snapshots: Minimal use
- 50-500 snapshots: Moderate history (good)
- 500+: Heavily used site (premium if content was legitimate)
- **VIEW THE ACTUAL SNAPSHOT**: `https://web.archive.org/web/*/example.com` — visually check for spam/adult/pharma content
- First snapshot date = true domain "age" for web purposes

---

## 7. Google Safe Browsing API

**What it provides:** Checks if a URL/domain is flagged for malware, social engineering, unwanted software, or potentially harmful applications.

**Why it matters for domains:** A domain flagged by Safe Browsing is essentially blacklisted by Chrome and Google Search. This is a HARD DISQUALIFIER — never buy a flagged domain.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://safebrowsing.googleapis.com/v4/threatMatches:find` |
| Auth | API key (Google Cloud Console) |
| Format | POST, JSON |
| Free tier | **10,000 requests/day** (non-commercial use free) |
| Paid tier | Google Cloud billing for commercial use |
| Docs | https://developers.google.com/safe-browsing/v4 |

### Example Request

```bash
curl -X POST \
  "https://safebrowsing.googleapis.com/v4/threatMatches:find?key=YOUR_GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "client": {
      "clientId": "domain-scorer",
      "clientVersion": "1.0"
    },
    "threatInfo": {
      "threatTypes": [
        "MALWARE",
        "SOCIAL_ENGINEERING",
        "UNWANTED_SOFTWARE",
        "POTENTIALLY_HARMFUL_APPLICATION"
      ],
      "platformTypes": ["ANY_PLATFORM"],
      "threatEntryTypes": ["URL"],
      "threatEntries": [
        {"url": "http://example.com"},
        {"url": "https://example.com"}
      ]
    }
  }'
```

### Example Response — Clean Domain

```json
{
  "matches": []
}
```

### Example Response — Flagged Domain

```json
{
  "matches": [{
    "threatType": "MALWARE",
    "platformType": "ANY_PLATFORM",
    "threat": {"url": "http://evil-example.com"},
    "cacheDuration": "300s",
    "threatEntryType": "URL"
  }]
}
```

### Domain Scoring Use

- Empty matches array: CLEAN (proceed)
- Any match: **HARD REJECT** — do not buy this domain
- Can batch up to 500 URLs per request
- Check both `http://` and `https://` variants

---

## 8. Trademark / Brand Search APIs

**What it provides:** Check if a domain name (the word itself) is already trademarked, reducing legal risk.

**Why it matters for domains:** Buying a domain that matches an existing trademark = cease & desist letter. This check is critical for brandable domains.

### 8a. USPTO TSDR API (US Trademarks)

**Note:** The old TESS search system was retired in 2023. The new system (TEASi) has anti-bot protections. The TSDR API still works for known serial numbers/reg numbers.

| Item | Value |
|------|-------|
| Base URL | `https://tsdr.uspto.gov/` |
| Search URL | `https://tsdr.uspto.gov/caseSearch` |
| Bulk Data | https://developer.uspto.gov/api-catalog |
| Auth | None for TSDR status lookup |
| Free | Yes, fully free |
| Limitation | Cannot do keyword search via API; must use web interface or bulk XML downloads |

#### Manual search (best current approach):
```
https://www.uspto.gov/trademarks/search
```

#### TSDR Status API (if you have a serial number):
```bash
curl "https://tsdr.uspto.gov/documentdownload/status?sn=12345678&type=ST66"
```

### 8b. Trademarkia / WIPO Global Brand Database

For broader trademark searches beyond US:

| Service | URL | Notes |
|---------|-----|-------|
| Trademarkia | https://www.trademarkia.com/ | Search interface, no free API |
| WIPO Global Brand | https://branddb.wipo.int/ | Search 60M+ records across countries, free web access |
| EUIPO TMview | https://www.tmdn.org/tmview/ | European trademarks, free web access |

### 8c. Programmatic Workaround

Since no free trademark search API exists, the practical approach:

```bash
# Google search for trademark conflicts
curl "https://www.googleapis.com/customsearch/v1?key=API_KEY&cx=SEARCH_ENGINE_ID&q=%22brandname%22+trademark"

# Or use the word in brand-checking context
curl "https://www.googleapis.com/customsearch/v1?key=API_KEY&cx=SEARCH_ENGINE_ID&q=%22brandname%22+%22is+a+registered+trademark%22"
```

### Domain Scoring Use

- No trademark found: SAFE (proceed)
- Active trademark in same class (software/tech): **REJECT**
- Dead/abandoned trademark: Proceed with caution
- Trademark in unrelated class (food vs. tech): Lower risk but still flaggable

---

## 9. Dictionary / Word APIs

**What it provides:** Verify if a domain is a real English word, get definitions, parts of speech, syllable counts, pronunciation, frequency scores.

**Why it matters for domains:** Real English words as domains are extremely valuable (e.g., `frame.io`, `notion.so`). Short, pronounceable, recognizable words command premium prices.

### 9a. Free Dictionary API (Best Free Option)

| Item | Value |
|------|-------|
| Base URL | `https://api.dictionaryapi.dev/api/v2/entries/en/` |
| Auth | **None required** |
| Rate limits | **No limits** |
| Cost | **Completely free** |
| Docs | https://dictionaryapi.dev/ |

```bash
curl "https://api.dictionaryapi.dev/api/v2/entries/en/brandable"
```

Response:
```json
[{
  "word": "brandable",
  "phonetics": [{"text": "/ˈbɹændəbəl/"}],
  "meanings": [{
    "partOfSpeech": "adjective",
    "definitions": [{
      "definition": "Capable of being branded."
    }]
  }]
}]
```

404 response = not a recognized word.

### 9b. Datamuse API (Best for Linguistic Analysis)

| Item | Value |
|------|-------|
| Base URL | `https://api.datamuse.com/` |
| Auth | **None required** |
| Rate limits | **100,000 req/day** |
| Cost | **Completely free** |
| Docs | https://www.datamuse.com/api/ |

#### Check if a word exists + get metadata
```bash
curl "https://api.datamuse.com/words?sp=notion&md=dpf&max=1"
```

Response:
```json
[{
  "word": "notion",
  "score": 79425,
  "numSyllables": 2,
  "tags": ["n", "f:24.51"],
  "defs": ["n\tA general inclusive concept", "n\tAn odd or fanciful idea"]
}]
```

#### Metadata flags (`md=`)
| Flag | Returns |
|------|---------|
| `d` | Definitions |
| `p` | Parts of speech |
| `s` | Syllable count |
| `r` | Pronunciation (IPA) |
| `f` | Frequency (per million words) |

#### Useful queries for domain scoring
```bash
# Check if word exists and get frequency
curl "https://api.datamuse.com/words?sp=zovo&md=dpf&max=1"

# Find similar-sounding words (for brandability)
curl "https://api.datamuse.com/words?sl=zovo&max=5"

# Find words with similar meaning
curl "https://api.datamuse.com/words?ml=innovation&max=10&md=f"
```

### 9c. WordsAPI (via RapidAPI)

| Item | Value |
|------|-------|
| Base URL | `https://wordsapiv1.p.rapidapi.com/words/` |
| Auth | RapidAPI key (X-RapidAPI-Key header) |
| Free tier | 500 requests/month |
| Paid | $10/mo for 25,000 req |
| Docs | https://rapidapi.com/dpventures/api/wordsapi |

```bash
curl "https://wordsapiv1.p.rapidapi.com/words/notion" \
  -H "X-RapidAPI-Key: YOUR_KEY" \
  -H "X-RapidAPI-Host: wordsapiv1.p.rapidapi.com"
```

Returns definitions, synonyms, antonyms, examples, syllables, pronunciation, frequency, rhymes, and more.

### Domain Scoring Use

- Is a real word: +50 points (major value indicator)
- Frequency > 10/million: Common word (premium)
- Frequency 1-10/million: Known word (good)
- Frequency < 1/million: Rare/archaic (less value unless trendy)
- Not a word but pronounceable: Brandable (e.g., "Spotify")
- Not a word AND unpronounceable: Low value
- 1-2 syllables: Premium
- 3+ syllables: Lower value

---

## 10. Domain Valuation APIs

**What they provide:** Automated dollar-value estimates based on comparable sales, SEO metrics, domain length, TLD, and other factors.

**Why it matters for domains:** Baseline price estimates for negotiations. Not gospel, but useful for quick screening.

### 10a. GoDaddy GoValue API

| Item | Value |
|------|-------|
| Base URL | `https://api.godaddy.com/v1/domains/govalues` |
| Auth | `Authorization: sso-key API_KEY:SECRET` header |
| Free tier | Free with GoDaddy developer account (limited) |
| Paid plans | Enterprise: 5,000+ valuations/day, $109.99/mo |
| Docs | https://www.godaddy.com/help/make-a-call-to-the-govalue-api-41963 |

```bash
curl -H "Authorization: sso-key YOUR_API_KEY:YOUR_SECRET" \
  "https://api.godaddy.com/v1/domains/govalues?domainName=example.com"
```

Response includes:
- `govalue`: Estimated value in USD
- `comparable_sales`: Recent similar domain sales
- Trained on 65M+ data points and 20+ years of GoDaddy sales

### 10b. EstiBot API

| Item | Value |
|------|-------|
| Base URL | `https://www.estibot.com/appraise/api.php` |
| Auth | API key parameter |
| Free tier | None — Expert plan only ($29.99/mo) |
| Paid plans | Expert $29.99/mo (includes API access, 200 appraisals/day) |
| Batch | Up to 200 domains per request (delimiter: `>>`) |
| Docs | https://www.estibot.com/api-info |

```bash
curl "https://www.estibot.com/appraise/api.php?k=YOUR_API_KEY&d=example.com&t=cache&f=json"
```

Parameters:
- `k` = API key
- `d` = domain(s), use `>>` delimiter for bulk: `test.com>>great.com`
- `t` = `cache` (fast, cached) or `live` (fresh calculation)
- `f` = `json` or `xml`

Returns ~100 data points per domain including:
- Appraised value
- Comparable sales
- Domain length, word count
- Search volume for the keyword
- CPC value
- Extension score

### 10c. Free Alternative: Manual GoDaddy Appraisal

```bash
# No API needed — just scrape/check the web interface
# URL: https://www.godaddy.com/domain-value-appraisal/appraisal/?domain=example.com
# GoDaddy provides free single-domain appraisals via their web tool
```

### Domain Scoring Use

- GoDaddy GoValue > $5,000: Premium domain
- GoDaddy GoValue $1,000-$5,000: Good domain
- GoDaddy GoValue $100-$1,000: Moderate
- GoDaddy GoValue < $100: Low value (but could still be good for branding)
- EstiBot CPC > $5: Commercially valuable keyword
- Compare both tools: If they agree, estimate is more reliable

---

## 11. Bonus: DataForSEO

**What it provides:** Budget-friendly alternative to Ahrefs/Moz. Domain rank, backlinks, referring domains, organic keywords, SERP data. Uses its own index.

**Why it matters for domains:** Get Ahrefs-comparable data at 1/100th the cost. Pay-as-you-go model is ideal for checking individual domains.

### API Details

| Item | Value |
|------|-------|
| Base URL | `https://api.dataforseo.com/v3/` |
| Auth | HTTP Basic Auth (login:password) |
| Format | POST, JSON |
| Free tier | Free trial with limited credits |
| Minimum | $50 deposit, then pay-per-use |
| Cost | ~$0.0006 per SERP request; backlinks API $100/mo minimum |
| Docs | https://docs.dataforseo.com/ |

### Useful Endpoints for Domain Scoring

```bash
# Domain rank & backlink summary
curl -X POST "https://api.dataforseo.com/v3/backlinks/summary/live" \
  -u "login:password" \
  -H "Content-Type: application/json" \
  -d '[{"target": "example.com"}]'

# Referring domains
curl -X POST "https://api.dataforseo.com/v3/backlinks/referring_domains/live" \
  -u "login:password" \
  -H "Content-Type: application/json" \
  -d '[{"target": "example.com", "limit": 10}]'
```

Returns: `rank`, `backlinks`, `referring_domains`, `referring_domains_nofollow`, `broken_backlinks`, etc.

---

## 12. Cost Summary & Recommendations

### Free Tier Stack (Zero Cost)

These APIs can be used today with no payment:

| API | What You Get | Limit |
|-----|-------------|-------|
| Wayback CDX | Full archive history, snapshot count, dates | Unlimited |
| Google Safe Browsing | Malware/blacklist check | 10,000/day |
| Free Dictionary API | Word validation, definitions | Unlimited |
| Datamuse | Word frequency, syllables, pronunciation | 100,000/day |
| Moz (free) | DA, PA, spam score | 2,500 rows/mo |
| BuiltWith (free) | Tech category counts | 1 req/sec |

**Total cost: $0/mo. This covers 80% of what you need for domain scoring.**

### Budget Stack ($50-80/mo)

| API | What You Add | Cost |
|-----|-------------|------|
| Free stack above | Everything above | $0 |
| DataForSEO | DR-equivalent, backlinks, organic traffic | ~$50 deposit |
| EstiBot Expert | Automated valuations, 200/day | $29.99/mo |

**Total: ~$80/mo for comprehensive domain intelligence.**

### Premium Stack ($200+/mo)

| API | What You Add | Cost |
|-----|-------------|------|
| Budget stack above | Everything above | ~$80 |
| WhoisXML API | Domain age, WHOIS history | ~$29/mo |
| Majestic Pro | Trust Flow, Citation Flow | $99.99/mo |
| GoDaddy GoValue | Secondary valuation | $109.99/mo |

### Recommended Priority Order for Implementation

1. **Wayback CDX API** — Free, most informative, implement first
2. **Free Dictionary + Datamuse** — Free, instant word validation
3. **Google Safe Browsing** — Free, critical safety check
4. **Moz free tier** — Free, DA/PA baseline
5. **DataForSEO** — Cheap, fills backlink data gap
6. **EstiBot** — Cheap, automated dollar valuation
7. **WhoisXML** — Domain age/history (can substitute Whoxy at $2/1K lookups)
8. **BuiltWith free** — Nice-to-have for tech history
9. **Majestic/Ahrefs** — Premium, only if you need highest accuracy

### Quick Domain Score Formula (Using Free APIs Only)

```
SCORE = 0

# Wayback Machine (0-25 points)
if snapshots > 500: SCORE += 25
elif snapshots > 100: SCORE += 20
elif snapshots > 10: SCORE += 10
elif snapshots > 0: SCORE += 5

# Moz DA (0-25 points)
SCORE += min(DA, 25)

# Dictionary word check (0-20 points)
if is_real_word: SCORE += 15
if frequency > 10/million: SCORE += 5

# Domain properties (0-15 points)
if length <= 5: SCORE += 15
elif length <= 7: SCORE += 10
elif length <= 10: SCORE += 5

# Safety (pass/fail)
if safe_browsing_flagged: SCORE = 0  # Hard reject

# Syllables (0-10 points)
if syllables == 1: SCORE += 10
elif syllables == 2: SCORE += 7
elif syllables == 3: SCORE += 3

# TLD bonus (0-5 points)
if tld == ".com": SCORE += 5
elif tld in [".io", ".co", ".ai"]: SCORE += 3

# MAX POSSIBLE: 100
```

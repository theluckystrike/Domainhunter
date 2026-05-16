# Sprint 9: Hidden Platforms Access Guide

Generated: 2026-05-07 | Agent 5: Hidden Platforms Scout

This guide covers the 6 platforms identified in Sprint 8 that have 300K+ domains behind login walls, plus new tools discovered during this sprint. Organized by signup priority.

---

## PRIORITY 1: ExpiredDomains.net (FREE - Sign Up Immediately)

**URL:** https://www.expireddomains.net/
**Cost:** Free
**Time to set up:** 2 minutes

### Why It's Critical
- THE largest expired domain database on the internet
- 677 TLDs supported, thousands of domains updated daily
- Free registration unlocks ALL filters and search capabilities

### What You Get After Signup
- **Deleted Domains** — Available to register right now
- **Expired/Pending Delete Domains** — Backorderable before they drop
- **GoDaddy Closeout Domains** — $5-11, declining daily price
- **GoDaddy Auctions with Bids** — Updated every minute
- **Sedo Expired/Auction Domains** — Tracked on ExpiredDomains.net too

### Key Filters After Signup
- Keyword search (use: recipe, cook, food, health, fitness, finance, photo, editor, dev)
- Sort by: Backlinks (BL), Domain Pop (DP), Archive.org age
- Filter by TLD, length, hyphens

### Recommended First Search
1. Go to Deleted Domains
2. Enter keyword: "recipe" OR "cook" OR "food"
3. Sort by Domain Pop (DP) descending
4. Look for domains with DP 50+ and BL 500+
5. Cross-check top finds with OpenPageRank API

---

## PRIORITY 2: CatchDoms (FREE tier + Pro evaluation)

**URL:** https://catchdoms.com/
**Cost:** Free (blurred names) / Pro plan for full access
**Time to set up:** 2 minutes

### Why It's Important
- Aggregates 55,000+ expired domains DAILY from 12 platforms
- Quality Score system (0-100) combines DA + TF + CF + RDs + Wayback age
- Includes domains from: GoDaddy, Dynadot, DropCatch, Catched, Gname, SnapNames, BloomUp, Park.io

### What You Get
- **Free:** Browse domains, see metrics, but names are blurred. 10 domains visible.
- **Pro:** Full access to 370K+ domains, CSV export, saved searches with email alerts, API access, MCP server

### Programmatic Access
- **Apify Actor:** https://apify.com/catchdoms/expired-domains-api
- Official CatchDoms API on Apify (joined Mar 2026)
- Can integrate into daily_hunter.py pipeline

### Quality Score Guide
- **50+:** Good quality, most spam filtered out
- **30-49:** Mixed quality, manual review needed
- **Below 30:** Almost always low quality or spam

---

## PRIORITY 3: OpenPageRank API (FREE - Get API Key)

**URL:** https://www.domcop.com/openpagerank/
**Signup:** https://www.domcop.com/openpagerank/auth/signup
**Documentation:** https://www.domcop.com/openpagerank/documentation
**Cost:** Free forever
**Time to set up:** 1 minute

### Why It's Essential
- FREE alternative to Moz DA / Ahrefs DR
- 10,000 API calls per hour
- Data from Common Crawl + Common Search (open source)
- Last updated: Mar 28, 2026

### API Usage
```
GET https://openpagerank.com/api/v1.0/getPageRank?domains[]=example.com&domains[]=example2.com
Header: API-OPR: YOUR_API_KEY
```

### Returns
- `page_rank_integer` (0-10 scale)
- `page_rank_decimal` (precise score)
- `rank` (global ranking position)

### Integration Plan
Add to daily_hunter.py to automatically check PageRank for all discovered domains.

---

## PRIORITY 4: Dynadot Expired Marketplace ($5 deposit)

**URL:** https://www.dynadot.com/market
**Expired Auctions:** https://www.dynadot.com/market/auction
**Closeouts:** https://www.dynadot.com/market/expired-closeout
**Registry Expired:** https://www.dynadot.com/market/registry-expired-auction
**Cost:** Free signup + $5 minimum deposit to bid
**Time to set up:** 5 minutes

### Why It's Worth It
- Less competition than GoDaddy for expired domain auctions
- Closeout domains = fixed price, first-come-first-served (domains that got NO auction bids)
- Tracked by CatchDoms, so we can discover domains there first

### Auction Details
- Duration: 7-11 days
- Late bid extension: 5 minutes if bid placed in last 5 min
- Payment window: 48 hours after winning
- Deposits: 10% required for bids $2,000+
- Closeout pricing: Decreasing daily for 5 days after unsold auction

### Strategy
Focus on **Closeout** domains — these are domains nobody else wanted in the auction, available at declining fixed prices. Best value.

---

## PRIORITY 5: OpenRank.io (FREE bulk DA checks)

**URL:** https://openrank.io/
**Cost:** Free

### Why It's Useful
- 10,000 requests per 24 hours
- 50 domains per request = 500,000 domains/day
- "Good enough" data for large-scale domain authority comparisons
- Use alongside OpenPageRank for cross-validation

---

## LOWER PRIORITY PLATFORMS

### Sedo (Premium Market - LOW priority for budget hunting)

**URL:** https://sedo.com/
**Expiring Domains:** https://expiringdomains.sedo.com/
**Cost:** Free to browse, account needed to bid

- 2,000+ domains daily in expiring auctions
- Auctions start from $79 (premium-focused, $500-$50K+ typical)
- NOT ideal for $5-$50 budget hunting
- Already tracked by ExpiredDomains.net under Sedo sections
- JavaScript SPA — requires browser access

### Flippa (Website Marketplace - LOW priority for domains)

**URL:** https://flippa.com/
**Domains:** https://flippa.com/domains
**Cost:** Free to browse, listing starts at $29 + 10% success fee

- Average domain sale: ~$15,000
- Better for buying established websites/businesses with revenue
- GoDaddy Auctions is better for sub-$500 domain purchases
- JavaScript SPA — requires browser access

### Moonsy (PAYWALLED - skip)

**URL:** https://moonsy.com/expired_domains/
**Cost:** Paid subscription (was formerly free)

- Was popular free tool resembling ExpiredDomains.net
- Now requires paid subscription
- Better free alternatives: ExpiredDomains.net, CatchDoms, Karma.Domains
- Skip unless other options fail

---

## NEW TOOLS DISCOVERED (2025-2026)

### UpSnatch (AI-powered, from $25/mo)
**URL:** https://upsnatch.com/
- Launched early 2025
- AI "Magic Search" finds related concepts, synonyms, multilingual equivalents
- Aggregates from GoDaddy, Namecheap, Dynadot
- Smart Domain Rating + Spam Quality Score
- No free plan

### DomRaider (Relaunched 2025, curated marketplace)
**URL:** https://www.domraider.com/
- 140K+ domains, 150 countries, all pre-vetted
- TF/CF/backlink quality/index status checked before listing
- Fixed buy-now pricing (no auction stress)
- Accepts crypto (Bitcoin, Ethereum, 15+ cryptos)

### SpamZilla (Best spam detection, from $37/mo)
**URL:** https://www.spamzilla.io/
- 350K+ domains processed daily, 16 TLD sources
- Proprietary spam score 1-100
- 80+ filters (Majestic, Ahrefs, Moz, SEMrush)
- Wayback Machine integration built-in
- Free tier: 25 domain checks/month

### Karma.Domains (Free multi-platform aggregator)
**URL:** https://karma.domains/
- Aggregates: GoDaddy, DropCatch, NameJet, Sedo, Dynadot, Namesilo
- 50+ filters including DA, TF, category, price, bids
- Hourly updates for GoDaddy auctions
- Wayback Machine history analysis
- FREE to browse

### ABTdomain (Aged domain tracker)
**URL:** https://abtdomain.com/
- Tracks 20+ year old domains entering pending delete
- 1,000-1,500 aged domains per day in May 2026
- URL pattern: `abtdomain.com/expired-domains/deletion/2026-05/on-2026-05-DD`
- High-value targets due to 20+ year domain age

### ExpiredDomains.com (Free, different from .net)
**URL:** https://expireddomains.com/
- 1M+ expired domains, no signup required
- DA/PA/backlink metrics included in listings
- Daily updated with Moz DA/PA scores

### ExpiredDomains.ai (Free hourly updates)
**URL:** https://expireddomains.ai/
- Hourly-updated expired domain list
- DA/TF filtering available
- Free access, last updated Apr 21, 2026

### Domain Ronin (Desktop crawler for power users)
**URL:** https://www.domainronin.com/
- Desktop software (Win/Mac/Unix)
- Crawls 250K pages per 5 minutes
- Built-in SpamZilla spam checker
- Pulls Moz DA/PA + Majestic TF/CF metrics
- For users who want to find domains not on public lists

---

## FREE AUTHORITY CHECK APIs (Summary)

| Service | Rate Limit | Cost | Best For |
|---------|-----------|------|----------|
| OpenPageRank | 10K calls/hour | Free | Bulk PageRank checks |
| OpenRank.io | 500K domains/day | Free | Mass DA comparisons |
| Moz Link Explorer | 10 queries/month | Free | Spot-checking top candidates |
| Ahrefs Backlink Checker | Top 100 backlinks | Free | Quick backlink profile view |
| OpenLinkProfiler | Unlimited | Free | Backlink analysis, no signup |
| SEO Review Tools | Varies | Free | Web-based quick checks |

---

## RECOMMENDED DAILY WORKFLOW

1. **Morning (5 min):** Check ExpiredDomains.net deleted domains with niche keywords
2. **Morning (5 min):** Check Karma.Domains for GoDaddy closeout deals
3. **Automated:** daily_hunter.py scans via OpenPageRank API + CatchDoms Apify Actor
4. **When candidates found:** Verify with SpamZilla free (25/mo) + OpenLinkProfiler (free)
5. **If worth pursuing:** Bid on Dynadot closeouts or GoDaddy auctions
6. **Weekly:** Check ABTdomain for aged domains entering pending delete

---

## AUTOMATION INTEGRATION PLAN

### Phase 1: Free API Integration (immediate)
- Add OpenPageRank API to daily_hunter.py
- Add OpenRank.io as secondary authority check
- Use for all discovered domains automatically

### Phase 2: CatchDoms Apify Integration (30 min development)
- Use CatchDoms Apify Actor to pull daily expired domain data
- Filter by quality score 50+, DA 20+, target niche keywords
- Feed results into daily_hunter.py pipeline

### Phase 3: Full Automation (1-2 hours development)
- Combine CatchDoms data + OpenPageRank scoring + SpamZilla validation
- Auto-filter by niche keywords matching our portfolio
- Generate daily report of top 10 candidates with action items
- Set up CatchDoms Pro email alerts for high-quality domains in target niches

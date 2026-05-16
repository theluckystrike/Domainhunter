# Expired Domain Acquisition Strategy

**Date:** 2026-05-02
**Objective:** Find and acquire short (4-7 letter), brandable .com domains through expired/deleted domain channels

---

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Platform-by-Platform Guide](#platform-by-platform-guide)
3. [Discovery & Research Tools](#discovery--research-tools)
4. [Brandable Domain Generators](#brandable-domain-generators)
5. [Automation & API Access](#automation--api-access)
6. [Daily Workflow](#daily-workflow)
7. [Cost Summary](#cost-summary)
8. [Action Plan](#action-plan)

---

## Strategy Overview

### The Domain Lifecycle (When to Intercept)

```
Domain Registered
    |
    v
Expiration Date (owner fails to renew)
    |
    v
Grace Period (30-45 days, owner can still renew)
    |
    v
Redemption Period (30 days, owner can renew at higher cost)
    |
    v
Pending Delete (5 days, domain queued for deletion)
    |
    v
DROP DAY  <--- This is where you catch it
    |
    v
Available for registration (first-come, first-served)
```

**Three ways to acquire expired .com domains:**

1. **Backorder/Drop Catch** -- Place a backorder before the domain drops. A service attempts to register it the instant it becomes available. If caught and you are the only bidder, you pay the minimum. If multiple bidders, it goes to auction.

2. **Expired Auction** -- Registrars auction domains that expire on their platform before they hit the open market. GoDaddy, Dynadot, and others run these.

3. **Post-Drop Registration** -- After a domain drops and nobody catches it, it becomes available for standard registration at ~$10. This is rare for valuable short .com domains but happens for obscure/niche names.

### What Makes a Domain "Brandable"

For this strategy, target domains that are:
- 4-7 letters long
- Pronounceable (follows natural consonant-vowel patterns)
- No hyphens, no numbers
- Single word or looks like a single word
- Memorable and unique (not a generic dictionary word)
- Clean history (no spam/penalty baggage)

---

## Platform-by-Platform Guide

### 1. ExpiredDomains.net

**URL:** https://www.expireddomains.net/
**Cost:** Free (account required)
**Role:** Primary research and discovery tool

#### How to Use It

This is the single most important free tool for finding expired domains. It aggregates data from all registrars and provides daily-updated lists.

**Key Sections:**
- **Pending Delete** -- Domains that will drop in the next 1-5 days. This is where you find domains to backorder elsewhere.
- **Deleted .com** -- Domains that already dropped and may still be available for standard registration.
- **Expired .com** -- Domains that have expired but have not yet entered pending delete.

**Filters for Short Brandable .com Domains:**

1. Click "Show Filter" (red link below the tabs)
2. Set these filters:
   - **Min Length:** 4
   - **Max Length:** 7
   - **Only .com:** Yes (use the .com tab)
   - **No Hyphens:** Check
   - **No Numbers:** Check (or use the "no numbers at position" filters to remove domains like x3fg4m.com)
   - **Pattern Filter:** Use CVCVCV, CVCCV, CVCVC, VCVCV patterns (C=consonant, V=vowel) to find pronounceable names. You can enter up to 30 patterns at once.
   - **Additional:** Sort by "Available Domains" or by backlink count (ABL column) to find domains with existing SEO value.

3. For brandable names specifically, the Pattern Filter is the most powerful feature. Examples:
   - `CVCVC` finds names like "bokam", "liven", "rapid"
   - `CVCCV` finds names like "bumpy", "canto", "delta"
   - `CVCVCV` finds names like "banana", "zenodo", "kavara"

**Automation:** No official API. Scraping is possible via third-party services (Apify actors, ScrapingBee) but risks IP bans and ToS violations. Best approach: manual daily checks + CSV export for offline analysis.

**Tip:** Create a free account. The site limits results without login. With an account you get full access to all filters and can save filter presets.

---

### 2. GoDaddy Auctions

**URL:** https://auctions.godaddy.com/
**Cost:** $4.99/year membership + auction prices
**Role:** Largest expired domain auction marketplace

#### How to Use It

GoDaddy runs the largest domain auction platform. Domains expiring at GoDaddy AND domains forwarded from other registrars (including Porkbun) land here.

**Three Listing Types:**

| Type | Description | Typical Price |
|------|-------------|---------------|
| **Expiring Auctions** | 10-day auction for GoDaddy-registered domains that expired | $5 - $thousands |
| **Closeout** | Post-auction domains nobody bid on, Buy Now pricing | $5 - $11 |
| **User Listings** | Domains listed for sale by other GoDaddy users | Varies widely |

**Finding Short Brandable .com Under $20:**

1. Go to auctions.godaddy.com
2. Use Advanced Search:
   - **Extension:** .com
   - **Min Characters:** 4
   - **Max Characters:** 7
   - **Listing Type:** "Closeout" (for cheapest options, $5-$11)
   - **No Hyphens / No Numbers:** Check both
   - **Price:** Sort low to high
3. For the best deals, check the **Closeout section** daily:
   - Closeout runs for 5 days after a 10-day Expired Auction ends with no bids
   - Day 1: $11, Day 2: $10, Day 3: $9, Day 4: $6, Day 5: $5
   - If nobody buys during closeout, the domain drops to the open market

**Automation:** GoDaddy has an official Auctions API documented at https://developer.godaddy.com/doc/endpoint/auctions but access is restricted. New API key requests are reportedly being denied. Third-party scrapers exist on Apify but are fragile.

**Tip:** The closeout section is the hidden gem. Most domain investors focus on the main auctions. Check closeouts daily at the $5-$6 price point for overlooked short .com domains.

---

### 3. Porkbun

**URL:** https://porkbun.com/products/marketplace (marketplace) / No dedicated expired auction page
**Cost:** Standard registration pricing (~$10.37/year for .com)
**Role:** Feeder to GoDaddy Auctions, own marketplace for user listings

#### How It Works

Porkbun does NOT run its own expired domain auctions. Instead:
- Domains expiring at Porkbun are sent to **GoDaddy Auctions** starting at day 21 after expiration
- Porkbun has a **user marketplace** where registered users can list domains for sale
- Owners have a 30-day grace period to renew before their domain goes to auction

**What This Means for You:**
- Do not look at Porkbun for expired domain auctions -- they flow to GoDaddy
- Porkbun's marketplace is for aftermarket sales (user-set prices), not expired domains
- If you see a domain registered at Porkbun on ExpiredDomains.net's pending delete list, backorder it through DropCatch/NameJet, or wait for it to appear on GoDaddy Auctions

---

### 4. NameJet

**URL:** https://www.namejet.com/
**Cost:** Minimum backorder bid $69 (only charged if you win)
**Role:** Premium expired domain auctions with exclusive registrar partnerships

#### How to Use It

NameJet specializes in pre-release domains from premium registrars like Network Solutions and Register.com. These are often higher-quality domains because they come from older, established registrars.

**Key Features:**
- **Pre-Release Names:** Exclusive access to domains from partner registrars before they hit the open market
- **Backorders:** Place a bid (min $69) on any pending-delete domain; only charged if caught
- **3-Day Private Auction:** If multiple people backorder the same domain, all bidders compete in a private auction

**Finding Short .com Domains:**
1. Browse the auction listings at namejet.com
2. Use the search/filter to narrow by TLD (.com) and character count
3. Sort by ending time to see what is dropping soon
4. Place backorders on domains you want with minimum $69 bid

**Important:** NameJet and SnapNames share inventory since 2020. Do NOT backorder the same domain on both -- you will be bidding against yourself.

**Automation:** NameJet has a partner API (test console visible at partnertest.namejet.com) but it appears to be for approved partners/resellers only, not general public access.

---

### 5. SnapNames

**URL:** https://www.snapnames.com/
**Cost:** Minimum backorder bid $79 (only charged if you win)
**Role:** Sister platform to NameJet (shared inventory)

#### How to Use It

SnapNames and NameJet merged operations in 2020. They share the same domain inventory and auction system.

**Key Differences from NameJet:**
- Slightly higher minimum bid ($79 vs $69)
- Same domains, same auctions, same catch infrastructure
- Different interface/branding

**Recommendation:** Use NameJet instead of SnapNames (lower minimum bid, same inventory). Only use SnapNames if you find its interface more convenient.

**Backorder Deadline:** Must be placed by 9 PM PT the night before the domain's release date.

---

### 6. DropCatch

**URL:** https://www.dropcatch.com/
**Cost:** $59-$60 per backorder (only charged if caught)
**Role:** Highest catch rate for competitive drop-catching

#### How to Use It

DropCatch operates 1,200+ ICANN-accredited registrars, giving it the highest probability of catching a domain when it drops. This is the platform to use when you absolutely must catch a specific domain.

**How Backorders Work:**
1. Search for a domain on dropcatch.com
2. Place a backorder ($59 minimum)
3. DropCatch sends simultaneous registration requests from 1,200+ registrars when the domain drops
4. If caught with only your backorder: you win at $59
5. If caught with multiple backorders: 7-day public auction among all bidders

**Success Rates:**
- 60-80% for moderately competitive domains
- Lower for highly sought-after premium domains (many professional investors also use DropCatch)

**Finding Short .com Domains:**
- Browse dropcatch.com/browse for upcoming drops
- Filter by extension and character length
- Monitor ExpiredDomains.net for upcoming drops, then place backorders here

**Automation:** No public API. The platform is web-interface only. Professional domain investors use browser automation but this is against ToS.

**Tip:** DropCatch is your best bet for catching a specific domain. If you identify a valuable short .com on ExpiredDomains.net's pending delete list, place a backorder on DropCatch AND NameJet for maximum catch probability. (Unlike NameJet/SnapNames, DropCatch uses a separate auction system, so bidding on both is fine.)

---

### 7. Dynadot

**URL:** https://www.dynadot.com/market/auction
**Cost:** Free account, $5 minimum balance required, auction prices start at $1
**Role:** Growing auction platform with full API access (best for automation)

#### How to Use It

Dynadot runs its own expired domain auctions and has gained significant market share, especially for .ai, .io, and .com extensions.

**Auction Types:**
- **Expired Auctions:** 7-11 day auctions for domains that expired at Dynadot
- **Expired Closeout:** Reduced-price Buy Now for domains that did not sell at auction
- **Backorder Auctions:** Domains caught by Dynadot's drop-catch system

**Requirements:**
- Dynadot account (free)
- $5 minimum balance or a purchase of $5+ in the last 365 days
- Bids over $2,000 require a 10% deposit

**Finding Short .com Domains:**
1. Go to dynadot.com/market/auction
2. Filter by extension (.com), character length, and keyword
3. Auctions use proxy bidding (set your max, system bids incrementally)
4. Winning bidder has 48 hours to pay (enable auto-pay)

**Automation (Best-in-Class):** Dynadot offers a comprehensive API with 50+ commands:

| Command | Purpose |
|---------|---------|
| `GET_OPEN_AUCTIONS` | List all active auctions |
| `GET_AUCTION_DETAILS` | Get details for a specific auction |
| `PLACE_AUCTION_BID` | Place a bid programmatically |
| `ADD_BACKORDER_REQUEST` | Place a backorder |
| `BACKORDER_REQUEST_LIST` | Check backorder status |
| `GET_EXPIRED_CLOSEOUT_DOMAINS` | List closeout domains |
| `GET_CLOSED_AUCTIONS` | Review past auctions |

API docs: https://www.dynadot.com/domain/api-document

**Tip:** Dynadot is the only major platform with a fully documented, publicly accessible API for auction participation. This makes it the best platform for building automated monitoring and bidding scripts.

---

### 8. Park.io

**URL:** https://park.io/
**Cost:** $99 per successful catch (no cost to place backorder)
**Role:** Premium backorder service for ccTLDs (NOT .com)

#### Important Limitation

Park.io does NOT support .com backorders. It focuses exclusively on "hacker" TLDs:
- .io, .ly, .me, .to, .sh, .ac, .vc, .je, .gg

**How It Works:**
- Place a free backorder on any supported domain
- If Park.io catches it and you are the only bidder: $99 flat fee
- If multiple bidders: 10-day public auction
- No charge if they do not catch it

**Relevance to This Strategy:** Park.io is NOT relevant for .com acquisition. Include it only if expanding to alternative TLDs like .io for tech-branded domains.

---

## Discovery & Research Tools

### Free Tools

| Tool | URL | Purpose | Short Domain Filters |
|------|-----|---------|---------------------|
| **ExpiredDomains.net** | expireddomains.net | Pending delete + deleted domain lists | Length, pattern, no hyphens/numbers |
| **Micro Domains** | micro.domains | Find available short domains (5 letters or less) | Built-in length filter, sorts by price |
| **Domain Name Soup** | domainnamesoup.com | Generate 4-5 letter pronounceable domains | Wildcard patterns, vowel/consonant alternation |
| **Names4Brands** | names4brands.com | Available 6-letter domains | Pre-filtered lists by length |
| **Internet.bs Drops** | internetbs.net/en/RecentlyDroppedDomains.html | Recently dropped .com and .net | Basic list, no advanced filters |
| **WhoisFreaks Free List** | whoisfreaks.com | 10,000 expired domains daily + 100 curated | API access, TLD filtering |

### Paid Tools

| Tool | URL | Price | Key Feature |
|------|-----|-------|-------------|
| **DomCop** | domcop.com | $816-$4,272/year | 10M+ domains tracked daily, Ahrefs/Moz/Majestic metrics |
| **SpamZilla** | spamzilla.io | ~$37/month | Spam detection, clean domain filtering |
| **Domain Hunter Gatherer** | domainhuntergatherer.com | One-time ~$47-$197 | Desktop software, expired domain crawling |
| **Karma.Domains** | karma.domains | Freemium | Content history analysis, GoDaddy auction tracking |
| **UpSnatch** | upsnatch.com | Varies | AI-powered "Magic Search" across multiple platforms |
| **TheDomainRobot** | thedomainrobot.com | Varies | 20M+ records, hourly updates |

### Recommendation for This Strategy

**Start with (free):** ExpiredDomains.net + Micro Domains + WhoisFreaks free tier
**Upgrade to (paid):** DomCop (if doing this at volume) or SpamZilla (if SEO history matters)

---

## Brandable Domain Generators

These tools generate brandable names and check availability in real-time. Use them to find domains that were never registered, as a complement to the expired domain strategy.

| Tool | URL | Best For | Free? |
|------|-----|----------|-------|
| **Namelix** | namelix.com | AI-generated brandable business names | Yes |
| **DomainsGPT** | oneword.domains/domains-gpt | AI brandable names, portmanteaus, alternate spellings | Yes |
| **Instant Domain Search** | instantdomainsearch.com | Real-time availability as you type | Yes |
| **Namify** | namify.tech | LLM-generated names + trademark check + social check | Yes |
| **DecideDomain** | decidedomain.com | AI generation + real-time RDAP/WHOIS availability | Yes |
| **Domain Name Soup** | domainnamesoup.com/short-random-domain-names.php | Random pronounceable 4-5 letter names | Yes |
| **BustAName** | bustaname.com | Combine word fragments, check availability | Yes |
| **Panabee** | panabee.com | Name suggestions + social media availability | Yes |

**Strategy:** Run your target keywords through 3-4 generators, collect the best suggestions, then batch-check availability. All of these tools are free to search; you only pay when registering through a connected registrar.

**Reality Check:** Every 3-letter and 4-letter .com is already registered. Five-letter .com domains are extremely scarce for dictionary words. Your best bet for finding available short .com domains is:
1. Invented/coined words (e.g., "Zovo", "Kavix", "Plonq")
2. Expired domains that drop and are not caught
3. Creative respellings of real words

---

## Automation & API Access

### API Availability Summary

| Platform | Public API? | Free Tier? | Key Capabilities |
|----------|------------|------------|------------------|
| **ExpiredDomains.net** | No | N/A | No API at all; web scraping only option |
| **GoDaddy Auctions** | Restricted | No | API exists but new access requests denied |
| **NameJet** | Partners only | No | Partner API for approved resellers |
| **SnapNames** | Partners only | No | Same system as NameJet |
| **DropCatch** | No | N/A | Web interface only |
| **Dynadot** | Yes (full) | Yes | 50+ commands: auctions, backorders, search |
| **Park.io** | No | N/A | Web interface only |
| **WhoisFreaks** | Yes | 500 free credits | Expired domain lists, WHOIS data, availability |
| **DomCop** | Yes | No | Domain metrics and lists |

### Recommended Automation Stack

**For monitoring (what to build):**

```
Daily Cron Job
    |
    v
WhoisFreaks API (free tier)
  - Pull daily deleted .com list
  - Filter: 4-7 chars, no hyphens, no numbers
    |
    v
Pronunciation Filter (custom script)
  - Check consonant-vowel patterns
  - Score brandability
    |
    v
Availability Check
  - Dynadot API (SEARCH command) or
  - RDAP/WHOIS lookup
    |
    v
Alert (email/Slack)
  - Notify with domain + metrics
  - Direct link to register or backorder
```

**For bidding (Dynadot API example):**

```
# List open expired auctions
GET https://api.dynadot.com/api3.json?key=YOUR_KEY&command=get_open_auctions

# Place a bid
GET https://api.dynadot.com/api3.json?key=YOUR_KEY&command=place_auction_bid&domain=example.com&bid_amount=15

# Place a backorder
GET https://api.dynadot.com/api3.json?key=YOUR_KEY&command=add_backorder_request&domain=example.com
```

### WhoisFreaks Automation (Best Free Option)

- **Free tier:** 500 credits on signup, 10,000 expired domains daily, 100 curated domains daily
- **API endpoint:** `https://api.whoisfreaks.com/v1.0/domains/expiring`
- **Filters:** TLD, date range, WHOIS data
- **Format:** JSON or CSV
- **Rate limits (free):** Reasonable for daily monitoring
- **Paid plans:** Start at $19 for 5K credits

---

## Daily Workflow

### Morning Routine (15-20 minutes)

1. **Check ExpiredDomains.net Pending Delete (.com tab)**
   - Apply saved filter: 4-7 chars, no hyphens, no numbers, CVCVC/CVCCV/CVCVCV patterns
   - Note any promising domains dropping in next 1-3 days
   - Export CSV for offline review

2. **Check GoDaddy Closeouts**
   - Filter: .com, 4-7 chars, sort by price low-to-high
   - Buy any good domains at $5-$6 immediately (they sell fast)

3. **Check Dynadot Expired Auctions**
   - Filter by .com, short length
   - Place proxy bids on promising domains

4. **Place Backorders** (for domains dropping tomorrow)
   - DropCatch: $59 backorder on top picks
   - NameJet: $69 backorder on secondary picks
   - Do NOT place on both NameJet AND SnapNames (shared inventory)

### Weekly Review (30 minutes)

1. Review domains won/lost in the past week
2. Adjust bidding strategy based on competition levels
3. Run brandable name generators for new keyword ideas
4. Check WhoisFreaks curated list for any missed opportunities

---

## Cost Summary

### Minimum Viable Setup (Free/Cheap)

| Item | Cost |
|------|------|
| ExpiredDomains.net account | Free |
| GoDaddy Auctions membership | $4.99/year |
| Dynadot account + $5 balance | $5 one-time |
| WhoisFreaks free tier | Free |
| Domain registration (per domain) | ~$10-$12 |
| **Total startup cost** | **~$20** |

### Per-Domain Acquisition Costs

| Method | Cost Range | When It Happens |
|--------|-----------|-----------------|
| Post-drop registration (uncaught) | $10-$12 | Domain drops, nobody catches it |
| GoDaddy Closeout | $5-$11 | Domain goes unsold at auction |
| GoDaddy Expired Auction (no competition) | $5-$20 | Low-interest domains |
| GoDaddy Expired Auction (competitive) | $20-$500+ | Popular short .com domains |
| DropCatch backorder (sole bidder) | $59 | You are the only backorder |
| DropCatch auction (competitive) | $59-$10,000+ | Multiple backorders |
| NameJet backorder (sole bidder) | $69 | You are the only backorder |
| NameJet auction (competitive) | $69-$50,000+ | Multiple backorders, especially pre-release |
| Dynadot expired auction | $1-$500+ | Varies by domain quality |
| Dynadot closeout | $5-$15 | Post-auction unsold domains |

### Realistic Budget Expectation

For **short brandable .com domains** (4-7 letters, pronounceable):
- **Mediocre names** (odd letter combos, hard to pronounce): $5-$60
- **Decent brandable names** (pronounceable, memorable): $60-$500
- **Premium short .com** (real words, perfect brands): $500-$50,000+

**Budget recommendation:** Allocate $50-$200/month for domain acquisition. Focus on:
- GoDaddy closeouts at $5-$11 (quantity play)
- Selective DropCatch/NameJet backorders at $59-$69 (quality play)
- Dynadot expired auctions for occasional steals

---

## Action Plan

### Phase 1: Setup (Day 1)

- [ ] Create accounts on all platforms:
  - [ ] ExpiredDomains.net (free) -- https://www.expireddomains.net/register/
  - [ ] GoDaddy Auctions ($4.99/yr) -- https://auctions.godaddy.com/
  - [ ] Dynadot (free + $5 deposit) -- https://www.dynadot.com/
  - [ ] DropCatch (free) -- https://www.dropcatch.com/
  - [ ] NameJet (free) -- https://www.namejet.com/
  - [ ] WhoisFreaks (free) -- https://whoisfreaks.com/
- [ ] Save filter presets on ExpiredDomains.net for short brandable .com

### Phase 2: Daily Monitoring (Week 1-2)

- [ ] Spend 15-20 min/day on the morning routine described above
- [ ] Track all domains found in a spreadsheet (domain, source, price, status)
- [ ] Place 2-3 test backorders to understand the process
- [ ] Buy 1-2 GoDaddy closeout domains to practice

### Phase 3: Automation (Week 3-4)

- [ ] Build a WhoisFreaks API script to pull daily deleted .com list
- [ ] Add pronunciation/brandability scoring filter
- [ ] Build a Dynadot API script to monitor expired auctions
- [ ] Set up email/Slack alerts for matching domains

### Phase 4: Scale (Month 2+)

- [ ] Evaluate DomCop or SpamZilla if volume justifies cost
- [ ] Refine brandability criteria based on wins/losses
- [ ] Consider building a portfolio of brandable .com domains for resale
- [ ] Track domain registration costs vs. estimated resale value

---

## Key Insights

1. **GoDaddy Closeouts are the lowest-hanging fruit.** Domains that go through a 10-day auction with zero bids, then hit closeout at $5-$11, are often overlooked. Check daily.

2. **ExpiredDomains.net is for research, not acquisition.** Use it to find domains, then acquire them through DropCatch, NameJet, GoDaddy, or Dynadot.

3. **DropCatch has the highest catch rate** due to 1,200+ registrar accreditations. For any domain you truly want, place a backorder here.

4. **Dynadot is the best platform for automation** with its full public API supporting auction browsing, bidding, and backorders.

5. **NameJet/SnapNames share inventory.** Never backorder the same domain on both. Use NameJet (lower minimum bid).

6. **Porkbun and Park.io are not useful for .com expired domains.** Porkbun feeds into GoDaddy Auctions. Park.io only supports ccTLDs like .io and .me.

7. **The real competition is institutional.** Professional domain investors run automated systems that catch the best domains milliseconds after they drop. Your edge is finding domains they overlook: unusual brandable coinages, niche-specific terms, creative respellings.

8. **Combine strategies.** Use expired domain hunting (this document) alongside brandable name generators (Namelix, DomainsGPT) and your existing word-list approach to maximize coverage.

---

## Sources

- [ExpiredDomains.net](https://www.expireddomains.net/)
- [ExpiredDomains.net Help](https://www.expireddomains.net/help/)
- [GoDaddy Auctions](https://auctions.godaddy.com/)
- [GoDaddy Expired Domains Guide 2026](https://www.godaddy.com/resources/skills/how-do-you-find-expiring-domains)
- [GoDaddy Auctions API](https://developer.godaddy.com/doc/endpoint/auctions)
- [GoDaddy Closeout Timeline](https://www.godaddy.com/help/timeline-for-godaddy-auctions-expired-domains-42743)
- [Porkbun Expiration FAQ](https://kb.porkbun.com/article/37-what-happens-after-a-domain-expires)
- [Porkbun Expiry Stream to GoDaddy](https://domainnamewire.com/2022/03/04/porkbun-moves-expiry-stream-to-godaddy-auctions/)
- [NameJet](https://www.namejet.com/)
- [NameJet FAQ](https://www.namejet.com/faqs.action)
- [SnapNames](https://www.snapnames.com/)
- [DropCatch](https://www.dropcatch.com/)
- [DropCatch Backorders](https://www.dropcatch.com/hiw/backorders)
- [Dynadot Expired Auctions](https://www.dynadot.com/market/auction)
- [Dynadot API Documentation](https://www.dynadot.com/domain/api-document)
- [Dynadot Auction Help](https://www.dynadot.com/help/question/expired-auctions)
- [Park.io](https://park.io/)
- [Park.io FAQ](https://park.io/support)
- [WhoisFreaks Expired Domains API](https://whoisfreaks.com/products/expiring-dropped-domains)
- [WhoisFreaks Pricing](https://whoisfreaks.com/pricing/api-plans)
- [DomCop](https://www.domcop.com/)
- [DomCop Pricing](https://www.domcop.com/blog/domcop-pricing-guide/)
- [SpamZilla](https://www.spamzilla.io/)
- [Micro Domains](https://micro.domains/)
- [Domain Name Soup](https://www.domainnamesoup.com/short-random-domain-names.php)
- [Namelix](https://namelix.com/)
- [DomainsGPT](https://oneword.domains/domains-gpt)
- [DecideDomain Short Domain Strategies](https://decidedomain.com/ideas/short)
- [Expired Domain Auctions Comparison (DomainDetails)](https://domaindetails.com/kb/domain-investing/expired-domain-auctions-comparison)
- [Best Expired Domain Tools 2026 (Quirk.biz)](https://quirk.biz/the-best-expired-domain-finder-tools/)
- [CanItFlip Expired Domains Guide 2026](https://canitflip.com/expired-domains/)
- [Karma.Domains](https://karma.domains/)
- [NamePros ExpiredDomains.net Tips](https://www.namepros.com/threads/expireddomains-net-tips.1213928/)
- [DomCop Guide to Domain Drop Catching](https://www.domcop.com/blog/guide-to-domain-drop-catching/)

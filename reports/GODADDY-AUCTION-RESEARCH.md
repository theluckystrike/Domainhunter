# GoDaddy Auction System — Complete Research (Sprint 31)

**Date:** 2026-05-16 | **Agents:** 8 parallel | **Cost:** $0.00

---

## Executive Summary

GoDaddy is the DOMINANT expired domain marketplace. **29 registrars** (including GoDaddy, Wild West Domains, Tucows, Squarespace, Wix, Name.com, Hostinger, Enom) all funnel expired domains into GoDaddy Auctions BEFORE they ever reach the open drop pool.

**Key Implication**: Our targets (cytheris.com on GoDaddy, ghostautonomy.com on Wild West/GoDaddy) will go through GoDaddy's auction pipeline ~26 days after expiry. DropCatch only gets a chance ~77 days after expiry IF nobody buys at GoDaddy auction or closeout.

**Cheapest path**: Buy at GoDaddy Closeout for $5-$11 + $23 renewal = ~$28-34 total.

---

## Complete GoDaddy Expiry Timeline

```
Day 0:       Domain expires (auto-renew attempted)
Day 1-4:     Domain still active, owner can renew at standard price
Day 5:       Domain PARKED (site/email down), owner can still renew
Day 12:      Final auto-renewal attempt
Day 18-19:   Redemption period ($80+ fee to recover)
Day 26:      GoDaddy Expired Auction STARTS (10-day auction, min bid $12)
Day 30-35:   Owner CANNOT renew if there is an active bid
Day 36:      Auction ends → if no bids → CLOSEOUT begins (5-day Dutch auction)
Day 36-41:   Closeout: Buy Now price drops daily ($9→$8→$7→$6→$5)
Day 41-42:   Closeout ends. If unsold, domain released.
Day 42-72:   Registry redemption grace period (~30 days)
Day 72:      Domain removed from account, sent to registry
Day 72-77:   PENDING DELETE (5 days, no recovery possible)
Day 77+:     DOMAIN DROPS → DropCatch/NameBright/SnapNames compete
```

**Total time from expiry to public drop: ~77 days.**

---

## Our Targets: Specific Timelines

### cytheris.com (Expires Jun 4, 2026 — GoDaddy registrar)

| Day | Date | Event | Action |
|-----|------|-------|--------|
| 0 | Jun 4 | Expiry | Monitor |
| 5 | Jun 9 | Domain parked | Confirm site down |
| 26 | **Jun 30** | **GoDaddy Auction starts** | Watch/bid (need $4.99 membership) |
| 36 | **Jul 10** | **Closeout starts ($9)** | BUY if still available |
| 37 | Jul 11 | Closeout Day 2 ($8) | |
| 38 | Jul 12 | Closeout Day 3 ($7) | |
| 39 | Jul 13 | Closeout Day 4 ($6) | |
| 40 | Jul 14 | Closeout Day 5 ($5) | LAST CHANCE at closeout |
| 41 | Jul 15 | Released to registry | |
| 72 | Aug 15 | Redemption ends | |
| 77 | **Aug 20** | **DROPS** | DropCatch backup |

### ghostautonomy.com (Expires Jun 7, 2026 — Wild West Domains/GoDaddy)

| Day | Date | Event | Action |
|-----|------|-------|--------|
| 0 | Jun 7 | Expiry | Monitor |
| 5 | Jun 12 | Domain parked | Confirm site down |
| 26 | **Jul 3** | **GoDaddy Auction starts** | Watch/bid |
| 36 | **Jul 13** | **Closeout starts ($9)** | BUY if still available |
| 40 | Jul 17 | Closeout Day 5 ($5) | LAST CHANCE |
| 41 | Jul 18 | Released to registry | |
| 77 | **Aug 23** | **DROPS** | DropCatch backup |

---

## Cost Comparison: All Acquisition Paths

| Method | Cost | When | Success Rate | Notes |
|--------|------|------|-------------|-------|
| **GoDaddy Closeout Day 5** | $5 + $23 renewal = **$28** | Jul 14-17 | Medium | Cheapest. Risk: scooped on Day 1-4 |
| **GoDaddy Closeout Day 1** | $9 + $23 renewal = **$32** | Jul 10-13 | High | Beat the crowd |
| **GoDaddy Auction** | $12+ (bidding war) | Jun 30 - Jul 13 | Highest | Competitive; other bidders |
| **DropCatch backorder** | $59 (auction if contested) | ~Aug 20-23 | 40-60% | Only if GD pipeline fails entirely |
| **Dynadot backorder** | $10.99 | ~Aug 20-23 | 1-3% | Insurance only |

---

## GoDaddy API Access

### Developer API (developer.godaddy.com)
- **Auth**: `Authorization: sso-key API_KEY:API_SECRET`
- **Rate limit**: 60 req/min, 20K calls/month
- **Availability check**: Requires 50+ domains in account
- **Auction bidding**: Requires special access (email apihelp@godaddy.com)
- **No search endpoint** for auctions — must use inventory files

### Free Inventory Files (NO AUTH REQUIRED)
**URL**: https://inventory.auctions.godaddy.com/

| File | Contents |
|------|----------|
| `all_biddable_auctions.json.zip` | All domains currently in auction |
| `closeout_listings.json.zip` | All closeout domains with prices |
| `all_expiring_auctions.json.zip` | All expiring auctions |
| `auctions_ending_today.json.zip` | Auctions ending today |
| `auctions_ending_tomorrow.json.zip` | Auctions ending tomorrow |
| `recent_listings.json.zip` | Newly listed domains |

Updated daily 7-8am PST. JSON/CSV/XML formats available.

### Python Code to Monitor Closeouts:
```python
import requests, zipfile, json, io

url = "https://inventory.auctions.godaddy.com/closeout_listings.json.zip"
resp = requests.get(url)

with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
    for filename in z.namelist():
        with z.open(filename) as f:
            data = json.loads(f.read())
            for listing in data:
                if listing.get('DomainName') in ['cytheris.com', 'ghostautonomy.com']:
                    print(f"FOUND: {listing['DomainName']} - ${listing['Price']}")
```

---

## GoDaddy Auctions Account Setup

| Requirement | Cost | Notes |
|-------------|------|-------|
| GoDaddy account | Free | Regular signup |
| Auctions membership | **$4.99/year** | Required to bid/buy closeout |
| Payment method | Credit card or Good as Gold | Auto-charged on win |
| Identity verification | Free | Required for 2+ auction wins or >$1,500 |

**Optional upgrades:**
- Discount Domain Club Basic: $119.88/yr (40% off domains)
- Domain Pro: $359.88/yr ($20/mo auction credits, 60% off, investor tools)

---

## 29 Registrars Feeding GoDaddy Auctions (March 2026)

All expired domains from these registrars go through GoDaddy's auction pipeline:

1. GoDaddy
2. Wild West Domains (GoDaddy-owned)
3. Enom
4. Name.com
5. Tucows
6. Hostinger
7. Squarespace
8. Wix
9. Automattic (WordPress)
10. Key-Systems
11. 123-Reg
12. Internet.bs
13. Moniker
14. Instra
15. + 15 more GoDaddy subsidiaries and partners

---

## Revised Strategy for cytheris.com + ghostautonomy.com

### Priority 1: GoDaddy Closeout (cheapest, ~$28-34)
- Buy $4.99 GoDaddy Auctions membership NOW
- Add both domains to GoDaddy Auctions watchlist
- Script daily inventory file check starting Jun 25
- Buy at closeout Day 1 ($9+$23=$32) for safety, or Day 5 ($5+$23=$28) for cheapest

### Priority 2: GoDaddy Auction Bid (if competitive, $12-$200)
- If someone else bids, decide max bid based on domain value
- cytheris.com: max $50 (biotech name, $45.7M company, but niche)
- ghostautonomy.com: max $200 (DA 52, $220M funded, TM clear, high upside)

### Priority 3: DropCatch (backup, $59+)
- Only needed if both GoDaddy auction AND closeout are won by someone else
- Place DropCatch backorder once NameBright credentials arrive
- Also place Dynadot backorder ($10.99 insurance, 1-3% catch rate)

---

## Action Items for ClaudeChrome

1. **Go to godaddy.com** → Create account (or log in if existing)
2. **Buy Auctions membership** ($4.99/year) at auctions.godaddy.com
3. **Add to watchlist**: cytheris.com, ghostautonomy.com, bside.com
4. **Get API key** at developer.godaddy.com/keys (for future automation)
5. **Enable text/push alerts** for watched domains

---

## Key Learnings

1. **GoDaddy controls the expired domain market** — 29 registrars, dominant position
2. **DropCatch is last resort for GoDaddy domains** — only gets chance at Day 77+
3. **Closeout is the cheapest acquisition path** — $28-34 total vs $59+ DropCatch
4. **Free inventory files** are the best monitoring tool — no API key needed
5. **$4.99/year membership** unlocks everything — no need for expensive plans
6. **Identity verification since 2024** — needed for 2+ auctions or >$1,500
7. **No buyer premium** — GoDaddy doesn't charge extra fees to buyers
8. **HugeDomains (DropCatch parent)** reportedly bids on GoDaddy auctions with bots

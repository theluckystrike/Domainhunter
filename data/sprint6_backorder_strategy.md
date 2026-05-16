# Sprint 6 — Backorder Strategy Document
## Project REVENANT | Updated: 2026-05-07

---

## Executive Summary

Four domains approaching expiry within the next 30 days. Two have HIGH drop probability (taskplanner.com with clientRenewProhibited, aidevtools.com already in grace period with client hold). Two others (bestdevtools.com, finetuneai.com) are standard expiries that may or may not renew.

---

## Domain Backorder Plans

### 1. aidevtools.com — PRIORITY 1 (CRITICAL)

| Field | Value |
|-------|-------|
| **Current WHOIS Status** | Expired — in auto-renew grace period + clientHold |
| **Registry Expiry Date** | 2026-05-06 (ALREADY EXPIRED) |
| **Registrar** | NameSilo, LLC |
| **Status Codes** | `renewPeriod`, `clientHold` |
| **Name Servers** | ParkLogic (parked/monetized) |
| **Estimated Drop Date** | ~June 17, 2026 (grace ~30d + redemption ~30d + pendingDelete 5d) |
| **Drop Timeline** | Grace period ends ~Jun 5 → Redemption ~Jun 5-Jul 5 → PendingDelete ~Jul 5-10 → DROP ~Jul 10 |

**Analysis:** Domain is ALREADY EXPIRED and on clientHold with ParkLogic nameservers (monetization parking). The owner has NOT renewed despite expiry on May 6. This is a very strong signal they intend to let it drop. NameSilo grace period is typically 30 days.

**Recommended Backorder Services:**
1. DropCatch.com — Primary (best catch rate for .com)
2. SnapNames.com — Secondary
3. NameJet.com — Tertiary
4. Dynadot Backorder — Free backup

**Recommended Bid Range:** $50-150 (if auction triggered)
**Risk Assessment:** MEDIUM — Domain is on ParkLogic which sometimes auto-renews parked domains for revenue. However, clientHold suggests registrar has already suspended resolution.

---

### 2. taskplanner.com — PRIORITY 1 (CRITICAL)

| Field | Value |
|-------|-------|
| **Current WHOIS Status** | Active but clientRenewProhibited |
| **Registry Expiry Date** | 2026-05-27 (20 days away) |
| **Registrar** | GoDaddy.com, LLC |
| **Status Codes** | `clientDeleteProhibited`, `clientRenewProhibited`, `clientTransferProhibited`, `clientUpdateProhibited` |
| **Name Servers** | NS19/NS20.DOMAINCONTROL.COM (GoDaddy default) |
| **Estimated Drop Date** | ~July 9-15, 2026 |
| **Drop Timeline** | Expiry May 27 → GoDaddy grace ~42d → Auction (if GoDaddy catches) OR redemption → PendingDelete → DROP |

**Analysis:** The `clientRenewProhibited` status is the STRONGEST signal a domain will drop. This means the registrar has explicitly blocked renewal — typically because the owner requested deletion, failed payment permanently, or is in a dispute. Combined with ALL four lock statuses, this domain is almost certainly dropping. Premium .com keyword domain (registered 2004, 22 years old).

**CRITICAL NOTE:** GoDaddy domains with this status often go to GoDaddy Auctions FIRST before dropping to the open market. Must monitor GoDaddy Auctions starting May 27.

**Recommended Backorder Services:**
1. GoDaddy Auctions — MUST MONITOR (GoDaddy catches their own expiring domains)
2. DropCatch.com — If it passes GoDaddy auction
3. SnapNames.com — Secondary
4. NameJet.com — Tertiary

**Recommended Bid Range:** $75-200 (GoDaddy auction could go higher due to keyword value)
**Risk Assessment:** LOW risk of non-drop (clientRenewProhibited is definitive). MEDIUM risk of high auction price due to premium keyword.

---

### 3. bestdevtools.com — PRIORITY 2 (HIGH)

| Field | Value |
|-------|-------|
| **Current WHOIS Status** | Active |
| **Registry Expiry Date** | 2026-05-22 (15 days away) |
| **Registrar** | 1API GmbH (via DNSimple) |
| **Status Codes** | `clientTransferProhibited` |
| **Name Servers** | DNSimple (active DNS provider) |
| **Estimated Drop Date** | ~July 3-8, 2026 |
| **Drop Timeline** | Expiry May 22 → Grace ~30-45d → Redemption ~30d → PendingDelete 5d → DROP |

**Analysis:** Domain is currently ACTIVE with real DNS (DNSimple nameservers). The owner is using a premium DNS service, which suggests the domain may still be in active use. DR 15 with 60 referring domains. Created 2014. However, we have already sent a $75 WHOIS offer — if they don't renew AND don't accept our offer, it drops.

**Risk:** MODERATE chance of renewal — active DNS suggests current use. The offer may prompt them to either sell or realize they should renew.

**Recommended Backorder Services:**
1. DropCatch.com — Primary
2. SnapNames.com — Secondary
3. NameJet.com — Tertiary

**Recommended Bid Range:** $30-100 (if auction triggered)
**Risk Assessment:** HIGH risk domain gets renewed. Owner appears active (premium DNS, recent WHOIS update Nov 2025). Backorder as insurance against non-renewal.

---

### 4. finetuneai.com — PRIORITY 3 (MEDIUM)

| Field | Value |
|-------|-------|
| **Current WHOIS Status** | Active |
| **Registry Expiry Date** | 2026-05-26 (19 days away) |
| **Registrar** | NameCheap, Inc. |
| **Status Codes** | `clientTransferProhibited` |
| **Name Servers** | AWS Route53 (active infrastructure) |
| **Estimated Drop Date** | ~July 8-12, 2026 |
| **Drop Timeline** | Expiry May 26 → NameCheap grace ~30d → Redemption ~30d → PendingDelete 5d → DROP |

**Analysis:** Domain uses AWS Route53 nameservers, suggesting active infrastructure/project. DR 5 with 10 referring domains — relatively low authority. Created 2021 (5 years old). "FinetuneAI" is a hot keyword in the AI/ML space. NameCheap typically sends multiple renewal reminders.

**Risk:** HIGH chance of renewal — AWS infrastructure + AI keyword relevance in 2026 market makes this likely to be renewed. However, many AI startups have folded, so there's a chance the project is dead but domain auto-renews.

**Recommended Backorder Services:**
1. DropCatch.com — Primary
2. SnapNames.com — Secondary
3. Dynadot Backorder — Free backup

**Recommended Bid Range:** $20-75 (lower value due to DR 5)
**Risk Assessment:** HIGH risk of renewal. Low priority given modest backlink profile. Worth a free/cheap backorder as a lottery ticket.

---

## Backorder Service Comparison

| Service | Cost to Place | Min Auction | Catch Rate | Notes |
|---------|--------------|-------------|------------|-------|
| DropCatch.com | Free (pay if caught) | $59 | Highest | Best for .com, Discount Club $10 |
| SnapNames.com | Free (pay if caught) | $69 | High | Good secondary option |
| NameJet.com | Free (pay if caught) | $69 | High | Partners with SnapNames |
| GoDaddy Auctions | Membership $5/yr | Varies | N/A | For GoDaddy-registered expiries only |
| Dynadot Backorder | Free | $10 | Lower | Good free backup option |

---

## Budget Allocation for Backorders

| Domain | Max Bid | Probability of Catching | Expected Cost |
|--------|---------|------------------------|---------------|
| taskplanner.com | $200 | 70% (if drops) | $100-200 |
| aidevtools.com | $150 | 80% (if drops) | $59-150 |
| bestdevtools.com | $100 | 30% (if drops) | $59-100 |
| finetuneai.com | $75 | 20% (if drops) | $20-75 |
| **Total max exposure** | **$525** | | |

**Budget remaining: $565.82** — Sufficient to cover all backorders even at maximum bids.

---

## Action Items

1. **IMMEDIATE (Today):**
   - Place backorders on DropCatch for all 4 domains
   - Place backorders on SnapNames for taskplanner.com and aidevtools.com
   - Set up GoDaddy Auctions monitoring for taskplanner.com

2. **May 22 (bestdevtools.com expiry):**
   - Monitor WHOIS for status changes
   - Check if offer was accepted/rejected

3. **May 26-27 (finetuneai.com + taskplanner.com expiry):**
   - Monitor WHOIS daily for status transitions
   - Watch for redemptionPeriod or pendingDelete status

4. **June 5-17 (aidevtools.com grace period end):**
   - Daily WHOIS checks
   - Watch for transition from renewPeriod to redemptionPeriod

5. **July 1-15 (estimated drop window for all):**
   - Maximum alertness
   - Ensure backorder accounts are funded
   - Be ready to bid in auctions within minutes

---

## Registrar-Specific Drop Behavior

### GoDaddy (taskplanner.com):
- Grace period: 18-42 days after expiry
- GoDaddy catches and auctions their own expiring domains
- If domain gets 0 bids at GoDaddy auction, it may release to open market
- Timeline: Expiry → Parked (18d) → Auction (10d) → Redemption (30d) → PendingDelete (5d)

### NameSilo (aidevtools.com):
- Grace period: 30 days after expiry
- Redemption period: 30 days (extra fee ~$100)
- NameSilo does NOT run their own auction — domains drop to open registry
- Best chance: DropCatch/SnapNames backorder

### 1API/DNSimple (bestdevtools.com):
- Grace period: Typically 30-45 days
- Smaller registrar — less likely to catch for own auction
- Domains typically drop to open registry
- Good candidate for DropCatch

### NameCheap (finetuneai.com):
- Grace period: 30 days (renewal at normal price)
- Redemption period: 30 days (extra fee ~$150)
- NameCheap runs auctions on some premium expiring domains
- Monitor NameCheap marketplace as well

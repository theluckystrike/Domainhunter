# CATCH WINDOW PLAYBOOK: June-July 2026

**Print this. Pin it to your wall. Read it at 3am.**

Last updated: 2026-05-16

---

## QUICK REFERENCE — DOMAINS & MAX BIDS

| Domain | Expires | GD Auction | GD Closeout | Max Bid | Post-Catch |
|--------|---------|-----------|-------------|---------|------------|
| cytheris.com | Jun 4 | ~Jun 30 | ~Jul 10 | $50 | FLIP $5K-$15K |
| ghostautonomy.com | Jun 7 | ~Jul 3 | ~Jul 13 | $200 | FLIP $20K-$50K |
| bside.com | Jun 23 | ~Jul 19 | ~Jul 29 | $500 | FLIP $5K-$25K |
| guerrameats.com | clientHold | ~Jun 26 pD | Dynadot catch | $10.99 | DEVELOP (ETV $11K/mo) |
| sunnyray.org | autoRenew | ~Jun 30 pD | Dynadot catch | $10.99 | DEVELOP (ETV $2.8K/mo) |
| globalgeopark.org | autoRenew | ~Jul 1 pD | Dynadot catch | $10.99 | DEVELOP (DA 49) |

**Key:**
- "GD Auction" = when 10-day GoDaddy expired auction starts
- "GD Closeout" = when 5-day declining-price Buy Now begins
- "pD" = pendingDelete window (5 days before public drop)
- Max Bid = ABSOLUTE WALK-AWAY price. No exceptions. Not even at 3am.

---

## SCENARIO A: GODADDY CLOSEOUT NOTIFICATION

**What happened:** Your daily GoDaddy inventory scan found a domain in closeout. Or you checked manually and it is there.

**Step-by-step:**

1. Open: `https://auctions.godaddy.com/beta?q=DOMAIN`
2. Confirm auction type says "Closeout" (NOT "Expired Auction")
3. Check the current Buy Now price:
   - Day 1: $50 + renewal
   - Day 2: $40 + renewal
   - Day 3: $30 + renewal
   - Day 4: $11 + renewal  <-- SWEET SPOT
   - Day 5: $5 + renewal   <-- CHEAPEST (but risky)
4. **Decision matrix:**
   - ghostautonomy.com: Buy on Day 4 ($11+renewal = ~$22-$34 total). Day 5 only if no competition signals.
   - cytheris.com: Buy on Day 5 ($5+renewal = ~$16-$28). Niche pharma name = zero competition.
   - bside.com: Buy on Day 1 ($50+renewal). Premium 5L .com = someone WILL buy it.
5. Click "Buy Now" button
6. Confirm payment (credit card on file)
7. Domain assigned to your GoDaddy account within minutes
8. Proceed to POST-CATCH CHECKLIST below

**URL for closeout inventory file:**
`https://inventory.auctions.godaddy.com/` --> download `closeout_service_auctions` CSV

**Automation:** `python3 scripts/godaddy_monitor.py` scans inventory daily at 7am PST.

---

## SCENARIO B: GODADDY AUCTION — OUTBID ALERT

**What happened:** Domain is in a 10-day GoDaddy expired auction and someone bid, or you got outbid.

**Step-by-step:**

1. Open: `https://auctions.godaddy.com/beta?q=DOMAIN`
2. Note: current bid, number of bidders, time remaining
3. **If 0 bidders (just you):**
   - You are winning. Do nothing until last 60 seconds.
   - GoDaddy has 5-minute snipe protection (bids in final minutes extend auction).
4. **If 1-3 bidders and price < max bid:**
   - Set proxy bid at your max. GoDaddy auto-bids $5-$25 increments on your behalf.
   - DO NOT increase max bid beyond the table above.
5. **If 5+ bidders OR price > max bid:**
   - WALK AWAY. Close the tab. Do not look back.
   - The domain will reach closeout (Scenario A) or pendingDelete (Scenario D).
   - You lose nothing. All platforms refund if you don't win.

**Snipe strategy (if bidding):**
- Place first bid on Day 8-9 of the 10-day auction (never earlier)
- Use proxy bidding (set your max, let GoDaddy auto-increment)
- Late bidding avoids triggering price-watcher alerts for other bidders

**Max bids (hard caps):**
| Domain | Max Auction Bid | Walk Away Above |
|--------|----------------|-----------------|
| cytheris.com | $50 | $50 |
| ghostautonomy.com | $200 | $200 |
| bside.com | $500 | $500 |

---

## SCENARIO C: DYNADOT AUTO-CATCH

**What happened:** Dynadot notification says a domain was caught. Or you see it in your Dynadot account.

**This applies to:** guerrameats.com, sunnyray.org, globalgeopark.org

**What actually happened under the hood:**
1. Domain entered pendingDelete at the registry (5-day countdown)
2. Dynadot's 15 registrar accreditations raced against DropCatch's 1,201
3. Dynadot won the race (10-25% chance for .org, 1-3% for .com)
4. Domain was auto-registered under your Dynadot account
5. $10.99 was charged from your Dynadot balance

**Immediate actions (within 1 hour):**
1. Log in to Dynadot: `https://www.dynadot.com/account/domain/name/list.html`
2. Confirm domain appears in your domain list with status "Active"
3. Verify you have full control (can change NS, transfer, etc.)
4. Proceed to POST-CATCH CHECKLIST below

**If Dynadot balance was insufficient:**
- Catch FAILS. Domain goes to next competing registrar.
- This is why Dynadot balance must be $35+ BEFORE the catch window opens.

---

## SCENARIO D: DROPCATCH CATCH (BACKUP)

**Only relevant if:** GoDaddy pipeline fails entirely for ghostautonomy.com/cytheris.com (domain passes through auction + closeout unsold, ~Day 41+), OR for guerrameats.com if Dynadot fails to catch.

**What happened:** DropCatch caught the domain at pendingDelete drop.

**Two sub-scenarios:**

### D1: Solo catch (you are the only backorder holder)
- DropCatch charges $59 to your account
- Domain transferred to your DropCatch/NameBright account within 24-48 hours
- Proceed to POST-CATCH CHECKLIST

### D2: Multiple backorder holders (auction starts)
- DropCatch notifies you: "Domain caught! Auction starting."
- 3-day public auction begins (ANYONE can bid, not just backorder holders)
- Bid increments: <$99 = $5 min; $100-$499 = $10; $500-$1000 = $25; $1000+ = $100
- Snipe protection: bids in last 5 minutes extend auction by 5 minutes
- **Your max bids:**
  - guerrameats.com: $200
  - ghostautonomy.com: $200
  - cytheris.com: $50
- If price exceeds your max: WALK AWAY. You lose nothing ($59 refunded).

**DropCatch account URL:** `https://www.dropcatch.com/account`
**Backorder management:** `https://www.dropcatch.com/account/backorders`

---

## SCENARIO E: DOMAIN UNEXPECTEDLY RENEWED

**How to detect:**
- RDAP check shows EPP status changed from `clientRenewProhibited` to `ok`
- Or: domain resolves again (DNS came back to life)
- Or: GoDaddy auction never appears past expected date (+3 days buffer)
- daemon_scheduler.py fires an alert: "Status change detected: ok (renewed)"

**What to do:**
1. Confirm renewal via RDAP: `python3 scripts/drop_monitor.py --domain DOMAIN`
2. Remove domain from all backorder queues (Dynadot, DropCatch)
3. Update `data/backorder_queue.json` — set status to "RENEWED_DEAD"
4. Update `data/sprint29_drop_countdown.json` — remove entry
5. Reallocate budget to remaining domains
6. Do NOT contact the registrant. Do NOT make an offer. Move on.

**Budget reallocation priority:**
- If ghostautonomy renewed: shift $200 reserve to bside.com closeout budget
- If guerrameats renewed: shift $70 to DropCatch backorders for sunnyray/globalgeopark
- If a Tier S renewed: no budget impact ($10.99 Dynadot refunds automatically)

---

## POST-CATCH CHECKLIST (applies to ALL scenarios)

Do this IN ORDER within 24 hours of catching any domain:

### Hour 0-1: Secure the Domain

- [ ] Verify domain is in your registrar account with full control
- [ ] Enable registrar lock (clientTransferProhibited)
- [ ] Enable WHOIS privacy
- [ ] Set auto-renew ON
- [ ] Transfer DNS to Cloudflare:
  1. Log in to `dash.cloudflare.com`
  2. "Add a Site" --> enter domain
  3. Select Free plan
  4. Copy the two Cloudflare nameservers
  5. Go back to registrar (Dynadot/GoDaddy/DropCatch) and update NS
  6. Wait 15-60 min for propagation

### Hour 1-4: Deploy & Verify

- [ ] Run: `python3 scripts/post_catch_executor.py DOMAIN`
  - This deploys landing page, sets up GSC, submits sitemap
  - Use `--dry-run` first if nervous
- [ ] Verify site loads at `https://DOMAIN`
- [ ] Check Ahrefs/Moz that DA/backlinks survived the expiry gap
- [ ] Set up Google Search Console: `https://search.google.com/search-console`
- [ ] Submit sitemap.xml to GSC

### Hour 4-24: Monetize

- [ ] List on Afternic: `https://www.afternic.com/sell` (GoDaddy-integrated, highest traffic)
- [ ] List on Dan.com: `https://www.dan.com/sell` (lower commission, installment payments)
- [ ] List on Sedo: `https://sedo.com/us/sell-domains/` (backup marketplace)
- [ ] Set BIN prices per domain:
  - ghostautonomy.com: $15,000 Afternic / $12,000 Dan.com
  - cytheris.com: $2,500 BIN / $500 minimum offer
  - bside.com: $25,000 Afternic / $20,000 Dan.com
  - guerrameats.com: DO NOT LIST (develop instead)
  - sunnyray.org: DO NOT LIST (develop instead)
  - globalgeopark.org: $5,000 BIN (DA 49 premium)

### Day 2-7: Content & Outreach

- [ ] Deploy topically-aligned content (3-5 pages minimum)
- [ ] Check Wayback Machine for recoverable historical content
- [ ] Monitor GSC for indexing and impressions
- [ ] For DEVELOP domains: begin content strategy
- [ ] For FLIP domains: identify 3-5 potential end-user buyers

### Ongoing:

- [ ] Update `data/portfolio.json` with new acquisition
- [ ] Update DASHBOARD.html
- [ ] Track DA/DR weekly (expect 10-20% DA loss from expiry gap, recovers in 2-3 months)

---

## PAYMENT VERIFICATION

Check ALL of these BEFORE June 1:

| Platform | Method | Status | Action Needed |
|----------|--------|--------|---------------|
| GoDaddy | Credit card on file | Membership confirmed (conf# 4082361684) | Verify card not expired |
| Dynadot | Account balance | $25.00 current | TOP UP TO $35 by Jun 15 |
| DropCatch | NameBright account | Verification pending | COMPLETE ID verification by Jun 1 |
| SnapNames | N/A | No account | CREATE account by Jun 1 (optional) |

**Critical blockers (from sprint 28):**
1. DropCatch verification (government ID + selfie) -- DEADLINE JUN 1
2. Dynadot top-up (+$10 minimum, recommend +$25 to reach $50) -- DEADLINE JUN 15
3. GoDaddy credit card -- verify not expiring before August

**Total max exposure if everything drops perfectly:** ~$313
**Realistic exposure (most likely scenario):** $50-$150
**Available budget:** $565.02

---

## DAILY ROUTINE DURING CATCH WINDOW (5 minutes)

**Every morning, 9:00 AM local (do this on your phone if needed):**

```
[ ] 1. Check daemon status:
      python3 scripts/daemon_scheduler.py status

[ ] 2. Check for overnight alerts:
      - Slack channel
      - Email inbox (search: "domainhunter" or "domain alert")

[ ] 3. Quick RDAP scan (critical domains only):
      python3 scripts/drop_monitor.py --tier critical

[ ] 4. GoDaddy inventory check (July 1 onwards):
      python3 scripts/godaddy_monitor.py
      OR manual: https://auctions.godaddy.com/beta?q=ghostautonomy.com

[ ] 5. Glance at dashboard:
      open DASHBOARD.html
```

**Time-sensitive windows (set phone alarms):**

| Date Range | Alarm Time | What to Check |
|------------|-----------|---------------|
| Jun 21-26 | 2:00 PM EDT | guerrameats.com pendingDelete/drop |
| Jun 25-30 | 2:00 PM EDT | sunnyray.org pendingDelete/drop |
| Jun 26-Jul 1 | 2:00 PM EDT | globalgeopark.org pendingDelete/drop |
| Jul 3-12 | 9:00 AM + 9:00 PM | ghostautonomy GoDaddy auction |
| Jul 13-17 | Every 4 hours | ghostautonomy closeout window |
| Jun 30-Jul 14 | 9:00 AM + 9:00 PM | cytheris GoDaddy auction |
| Jul 14-19 | Every 4 hours | cytheris closeout window |

**Verisign .com drops happen between 2:00-2:30 PM EDT daily.**

---

## WHAT TO DO IF SOMETHING BREAKS

### Daemon dies

**Symptoms:** No alerts, no log entries, `daemon_scheduler.py status` shows "not running"

**Fix (30 seconds):**
```bash
cd /Users/mike/Desktop/domainhunter
python3 scripts/daemon_scheduler.py start
python3 scripts/daemon_scheduler.py status   # confirm "running"
```

**If it won't start:**
```bash
# Check logs
tail -50 logs/daemon_scheduler.log

# Nuclear restart
python3 scripts/daemon_scheduler.py stop
rm -f logs/.daemon.pid
python3 scripts/daemon_scheduler.py start
```

**Temporary workaround while debugging:**
```bash
python3 scripts/daemon_scheduler.py run-once   # runs all tasks immediately
```

---

### GoDaddy inventory file changes format

**Symptoms:** `godaddy_monitor.py` errors out, can't parse CSV/JSON

**Manual workaround:**
1. Go to `https://inventory.auctions.godaddy.com/`
2. Download `metadata.json` -- check file names/formats
3. Download the CSV file manually
4. Search (Cmd+F) for your domain names
5. If domain found: note auction type, price, end date
6. Act on Scenario A or B above

**Long-term fix:** Update the parser in `scripts/godaddy_monitor.py`

---

### You're on a plane during closeout window

**Pre-flight checklist (do this before boarding):**
1. Set a proxy bid on GoDaddy at your max if domain is in auction
2. If domain is entering closeout tomorrow, BUY IT NOW before boarding (even at Day 1 price)
3. Confirm DropCatch + Dynadot backorders are active as fallback
4. Text a trusted friend the GoDaddy login + instructions: "If X appears at closeout for <$50, buy it"

**On-flight (if you have WiFi):**
- GoDaddy Investor mobile app works on plane WiFi
- `https://auctions.godaddy.com/beta` works in mobile browser
- Closeout = Buy Now = one click. No bidding war. Just pay.

**After landing:**
- Run daily routine immediately
- Check email/Slack for any alerts fired while offline

---

### Your credit card is declined

**GoDaddy:**
- Payment due within 48 hours of winning auction
- If declined: log in immediately, update card, retry
- If you can't fix in 48 hours: you LOSE the domain AND may get account flagged
- **Prevention:** Add a backup payment method NOW (PayPal or second card)

**Dynadot:**
- Catch uses pre-loaded balance. No card decline possible IF balance is sufficient.
- If balance is $0 at catch time: catch FAILS silently. Domain goes to competitor.
- **Prevention:** Top up to $50 now. Check balance weekly.

**DropCatch:**
- $59 charged post-catch. If card fails: 7-day grace period to update payment.
- Less urgent than GoDaddy but still fix immediately.

---

### A domain you weren't tracking appears at closeout

**What happened:** While scanning GoDaddy inventory for your targets, you spot an interesting domain in closeout at $5-$11.

**Decision framework (60 seconds):**
1. Is it a .com? (yes = continue, no = skip unless .org with DA 30+)
2. Quick-check DA: `https://moz.com/link-explorer` (free 10 queries/month)
3. Is DA > 20? (yes = consider, no = skip)
4. Is it brandable/pronounceable? (yes = buy, no = skip)
5. Any obvious trademark issue? (company name = check, generic word = safe)
6. Price < $30 total? BUY. You can always flip a DA 20+ .com for $200+.

---

## TIMELINE CHEAT SHEET

```
TODAY (May 16) -----> Jun 1: PREP COMPLETE (accounts, payments, backorders)
                      Jun 4: cytheris.com EXPIRES
                      Jun 7: ghostautonomy.com EXPIRES
                      Jun 21-26: guerrameats.com pendingDelete/DROP
                      Jun 23: bside.com EXPIRES
                      Jun 25-30: sunnyray.org pendingDelete/DROP
                      Jun 26-Jul 1: globalgeopark.org pendingDelete/DROP
                      Jun 30: cytheris.com GD AUCTION starts
                      Jul 3: ghostautonomy.com GD AUCTION starts
                      Jul 10-14: cytheris.com GD CLOSEOUT
                      Jul 13-17: ghostautonomy.com GD CLOSEOUT
                      Jul 19: bside.com GD AUCTION starts
                      Jul 29: bside.com GD CLOSEOUT
                      Aug 13-18: ghostautonomy.com pendingDelete (if GD pipeline failed)
                      Aug 23-28: cytheris.com pendingDelete (if GD pipeline failed)
```

**The golden window is June 21 - July 17.** Four weeks where 5 of 6 domains reach their catch point. Be ready.

---

## EMERGENCY CONTACTS & URLS

| What | URL/Command |
|------|-------------|
| GoDaddy Auctions | `https://auctions.godaddy.com/beta` |
| GoDaddy Inventory | `https://inventory.auctions.godaddy.com/` |
| Dynadot Account | `https://www.dynadot.com/account/domain/name/list.html` |
| DropCatch Backorders | `https://www.dropcatch.com/account/backorders` |
| Cloudflare Dashboard | `https://dash.cloudflare.com` |
| RDAP Check (.com) | `https://rdap.verisign.com/com/v1/domain/DOMAIN` |
| RDAP Check (.org) | `https://rdap.org/domain/DOMAIN` |
| Daemon start | `python3 scripts/daemon_scheduler.py start` |
| Manual RDAP scan | `python3 scripts/drop_monitor.py --tier critical` |
| GoDaddy scan | `python3 scripts/godaddy_monitor.py` |
| Post-catch script | `python3 scripts/post_catch_executor.py DOMAIN` |
| Afternic sell | `https://www.afternic.com/sell` |
| Dan.com sell | `https://www.dan.com/sell` |

---

## ONE-LINE DECISION RULES

- **Under max bid?** BUY.
- **Over max bid?** WALK AWAY. No exceptions.
- **Closeout Day 4-5?** BUY IMMEDIATELY (ghostautonomy, cytheris).
- **Closeout Day 1?** BUY IMMEDIATELY (bside only -- too competitive to wait).
- **Dynadot balance < $11?** TOP UP NOW.
- **DropCatch not verified?** FIX TODAY.
- **Unsure if domain is worth it at 3am?** If it is on THIS LIST, it is worth it. You already did the research. Trust the plan.

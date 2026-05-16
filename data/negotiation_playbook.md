# Domain Acquisition Negotiation Playbook

## Counter-Offer Response Matrix

| Domain | Open ($) | Counter 1 ($) | Counter 2 ($) | Walk-Away ($) | Strategy |
|--------|----------|---------------|---------------|---------------|----------|
| devhub.io | 500 | 750 | 1,000 | 1,000 | Best authority asset. DR 27 + ethereum.org backlink is rare. Worth stretching to $1K. |
| apitools.com | 200 | 300 | 400 | 400 | 69 GitHub mentions + Red Hat docs give it real SEO juice. Dynadot marketplace. |
| sitegrader.com | 100 | 200 | 300 | 300 | 18-year domain age is valuable. SEO tool keyword exact match. |
| imageeditor.net | 75 | 100 | 150 | 150 | High search volume (673K/mo) but .net limits ceiling. |
| codeguide.com | 50 | 75 | 100 | 100 | 25-year .com but likely parked/unresponsive owner. Low effort, low expectations. |
| bestdevtools.com | 75 | 100 | 150 | 150 | Expires May 22 -- may drop for free. Only offer if owner engages. |
| taskplanner.com | 75 | 100 | 150 | 150 | clientRenewProhibited flag -- likely drops. Offer is insurance. |
| codetools.com | 50 | 75 | 100 | 100 | 26-year .com, probably parked. Minimal investment. |
| prompttools.com | 50 | 75 | 100 | 100 | AI prompt keyword trending. Low-ball because current owner may not know value. |

## Escalation Strategy

### Phase 1: Initial Offer (Days 1-3)
- Submit opening bid at listed offer price
- For marketplace domains (Afternic, Dynadot): use platform's Make Offer feature
- For WHOIS domains: send professional email via extracted contact
- Tone: casual, developer-to-developer, budget-constrained

### Phase 2: Wait Period (Days 4-14)
- No contact for 10 days after initial offer
- Monitor marketplace for any counter-offers
- Check if domain status changes (transferred, renewed, etc.)

### Phase 3: Follow-Up (Day 14)
- Send exactly ONE follow-up (CAN-SPAM compliance, MAX_FOLLOWUPS = 1)
- Reference original offer
- Slight urgency: "wrapping up my domain acquisition phase"
- Do NOT increase offer in follow-up

### Phase 4: Counter-Offer Response (If received)
1. Counter <= Walk-Away: Accept immediately if <= max_usd, counter once if between offer and max
2. Counter > Walk-Away: Politely decline with "budget won't stretch that far"
3. Never counter more than twice total
4. Always use escrow (Escrow.com or marketplace native)

### Phase 5: Walk-Away (Day 21+)
- If no response after follow-up: mark as "unresponsive" and move on
- If counter exceeds walk-away: thank them and close
- Never re-engage a walked-away domain for at least 90 days

## Timing Recommendations

### Best Days to Send Offers
- **Tuesday-Thursday**: Highest response rates for business email
- **10am-2pm recipient local time**: When inboxes are actively monitored
- Avoid: Fridays, weekends, holidays

### Marketplace-Specific Timing
- **Afternic**: Offers visible immediately. Submit Tuesday AM.
- **Dynadot**: Auction/offer system. Check if BIN available first.
- **WHOIS direct**: Tuesday-Wednesday morning sends.

### Expiration-Adjacent Domains
- **bestdevtools.com** (expires May 22): Wait until May 20. If not renewed, prepare for drop catch. If renewed, no offer needed.
- **taskplanner.com** (clientRenewProhibited): Monitor daily. If status changes to pendingDelete, prepare for drop catch instead of paying.

### Follow-Up Spacing
- First contact -> Follow-up: exactly 14 days
- Follow-up -> Walk-away: 7 days
- Walk-away -> Re-engagement: minimum 90 days
- Maximum follow-ups per domain: 1 (hard limit, CAN-SPAM)

## Response Templates

### If Owner Asks "What's Your Best Offer?"
> "I appreciate you engaging. My budget for this specific domain is [Counter 1 price].
> I know that may be below market rate, but I'm a solo developer and this is what
> I can work with. Happy to use Escrow.com for a smooth transaction."

### If Owner Says "Not For Sale"
> "Totally understand. If that ever changes, I'd love to hear from you.
> Thanks for your time."

### If Owner Counters Above Walk-Away
> "Thanks for the counter. Unfortunately [amount] is above my budget for this project.
> If you'd consider [walk-away price], I can move quickly. Otherwise, I understand
> and wish you the best with the domain."

### If Owner Accepts
> "Great, thank you! I'd like to use Escrow.com to handle the transaction.
> I'll initiate the escrow and send you the link. What email should I use
> for the escrow invitation?"

## Risk Assessment

### High-Confidence Acquisitions (>50% chance)
- **bestdevtools.com**: Likely drops May 22 for free
- **taskplanner.com**: clientRenewProhibited = probable drop
- **imageeditor.net**: .net owners often undervalue

### Medium-Confidence (25-50%)
- **sitegrader.com**: 18yr domain, owner may be attached
- **prompttools.com**: AI hype may inflate owner expectations
- **apitools.com**: Dynadot marketplace = owner is actively selling

### Low-Confidence (<25%)
- **devhub.io**: Active backlink profile = owner likely knows value
- **codeguide.com**: 25yr .com owners rarely sell cheap
- **codetools.com**: 26yr .com, same pattern

## Budget Summary

| Scenario | Total Spend |
|----------|-------------|
| All at opening offers | $1,150 |
| All at walk-away prices | $2,600 |
| Realistic (mix of opens, counters, drops) | $800 - $1,500 |
| Drop catches only (bestdevtools + taskplanner) | $20 - $50 |

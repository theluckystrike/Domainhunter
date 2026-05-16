# Domain Transfer to Cloudflare -- Step by Step

## For GoDaddy Purchases
1. **Wait 60 days** after purchase (ICANN transfer lock)
   - If domain was already at GoDaddy 60+ days, transfer immediately
2. **Unlock domain:** GoDaddy > My Products > Domain > Domain Settings > Turn OFF Domain Lock
3. **Get EPP code:** Domain Settings > Authorization Code > Get Code > emailed to you
4. **Initiate at Cloudflare:** dash.cloudflare.com > Registrar > Transfer > Enter domain + EPP code
5. **Pay renewal:** Cloudflare charges 1 year at cost (~$10.11 for .com, ~$10.46 for .net)
6. **Approve transfer:** Click confirmation link in email from current registrar
7. **Wait 5-7 days:** Transfer completes, DNS moves to Cloudflare
8. **Verify:** Check Cloudflare dashboard > domain shows as active

## For NameSilo Purchases
1. Unlock at NameSilo > Domain Manager > unlock
2. Get EPP code from NameSilo
3. Same Cloudflare steps as above

## For Other Registrars
Same pattern: unlock > get EPP > initiate at Cloudflare > approve > wait

## Cloudflare Registration Pricing (at cost)
- .com: $10.11/year
- .net: $10.46/year
- .org: $10.11/year
- .io: $43.26/year

## Important Notes
- Transfers add 1 year to expiry (you are paying for renewal)
- Free incoming transfers at Cloudflare
- Cannot transfer within 60 days of registration or previous transfer
- Must have domain unlocked and EPP/auth code ready

# ZOVO BRANDS — Live Deployment Report

**Date:** 2026-05-02
**Project:** ~/zovo-brands/
**Commit:** 206ee89
**Worker Version:** f7049943-8398-4c95-b9bb-3a47586d10cb
**Tests:** 424/424 PASS

---

## Status: DEPLOYED — Pending DNS Activation

| Component | Status |
|-----------|--------|
| Worker code uploaded | DONE (57.28 KiB) |
| 14 CF zones created | DONE (all pending) |
| 14 Custom Domains bound | DONE (all enabled) |
| Porkbun NS updated | BLOCKED (need API secret key) |
| Domains resolving | NOT YET (NS still at Porkbun defaults) |
| belikenative dofollow links | DONE (both template + directory) |
| Test suite | 424/424 PASS |

---

## Cloudflare Zones (14/14 Created)

All zones assigned to: `aarav.ns.cloudflare.com` + `ximena.ns.cloudflare.com`

| Domain | Zone ID | Status |
|--------|---------|--------|
| curl.beauty | 01b14632450e67e9df76bff1b4f7fcd2 | pending |
| dawn.skin | e317012842f6d3e975445bfa4d38d567 | pending |
| mist.hair | b6a14a17a1e8c15c9d45bc22cc6a7fde | pending |
| fawn.skin | 5aeb551bfb0418e84b12f8b939923789 | pending |
| petal.hair | 1292834e83bc84ffed87849f2ab99f33 | pending |
| flax.hair | f52fd249f910fbf0a6bf208fc34efb5c | pending |
| dusk.quest | 4eaef401b0ac7b610184632eac4c95bd | pending |
| pine.beer | bb13470cf97c926495512f85c0a4678c | pending |
| hops.garden | 44e7e6df93686734c92d4bec5d32d5d7 | pending |
| fjord.surf | cb081c167a1fa3ef91425eca2c5b1c8a | pending |
| kelp.surf | e037c33c0ae9211f52f13eb45dc35197 | pending |
| wort.beer | 9a1b6d265f2f2d7748ff88a939a27325 | pending |
| wraith.monster | 6f75a9107a875ee5ad4cd4ac412fa9ad | pending |
| bane.monster | e5bfffc60a8a7937cbcff3d79f71b15e | pending |

---

## Custom Domains (14/14 Bound)

All bound via `PUT /accounts/{id}/workers/domains` API. This is the recommended approach (not routes).

Each Custom Domain:
- Auto-provisions SSL certificate
- Auto-creates DNS AAAA record pointing to CF edge
- Routes all traffic to `zovo-brands` worker
- No zone-level Workers Routes needed

---

## ONE REMAINING STEP: Porkbun NS Update

Domains currently use Porkbun's default nameservers. They must be changed to:
- `aarav.ns.cloudflare.com`
- `ximena.ns.cloudflare.com`

### Option A: Via Porkbun API (automated)

You need a Porkbun API key + secret. Your existing keys:
- `zovo` (pk1_3fbf...89f2)
- `newdomains` (pk1_7b8c...d23f)

The secret key is needed but not displayed in Porkbun dashboard. If you have it saved:

```bash
export PORKBUN_API_KEY="pk1_..."
export PORKBUN_SECRET_KEY="sk1_..."
cd ~/zovo-brands && ./update-porkbun-ns.sh
```

If you lost the secret, create a new API key pair at https://porkbun.com/account/api

### Option B: Via Porkbun Dashboard (manual, ~5 min)

For each of the 14 domains:
1. Go to Domain Management > domain > Nameservers
2. Switch from "Porkbun nameservers" to "Authoritative nameservers"
3. Enter: `aarav.ns.cloudflare.com` and `ximena.ns.cloudflare.com`
4. Save

### After NS Update

DNS propagation: 5-30 minutes. Then:
```bash
cd ~/zovo-brands && ./verify.sh --json
```

---

## belikenative Links — Verified

### Brand Pages (template.js)
```html
<a href="https://www.belikenative.com" rel="dofollow"
   title="belikenative — AI Writing Assistant">belikenative</a>
```
- URL: www.belikenative.com
- rel: dofollow (explicit)
- Anchor text: "belikenative" (keyword)

### Directory Page (index.js)
```html
<a href="https://www.belikenative.com" rel="dofollow">belikenative</a>
```
- URL: www.belikenative.com
- rel: dofollow (explicit)
- Anchor text: "belikenative" (keyword)

**Both verified present on every page via test assertions T4.7 and T11.6.**

---

## Architecture Change: Routes -> Custom Domains

| Before | After |
|--------|-------|
| wrangler.toml had 14 [[routes]] | wrangler.toml has 0 routes |
| Routes need Workers Routes token permission | Custom Domains need Workers Scripts permission |
| Routes don't provision SSL | Custom Domains auto-provision SSL |
| Routes don't create DNS records | Custom Domains auto-create AAAA records |
| Deploy fails if any zone is pending | Deploy succeeds regardless of zone status |

**Why this is better:** Custom Domains are the recommended approach since 2023. They handle SSL and DNS automatically. The worker deploys cleanly without needing per-zone route permissions.

---

## Token Inventory

| Token | Permissions | Used For |
|-------|------------|----------|
| CLOUDFLARE_API_TOKEN (original) | Workers Scripts:Edit | `npx wrangler deploy` |
| CF_ZONE_TOKEN (new, cfut_0vOd...) | Zone:Edit, DNS:Edit, Workers Scripts:Edit | Zone creation, Custom Domain binding |

Both tokens are needed:
- Original: for ongoing `npx wrangler deploy` (code updates)
- New: for adding/removing zones and custom domains

---

## Git Log

```
206ee89 Deploy: Custom Domains bound, worker live, belikenative dofollow links fixed
5397259 Add deploy-now.sh and update-porkbun-ns.sh automation scripts
31d8802 Remove wren.beauty (not in Porkbun account), 15 -> 14 domains
b7b407d Upgrade holding pages to full sales pages with pricing
29bf9ca Harden all files to NASA Power of 10 compliance
2900415 Initial import from files (3)
```

---

## Sales Page Features (per domain)

Each brand page includes:
- Hero with niche badge, brand name, tagline, and price
- "What's Included" 2x3 grid (6 SVG icons): domain, brand identity, landing page, social handles, brand strategy, 30-day support
- CSS-only brand preview mockups: product bottle + social profile card
- Pricing section with Stripe CTA (placeholder) + trust badges
- Product JSON-LD schema with price for Google rich results
- BLN dofollow backlink (keyword: "belikenative")
- Zovo Labs attribution
- Performance: ~12 KB per page, zero external JS

---

## Pricing Summary

| Tier | Domains | Price Each | Total |
|------|---------|-----------|-------|
| T1 | curl.beauty, dawn.skin, mist.hair, fjord.surf | $4,997 | $19,988 |
| T2 | fawn.skin, petal.hair, flax.hair, kelp.surf | $2,997 | $11,988 |
| T3 | dusk.quest, pine.beer, hops.garden, wort.beer | $1,997 | $7,988 |
| T4 | wraith.monster, bane.monster | $997 | $1,994 |
| **Total** | **14 domains** | | **$41,958** |

---

## CCG (claudecodeguides.com) Status

- Last deploy: STABLE-1 (commit c6e8be15c)
- 3,810 articles, 3,571 indexable, 10 tools
- Day 14 measurement: May 8 (45 keyword pages)

---

*Generated by Claude Code — 5 parallel agents, NASA P10 strict compliance, 424/424 tests pass*

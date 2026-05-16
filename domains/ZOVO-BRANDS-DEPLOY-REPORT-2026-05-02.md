# ZOVO BRANDS — Deployment Report

**Date:** 2026-05-02
**Project:** ~/zovo-brands/
**Commit:** 5397259
**Status:** CODE COMPLETE | 424/424 TESTS PASS | DEPLOY BLOCKED (CF token needs zone.create permission)

---

## Executive Summary

Removed wren.beauty (not in Porkbun account), reducing portfolio from 15 to 14 domains. All code updated, tests pass. Attempted CF zone creation for all 14 domains — blocked by API token lacking `zone.create` permission. Worker code uploaded successfully (57.26 KiB) but route binding fails because zones don't exist yet. Created two new automation scripts for one-shot deployment once credentials are ready.

---

## What Changed This Sprint

### 1. wren.beauty Removed (14 domains now)

Removed from all 7 files: domains.js, stripe-links.js, wrangler.toml, setup.sh, verify.sh, generate-stripe-links.sh, README.md

**Reason:** Domain not found in Porkbun account (59 domains checked, not present).

### 2. Two New Deploy Scripts Created

| Script | Lines | Purpose |
|--------|-------|---------|
| deploy-now.sh | 617 | One-shot 4-phase deploy (zones + NS + worker + verify) |
| update-porkbun-ns.sh | 255 | Standalone Porkbun NS updater |

---

## Domain Inventory (14 domains)

| # | Domain | Price | Category | Porkbun API | CF Zone |
|---|--------|-------|----------|-------------|---------|
| 1 | curl.beauty | $4,997 | beauty | ENABLED | PENDING |
| 2 | dawn.skin | $4,997 | beauty | ENABLED | PENDING |
| 3 | mist.hair | $4,997 | beauty | ENABLED | PENDING |
| 4 | fjord.surf | $4,997 | adventure | needs enable | PENDING |
| 5 | fawn.skin | $2,997 | beauty | ENABLED | PENDING |
| 6 | petal.hair | $2,997 | beauty | ENABLED | PENDING |
| 7 | flax.hair | $2,997 | beauty | ENABLED | PENDING |
| 8 | kelp.surf | $2,997 | adventure | needs enable | PENDING |
| 9 | dusk.quest | $1,997 | gaming | needs enable | PENDING |
| 10 | pine.beer | $1,997 | brewing | needs enable | PENDING |
| 11 | hops.garden | $1,997 | brewing | needs enable | PENDING |
| 12 | wort.beer | $1,997 | brewing | needs enable | PENDING |
| 13 | wraith.monster | $997 | gaming | needs enable | PENDING |
| 14 | bane.monster | $997 | gaming | needs enable | PENDING |

**Porkbun API status:** 6/14 enabled, 8 remaining

---

## Blocker: CF API Token Permissions

### Current Token (CLOUDFLARE_API_TOKEN)
- Works for: `wrangler deploy` (worker upload)
- Missing: `com.cloudflare.api.account.zone.create` permission
- Worker uploaded: 57.26 KiB (SUCCESS)
- Route binding: FAILED (zones don't exist)

### Fix Required

Create a new CF API token with broader permissions:

1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create Token > Custom Token
3. **Permissions:**
   - Zone : Zone : Edit (includes zone.create)
   - Zone : DNS : Edit
   - Account : Workers Scripts : Edit
4. **Zone Resources:** Include All Zones
5. **Account Resources:** Include account `dd3f2a29b7707e21a87f26a622c0bb9d`

Then set it:
```bash
export CF_ZONE_TOKEN="new-token-here"
```

---

## Deployment — One Command

Once credentials are ready:

```bash
# Set all credentials
export CF_ZONE_TOKEN="token-with-zone-create"
export PORKBUN_API_KEY="pk_..."
export PORKBUN_SECRET_KEY="sk_..."

# Run one-shot deploy
cd ~/zovo-brands && ./deploy-now.sh
```

This single script handles all 4 phases:

| Phase | Action | Requires |
|-------|--------|----------|
| 1 | Add 14 domains to CF as zones | CF_ZONE_TOKEN |
| 2 | Update NS on Porkbun to CF nameservers | PORKBUN_API_KEY + SECRET |
| 3 | Deploy worker with routes | CLOUDFLARE_API_TOKEN (already set) |
| 4 | HTTP verify all 14 domains | none |

**Smart fallbacks:** Each phase skips gracefully if its token is missing. Phase 3 always runs. Results written to `deploy-results.json`.

### Alternative: Phase-by-Phase

If you prefer manual control:

```bash
# Phase 1: Add zones (needs new CF token)
# Use CF dashboard manually, or:
export CF_ZONE_TOKEN="..." && ./deploy-now.sh

# Phase 2: Update NS (once zones exist + Porkbun API enabled)
export PORKBUN_API_KEY="..." PORKBUN_SECRET_KEY="..." && ./update-porkbun-ns.sh

# Phase 3: Deploy worker (once zones are active)
npx wrangler deploy

# Phase 4: Verify
./verify.sh --json
```

---

## Remaining Porkbun API Enablement

8 domains still need API access enabled in Porkbun dashboard:

1. fjord.surf
2. kelp.surf
3. dusk.quest
4. pine.beer
5. hops.garden
6. wort.beer
7. wraith.monster
8. bane.monster

**How:** Porkbun Dashboard > Domain Management > each domain > API Access > Enable

---

## Test Suite Status

| Metric | Value |
|--------|-------|
| Total assertions | 424 |
| Passed | 424 |
| Failed | 0 |
| Domains tested | 14 |
| Largest page | hops.garden (12,157 B) |
| Average page size | 12,121 B |

---

## Git Log

```
5397259 Add deploy-now.sh and update-porkbun-ns.sh automation scripts
31d8802 Remove wren.beauty (not in Porkbun account), 15 -> 14 domains
b7b407d Upgrade holding pages to full sales pages with pricing
29bf9ca Harden all files to NASA Power of 10 compliance
2900415 Initial import from files (3)
```

---

## File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| src/domains.js | 213 | 14 domain configs (frozen), validation, escapeHtml |
| src/template.js | 304 | Full sales page renderer (5 sections) |
| src/index.js | 244 | CF Worker entry, routing, directory page |
| src/stripe-links.js | 57 | Placeholder Stripe payment links |
| deploy-now.sh | 617 | One-shot 4-phase deployment |
| update-porkbun-ns.sh | 255 | Standalone Porkbun NS updater |
| setup.sh | 410 | Original setup (needs all 4 env vars) |
| verify.sh | 249 | Domain verification with --json |
| test.sh | 319 | 424-assertion test suite |
| generate-stripe-links.sh | 198 | Stripe CLI link generation |
| wrangler.toml | 73 | Worker config with 14 routes |
| package.json | 5 | ES module support |
| README.md | 85 | Documentation |

**Total:** 3,029 lines across 13 files

---

## Critical Path to Live

```
[YOU ARE HERE]
     |
     v
1. Create CF API token with zone.create permission (~2 min)
     |
     v
2. Enable Porkbun API for remaining 8 domains (~5 min)
     |
     v
3. Set env vars + run deploy-now.sh (~3 min)
     |
     v
4. Wait for DNS propagation (5-30 min)
     |
     v
5. Run verify.sh --json (~1 min)
     |
     v
6. Generate Stripe payment links (~10 min)
     |
     v
14 LIVE SALES PAGES
```

---

## CCG (claudecodeguides.com) Status

- Last deploy: STABLE-1 (commit c6e8be15c)
- 3,810 articles, 3,571 indexable, 10 tools
- Day 14 measurement: May 8 (45 keyword pages)
- CCG pipeline sprints complete: 7/7

---

*Generated by Claude Code — 5 parallel agents, NASA P10 strict compliance, 424/424 tests pass*

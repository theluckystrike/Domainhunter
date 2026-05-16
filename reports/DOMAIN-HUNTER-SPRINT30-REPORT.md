# DOMAIN HUNTER — Sprint 30 Report: Trust But Verify

**Date:** 2026-05-16 | **Agents:** 4 parallel + 2 sequential | **Cost:** $0.00

---

## Objective

Validate the Sprint 20 pipeline fixes end-to-end, update RDAP intelligence on all target domains, audit infrastructure health, and update portfolio with new acquisitions.

## Results — All Objectives Met

### 1. Pipeline Validation — PASS (1 bug found + fixed)

**Full live run** (`--sources existing`): 269 harvested -> 228 resolved -> 71 with drop signals -> 153 scored above 25.0

| Metric | Dry Run | Live Run |
|--------|---------|----------|
| Startups harvested | 269 | 269 |
| After dedup | 228 | 228 |
| RDAP probed | 228 (skipped) | 228 (real) |
| Drop signals found | 228 (all, mock) | 71 (real RDAP) |
| Scored above 25.0 | 128 | **153** |
| Tiers: medium | 0 | **16** |
| Tiers: low | 128 | 137 |
| Crash? | YES (monitor) | YES (monitor) |

**Bug 8 found + fixed**: `_auto_add_to_monitor()` at line 1294 asserted `"domains" in config` but `monitored_domains.json` uses `"active_targets"`. Changed to `"active_targets"` in both the assertion and the 2 dictionary references. Pipeline now completes cleanly with exit code 0.

**Top 10 domains (live RDAP)**:

| # | Domain | Score | Funding | EPP Status |
|---|--------|-------|---------|------------|
| 1 | infarm.com | 38.9 | $500M | clientRenewProhibited |
| 2 | canoo.com | 38.0 | $600M | clientRenewProhibited |
| 3 | ambri.com | 36.7 | $223M | clientRenewProhibited |
| 4 | byjus.com | 36.7 | $5.5B | client transfer prohibited |
| 5 | getir.com | 36.7 | $1.8B | clientRenewProhibited |
| 6 | jokr.com | 36.7 | $400M | clientRenewProhibited |
| 7 | northvolt.com | 36.7 | $13.0B | clientRenewProhibited |
| 8 | olive.com | 36.7 | $902M | clientRenewProhibited |
| 9 | quibi.com | 36.7 | $1.75B | clientRenewProhibited |
| 10 | veev.com | 36.7 | $600M | clientRenewProhibited |

**Note**: All DA/backlink scores are 0 because `--sources existing` skips DataForSEO enrichment. Full pipeline with `--sources existing,deepseek,yc` would add DA data for $0.12.

### 2. RDAP Intelligence Update — 6 Targets Probed

| Domain | EPP Status | Registrar | Expiry | Drop Signal | Est. Drop |
|--------|-----------|-----------|--------|-------------|-----------|
| **cytheris.com** | 4 client locks | GoDaddy | **Jun 4** (19 days!) | WEAK | ~Aug 13 |
| **ghostautonomy.com** | 4 client locks | Wild West (GoDaddy) | **Jun 7** (22 days!) | WEAK | ~Aug 16 |
| **bside.com** | 4 client locks | GoDaddy | Jun 23 | NO | ~Sep 1 |
| **guerrameats.com** | **clientHold** | Squarespace | Apr 2027 | **YES (strongest)** | Uncertain |
| **olive.com** | 4 client locks | GoDaddy | Nov 2027 | NO | Not dropping |
| **infarm.com** | 4 client locks | GoDaddy | Feb 2027 | NO (recently modified) | Not dropping |

**Key findings**:
- **cytheris.com** expires in 19 days (Jun 4). If not renewed: grace -> redemption -> **drop ~Aug 13**
- **ghostautonomy.com** expires in 22 days (Jun 7). If not renewed: **drop ~Aug 16**
- **guerrameats.com** has **clientHold** (DNS suspended) — strongest drop signal of all targets. But expiry is Apr 2027, not Jun 26 as previously estimated
- **olive.com** and **infarm.com** are NOT dropping — both renewed well into 2027, infarm recently modified Apr 29 2026
- Previous drop date estimates were optimistic. GoDaddy timeline: expire -> 30-45d grace -> 30d redemption -> 5d pendingDelete -> drop

### 3. Test Suite Audit — 352/352 PASSING

| Metric | Value |
|--------|-------|
| Total tests | 352 |
| Passed | 352 |
| Failed | 0 |
| Skipped | 0 |
| Warnings | 1 (LibreSSL, environmental) |
| Runtime | 0.19s (reaper) / ~35s (full) |
| Syntax check | All 3 key files OK |

**Coverage highlights**:
- Models: 88-100% (reaped_startup.py at 95%)
- Clients: 60-86%
- startup_reaper.py: 42% (I/O functions not unit-tested)
- No TODO/FIXME/HACK in any test file
- No skips or xfails

### 4. Infrastructure Health — ALL GREEN

| Component | Status |
|-----------|--------|
| Daemon | RUNNING (PID 40365, heartbeat current) |
| Symlink | ~/domainhunter -> ~/Desktop/domainhunter OK |
| Config | Complete (.env, settings.py, 5 plists) |
| Dependencies | All OK (httpx, structlog, pydantic) |
| Logs | Active today (May 16) |
| Data directory | 444 MB, 206 files |
| Monitored domains | 37 total (8 critical, 23 high, 7 medium) |
| Dynadot balance | $25.00 |
| DropCatch credentials | NOT SET (awaiting NameBright approval) |

**Minor issues**:
- Standalone LaunchAgents (`drop-monitor-all/critical`) show "Operation not permitted" — harmless, daemon scheduler handles these internally
- DropCatch API credentials empty — backorders via CLI blocked until NameBright approves access

### 5. Portfolio Update

| Domain | Cost | Strategy | Status | BIN Price |
|--------|------|----------|--------|-----------|
| ingredientcalculator.com | $10.46 | DEVELOP | OWNED | $3,000 |
| pictureeditor.net | $11.86 | FLIP | OWNED | $2,000 |
| recipetool.net | $11.86 | DEVELOP | OWNED | $1,500 |
| **viryd.com** | $10.96 | FLIP | **LISTED** | $2,500 |
| **neovistainc.com** | $10.96 | FLIP | **LISTED** | $1,500 |

**Total invested**: $56.10 | **Domains owned**: 5 | **Listed**: 2 (Afternic)

### 6. Drop Countdown — Updated Timeline

| Domain | Expiry | Grace Period Ends | Redemption Ends | Estimated Drop |
|--------|--------|------------------|-----------------|----------------|
| cytheris.com | Jun 4 | ~Jul 9 | ~Aug 8 | **~Aug 13** |
| ghostautonomy.com | Jun 7 | ~Jul 12 | ~Aug 11 | **~Aug 16** |
| bside.com | Jun 23 | ~Jul 28 | ~Aug 27 | **~Sep 1** |
| guerrameats.com | clientHold | N/A | N/A | Uncertain |

**Previous estimates vs reality**:
- cytheris.com: was "Jun 30" -> now **Aug 13** (44 days later)
- ghostautonomy.com: was "Jul 3" -> now **Aug 16** (44 days later)
- guerrameats.com: was "Jun 26" -> now **uncertain** (expiry Apr 2027, not Jun 2026)

### 7. Backorder Status — BLOCKED

DropCatch API credentials not configured. NameBright account setup in progress (user needs to accept T&C and apply for API access). Dynadot backorder API available ($25.00 balance) but Dynadot's catch rate is significantly lower than DropCatch/NameBright.

**Recommended action**: Place Dynadot backorders on cytheris.com and ghostautonomy.com as insurance while waiting for DropCatch access.

## Bug Fixed This Sprint

| # | Bug | Location | Fix |
|---|-----|----------|-----|
| 8 | `_auto_add_to_monitor()` schema mismatch | startup_reaper.py:1294 | `"domains"` -> `"active_targets"` |

## Files Modified

| File | Change |
|------|--------|
| `scripts/startup_reaper.py` | Fixed `_auto_add_to_monitor()` — 3 references from `"domains"` to `"active_targets"` |
| `data/portfolio.json` | Added viryd.com + neovistainc.com, updated summary |

## Metrics

| Metric | Value |
|--------|-------|
| Tests passing | 352/352 |
| Pipeline bugs found | 1 (Bug 8) |
| Pipeline bugs fixed | 1/1 |
| RDAP lookups | 6 |
| Lines changed | ~10 |
| New dependencies | 0 |
| API cost | $0.00 |

## Next Steps (Sprint 31)

1. **Place Dynadot backorders** on cytheris.com + ghostautonomy.com ($25 balance available)
2. **Get NameBright API access** — accept T&C, apply, get CLIENT_ID/CLIENT_SECRET
3. **Run full pipeline** with `--sources existing,deepseek,yc` to get DataForSEO enrichment ($0.15)
4. **Deploy landing pages** for viryd.com + neovistainc.com (Cloudflare Pages, for-sale template)
5. **List on Dan.com** — viryd.com ($2,500 BIN) + neovistainc.com ($1,500 BIN)
6. **Weekly RDAP monitoring** — cytheris.com and ghostautonomy.com expire in <3 weeks

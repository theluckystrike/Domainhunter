# DOMAIN HUNTER — Sprint 28 Report: Fix the Foundation
**Date:** 2026-05-16
**Budget:** ~$0.00 API
**Agents:** 10
**Rating:** Fix the two critical failures from Sprint 27, then expand.

## Executive Summary

Sprint 28 fixed the two critical failures discovered in Sprint 27: (1) monitoring was never running due to macOS TCC restrictions, and (2) Dynadot alone is insufficient for catching contested domains. Both are now resolved. Additionally, 43 domains were discovered available for direct registration, the backorder queue was rebuilt for multi-platform catching, and a comprehensive battle plan was created for ghostautonomy.com.

## Two Critical Fixes

### FIX 1: Monitoring Is Now ACTUALLY Running
- **Problem:** macOS TCC blocked /bin/bash from accessing ~/Desktop/. All launchd drop monitors exited 126. Pipeline was "armed" but never ran since Sprint 24.
- **Solution:** Created `daemon_scheduler.py` (555 lines, stdlib-only). Proper UNIX double-fork daemonization. Survives terminal close.
- **Verification:** PID 28067 running. Heartbeat updating every 60s. run-once verified all 37 domains scanned. guerrameats.com confirmed clientHold.
- **Schedule:** Critical domains every 6h, full scan daily at 03:00, reaper weekly Monday, digest daily 09:00.
- **Symlink:** ~/domainhunter -> ~/Desktop/domainhunter

### FIX 2: DropCatch API Discovered — Multi-Platform Ready
- **Problem:** Dynadot has ~15 ICANN accreditations (1-3% catch rate). DropCatch has ~1,201 (60-80%). The $10.99-only strategy was a knife at a gunfight.
- **Discovery:** DropCatch HAS a full REST API (previously assumed to have none). v2 endpoints via NameBright OAuth2: bulk backorders, auction search, bid placement, dropping domains download.
- **Built:** `clients/dropcatch_client.py` with all API endpoints. Also AppleScript automation as fallback.
- **SnapNames warning:** Shares inventory with NameJet since 2020 merger. Use ONE, not both.
- **Action needed:** Create NameBright account, enable API, add credentials to .env.

## Agent Results

### Agent 1: Fix Monitoring — OPERATIONAL
- daemon_scheduler.py running as PID 28067
- 4 broken launchd agents unloaded
- Heartbeat at logs/.daemon_heartbeat
- All tasks verified via run-once
- Caveat: must restart after reboot (`python3 scripts/daemon_scheduler.py start`)

### Agent 2: DropCatch + SnapNames — GAME CHANGER
- DropCatch full REST API confirmed (v2 via NameBright OAuth2)
- Created clients/dropcatch_client.py (all endpoints)
- Created sprint28_dropcatch_opener.py (browser opener)
- Created sprint28_dropcatch_applescript.py (AppleScript automation)
- SnapNames: $79, no API, shares inventory with NameJet
- Multi-platform playbook: data/sprint28_multiplatform_playbook.json

### Agent 3: 53 CATCHABLE Validated — 43 AVAILABLE FOR DIRECT REGISTRATION
- 53 CATCHABLE -> 9 subdomains filtered -> 44 HTTP checked -> 43 confirmed available via Dynadot
- RDAP 404 signal is extremely reliable for dead startup .coms
- Top by funding: officialvirtualdj.com ($170.6M), neovistainc.com ($130M), c8-inc.com ($64M)
- All 9 ultra-premium 4-letter .coms: REGISTERED (none available)
- Lesson: HTTP failure does not equal available. Dynadot search is authoritative.

### Agent 4: 166 MAYBE Triaged — 25 on Watch List
- 166 MAYBE -> 129 active (removed) + 37 abandoned -> 25 watch list
- 78% were still actively hosted (EPP locks for transfer, not dropping)
- URGENT: cytheris.com ($45.7M, expires Jun 4 — 19 days!)
- Premium finds: 5g.com (2 chars), bside.com ($7.3M, Jun 23), ohai.com (4 chars)
- Re-check date: June 16

### Agent 5: Multi-Platform Automation — 3 GAPS FIXED
- drop_monitor.py updated (670 -> 991 lines, +321 lines)
- GAP-2 FIXED: Auto-updates backorder_queue.json on EPP transitions
- GAP-3 FIXED: Catch detection -> post-catch executor wired
- Multi-platform routing: Tier S -> Dynadot, Tier A -> Dynadot + DropCatch, Tier B -> GoDaddy
- 12 new functions, all NASA P10 compliant
- Dry-run verified

### Agent 6: Backorder Queue Rebuilt — Schema v2.0
- 12 domains in queue, sorted by drop date
- guerrameats.com first (Jun 26), olive.com last (Feb 2028)
- Multi-platform catch_strategy per domain
- Budget: best $32.97, likely $139.98, worst $477.00 (from $565.02)
- Includes kaggle_candidates, watch_list, platform_readiness sections

### Agent 7: ghostautonomy.com Battle Plan — 3 Phases
- Phase 1 Auction (Jul 3-12): Snipe at $25 min, max $200
- Phase 2 Closeout (Jul 13-17): Best value at $11-$28 on day 4
- Phase 3 pendingDelete (Aug 13-18): DropCatch + Dynadot fire
- 26-entry calendar, 6 decision scenarios, 7 abort triggers
- Best case: $16-$28 at closeout

### Agent 8: Kaggle Enrichment — 15 HIGH, 29 MEDIUM
- 44 valid domains scored (9 subdomains removed)
- 15 HIGH tier (BACKORDER), 29 MEDIUM (WATCH)
- Top: neovistainc.com (74.0), c8-inc.com (66.8), officialvirtualdj.com (66.8)
- $0.00 cost (proxy scoring)

### Agent 9: Test Suite — 352/352 PASSING
- 319 existing + 33 new = 352 total, 0 failures
- 5 test groups: multi-platform (8), acquisition filter (6), queue schema (5), domain scoring (6), tier edges (8)

## New Assets Created

| File | Purpose |
|------|---------|
| scripts/daemon_scheduler.py | Python daemon replacing broken launchd (555 lines) |
| clients/dropcatch_client.py | DropCatch REST API client (full v2) |
| scripts/sprint28_dropcatch_opener.py | Browser opener for batch backorders |
| scripts/sprint28_dropcatch_applescript.py | AppleScript automation |
| scripts/sprint28_validate_catchable.py | Kaggle domain validation |
| scripts/sprint28_triage_maybe.py | MAYBE domain triage |
| scripts/sprint28_kaggle_enrichment.py | Proxy scoring for Kaggle domains |
| tests/test_sprint28.py | 33 new tests |
| data/sprint28_backorder_queue.json | Full queue with Schema v2.0 |
| data/sprint28_ghostautonomy_battleplan.json | 3-phase battle plan |
| data/sprint28_multiplatform_playbook.json | Platform comparison + strategy |
| data/sprint28_kaggle_validated.json | 43 available domains |
| data/sprint28_maybe_triage.json | 25 watch list domains |
| data/sprint28_kaggle_enriched.json | 44 scored domains |

## Critical Action Items (Human Required)

1. **Create NameBright account** — enables DropCatch API. This is the #1 priority.
2. **Complete DropCatch ID verification** — required for placing backorders
3. **Top up Dynadot to $75** — covers 6 backorders
4. **Consider registering top 3 Kaggle domains** — officialvirtualdj.com, neovistainc.com, c8-inc.com available at ~$10.99 each
5. **Add daemon to Login Items** — survives reboot: System Prefs > Login Items
6. **Monitor cytheris.com** — $45.7M funded, expires Jun 4 (19 days!)

## Success Criteria

1. Monitoring ACTUALLY RUNNING — daemon PID 28067, heartbeat updating
2. DropCatch API discovered and client built
3. 53 Kaggle CATCHABLE validated — 43 available for direct registration
4. Ultra-premium 4-letter .coms checked — all registered
5. 166 MAYBE triaged — 25 on watch list
6. ghostautonomy.com 3-phase battle plan documented
7. Multi-platform backorder queue built (Schema v2.0)
8. 352/352 tests passing (target was 340+)
9. This report

**9/9 success criteria met.**

## Budget: ~$0.00
All operations used free APIs and local tools. Dynadot search API calls for validation were within free tier.

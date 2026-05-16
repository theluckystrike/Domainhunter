# SPRINT 19 — DR40+ Domain Catcher
## Automated Drop Monitoring + Backorder Pipeline
**Date: 2026-05-14 | Budget: $538.47 remaining | DeepSeek: $18.87**

---

## Sprint Goal
Build an automated domain drop monitoring and backorder system that catches DR40+ domains at $59-$79 through DropCatch + Dynadot, powered by DeepSeek V3 classification and RDAP-based status tracking.

---

## Architecture

```
RDAP Monitor (cron 6h) → Status Change Detector → DeepSeek Classifier → Auto-Backorder (Dynadot API) → Alert (Slack + Desktop)
                                                                          ↓
                                                              Manual Backorder Reminder (DropCatch — no API)
```

---

## Deliverables (5 chunks)

### Chunk 1: RDAP Client + Drop Monitor (core infrastructure)
**Files:** `clients/rdap_client.py`, `scripts/drop_monitor.py`
- Async RDAP client for .com/.org/.ai/.io/.co TLDs
- TLD-specific RDAP server routing (Verisign for .com, PIR for .org, etc.)
- Rate-limited: 3s between queries per TLD, token bucket limiter
- Status change detection: compare current vs last-known EPP status
- SQLite persistence: `domain_monitoring` table with status history
- Tiered monitoring schedule:
  - CRITICAL (expired/grace): every 6 hours
  - HIGH (expiry <60 days): daily
  - MEDIUM (expiry <180 days): every 3 days
  - LOW (long-dated): weekly
- **LOC estimate:** ~250

### Chunk 2: Dynadot API Client (automated backorders)
**Files:** `clients/dynadot_client.py`
- REST client for `https://api.dynadot.com/api3.json`
- Commands: `backorder`, `delete_backorder`, `list_backorder`, `domain_info`
- $10.99/catch (only charged if caught)
- Auto-backorder trigger when domain enters `pendingDelete` status
- Dry-run mode for testing
- **LOC estimate:** ~150

### Chunk 3: DeepSeek Re-Integration (classification brain)
**Files:** Update `clients/deepseek.py`, create `scripts/classify_targets.py`
- Fresh API key setup (user action: get new key from platform.deepseek.com)
- Batch classify all 41 monitored domains by niche + acquisition value
- JSON mode: structured output with niche, brandability, max_bid, priority
- Cost: ~$0.02 per classification run (50 domains/batch)
- **LOC estimate:** ~80

### Chunk 4: Alert System Enhancement
**Files:** Update `notifications/notifier.py`, create `scripts/alert_formatter.py`
- macOS desktop notifications via `osascript` for real-time alerts
- Enhanced Slack formatting with domain status cards
- Alert matrix:
  - `pendingDelete` → Slack + email + desktop + "BACKORDER NOW" action items
  - `redemptionPeriod` → Slack + desktop + manual backorder reminder
  - `autoRenewPeriod` past grace → Slack only
- Include DropCatch direct link in alerts (manual placement required)
- **LOC estimate:** ~120

### Chunk 5: Dashboard + Cron Setup
**Files:** Update `dashboard.py`, create `scripts/setup_cron.sh`
- Dashboard tab: Domain Drop Timeline (visual Gantt-style drop schedule)
- Dashboard tab: RDAP Status History (status changes over time)
- Dashboard tab: Backorder Coverage (which domains on which platforms)
- 3 cron jobs:
  1. `drop_monitor.py --tier critical` every 6 hours
  2. `drop_monitor.py --tier all` daily at 06:00 UTC
  3. `dashboard.py --generate` daily at 06:30 UTC
- **LOC estimate:** ~200

---

## Target Domains (41 monitored, 7 active targets)

### TIER 1 — BACKORDER IMMEDIATELY
| Domain | ETV/mo | Status | Drop Est. | Platforms | Max Bid |
|--------|--------|--------|-----------|-----------|---------|
| guerrameats.com | $11,376 | clientHold + DNS DEAD | ~Jun 26 | DropCatch + Dynadot | $200 |
| sunnyray.org | $2,842 | autoRenewPeriod | ~Jun 30 | DropCatch + Dynadot | $100 |
| globalgeopark.org | $626 | autoRenewPeriod | ~Jul 1 | DropCatch + Dynadot | $400 |

### TIER 2 — BACKORDER THIS MONTH
| Domain | ETV/mo | Status | Drop Est. | Max Bid |
|--------|--------|--------|-----------|---------|
| ghostautonomy.com | $1,428 | clientRenewProhibited | ~Jul 20 | $75 |
| goodglammgroup.com | ~$0 | clientRenewProhibited | ~Jul 6+ | $100 |
| sendy.co | $3,179 | clientRenewProhibited | ~Jul 16+ | $150 |
| readingfoundation.org | $7,207 | clientRenewProhibited | ~Jul 30+ | $200 |

### ghostautonomy.com — The Crown Jewel
- $220M OpenAI-backed autonomous driving startup
- Shut down April 2024, patents sold to Applied Intuition
- DA 52, press backlinks: TechCrunch, OpenAI blog, YC News
- Wild West Domains (GoDaddy subsidiary) → **WILL go through GoDaddy Auctions first**
- Expires Jun 7 → GoDaddy auction ~Jun 26 → Public drop ~Jul 20
- **CRITICAL: Must join GoDaddy Auctions ($4.99/yr) to bid**
- Backorder on DropCatch ($59) + Dynadot ($10.99) as backup

---

## Human Actions Required (NOT automatable)

### TODAY (10 minutes)
1. ✅ DropCatch: Place backorders on guerrameats.com, sunnyray.org, globalgeopark.org ($59 each = $177)
2. ✅ Dynadot: Place backorders on same 3 domains ($10.99 each = $33)
3. ✅ GoDaddy Auctions: Join membership ($4.99/yr) — **CRITICAL for ghostautonomy.com**

### THIS WEEK
4. Get new DeepSeek API key from platform.deepseek.com (current key expired, $18.87 balance)
5. Place ghostautonomy.com backorder on DropCatch ($59)
6. Place ghostautonomy.com backorder on Dynadot ($10.99)

### Projected Spend: $345 (leaves $193 buffer)
| Item | Cost |
|------|------|
| DropCatch backorders (4 domains) | $236 |
| Dynadot backorders (4 domains) | $44 |
| GoDaddy Auctions membership | $5 |
| GoDaddy Auctions bids (ghostautonomy) | ~$60 |
| **Total** | **$345** |

---

## Platform Strategy (Final)

| Platform | Status | Role | Cost/Catch |
|----------|--------|------|-----------|
| **DropCatch** | ✅ VERIFIED | Primary catcher (60-80% rate) | $59 min |
| **Dynadot** | ✅ WORKING | Secondary catcher + API automation | $10.99 |
| **GoDaddy Auctions** | ❌ NOT JOINED | Required for GoDaddy/Wild West domains | $4.99/yr + bid |
| ~~SnapNames~~ | ❌ DEAD | Email verification broken | — |

---

## Technical Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| WHOIS monitoring | RDAP protocol (free, structured JSON) | $0 |
| Bulk WHOIS | DataForSEO WHOIS API | $0.0003/query |
| Classification | DeepSeek V3 (deepseek-chat) | $0.27/M tokens |
| ETV verification | DataForSEO Labs | $0.01/domain |
| Authority check | OpenPageRank (free, 10K/day) | $0 |
| Storage | SQLite via aiosqlite | $0 |
| Alerts | Slack + macOS desktop | $0 |
| Scheduling | cron (3 jobs) | $0 |

---

## Success Criteria

- [ ] RDAP monitor running on cron, checking all 41 domains on schedule
- [ ] Status changes detected and alerted within 6 hours
- [ ] Dynadot auto-backorder triggered on pendingDelete detection
- [ ] DropCatch manual backorder reminder sent with direct links
- [ ] DeepSeek classifying new candidates at $0.02/batch
- [ ] Dashboard showing drop timeline for all targets
- [ ] ghostautonomy.com backorder placed on all 3 platforms (DropCatch + Dynadot + GoDaddy)
- [ ] All 3 cron jobs installed and verified

---

*Sprint 19 | Project REVENANT | NASA Power of 10 Compliant*
*Estimated code: ~800 LOC across 5 chunks | Estimated API cost: <$1/month*

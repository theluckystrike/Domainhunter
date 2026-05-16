# Domain Hunter — Project Overview

**Project**: REVENANT — Autonomous Domain Acquisition System
**Date**: 2026-05-15 | **Sprint**: 21 | **Tests**: 86 passing

---

## What Is Domain Hunter?

An autonomous system that discovers, evaluates, monitors, and acquires high-value expired/dropping domains from dead startups. The pipeline chains 7 AI agents, 15 API clients, and 3 automated cron jobs into a fully autonomous acquisition machine.

## The $10.99 Strategy (Sprint 21)

Professional drop-catchers fight over DR 60+ domains at $500-5000. We target **DR 10-35 domains with hidden editorial backlinks** — the sweet spot they ignore. Cost: **$10.99 flat** per catch via Dynadot backorder.

| | Traditional | Domain Hunter |
|---|---|---|
| Target | DR 60+ domains | DR 10-35 + editorial |
| Cost | $500-5000 auction | $10.99 flat backorder |
| Competitors | 50+ per domain | 0-3 per domain |
| Catch rate | ~10% | ~40% projected |
| Signal source | Ahrefs/DR metrics | Dead startup → domain |

## Key Metrics

| Metric | Value |
|--------|-------|
| Domains monitored | 35 (4 critical, 20 high, 8 medium, 3 low) |
| Reaper scored | 149 (38 sweet_spot, 111 junk) |
| Dead startups DB | 1,235 deduped |
| Pipeline cost/scan | $0.15 |
| Backorder cost | $10.99 (charge on success) |
| Dynadot balance | $25.00 |
| Cron jobs | 3 (6h critical, daily full, weekly reaper) |
| Tests | 86 passing (0.09s) |
| Sprints completed | 21 |

## System Architecture

```
DISCOVERY → VERIFICATION → CLASSIFICATION → DECISION → ACQUISITION → MONITORING
  SCOUT       SENTINEL       SPECTRE          ORACLE     Dynadot       Drop Monitor
  Reaper      ARCHIVIST      DeepSeek         Reaper     Backorder     RDAP + WHOIS
  DropCatch   Drop Monitor   RADIOGRAPH       Tier       Budget Gate   Cron (6h/daily)
```

## Files & Directories

| Directory | Contents | Count |
|-----------|----------|-------|
| scripts/ | Pipeline scripts | 12 |
| clients/ | API clients | 15 |
| agents/ | AI agents (SCOUT→ORACLE) | 7 |
| models/ | Frozen dataclasses | 7 |
| tests/ | Test modules + fixtures | 14 + 8 |
| data/ | JSON results, CSVs, GoDaddy data | 158+ files |
| reports/ | Sprint HTML/MD reports | 43 |
| tools/ | Utility scripts | 8 |
| config/ | Settings + constants | 3 |
| logs/ | Cron + monitor logs | 3 |

## Top Priority Domains (as of 2026-05-15)

### Critical (Action Required)
1. **guerrameats.com** — ETV $11,376, clientHold + DNS DEAD, dropping ~Jun 26
2. **ghostautonomy.com** — $220M funded, DA 52, TM abandoned, expires 2026-06-07
3. **sunnyray.org** — ETV $2,842, autoRenewPeriod, dropping ~Jun 30
4. **globalgeopark.org** — ETV $626, autoRenewPeriod, dropping ~Jul 1

### High (Reaper Top Scores)
1. humane.com — $241M funded, reaper 58.3, sweet_spot
2. arrival.com — $1.0B funded, reaper 56.5, sweet_spot
3. irl.com — $200M funded, reaper 56.0, sweet_spot
4. olive.com — $902M funded, reaper 56.0, sweet_spot
5. ghostautonomy.com — $220M funded, reaper 55.1, sweet_spot

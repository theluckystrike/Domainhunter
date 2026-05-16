# Domain Hunter — Pipeline Architecture

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  DOMAIN HUNTER — Autonomous Domain Acquisition System           │
│  15 API clients · 7 agents · 3 cron jobs · 7 data models       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STARTUP REAPER PIPELINE (7 stages)                             │
│  ════════════════════════════════════                            │
│  HARVEST → RESOLVE → PROBE → ENRICH → SCORE → OUTPUT → BACKORDER
│  (sources) (domain) (RDAP)  (SEO)    (9-dim)  (JSON)   (Dynadot)
│                                                                 │
│  AGENT PIPELINE (5 stages)                                      │
│  ═════════════════════════                                      │
│  SCOUT → SENTINEL → ARCHIVIST → SPECTRE → ORACLE               │
│  (find)  (verify)   (history)    (niche)   (verdict)            │
│                                                                 │
│  MONITORING (3 cron jobs)                                       │
│  ════════════════════════                                       │
│  Every 6h: RDAP critical │ Daily: RDAP all │ Weekly: Reaper    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Startup Reaper — 7 Stages

### Stage 1: HARVEST
- **Sources**: Existing data (269), YC dead list (1,034 inactive), DeepSeek LLM (50)
- **Dedup**: By normalized company name + domain, prefer richer metadata
- **Cap**: 1,500 startups max
- **Cost**: $0.02 (DeepSeek) + $0 (YC, existing)

### Stage 2: RESOLVE
- Pass through domains with valid `.` in field
- Batch-resolve unknowns via DeepSeek
- Cost: $0.01

### Stage 3: PROBE
- RDAP lookup per domain (0.3s rate limit)
- Classify EPP: pendingDelete, clientRenewProhibited, autoRenewPeriod, etc.
- Keep: drop signals + active domains expiring <12mo with funding >$10M
- Cost: $0.00

### Stage 4: ENRICH
- DataForSEO `bulk_ranks` (domain authority proxy)
- DataForSEO `bulk_pages_summary` (referring domains, backlinks)
- DataForSEO `referring_domains/live` (editorial source detection)
- Cost: $0.12

### Stage 5: SCORE
- 9-dimension weighted composite (see weights below)
- Competition penalty: DR brackets → 0.3x to 1.0x multiplier
- Competition tier: sweet_spot / stretch / auction / junk
- Tier assignment: critical (≥75), high (≥55), medium (≥35), low (<35)

### Stage 6: OUTPUT
- JSON: `data/startup_reaper_{date}.json`
- ASCII table: ranked display
- Auto-monitor: domains ≥55 → monitored_domains.json

### Stage 7: BACKORDER (Sprint 21)
- Filter: sweet_spot/stretch + pendingDelete/redemption + score ≥40
- Place via Dynadot `add_backorder_request`
- Budget: 20 slots, $220 cap
- $10.99/catch (charge on success only)

## 9-Dimension Scoring Weights

| # | Dimension | Weight | Range | Logic |
|---|-----------|--------|-------|-------|
| 1 | Editorial Links | 0.25 | 0-100 | Press mentions + editorial backlinks. +10 if TechCrunch/Bloomberg |
| 2 | Funding | 0.15 | 0-95 | $0→0, $5M→40, $50M→70, $200M+→95 |
| 3 | Drop Certainty | 0.15 | 15-100 | pendingDelete→100, clientRenew→60, active→20 |
| 4 | Domain Authority | 0.10 | 0-95 | Log-scale DataForSEO rank |
| 5 | Niche Fit | 0.10 | 30-90 | AI→90, fintech→80, healthtech→75, other→30 |
| 6 | Domain Name Value | 0.10 | 5-95 | Single-word .com→95, brandable→60, hyphenated→10 |
| 7 | Traffic Value | 0.05 | 0-90 | Referring domain count proxy |
| 8 | Domain Age | 0.05 | 10-90 | <1yr→10, 3-5yr→50, 10+yr→90 |
| 9 | Trademark Safety | 0.05 | 50-90 | >12mo since shutdown→90 |

## Competition Penalty

| DR Bracket | DataForSEO Rank | Multiplier | Tier |
|------------|----------------|------------|------|
| DR 60+ | ≥1,000,000 | 0.3x | auction |
| DR 50-60 | ≥100,000 | 0.5x | stretch |
| DR 35-50 | ≥10,000 | 0.7x | stretch |
| DR 10-35 | ≥100 | 1.0x | sweet_spot (if 2+ editorial) |
| DR <10 | <100 | 0.8x | junk (if <2 editorial) |

## API Client Inventory (15)

| Client | Rate Limit | Key Methods |
|--------|-----------|-------------|
| rdap_client.py | 3s/TLD, 20 concurrent | lookup(), lookup_batch() |
| dataforseo.py | 1000/bulk | bulk_ranks(), bulk_pages_summary(), bulk_referring_domains() |
| dynadot_client.py | 10 req/min | backorder(), delete_backorder(), list_backorder(), search() |
| deepseek.py | 200 domains/run, 50 batch | classify_domains_batch(), classify_domains_all() |
| anthropic_client.py | Per-model | AI verdicts (ORACLE) |
| wayback.py | Respectful | Archive history |
| whoisfreaks.py | Per-plan | Domain discovery |
| catchdoms.py | Per-plan | Expired domain discovery |
| google_cse.py | 100/day | Relevance scoring |
| moz_apify.py | Per-plan | Authority metrics |
| github_search.py | 30 req/min | Tech trend detection |
| reddit_search.py | 60 req/min | Community discovery |
| whois_lookup.py | ~1 req/s | Fallback registrar check |
| rate_limiter.py | N/A | Shared rate limiting utility |

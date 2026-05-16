# Domain Hunter — Codebase Inventory

**Root**: `/Users/mike/Desktop/domainhunter/`
**Total**: 32 Python files, 15 API clients, 7 agents, 7 models, 14 test modules

---

## Directory Structure

```
domainhunter/
├── scripts/          # 12 pipeline scripts
│   ├── startup_reaper.py        (1,262 LOC) — 7-stage reaper pipeline
│   ├── drop_monitor.py          (660 LOC)   — RDAP monitor + auto-backorder
│   ├── dropcatch_csv_scanner.py (223 LOC)   — CSV stream scorer
│   ├── classify_targets.py      — DeepSeek classifier
│   ├── dynadot_place_backorders.py — Batch backorders
│   ├── watchlist_monitor.py     — WHOIS expiry monitor
│   ├── dropcatch_opener.py      — Batch DropCatch page opener
│   ├── sprint16_*.py (4 files)  — Whale analysis + reclassifier
│   ├── run_drop_monitor.sh      — Cron wrapper
│   ├── run_startup_reaper.sh    — Cron wrapper
│   └── monitored_domains.json   — 35 watched domains
│
├── clients/          # 15 API clients
│   ├── rdap_client.py     (362 LOC) — RDAP domain status
│   ├── dataforseo.py      (375 LOC) — SEO bulk metrics
│   ├── dynadot_client.py  (391 LOC) — Backorder placement
│   ├── deepseek.py        (399 LOC) — LLM classification
│   ├── anthropic_client.py — Claude AI verdicts
│   ├── wayback.py         — Wayback CDX archives
│   ├── whoisfreaks.py     — Domain discovery
│   ├── catchdoms.py       — Expired domains
│   ├── google_cse.py      — Search relevance
│   ├── moz_apify.py       — Authority metrics
│   ├── github_search.py   — Tech trends
│   ├── reddit_search.py   — Community discovery
│   ├── whois_lookup.py    — WHOIS fallback
│   └── rate_limiter.py    — Shared utility
│
├── agents/           # 7 AI agents
│   ├── scout.py      — Domain discovery
│   ├── sentinel.py   — SEO verification
│   ├── archivist.py  — History verification
│   ├── spectre.py    — Niche classification
│   ├── oracle.py     — Final verdict
│   └── radiograph.py — 7-dim scoring
│
├── models/           # 7 frozen dataclasses
│   ├── candidate.py       (53 LOC)  — DomainCandidate
│   ├── scored.py          — ScoredDomain
│   ├── vetted.py          — VettedDomain
│   ├── verified.py        — VerifiedDomain
│   ├── verdict.py         — DomainVerdict
│   └── reaped_startup.py  (139 LOC) — DeadStartup→ReapedDomain
│
├── tests/            # 14 test modules + 8 fixtures
│   ├── test_startup_reaper.py  (86 tests) — Scoring, competition, dedup
│   ├── test_drop_monitor.py    — RDAP + transitions
│   ├── test_dynadot_client.py  — Backorder API
│   ├── test_dataforseo_bulk.py — SEO bulk
│   ├── test_rdap_client.py     — RDAP lookup
│   ├── test_deepseek.py        — Classification
│   ├── test_pipeline.py        — Integration
│   ├── test_scout.py           — Discovery
│   ├── test_sentinel.py        — Verification
│   ├── test_archivist.py       — History
│   ├── test_spectre.py         — Niche
│   ├── test_oracle.py          — Verdicts
│   ├── test_radiograph.py      — Scoring
│   ├── test_domain_offeror.py  — Offers
│   └── fixtures/               — 8 JSON mock files
│
├── config/           # Configuration
│   ├── settings.py   (86 LOC) — Pydantic Settings (frozen)
│   └── constants.py  — Pipeline constants
│
├── tools/            # 8 utility scripts
│   ├── daily_hunter.py       — Daily orchestrator
│   ├── bulk_etv_scan.py      — ETV scanning
│   ├── snapnames_etv_scan.py — SnapNames scanning
│   ├── domain_offeror.py     — Offer generator
│   ├── dropwatch_scorer.py   — Drop scoring
│   ├── gate_pipeline.py      — Quality gates
│   └── pipeline_status.py    — Status monitoring
│
├── data/             # 158+ files (~430MB)
│   ├── startup_reaper_*.json  — Reaper scan results
│   ├── sprint7_dead_startups.json (42 startups)
│   ├── sprint14_startup_domains.json (205 domains)
│   ├── sprint16_fresh_startups.json (28 entries)
│   ├── dropcatch_scan_*.json  — DropCatch results
│   ├── gd_expiring/   (300MB) — GoDaddy expiring
│   ├── gd_closeout/   (87MB)  — GoDaddy closeout
│   └── whois_records/         — WHOIS cache
│
├── reports/          # 43 HTML/MD reports
│   ├── DASHBOARD.html
│   ├── PIPELINE-IMPROVEMENT-DASHBOARD.html
│   ├── STARTUP-REAPER-SPRINT20.md
│   └── SPRINT1-SPRINT16 reports
│
├── logs/             # Execution logs
├── storage/          # SQLite management
├── notifications/    # Alert system
├── deploy/           # Deployment scripts
├── domains/          # 99+ domain analysis MDs
│
├── main.py           — Main pipeline orchestrator
├── dashboard.py      — Dashboard generator
├── .env              — API keys (not committed)
├── pyproject.toml    — Python project config
└── requirements.txt  — Dependencies
```

## Cron Schedule

```crontab
0 */6 * * * /bin/bash run_drop_monitor.sh --tier critical    # Every 6 hours
0 3 * * *   /bin/bash run_drop_monitor.sh --tier all         # Daily 3 AM
30 6 * * 1  /bin/bash run_startup_reaper.sh                  # Weekly Mon 6:30
```

## Key Dependencies

```
httpx, aiohttp          — HTTP clients
structlog               — Structured logging
tenacity                — Retry logic
pydantic, pydantic-settings — Config validation
pytest, pytest-cov      — Testing
ruff                    — Linting
mypy                    — Type checking
```

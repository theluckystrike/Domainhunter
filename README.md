# Project REVENANT — Domain Acquisition Pipeline

Automated system for discovering, scoring, monitoring, and acquiring high-value expiring domains.

## What It Does

1. **Discovers** expiring domains from DropCatch CSVs (700K+/day), RDAP queries, and WHOIS sweeps
2. **Scores** them across 7 dimensions: ETV, backlinks, brandability, keyword value, length, TLD, and niche fit
3. **Monitors** 18 tracked targets via cron (RDAP + WHOIS fallback, every 6h for critical tier)
4. **Alerts** on status changes via Slack, email, and macOS desktop notifications
5. **Places backorders** automatically via Dynadot REST API ($10.99/catch, pre-pendingDelete)
6. **Opens DropCatch pages** via AppleScript for manual backorder ($59, pendingDelete only)

## Architecture

```
clients/          API clients (RDAP, Dynadot, DeepSeek, Moz, DataForSEO, Wayback, WHOIS)
agents/           AI agents (Scout, Sentinel, Oracle, Spectre, Archivist, Radiograph)
models/           Domain lifecycle: Candidate → Scored → Vetted → Verified → Verdict
scripts/          Operational tools (drop monitor, CSV scanner, backorder automation, cron)
tools/            Daily pipeline, ETV scanner, SnapNames scanner, domain offer tool
config/           Settings + constants (RDAP servers, EPP signals, registrar grace periods)
notifications/    Slack, email, desktop alert formatters + sender
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/drop_monitor.py` | RDAP/WHOIS monitor for 18 tracked domains (cron) |
| `scripts/dropcatch_csv_scanner.py` | Score 700K+ domains from DropCatch daily CSV |
| `scripts/dynadot_place_backorders.py` | Batch backorder via Dynadot API |
| `scripts/dropcatch_opener.py` | Open DropCatch pages in Chrome via AppleScript |
| `scripts/classify_targets.py` | DeepSeek V3 domain classifier (7 dimensions) |
| `tools/daily_hunter.py` | Full daily pipeline orchestrator |

## Platform Strategy

| Platform | When | Cost |
|----------|------|------|
| **Dynadot** | Pre-pendingDelete backorders | $10.99/catch |
| **DropCatch** | PendingDelete window (5 days) | $59/backorder |
| **GoDaddy Auctions** | GoDaddy-registered internal auctions | $4.99/yr + bid |

## Quick Start

```bash
# Monitor all tracked domains
python scripts/drop_monitor.py --tier all

# Scan a DropCatch CSV for gems
python scripts/dropcatch_csv_scanner.py /path/to/csv --min-score 25 --top 50

# Place Dynadot backorders (dry run)
python scripts/dynadot_place_backorders.py --tier critical --dry-run

# Open DropCatch pages for manual backorder
python scripts/dropcatch_opener.py guerrameats.com sunnyray.org
```

## Stats

- **19 sprints** completed
- **2.29M domains** scanned to date
- **18 domains** under active monitoring (4 tiers)
- **3,500+ LOC** in Python (NASA P10 compliant)
- **38 tests** passing

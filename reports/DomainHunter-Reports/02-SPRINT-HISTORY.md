# Domain Hunter — Sprint History

**21 sprints completed** | 2026-01 through 2026-05-15

---

## Sprint 21: The $10.99 Pipeline (2026-05-15) — CURRENT

**Goal**: Transform Reaper from discovery tool to autonomous catch system

### Delivered
- 9-dimension scoring (added domain_name_value at 0.10 weight)
- Revised weights: editorial 0.25 (was 0.15), DA 0.10 (was 0.20)
- Competition penalty: 4-tier system (sweet_spot/stretch/auction/junk)
- Competition score multiplier: 0.3x (auction) to 1.0x (sweet_spot)
- Auto-backorder Stage 7: Dynadot API, 20 slots, $220 cap
- Editorial source detection: DataForSEO referring_domains
- Drop monitor fix: `backorder` → `add_backorder_request`
- CLI: --auto-backorder, --dry-run-backorder flags
- 86 tests (23 new)

### Results
- 149 domains scored, 38 sweet_spot, 111 junk
- Top: humane.com (58.3), arrival.com (56.5), irl.com (56.0)

---

## Sprint 20: Startup Reaper (2026-05-15)

**Goal**: Find 50-100 domains like ghostautonomy.com

### Delivered
- 6-stage pipeline: HARVEST → RESOLVE → PROBE → ENRICH → SCORE → OUTPUT
- 3 data sources: existing files (269), YC dead list (1,034), DeepSeek (50)
- 8-dimension scoring composite
- RDAP rate limiting (0.3s delay)
- YC dead list parser (filter status=Inactive from 5,906)
- DeepSeek anti-hallucination prompt
- Auto-add to monitored_domains.json
- 63 tests, weekly cron installed

---

## Sprint 19: Drop Monitor (2026-05-14)

**Goal**: RDAP-based domain status monitoring with auto-backorder

### Delivered
- RDAP monitor with WHOIS fallback
- Drop lifecycle detection: grace → redemption → pendingDelete → available
- SQLite persistence (domain_monitoring table)
- macOS desktop notifications + Slack alerts
- Auto-backorder on pendingDelete detection
- 660 LOC, NASA P10 compliant

---

## Sprint 18: Backorder Verification (2026-05)

- DropCatch acquisition strategy
- DismissTicket deep research (38KB report)
- LastChance pipeline analysis

## Sprint 17: SnapNames ETV Scan (2026-05-11)

- Whale domain blitz
- Keyword deep-dive analysis
- Goldmine domain identification
- 9,336-line scan results

## Sprint 16: Fresh Startups + Whales (2026-05)

- 28 new shutdowns catalogued
- Whale WHOIS sweep (98 domains)
- Monetization classifier (affiliate, SaaS, content, lead gen)
- Reclassifier for false positive distress signals

## Sprint 14: Startup Domains (2026-05)

- 205 dead startup domains tracked
- Cross-referenced funding + sector data
- Backorder guide published

## Sprint 7: Dead Startups DB (2026-04)

- 42 confirmed dead startups with $20B+ total funding
- ghostautonomy.com identified ($220M, DA 52, TM abandoned)
- Press coverage depth analysis

## Sprints 1-6: Foundation

- 5-agent pipeline: SCOUT → SENTINEL → ARCHIVIST → SPECTRE → ORACLE
- 7-dimension RADIOGRAPH scoring
- Domain classifier + appraiser
- SEO strategy + content recovery
- Backorder strategy guides
- Infrastructure + monitoring

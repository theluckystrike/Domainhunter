# DOMAIN HUNTER — Sprint 20 Report: Startup Reaper Bug Fix + Rate Limiter

**Date:** 2026-05-16 | **Agents:** 12 (8 research + 4 fix) | **Cost:** $0.00

---

## Objective

Execute Sprint 20 plan: fix startup_reaper.py model mismatches, add DropCatch rate limiter, validate pipeline end-to-end.

## Results — All Objectives Met

### 1. DropCatch Rate Limiter — FIXED

**File:** `clients/dropcatch_client.py`

The NameBright API has a hard rate limit: **30 requests per 30 seconds (~1 req/sec)**. Exceeding it revokes access.

**Changes:**
- Added `_RateLimiter` class — thread-safe sliding-window rate limiter using `deque` + `threading.Lock`
- Enforces dual constraints: min 1.0s interval between requests AND max 30 requests per 30-second window
- All 9 HTTP calls routed through single `_rate_limited_request()` chokepoint
- Zero new dependencies (stdlib only: `threading`, `collections.deque`)
- Logs when throttling kicks in via existing structlog logger
- NASA P10 compliant: all functions <60 lines, 3 assertions in `__init__`, 2 in `_rate_limited_request`

### 2. Startup Reaper Model Alignment — 7 CRITICAL BUGS FIXED

**Files:** `scripts/startup_reaper.py`, `tests/test_startup_reaper.py`, `models/reaped_startup.py`

The Sprint 20 plan rewrote the model dataclasses (`DeadStartup`, `ResolvedStartup`, `ProbedStartup`, `ReapedDomain`) with new field names, but the 1,411-line script still used the old field names. Every constructor call would crash at runtime.

**Bug 1: Constructor field names wrong in ALL 6 harvest functions**
- `company_name=` -> `name=` (6 locations)
- `shutdown_date=` (str) -> `death_year=` (int|None) (6 locations)
- `notes=` -> `description=` (4 locations)
- `press_mentions=` removed (2 locations, field doesn't exist)

**Bug 2: death_year type mismatch**
- Added `_parse_year()` helper: parses "2024-04", "2026-05-06", "Winter 2021", "2023" -> `int | None`
- Applied to all 6 constructor calls

**Bug 3: _batch_to_year regex didn't match YC format**
- YC API returns "Winter 2021" but regex expected "W21"
- Fixed: primary `r"(\d{4})"` regex + fallback `r"[WSws](\d{2})"`
- Return type changed from `str` to `int | None`

**Bug 4: _yc_tags_to_sector returned invalid sectors**
- Returned "devtools", "proptech", "robotics", "saas" which aren't in ALLOWED_SECTORS
- Fixed sector_map to map to valid values only
- Changed fallback from `str(tags[0]).lower()[:30]` to `"other"`

**Bug 5: Missing sector normalization**
- Added `_normalize_sector()` helper with 24 alias mappings
- Applied to all 6 harvest functions

**Bug 6: Sprint 16 used TLD as sector**
- `s.get("tld", "other")` was nonsensical (used ".com" as sector)
- Fixed to use reason/notes field with `_normalize_sector()`

**Bug 7: ReapedDomain constructor had 6 extra/missing fields**
- Removed: `tld`, `creation_date`, `editorial_sources`, `score_breakdown`, `competition_tier`, `domain_name_value`
- Added: `resolution_method`, `funding_score`, `authority_score`, `drop_certainty_score`, `editorial_score`, `age_score`, `niche_score`, `traffic_score`, `trademark_score`, `spam_score`
- Fixed `_format_table()` and `_auto_backorder()` references
- Fixed `run_reaper()` tier counting

### 3. Test Suite — ALL PASSING

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 104/123 (19 failures) | **123/123** |
| Full suite | 333/352 | **352/352** |
| Runtime | 0.46s | 0.28s |

### 4. Dry-Run Validation — CLEAN

```
$ python3 scripts/startup_reaper.py --dry-run --sources existing
  Stage 1: HARVEST — 269 startups loaded
  Stage 2: RESOLVE — 228 domains resolved
  Stage 3: PROBE — 228 checked
  Stage 5: SCORE — 128 domains above 25.0
  Stage 6: OUTPUT — Results saved
```

Top result: byjus.com (34.2 score, $5.5B funded, edtech). All tiers = "low" because dry-run skips RDAP/DataForSEO enrichment (no real EPP status or DA data).

### 5. Phase 1 Research (8 parallel agents)

| Agent | Key Finding |
|-------|-------------|
| Client patterns | DeepSeek async httpx, DataForSEO aiohttp, RDAP 20-concurrent semaphore, Wayback 1s delay |
| Data files | 4 sources: sprint7 (42), sprint14 (205), sprint16 (28), sprint27_kaggle (500) |
| CLI/output patterns | argparse + format_table + save_results + monitored_domains.json read/write |
| YC Dead List | 1,034 inactive companies, 98% have website field, NO funding data, "Winter 2021" batch format |
| monitored_domains.json | 4-tier structure (critical/high/medium/low), auto-add threshold = score >= 55 |
| Directory structure | 67 scripts, 15 clients, 18 test files, 207 data directories |
| config/settings.py | Pydantic BaseSettings, .env loading, monitored_domains_path, quality thresholds |

## Files Modified

| File | Change |
|------|--------|
| `clients/dropcatch_client.py` | +_RateLimiter class, +_rate_limited_request(), 9 HTTP calls wrapped |
| `models/reaped_startup.py` | Rewritten with 4 frozen dataclasses (new Sprint 20 model) |
| `scripts/startup_reaper.py` | 7 bugs fixed across ~30 locations, +_parse_year(), +_normalize_sector() |
| `tests/test_startup_reaper.py` | 19 test fixes (field names, return types, constructor args) |

## Metrics

| Metric | Value |
|--------|-------|
| Tests passing | 352/352 |
| Bugs found | 7 critical (all runtime crashes) |
| Bugs fixed | 7/7 |
| Lines changed | ~200 across 4 files |
| New dependencies | 0 |
| API cost | $0.00 |
| NASA P10 violations | 0 |

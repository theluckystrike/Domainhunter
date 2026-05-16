# Mass Domain Checker — Research & Discovery Report

**Date:** 2026-05-01
**Scope:** Full inventory of existing domain tools + technical research for next-gen mass domain checker

---

## Executive Summary

Your ecosystem already contains **a working bulk domain checker** (`domain_checker.py`) plus **7 deployed domain/DNS tools** across Zovo.one and GitHub. The existing Python checker handles RDAP-only availability checks at ~3,000 domains/2-3 min. The opportunity is to build a **next-gen Node.js/TypeScript mass domain checker** with a two-stage pipeline (DNS fast-pass + RDAP confirmation), richer data extraction (expiry, registrar, nameservers, DNS records), multi-format reporting (HTML/JSON/CSV/MD), and integration with your satellite monitoring infrastructure.

---

## Part 1: Existing Domain Tools Inventory

### A. Bulk Domain Checker (Python)

| Field | Value |
|-------|-------|
| **Path** | `~/Downloads/misc/files/domain_checker.py` |
| **Language** | Python 3 (async/aiohttp) |
| **Lines** | 245 |
| **Speed** | ~40 concurrent, ~3,000 domains in 2-3 min |
| **Protocol** | RDAP only (Verisign + rdap.org fallback) |
| **Output** | CSV (all results) + TXT (available only) |
| **Status** | Working, standalone |

**Strengths:**
- Fast async execution with semaphore-controlled concurrency
- RDAP fallback between two servers
- Rate limit handling (429 backoff)
- Progress bar with ETA

**Gaps (opportunities for v2):**
- RDAP-only — no DNS pre-filtering stage (hits RDAP for every domain)
- .com only (hardcoded Verisign endpoint)
- No data extraction (expiry dates, registrar, nameservers)
- No HTML report generation
- No satellite network integration
- No NASA P10 compliance (unbounded `results` array, no assertions, no function length limits)
- No multi-TLD support

### B. Domain Batch Files

| File | Count |
|------|-------|
| `~/Downloads/domains/domains_batch6.txt` | 50,053 domains |
| `~/Downloads/domains/domains_batch7.txt` | 10,612 domains |
| `~/Downloads/domains/domains_batch8_4letter.txt` | 45,000 domains |
| `~/Downloads/domains/domains_batch9_5letter.txt` | 50,000 domains |
| `~/Downloads/domains/domains_batch10_premium.txt` | 6,590 domains |
| `~/Downloads/domains/domains_batch12_keywords.txt` | 5,916 domains |
| **Total** | **~168,171 domains** |

### C. GitHub: matrix-domain-quest

| Field | Value |
|-------|-------|
| **Repo** | `theluckystrike/matrix-domain-quest` (private) |
| **Language** | TypeScript (React + Vite) |
| **Purpose** | Domain portfolio display with Matrix-theme UI |
| **Features** | 40+ domains tracked, pricing, expiry dates, categories (AI/ML, SaaS, Finance, Brand, SEO) |
| **Stack** | React 18, shadcn/ui, Tailwind, TanStack Query, Zod, Vitest, Playwright |
| **Updated** | 2026-04-05 |

### D. Zovo.one Production Tools (5 domain/DNS tools)

| Tool | Path | Lines | Live URL |
|------|------|-------|----------|
| WHOIS Lookup | `zovo-one-source/public/static-tools/whois-lookup/index.html` | 1,991 | zovo.one/free-tools/whois-lookup |
| DNS Lookup | `zovo-one-source/public/static-tools/dns-lookup/index.html` | 1,126 | zovo.one/free-tools/dns-lookup |
| SSL Checker | `zovo-one-source/public/static-tools/ssl-checker/index.html` | 1,312 | zovo.one/free-tools/ssl-checker |
| Domain Availability | `zovo-one-source/public/static-tools/domain-availability-checker/index.html` | 777 | zovo.one/free-tools/domain-availability-checker |
| DNS Propagation | `zovo-one-source/public/static-tools/dns-propagation-checker/index.html` | 773 | zovo.one/free-tools/dns-propagation-checker |
| Domain Name Generator | `zovo-one-source/public/static-tools/domain-name-generator/index.html` | 743 | zovo.one/free-tools/domain-name-generator |

All client-side HTML, using Google DNS-over-HTTPS API. No server dependency.

### E. Satellite Monitoring Infrastructure

| Tool | Path | Purpose |
|------|------|---------|
| Health Check | `~/zovo-monitoring/scripts/satellite-health-check.sh` | Monitor 18 domains (DNS, SSL, response time) |
| GSC Bulk Setup | `~/satellite/scripts/gsc-bulk-setup.py` | OAuth + Cloudflare DNS + GSC verification for 18 domains |
| Indexing Check | `~/satellite/scripts/check-indexing.py` | GSC impressions/clicks across satellite network |
| Sitemap Ping | `~/satellite/scripts/ping-sitemaps.sh` | Ping Google/Bing sitemaps for 18 domains |
| GSC Pipeline | `~/zovo-monitoring/gsc-indexing-pipeline.js` | Submit URLs to GSC (20/day, NASA P10 compliant) |

### F. GitHub DNS/Domain Repos (archived)

| Repo | Status | Purpose |
|------|--------|---------|
| `ext-dns` | Archived | DNS resolution for Chrome extensions |
| `webext-dns` | Archived | Typed DNS helpers for @zovo/webext |
| `webext-domain-permission-toggle-fork` | Public | Domain permission toggle for extensions |

---

## Part 2: Technical Research — Building the Next-Gen Mass Domain Checker

### Protocol Comparison

| Protocol | Speed | Rate Limit | Accuracy | Cost | Best For |
|----------|-------|-----------|----------|------|----------|
| **Node.js `dns` module** | 5-50ms | Effectively none | ~85% | Free | Fast first-pass filtering |
| **RDAP** (modern) | 200-1500ms | 1-10/sec/TLD | 99%+ (gTLD) | Free | Primary authoritative lookup |
| **WHOIS** (legacy, sunset Jan 2025) | 200-2000ms | 10-60/min | 99%+ | Free | ccTLD fallback |
| **DNS-over-HTTPS** | 20-100ms | Effectively none | ~85% | Free | Encrypted DNS, firewall bypass |
| **Registrar APIs** (GoDaddy, CF) | 100-500ms | 60/min | 100% | Account required | Pre-registration |

### Key Insight: WHOIS is Officially Dead

ICANN sunset WHOIS on **January 28, 2025**. gTLD operators no longer required to maintain port 43 servers. **RDAP is the mandatory replacement** with 100% gTLD coverage and ~60% ccTLD coverage (growing rapidly).

### Recommended Architecture: Two-Stage Pipeline

```
┌─────────────────────────────────────────────────────┐
│                  INPUT: domains.txt                  │
│              (1K - 1M+ domains)                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 1: DNS FAST PASS                             │
│  ─────────────────────                              │
│  • Node.js dns.promises.resolve()                   │
│  • 50-100 concurrent (no rate limits)               │
│  • 1,000-2,000 domains/min                          │
│  • NXDOMAIN → "probably available" → Stage 2        │
│  • Has records → "definitely registered" → SKIP     │
│  • Filters out 70-90% of domains instantly          │
└──────────────────────┬──────────────────────────────┘
                       │ (only NXDOMAIN domains)
                       ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 2: RDAP CONFIRMATION                         │
│  ──────────────────────                             │
│  • whoiser or @iocium/rdap-lite                     │
│  • 5-10 concurrent, 1-2 req/sec per TLD            │
│  • Bottleneck rate limiter (per-TLD groups)         │
│  • 404 = genuinely available                        │
│  • 200 = registered (extract full data)             │
│  • Fallback to WHOIS for ccTLDs without RDAP       │
│  • ~50-100 domains/min                              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 3: DATA ENRICHMENT (registered domains)      │
│  ──────────────────────────                         │
│  • Expiry date extraction                           │
│  • Registrar identification                         │
│  • Nameserver enumeration                           │
│  • EPP status codes                                 │
│  • DNSSEC status                                    │
│  • DNS records (A, MX, NS, TXT)                     │
│  • Hosting provider detection                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  OUTPUT: Multi-format Reports                       │
│  ────────────────────────                           │
│  • HTML report (sortable tables, color-coded)       │
│  • JSON data file (machine-readable cache)          │
│  • CSV export (spreadsheet analysis)                │
│  • MD summary (git-trackable)                       │
│  • Console output (progress + results)              │
└─────────────────────────────────────────────────────┘
```

### Why Two-Stage Beats Single-Stage

Your current `domain_checker.py` hits RDAP for every domain. For 50,000 domains at RDAP rate limits, that takes hours. The two-stage approach:

| Metric | Current (RDAP-only) | Two-Stage (DNS→RDAP) |
|--------|---------------------|----------------------|
| 1,000 domains | ~3-5 min | ~1-2 min |
| 10,000 domains | ~30-50 min | ~10-15 min |
| 50,000 domains | ~3-5 hours | ~30-60 min |
| 168K domains (your batches) | ~10-17 hours | ~2-4 hours |

DNS eliminates 70-90% of domains from the RDAP stage, so the bottleneck (rate-limited RDAP) only processes a fraction.

### Node.js Library Recommendations

**Core:**

| Library | Purpose | Why |
|---------|---------|-----|
| `dns` (built-in) | Stage 1 DNS resolution | Zero dependencies, fast, no rate limits |
| `whoiser` v2 | Stage 2 RDAP + WHOIS | TypeScript-native, 100% TS, auto-discovery, handles both protocols |
| `Bottleneck` | Rate limiting | Zero deps, per-TLD groups, Redis clustering, battle-tested |
| `p-limit` | DNS concurrency cap | Simple, lightweight, works with Promise.all |

**Report generation:**

| Library | Purpose |
|---------|---------|
| Built-in `fs` | JSON/CSV/MD output |
| Template literal | HTML report (no framework needed) |

### Rate Limiting Strategy

```
DNS STAGE:
  Concurrency: 50-100 parallel
  Rate limit: None needed
  Throughput: 1,000-2,000/min

RDAP STAGE (per-TLD Bottleneck groups):
  .com (Verisign):  5 concurrent, 2/sec
  .net (Verisign):  5 concurrent, 2/sec
  .org (PIR):       3 concurrent, 1/sec
  .io (Identity):   3 concurrent, 1/sec
  .dev (Google):    3 concurrent, 1/sec
  Other gTLDs:      2 concurrent, 1/sec
  ccTLDs (WHOIS):   2 concurrent, 0.5/sec

  HTTP 429 → exponential backoff (2s, 4s, 8s, max 3 retries)
```

### Data Extraction Schema

```typescript
interface DomainResult {
  domain: string;
  status: 'available' | 'registered' | 'error' | 'timeout';
  checkedAt: string;  // ISO 8601

  // Stage 1: DNS
  dnsResolved: boolean;
  dnsRecords?: {
    a?: string[];
    ns?: string[];
    mx?: string[];
    txt?: string[];
  };

  // Stage 2: RDAP/WHOIS
  registrar?: string;
  createdDate?: string;
  expiryDate?: string;
  updatedDate?: string;
  nameservers?: string[];
  eppStatus?: string[];
  dnssec?: boolean;

  // Derived
  daysUntilExpiry?: number;
  hostingProvider?: string;  // detected from A/NS records
  expiringSoon?: boolean;    // <90 days
}
```

### NASA Power of 10 Compliance Plan

| Rule | Implementation |
|------|----------------|
| R1: No complex flow | Flat if/else, no recursion, no switch fallthrough |
| R2: Bounded loops | All loops have MAX_ITERATIONS ceiling (DNS: 100K, RDAP: 50K, batches: domain count) |
| R3: No unbounded memory | Stream results to disk, max 10K results in memory, chunked processing |
| R4: Functions <60 lines | Each stage is a separate module, functions do one thing |
| R5: 2+ assertions/fn | Input validation at entry, output validation before return |
| R6: Restricted scope | No globals, module-scoped config only, no mutable shared state |
| R7: Check every return | Every DNS/RDAP call wrapped in try/catch with context |
| R8: Minimal build | Zero transpilation (Node.js ESM), only essential deps |
| R9: No mutations | All results are new objects, no argument mutation |
| R10: Zero warnings | Strict TypeScript, no suppressions |

### Throughput Estimates

| Domain Count | DNS Stage | RDAP Stage (10% pass-through) | Total |
|--------------|-----------|-------------------------------|-------|
| 1,000 | ~30s | ~1-2 min | ~2-3 min |
| 5,000 | ~2.5 min | ~5-8 min | ~8-11 min |
| 10,000 | ~5 min | ~10-15 min | ~15-20 min |
| 50,000 | ~25 min | ~50-75 min | ~1-1.5 hrs |
| 168,171 (your batches) | ~1.5 hrs | ~2.5-4 hrs | ~2.5-4 hrs |

### Use Cases for Your Ecosystem

**1. Satellite Domain Monitoring**
- Weekly automated check of all 18 satellite domains
- Expiry alerts (30/60/90 day warnings)
- DNS health verification (GitHub Pages IPs correct?)
- Registrar change detection

**2. New Domain Discovery**
- Process your 168K batch files through two-stage pipeline
- Filter by: length, brandability, keyword relevance, TLD pricing
- Auto-generate purchase recommendations

**3. Competitor Intelligence**
- RDAP lookup for competitor creation/expiry dates
- Hosting detection from DNS records (GitHub Pages, Vercel, Netlify, Cloudflare)
- Track changes over time with scheduled runs

**4. Domain Portfolio Management**
- Feed results into matrix-domain-quest UI
- Auto-update pricing and expiry data
- Alert on domains approaching renewal

---

## Part 3: Comparison — Current vs Proposed

| Feature | Current (`domain_checker.py`) | Proposed (Node.js v2) |
|---------|-------------------------------|----------------------|
| Language | Python 3 | TypeScript (ESM) |
| Protocol | RDAP only | DNS + RDAP + WHOIS fallback |
| Speed (10K domains) | ~30-50 min | ~15-20 min |
| Multi-TLD | .com only | All gTLDs + ccTLDs |
| Data extraction | Available/Taken only | Full RDAP data (expiry, registrar, NS, EPP) |
| DNS records | None | A, MX, NS, TXT, SOA |
| Report formats | CSV + TXT | HTML + JSON + CSV + MD |
| Satellite integration | None | Built-in monitoring mode |
| NASA P10 | No | Full compliance |
| Rate limiting | Basic (429 backoff) | Per-TLD Bottleneck groups |
| Hosting detection | No | Yes (from DNS records) |
| Expiry alerts | No | Yes (30/60/90 day) |
| Resume capability | No | Yes (JSON checkpoint) |

---

## Part 4: Recommended Tech Stack

```
Runtime:           Node.js 20+ (ESM)
Language:          TypeScript (strict mode)
DNS Layer:         Built-in dns.promises
RDAP/WHOIS:        whoiser v2 (TypeScript-native)
Rate Limiting:     Bottleneck (per-TLD groups)
Concurrency:       p-limit (DNS stage)
Report — HTML:     Template literals (no framework)
Report — JSON:     Built-in JSON.stringify
Report — CSV:      Manual serialization (no dep needed)
Testing:           Node.js test runner (built-in)
```

**Total new dependencies: 3** (whoiser, bottleneck, p-limit)

---

## Part 5: Recommended Next Steps

1. **Scaffold the project** — `~/mass-domain-checker/` with TypeScript ESM, strict mode, NASA P10 structure
2. **Build Stage 1** — DNS fast-pass module with p-limit concurrency
3. **Build Stage 2** — RDAP confirmation module with Bottleneck per-TLD rate limiting
4. **Build Stage 3** — Data enrichment (expiry, registrar, NS, hosting detection)
5. **Build reporter** — HTML + JSON + CSV + MD multi-format output
6. **Build CLI** — Single entry point: `node checker.js domains.txt --report html`
7. **Satellite mode** — `node checker.js --monitor` to check all 18 satellite domains
8. **Test against batch files** — Run against `~/Downloads/domains/` batches for validation

---

## CCG Status (claudecodeguides.com)

| Metric | Value |
|--------|-------|
| Articles | 3,810 total, 3,571 indexable |
| Tools | 10 live tools |
| Latest sprint | STABLE-1 (3,370 tool CTAs, 1,089 links) |
| Domain tools content | 380+ checker/validator keywords identified |
| Related keywords | "whois checker", "domain age checker", "dns checker" |
| Opportunity | Domain checker tool pages can target these keywords from CCG |

---

*Report generated 2026-05-01 by 5-agent parallel research sweep*

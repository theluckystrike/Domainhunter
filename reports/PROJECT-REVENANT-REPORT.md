# PROJECT REVENANT — Domain Hunter Pipeline
## Comprehensive Status Report | May 7, 2026

---

## EXECUTIVE SUMMARY

Project REVENANT is an autonomous 5-agent domain hunting pipeline that discovers, analyzes, and acquires expired/expiring domains to build revenue-generating tool websites. Built across 4 sprints with NASA Power of 10 coding standards.

### Key Stats
- **158 tests passing** across 38 Python files
- **44 domains** in active watchlist
- **3 domains registered** on Cloudflare ($34.18)
- **2 production tools** built (120KB combined)
- **Sprint Score: 9.5/10** (progression: 7.2 → 8.6 → 9.1 → 9.4 → 9.5)
- **Budget: $34.18 of $600 spent** (5.7%)

---

## DOMAINS PURCHASED

Three domains registered on Cloudflare on May 7, 2026. All active with auto-renew, expiring May 7, 2027.

| # | Domain | Cost | Expires | Tool Built? | Monthly Searches | Status |
|---|--------|------|---------|-------------|-----------------|--------|
| 1 | **ingredientcalculator.com** | $10.46 | May 7, 2027 | YES (66KB) | 22K "ingredient calculator" | Active |
| 2 | **pictureeditor.net** | $11.86 | May 7, 2027 | YES (54KB) | 110K "picture editor" | Active |
| 3 | **recipetool.net** | $11.86 | May 7, 2027 | PENDING | 8K "recipe tool" | Active |
| | **TOTAL** | **$34.18** | | | **140K combined** | |

### Why These Domains?

**ingredientcalculator.com** — Exact-match domain for "ingredient calculator" (22K monthly searches). .com TLD gives maximum trust. Recipe/cooking niche has high AdSense RPM ($8-15 CPM). Tool already built: recipe ingredient scaler + unit converter + substitution finder + nutrition estimator.

**pictureeditor.net** — Targets "picture editor" (110K monthly searches). Highest traffic potential in the portfolio. Image editing is an evergreen utility niche. Tool already built: resize, crop, compress, convert, and filter images entirely client-side.

**recipetool.net** — Companion to ingredientcalculator.com in the cooking niche. "Recipe tool" (8K searches) with long-tail potential. Cross-linking between the two cooking domains will boost both. Tool to be built.

---

## TOOLS BUILT

### 1. Ingredient Calculator (ingredientcalculator.com)

**File:** `tools/ingredientcalculator/index.html` (66KB, 1,497 lines)

| Feature | Description |
|---------|-------------|
| Recipe Scaler | Scale any recipe 0.25x to 10x with smart rounding |
| Unit Converter | Convert between 56 ingredient units (cups, grams, ml, oz, etc.) |
| Substitution Finder | Find ingredient substitutes from 56-item database |
| Nutrition Estimator | Estimate calories, protein, carbs, fat per ingredient |

- **Design:** Warm cooking palette — amber (#D97706) on cream (#FFFBF5)
- **Tech:** Zero dependencies, IIFE + strict mode, 14 functions, 28 assertions
- **SEO:** JSON-LD, OG tags, semantic HTML5, sitemap.xml
- **Deploy files:** _headers, _redirects, robots.txt, manifest.json, favicon.svg, 404.html

### 2. Picture Editor (pictureeditor.net)

**File:** `tools/pictureeditor/index.html` (54KB, 1,183 lines)

| Feature | Description |
|---------|-------------|
| Resize | Width/height in px, scale %, aspect ratio lock |
| Crop | Draggable selection, 6 presets (Free, 1:1, 16:9, 4:3, Story, Profile) |
| Compress | Quality slider 10-100%, before/after size comparison |
| Convert | Output as PNG, JPEG, or WebP with quality control |
| Filters | Grayscale, Sepia, Blur, Invert, Vintage + brightness/contrast/saturation |

- **Design:** Deep indigo (#6366f1) on white, dark header (#1e1b4b)
- **Tech:** Zero dependencies, Canvas API, 39 functions, 80 assertions, undo/redo (30 steps)
- **SEO:** JSON-LD WebApplication schema, OG + Twitter cards
- **Deploy files:** _headers, _redirects, robots.txt, sitemap.xml, 404.html
- **Ad zones:** 3 placements (header, below tool, right sidebar)

---

## WATCHLIST (44 Domains)

### CRITICAL Priority (3)
| Domain | Expiry | Notes |
|--------|--------|-------|
| aidevtools.com | May 6, 2026 | EXPIRED — backorder needed |
| seochecker.com | May 8, 2026 | SKIP — redirects to SEOptimer |
| builder.ai | Jun 4, 2026 | DR 68, over budget — monitor only |

### HIGH Priority (11)
| Domain | Expiry | DR | Notes |
|--------|--------|-----|-------|
| bestdevtools.com | May 22, 2026 | ~15 | Likely drops — register at $12 |
| finetuneai.com | May 26, 2026 | ~10 | AI niche |
| taskplanner.com | May 27, 2026 | ~15 | clientRenewProhibited |
| aitoolkit.com | Jun 12, 2026 | ~10 | AI tools niche |
| mortgagecalc.com | Jun 15, 2026 | 6 | SKIP — GoDaddy Corporate/Bankrate |
| loancompare.com | Jun 26, 2026 | ~10 | Finance niche |
| devtools.io | Jul 4, 2026 | ~20 | Developer tools |
| prompttools.com | Jul 18, 2026 | ~10 | AI prompt tools |
| devhub.io | Oct 17, 2026 | 27 | #1 TARGET — $500 Afternic offer |
| apitools.com | Dec 14, 2026 | ~42 | Red Hat docs backlinks |

### MEDIUM Priority (16) + LOW Priority (16)
- Remaining 32 domains tracked with expiry dates through 2030
- Includes domains like colorpicker.com, bmicalculator.com, codeparrot.ai

---

## ACQUISITION STATUS

### Active Offer: devhub.io ($500)
- **Method:** Afternic marketplace
- **DR:** 27 (Ahrefs verified)
- **Key asset:** ethereum.org backlink (DR 93)
- **Status:** Offer text ready, awaiting manual submission

### Eliminated Domains (3)
| Domain | Reason |
|--------|--------|
| fileforge.com | Active YC W24 startup — still operating |
| seochecker.com | 301 redirects to SEOptimer, DR only 1.3 |
| mortgagecalc.com | Owned by GoDaddy Corporate/Bankrate |

---

## BUDGET TRACKER

| Category | Budgeted | Spent | Remaining |
|----------|----------|-------|-----------|
| Domain registrations | $100 | $34.18 | $65.82 |
| devhub.io acquisition | $500 | $0 | $500 |
| Total | $600 | **$34.18** | **$565.82** |

---

## PIPELINE ARCHITECTURE

```
agents/scout.py       → Domain discovery (26+ sources)
agents/radiograph.py  → Authority scoring (DA/DR/backlinks)
agents/spectre.py     → Drop date intelligence (WHOIS/auction)
agents/oracle.py      → Niche keyword analysis (DeepSeek AI)
agents/sentinel.py    → Spam/penalty detection
agents/archivist.py   → Wayback Machine history analysis
clients/dataforseo.py → DataForSEO API (bulk + per-domain)
clients/deepseek.py   → DeepSeek AI API client
watchlist_monitor.py  → 44-domain WHOIS monitor + alerts
tools/domain_offeror.py → Automated offer system + SQLite tracking
config/constants.py   → Pipeline configuration
config/settings.py    → Pydantic settings (frozen)
deploy/deploy.sh      → Cloudflare Pages deployment
```

---

## SPRINT PROGRESSION

| Sprint | Score | Key Deliverables |
|--------|-------|-----------------|
| Sprint 1 | 7.2 | Pipeline architecture, 6 agents, 26 domains discovered |
| Sprint 2 | 8.6 | Scoring system, 22-domain watchlist, test suite |
| Sprint 3 | 9.1 | 287 domains scanned, 44-domain watchlist, 131 tests |
| Sprint 4 | 9.4 | ingredientcalculator tool, deployment pipeline |
| Sprint 4 FINAL | **9.5** | DataForSEO client, pictureeditor tool, offer system, 158 tests |

---

## REVENUE PROJECTIONS

| Period | Conservative | Optimistic |
|--------|-------------|------------|
| Month 3 | $37/mo | $205/mo |
| Month 6 | $150/mo | $750/mo |
| Month 12 | $375/mo | $1,970/mo |
| Year 1 Total | $1,800 | $9,600 |
| Year 1 ROI | 3x | 16x |

---

## IMMEDIATE NEXT ACTIONS

1. **Deploy ingredientcalculator.com** to Cloudflare Pages
2. **Deploy pictureeditor.net** to Cloudflare Pages
3. **Submit devhub.io $500 offer** on Afternic
4. **Activate DataForSEO Backlinks API** — app.dataforseo.com
5. **Backorder aidevtools.com** on DropCatch ($12)
6. **Build recipetool.net** tool site
7. **Submit all sites to Google Search Console**
8. **Monitor bestdevtools.com** (expires May 22)
9. **Monitor taskplanner.com** (expires May 27)

---

*Project REVENANT | 38 Python files | 158 tests | 44 domains | 3 registered | 2 tools built*
*Generated: May 7, 2026*

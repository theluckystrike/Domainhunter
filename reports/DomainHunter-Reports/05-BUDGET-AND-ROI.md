# Domain Hunter — Budget & ROI Analysis

---

## Current Balances

| Account | Balance | Purpose |
|---------|---------|---------|
| Dynadot | $25.00 | Backorder deposits |
| DataForSEO | Subscription | SEO bulk API |
| DeepSeek | ~$25 remaining | LLM classification |

## Cost Structure

### Per-Scan Costs (Weekly Reaper)

| Stage | API | Cost |
|-------|-----|------|
| HARVEST (DeepSeek) | 1 call, ~2K tokens | $0.02 |
| HARVEST (YC Dead) | 1 HTTP GET | $0.00 |
| RESOLVE (DeepSeek) | 1 call, ~1K tokens | $0.01 |
| PROBE (RDAP) | ~180 lookups | $0.00 |
| ENRICH (DataForSEO) | 2 bulk calls | $0.12 |
| **Total per scan** | | **$0.15** |

### Annual Operating Cost

| Item | Monthly | Annual |
|------|---------|--------|
| Weekly Reaper scans (4.3/mo) | $0.65 | $7.80 |
| Drop Monitor RDAP (free) | $0.00 | $0.00 |
| Backorder catches (~1/mo est.) | $10.99 | $131.88 |
| **Total operations** | **~$12** | **~$140** |

## Backorder Budget

| Parameter | Value |
|-----------|-------|
| Max concurrent backorders | 20 |
| Cost per backorder | $10.99 |
| Max budget exposure | $219.80 |
| Charge model | On success only |
| Current active backorders | 0 |
| Available slots | 20 |

## ROI Projections

### Domain Value Estimates (post-catch)

| Domain Type | Catch Cost | Flip Value | ROI |
|-------------|-----------|------------|-----|
| Premium .com (olive.com, irl.com) | $10.99 | $5,000-50,000 | 45,000%+ |
| Funded startup .com (ghostautonomy.com) | $10.99 | $1,000-10,000 | 9,000%+ |
| Keyword .com (codehelper.com) | $10.99 | $500-2,000 | 4,500%+ |
| Niche .ai/.io (codeparrot.ai) | $10.99 | $200-1,000 | 1,800%+ |

### Scenario Analysis

| Scenario | Catches/yr | Avg Value | Revenue | Cost | Profit | ROI |
|----------|-----------|-----------|---------|------|--------|-----|
| Conservative | 2 | $500 | $1,000 | $140 | $860 | 614% |
| Moderate | 5 | $1,000 | $5,000 | $195 | $4,805 | 2,464% |
| Optimistic | 10 | $2,000 | $20,000 | $250 | $19,750 | 7,900% |
| Whale catch | 1 | $10,000 | $10,000 | $151 | $9,849 | 6,522% |

### Key Insight
At $10.99/catch with no charge on failure, the risk profile is asymmetric:
- **Downside**: $10.99 per attempt (capped at $220 total exposure)
- **Upside**: $500-50,000 per successful catch
- **Break-even**: 1 catch at $140+ value covers entire year of operations

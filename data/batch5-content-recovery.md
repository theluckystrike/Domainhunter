# Batch 5: Content Recovery Analysis
## Sprint 2 — Deep Analysis of 5 Target Domains
### Generated: 2026-05-06

---

## EXECUTIVE SUMMARY

Analyzed 5 domains via Wayback Machine CDX API, WHOIS, live HTTP checks, web research, and GitHub repository inspection. Key finding: **devhub.io** has the most content recovery potential with ~25,900 archived URLs; **launchable.io** has the highest brand-authority pedigree from its CloudBees acquisition; **techstack.com** is still an active business and not available.

| Domain | Type | Pages Archived | Current Status | Recovery Feasibility | Priority |
|--------|------|---------------|----------------|---------------------|----------|
| launchable.io | SaaS (CI/CD) | ~30 | Domain held (autoRenewPeriod) | MEDIUM | HIGH |
| apitools.com | SaaS (API proxy) | ~158 | Parked (redirect to cdez.com) | LOW | LOW |
| techstack.com | Active business | ~9,136 | **LIVE SITE** (active .com) | N/A — NOT AVAILABLE | SKIP |
| devhub.io | Dev tool aggregator | ~25,924 | Parked (lander redirect) | HIGH | HIGH |
| codeguide.com | Parked/minimal | ~15 | Down (no HTTP response) | LOW | LOW |

---

## DOMAIN 1: launchable.io

### What Was the Site?
**SaaS Application — AI-Powered CI/CD Test Intelligence Platform**

Launchable was a software development intelligence platform focused on continuous integration (CI). Founded in 2019 by Kohsuke Kawaguchi (creator of Jenkins) and Harpreet Singh, both former CloudBees employees. Raised venture funding from Accel and others.

**Acquired by CloudBees in August 2024.** Product features absorbed into CloudBees Smart Tests platform at launchableinc.com.

### Core Product Features
- **Predictive Test Selection**: ML model that selects the right tests for specific code changes
- **Test Failure Diagnostics**: AI-powered triaging to reduce overhead
- **Test Insights Dashboard**: Trends, flaky test detection, health metrics
- **Integrations**: Jenkins, CircleCI, GitHub Actions, Bitbucket Pipelines
- **Test Runners**: Cucumber, Cypress, Gradle, Jest, Maven, minitest, pytest, Robot, RSpec

### Business Impact Claims
- 2,000+ hours saved per month
- 50% reduction in machine hours
- 90% reduction in test execution times
- 40% reduction in build times

### Wayback Archive Analysis
- **Total unique URLs archived**: ~30
- **First archived**: 2013 (earlier incarnation), primary content from 2021+
- **Earliest CDX record**: 2013-09-02 (HTTP 200)
- **Content depth**: Shallow — mostly landing pages, pricing, blog teasers

### WHOIS Status
- **Registrar**: Humbly LLC
- **Created**: 2021-04-10
- **Expiry**: 2027-04-10
- **Status**: autoRenewPeriod
- **Current HTTP**: Not responding (connection timeout)
- **Assessment**: Domain is in auto-renew period. CloudBees may be holding it or may let it lapse. The fact that it's not resolving and is in autoRenewPeriod suggests it may not be actively managed.

### Topics Covered
- CI/CD pipeline optimization
- AI/ML in software testing
- Predictive test selection methodology
- Developer productivity metrics
- Integration guides for major CI systems

### Old URL Structure
```
/                    (homepage/landing)
/pricing/            (pricing page)
/blog/               (blog)
/docs/               (documentation)
/features/           (feature pages)
```

### Content Recovery Assessment
- **Feasibility**: MEDIUM
- **Why**: Only ~30 unique URLs archived. Primary value is in the BRAND and BACKLINKS from the CloudBees acquisition press coverage (TechTarget, SiliconANGLE, DevOps.com, DEVOPSdigest, TFiR, Intellyx, DuploCloud all linked). The actual site content was thin — mostly a SaaS marketing site.
- **Rebuild Strategy**: Create a "Test Intelligence" or "CI/CD Optimization" content hub. Redirect to capture inbound links from acquisition press coverage. Estimated 10-15 high-quality referring domains from tech press.
- **Estimated Effort**: 2-3 days for initial content, ongoing blog posts
- **Key Risk**: Domain held through 2027, unlikely to drop soon

---

## DOMAIN 2: apitools.com

### What Was the Site?
**SaaS Application — API Traffic Proxy & Monitoring Tool**

APItools was launched by 3scale (API management company, later acquired by Red Hat) in April 2014. It was a free service that acted as an intelligent API proxy, allowing developers to:
- Track, transform, and analyze traffic between apps and external APIs
- Debug API integrations during development
- Monitor API traffic in production
- Apply middleware transformations to API requests/responses

Built on Lua + Nginx (OpenResty) stack. Open-source version available on GitHub (github.com/APItools/monitor).

### Wayback Archive Analysis
- **Total unique URLs archived**: ~158
- **First archived**: 2000-12-06 (different site originally)
- **Content era**: apitools.com (2000-era) was a DIFFERENT site. The 3scale APItools product was at apitools.com circa 2014-2016.
- **CDX records show**: Primarily 200-status HTML pages from 2000-2001 era

### WHOIS Status
- **Registrar**: Dynadot Inc
- **Created**: 2020-12-14 (re-registered)
- **Expiry**: 2026-12-14
- **Status**: clientTransferProhibited
- **Current HTTP**: Returns 200 — **PARKED DOMAIN** redirecting via frameset to cdez.com (domain marketplace)
- **Assessment**: Domain was re-registered by a speculator in 2020. Not the original 3scale owner. Currently parked.

### Topics Originally Covered (3scale era, 2014-2016)
- API traffic monitoring and analysis
- API middleware and transformation
- Developer API integration debugging
- API performance analytics
- OpenResty/Lua API proxy architecture

### Old URL Structure
```
/                    (homepage)
/docs/               (documentation)
/blog/               (blog)
/middleware/          (middleware marketplace)
```

### Content Recovery Assessment
- **Feasibility**: LOW
- **Why**: The domain changed hands in 2020 and is currently parked by a speculator. The original 3scale/APItools content was from 2014-2016 — very outdated in the current API ecosystem. Only ~158 archived URLs, many from a different era entirely. The API monitoring/proxy space is now dominated by Postman, Insomnia, and cloud-native solutions.
- **Rebuild Strategy**: Not recommended. Better API-related domain candidates exist (api-studio.io from Sprint 1 is more relevant).
- **Estimated Effort**: Would need to purchase from speculator (likely $500-5000) plus rebuild
- **Key Risk**: Speculator pricing, outdated niche positioning

---

## DOMAIN 3: techstack.com

### What Was the Site?
**ACTIVE BUSINESS — Technology Consulting / Software Development Agency**

techstack.com is currently a LIVE, ACTIVE website running on Next.js. It belongs to "Techstack" — a technology consulting firm that deploys "elite Technology Strike Teams" to eliminate digital roadblocks.

### Current Site Details
- **Tech Stack**: Next.js (/_next/ references in HTML), Google Tag Manager, idPixel analytics
- **Business Type**: Software development consultancy/agency
- **Services**: Technology consulting, engineering teams, digital transformation
- **Schema.org markup**: Organization type
- **Registrar**: GoDaddy
- **Created**: 2009-12-29
- **Expiry**: 2027-12-02
- **Status**: clientDeleteProhibited, clientRenewProhibited (fully locked down)

### Wayback Archive Analysis
- **Total unique URLs archived**: ~9,136
- **First archived**: 2010-04-23
- **Content depth**: DEEP archive — thousands of pages over 16+ years

### Content Recovery Assessment
- **Feasibility**: N/A — DOMAIN IS NOT AVAILABLE
- **Why**: This is an active, operating business with locked-down domain registration. Not a candidate for acquisition.
- **Alternative**: Consider tech-stack.com (also active, different company) or techstack.io, techstackguide.com, etc.
- **Recommendation**: REMOVE FROM CANDIDATE LIST

---

## DOMAIN 4: devhub.io

### What Was the Site?
**Web Application — Developer Tools & Repository Aggregator Platform**

DevHub.io was a developer ecosystem hub that aggregated and organized open-source projects, developer tools, libraries, and frameworks across programming languages. It functioned as a searchable directory of development resources.

### Technical Architecture (from GitHub repos)
- **Backend**: PHP (Laravel framework) — github.com/devhub-io/devhub.io
- **Frontend**: Vue.js (Server-Side Rendered)
- **API Server**: JavaScript/Node.js
- **Admin Panel**: Separate admin interface
- **Repositories**: 5 public repos under github.com/devhub-io organization
- **License**: MIT (admin, server, web) and AGPL-3.0 (Laravel version)

### Wayback Archive Analysis
- **Total unique URLs archived**: ~25,924
- **First archived**: 2015-11-14
- **Content depth**: VERY DEEP — massive archive of categorized developer resources

### URL Structure (from CDX data)
```
/                              (homepage)
/category/actionscript         (language categories)
/category/algorithm
/category/android
/category/app                  (900+ pages of app repos!)
/category/assembly
/category/books
/category/c
/category/c-sharp
/category/clojure
/category/cloud-service
/category/coffeescript
/category/cpp
/category/crystal
/category/css
/category/cuda
/category/d
... (dozens more language/topic categories)
```

Each category had paginated listings (e.g., /category/app?page=1 through /category/app?page=905), meaning the site indexed potentially tens of thousands of individual developer tools and repositories.

### WHOIS Status
- **Registrar**: Dynadot Inc
- **Created**: 2016-10-17
- **Expiry**: 2026-10-17
- **Status**: clientTransferProhibited
- **Current HTTP**: Returns 200 but redirects to /lander (parked/for-sale page)
- **Assessment**: Domain is registered but the original project appears abandoned. Currently showing a landing/parking page. Expires October 2026.

### Topics Covered
- Developer tools directory (all programming languages)
- Open-source repository aggregation
- Language-specific tool categories
- Books and educational resources for developers
- Cloud service tools
- Algorithm libraries
- Framework comparisons

### Content Recovery Assessment
- **Feasibility**: HIGH
- **Why**: 25,900+ archived URLs represents massive content depth. The URL structure (/category/{language}) is perfect for a developer tools comparison/directory site. The concept of a "developer tools hub" is highly relevant to our target niche. The domain expires October 2026 — it may drop.
- **Rebuild Strategy**:
  1. If domain acquired: Rebuild as an AI-powered developer tools directory with curated recommendations
  2. Map old /category/{language} URLs to new category pages via 301 redirects
  3. Focus on AI/LLM tools, modern frameworks, and trending categories
  4. Add comparison features, reviews, and "best of" content
  5. Leverage the ~25K archived URLs to capture long-tail organic traffic
- **Estimated Effort**: 2-3 weeks for MVP (auto-generate category pages from GitHub API data), ongoing curation
- **Key Value**: The sheer volume of archived pages means Google has deep crawl history for this domain. If rebuilt with relevant content, it could recover organic traffic relatively quickly.
- **Key Risk**: Domain may be renewed by current holder. Speculator may want premium price.

---

## DOMAIN 5: codeguide.com

### What Was the Site?
**Parked/Minimal Website — Coding Guides (Historical)**

Based on Wayback CDX data, codeguide.com has been mostly a parked or redirect domain since at least 2001. The earliest snapshots show 302 redirects, suggesting it was never a substantial content site. Not to be confused with:
- codeguide.co (Code Guide by @mdo — HTML/CSS coding standards)
- codeguide.dev (CodeGuide — AI-powered project documentation tool)

### Wayback Archive Analysis
- **Total unique URLs archived**: ~15
- **First archived**: 2001-08-03 (small HTML page, 565 bytes)
- **Content pattern**: Almost all snapshots are 302 redirects
- **Content depth**: MINIMAL — essentially a parked domain for 25 years

### WHOIS Status
- **Registrar**: InterNetX GmbH
- **Created**: 2001-06-07
- **Expiry**: 2026-06-07
- **Status**: clientTransferProhibited
- **Current HTTP**: Not responding (connection timeout)
- **Assessment**: 25-year-old domain but with essentially zero content history. Currently down but still registered. Expires June 2026.

### Content Recovery Assessment
- **Feasibility**: LOW
- **Why**: Only 15 archived URLs, almost all redirects. No meaningful content was ever hosted on this domain. The domain age (25 years) gives it some inherent authority, but there's nothing to "recover" — you'd be building entirely from scratch.
- **Rebuild Strategy**: If acquired, build a coding guides/best practices hub. The domain name is self-explanatory and SEO-friendly. But with no existing backlinks or content history, you're starting from zero.
- **Estimated Effort**: Full greenfield build — weeks to months for meaningful content
- **Key Risk**: Domain held by InterNetX (German registrar) — likely a domain investor. May want premium price. Expires June 2026 but may be renewed.
- **Alternative**: codeguide.dev is already an active AI coding tool. Consider codeGuide.io or similar alternatives.

---

## COMPARATIVE RANKING

| Rank | Domain | Recovery Value | Content Depth | Brand Value | Availability | Overall Score |
|------|--------|---------------|---------------|-------------|-------------|--------------|
| 1 | **devhub.io** | HIGH | 25,900 pages | STRONG (developer hub) | Expires Oct 2026 | **9/10** |
| 2 | **launchable.io** | MEDIUM | 30 pages | STRONG (CloudBees/Jenkins pedigree) | Held til 2027 | **7/10** |
| 3 | **techstack.com** | N/A | 9,136 pages | STRONG | NOT AVAILABLE (active business) | **N/A** |
| 4 | **codeguide.com** | LOW | 15 pages | MEDIUM (good keyword) | Expires Jun 2026 | **4/10** |
| 5 | **apitools.com** | LOW | 158 pages | MEDIUM (API keyword) | Parked by speculator | **3/10** |

---

## ACTIONABLE NEXT STEPS

### Immediate (This Week)
1. **Set backorder alert on devhub.io** via Park.io or Dynadot backorder — expiring Oct 17, 2026
2. **Monitor launchable.io** — in autoRenewPeriod, could lapse if CloudBees doesn't renew
3. **Remove techstack.com** from candidate list entirely — active business, not available

### Near-Term (Next 30 Days)
4. **Check codeguide.com** again after June 7, 2026 expiry — may drop
5. **Evaluate apitools.com** purchase price at Dynadot if interested in API niche (expiry Dec 2026)

### Strategic (Next 6 Months)
6. **Watch builder.ai** (expiring June 2026) — could be highest-value expired AI domain of the year if it drops from bankruptcy
7. **Watch codeparrot.ai** (expiring Dec 2026) — YC-backed AI coding startup domain
8. Add all Category A shut-down startup domains to watchlist_monitor.py automated alerts

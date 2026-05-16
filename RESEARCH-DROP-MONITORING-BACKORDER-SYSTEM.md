# Domain Drop Monitoring & Backorder Placement System -- Research Report

**Date:** 2026-05-14
**Project:** Domain Hunter REVENANT
**Scope:** Automated pipeline for monitoring domain status changes, detecting drops, and placing backorders

---

## Table of Contents

1. [DropCatch API -- Programmatic Backorder Placement](#1-dropcatch-api)
2. [Dynadot API -- Backorder Endpoints](#2-dynadot-api)
3. [WHOIS Lookup APIs -- Free/Cheap Options](#3-whois-lookup-apis)
4. [Detecting Pending Delete Status Programmatically](#4-pending-delete-detection)
5. [RDAP Protocol -- Better Than WHOIS?](#5-rdap-protocol)
6. [DataForSEO Domain WHOIS API](#6-dataforseo-whois-api)
7. [Python Libraries for WHOIS Lookups](#7-python-whois-libraries)
8. [Cron-Based Monitoring System Design](#8-cron-monitoring-system)
9. [Alert Systems -- Status Change Notifications](#9-alert-systems)
10. [Rate-Limiting Best Practices](#10-rate-limiting)
11. [Recommended Architecture for Domain Hunter](#11-architecture)
12. [Integration Plan with Existing Pipeline](#12-integration-plan)

---

## 1. DropCatch API

### Does It Exist?

**No public API exists.** DropCatch (owned by NameBright/Donuts) operates as a web-only auction platform. As of 2026, they do not offer:

- A REST API for placing backorders
- Webhooks for auction notifications
- Programmatic bid management
- Bulk backorder submission endpoints

### What IS Available

| Method | Viability | Details |
|--------|-----------|---------|
| Web UI (manual) | Current workflow | Place backorders at $59/domain, auction if multiple bidders |
| Browser automation (Playwright/Selenium) | Fragile but possible | Automate the web UI -- risk of CAPTCHAs, ToS violation |
| DropCatch email alerts | Semi-automated | They send email when domains drop -- parse with IMAP |
| NameBright API (parent company) | Partial | NameBright has an API for domain management but NOT for DropCatch auctions |

### DropCatch Business Model

- **Backorder cost:** $59 flat fee (refunded if not caught)
- **Auction mechanism:** If multiple backorders exist, goes to auction (starting at $59)
- **Catch rate:** Among the highest in industry (operates its own catching infrastructure)
- **Supported TLDs:** .com, .net, .org, .info, .biz, .mobi, .us, .co, .me, .tv, .cc, and 300+ others
- **Settlement:** Won domains go to NameBright account

### Workaround for Automation

The most practical approach is **not** to automate DropCatch itself, but to:

1. Monitor domains via WHOIS/RDAP (your system)
2. Alert when pendingDelete detected
3. Manually place DropCatch backorder (takes 30 seconds)
4. Also place parallel backorders on SnapNames, NameJet, Dynadot (hedging strategy)

### Alternative Services WITH APIs

| Service | API? | Backorder Cost | Notes |
|---------|------|----------------|-------|
| **Dynadot** | YES (full API) | $10.99/backorder | Detailed below |
| **SnapNames** | NO (web only) | $69 | GoDaddy subsidiary |
| **NameJet** | NO (web only) | $69 | Web2/NameBright partnership |
| **GoDaddy Auctions** | Partial (via GoDaddy Reseller API) | Varies | Complex, requires reseller account |
| **Park.io** | YES (limited) | $99 | Only for .io, .me, .to, .gg TLDs |
| **Pheenix** | NO | $19 | Budget option, lower catch rates |
| **CatchDomain.nl** | NO | EUR 19 | European focus |

---

## 2. Dynadot API -- Backorder Endpoints

### API Overview

Dynadot provides a comprehensive REST API (API v3) at `https://api.dynadot.com/api3.html`. Authentication is via an API key obtained from the Dynadot control panel.

**Base URL:** `https://api.dynadot.com/api3.html` or `https://api.dynadot.com/api3.json` (JSON format)

### Authentication

```
GET https://api.dynadot.com/api3.json?key=YOUR_API_KEY&command=...
```

API key is obtained from: Dynadot Account > My Account > API

### Backorder-Related Commands

#### Place Backorder
```
command=backorder
domain=example.com
```

**Full URL:**
```
https://api.dynadot.com/api3.json?key=API_KEY&command=backorder&domain=example.com
```

**Response (success):**
```json
{
  "BackorderResponse": {
    "ResponseCode": 0,
    "Status": "success"
  }
}
```

**Cost:** $10.99 per backorder (only charged if caught). Cheapest in the industry.

#### Delete Backorder
```
command=delete_backorder
domain=example.com
```

#### Get Backorder List
```
command=backorder_list
```

Returns all active backorders with status.

#### Check Domain Availability
```
command=search
domain=example
show_price=1
```

#### Get Domain Info
```
command=domain_info
domain=example.com
```

Returns WHOIS-like data including registration status, expiry date, nameservers.

### Additional Useful Dynadot API Commands

| Command | Purpose |
|---------|---------|
| `register` | Register an available domain |
| `renew` | Renew a domain |
| `set_ns` | Set nameservers |
| `get_ns` | Get current nameservers |
| `set_dns` | Set DNS records |
| `domain_info` | Full domain details |
| `account_info` | Account balance, etc. |
| `order_status` | Check order status |
| `search` | Domain availability search |

### Rate Limits

Dynadot API rate limits are not officially documented but are approximately:
- 10-20 requests per minute per API key
- Burst allowance of ~5 concurrent requests
- No daily cap documented

### Python Client for Dynadot API

```python
"""Dynadot API v3 client for domain backorders.

Endpoints:
  - backorder: Place a backorder
  - delete_backorder: Cancel a backorder
  - backorder_list: List all active backorders
  - search: Check domain availability
  - domain_info: Get domain WHOIS data
"""
import httpx
from typing import Any

_BASE_URL = "https://api.dynadot.com/api3.json"
_TIMEOUT = 30

class DynadotClient:
    def __init__(self, api_key: str) -> None:
        assert api_key and len(api_key) > 10, "Valid API key required"
        self._key = api_key

    async def place_backorder(self, domain: str) -> dict[str, Any]:
        """Place a backorder for a domain. Cost: $10.99 if caught."""
        assert "." in domain, f"Invalid domain: {domain}"
        params = {"key": self._key, "command": "backorder", "domain": domain}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def delete_backorder(self, domain: str) -> dict[str, Any]:
        """Cancel an existing backorder."""
        assert "." in domain, f"Invalid domain: {domain}"
        params = {"key": self._key, "command": "delete_backorder", "domain": domain}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def list_backorders(self) -> dict[str, Any]:
        """List all active backorders."""
        params = {"key": self._key, "command": "backorder_list"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def search(self, domain: str) -> dict[str, Any]:
        """Check if a domain is available for registration."""
        name = domain.split(".")[0]
        params = {"key": self._key, "command": "search", "domain": name, "show_price": "1"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    async def domain_info(self, domain: str) -> dict[str, Any]:
        """Get WHOIS-like details for a domain."""
        params = {"key": self._key, "command": "domain_info", "domain": domain}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()
```

---

## 3. WHOIS Lookup APIs -- Free/Cheap Options

### Comparison Table

| Service | Free Tier | Paid Pricing | Rate Limit | Format | Status Field? |
|---------|-----------|-------------|------------|--------|--------------|
| **System `whois` command** | Unlimited (OS) | $0 | ~10-20/min before ban | Raw text | Yes (parse manually) |
| **WhoisFreaks** | 100/mo free | $19/mo (10K) | 10/sec | JSON | Yes |
| **WhoisXML API** | 500/mo free | $19/mo (1K) | 20/sec | JSON | Yes |
| **RDAP (protocol)** | Unlimited | $0 | Varies by registry | JSON | Yes (standardized) |
| **ip-api.com/whois** | 45/min | $0 (limited) | 45/min | JSON | Basic |
| **Whois-API (jsonwhois.com)** | 500/mo | $10/mo (5K) | 10/sec | JSON | Yes |
| **DataForSEO WHOIS** | With plan | $0.0003/request | 2000/min | JSON | Yes |
| **DomainTools** | Trial only | $99+/mo | 1/sec | JSON | Yes (best data) |
| **who.is (scraping)** | Free | $0 | Slow | HTML | Via parsing |

### Recommended Stack for This Project

**Primary:** RDAP (free, structured JSON, no API key needed)
**Secondary:** System `whois` command (fallback, already implemented in `watchlist_monitor.py`)
**Bulk operations:** WhoisFreaks API (already have API key in `.env.example`)
**Historical data:** DataForSEO (already integrated for backlinks)

---

## 4. Detecting Pending Delete Status Programmatically

### Domain Lifecycle & Status Codes

A domain goes through these stages before becoming available:

```
REGISTERED (active)
    |
    v  (owner fails to renew)
AUTO-RENEW GRACE PERIOD (0-45 days)
  Status: clientRenewProhibited, autoRenewPeriod
    |
    v  (still not renewed)
REDEMPTION GRACE PERIOD (30 days)
  Status: redemptionPeriod
    |
    v  (still not redeemed)
PENDING DELETE (5 days)
  Status: pendingDelete
    |
    v  (domain drops)
AVAILABLE (anyone can register / backordered catch)
```

### EPP Status Codes to Monitor

| Status Code | Meaning | Action |
|-------------|---------|--------|
| `clientRenewProhibited` | Registrar blocked renewal (expired) | WATCH -- entering drop pipeline |
| `clientHold` | Domain suspended, not resolving | WATCH -- likely expired |
| `serverHold` | Registry-level hold | WATCH -- could be legal or expiry |
| `autoRenewPeriod` | In auto-renew grace period | MONITOR -- owner has ~45 days |
| `redemptionPeriod` | Owner missed renewal, expensive recovery only | HIGH ALERT -- ~30 days to drop |
| `pendingDelete` | Scheduled for deletion in ~5 days | CRITICAL -- place backorders NOW |
| `clientTransferProhibited` + no other locks | Normal registered domain | LOW -- just monitoring |
| `serverDeleteProhibited` | Registry preventing deletion | SKIP -- won't drop |

### Detection Logic (Already Partially Implemented)

Your `scripts/watchlist_monitor.py` (line 380-412) already classifies these statuses. The `_classify_status()` function handles:
- `pendingdelete` detection
- `redemption` detection
- Grace period detection via `clienthold` and `renew` codes
- Expiry date comparison

### What's Missing

1. **RDAP-based detection** (structured JSON, more reliable than parsing raw WHOIS text)
2. **Automated backorder placement** when pendingDelete is detected
3. **Multi-source verification** (WHOIS + RDAP + DNS to confirm status)
4. **Timeline tracking** (when did it enter each phase? How many days until drop?)

### Drop Timeline Calculation

```python
def estimate_drop_date(status: str, expiry_date: str) -> str:
    """Estimate when a domain will actually drop.

    Timeline from expiry:
      Day 0: Domain expires
      Day 0-45: Auto-renew grace period (registrar-dependent, typically 30-45 days)
      Day 45-75: Redemption period (30 days, expensive $80-200 to recover)
      Day 75-80: Pending delete (5 days, cannot be recovered)
      Day 80: Domain drops, available for registration / caught by backorder services

    Total: ~75-80 days from expiry to drop.
    """
    from datetime import datetime, timedelta
    exp = datetime.strptime(expiry_date[:10], "%Y-%m-%d")

    if status == "PENDING_DELETE":
        return (exp + timedelta(days=80)).strftime("%Y-%m-%d")  # ~5 days away
    elif status == "REDEMPTION":
        return (exp + timedelta(days=80)).strftime("%Y-%m-%d")  # ~5-35 days away
    elif status == "GRACE_PERIOD":
        return (exp + timedelta(days=80)).strftime("%Y-%m-%d")  # ~35-80 days away
    else:
        return (exp + timedelta(days=80)).strftime("%Y-%m-%d")
```

---

## 5. RDAP Protocol -- Better Than WHOIS for Monitoring?

### What is RDAP?

**Registration Data Access Protocol** (RFC 7480-7484) is the IETF-standardized replacement for WHOIS. It returns structured JSON instead of unstructured text.

### RDAP vs WHOIS Comparison

| Feature | WHOIS | RDAP |
|---------|-------|------|
| Format | Unstructured text (varies by registrar) | Standardized JSON |
| Authentication | None | None (public) or token-based |
| Status codes | Must parse text | Structured array |
| Encoding | ASCII only | UTF-8 (Unicode) |
| Rate limits | Aggressive (10-20/min) | More permissive (varies) |
| ICANN mandate | Being deprecated | Required for all gTLD registries since 2019 |
| Bootstrap | Must know which server to query | Auto-bootstrap via IANA |
| Error handling | Inconsistent | HTTP status codes |
| Internationalized domains | Poor | Native IDN support |
| Referrals | Manual redirect | HTTP 301/302 redirects |

### RDAP Endpoints

**Bootstrap URL (IANA):** `https://data.iana.org/rdap/dns.json`

This returns a mapping of TLDs to RDAP server URLs. For .com domains:

```
https://rdap.verisign.com/com/v1/domain/example.com
```

### RDAP Response Structure (Key Fields)

```json
{
  "objectClassName": "domain",
  "handle": "2138514_DOMAIN_COM-VRSN",
  "ldhName": "example.com",
  "status": [
    "client delete prohibited",
    "client transfer prohibited",
    "client update prohibited"
  ],
  "events": [
    {
      "eventAction": "registration",
      "eventDate": "1995-08-14T04:00:00Z"
    },
    {
      "eventAction": "expiration",
      "eventDate": "2026-08-13T04:00:00Z"
    },
    {
      "eventAction": "last changed",
      "eventDate": "2024-08-14T07:01:44Z"
    }
  ],
  "nameservers": [
    {"ldhName": "a.iana-servers.net"},
    {"ldhName": "b.iana-servers.net"}
  ],
  "entities": [
    {
      "roles": ["registrar"],
      "vcardArray": ["vcard", [
        ["fn", {}, "text", "RESERVED-Internet Assigned Numbers Authority"]
      ]]
    }
  ]
}
```

### RDAP Status Codes (Standardized)

These map to EPP status codes but are human-readable:

| RDAP Status | EPP Equivalent | Meaning |
|-------------|---------------|---------|
| `active` | `ok` | Normal registered domain |
| `redemption period` | `redemptionPeriod` | Expired, expensive recovery |
| `pending delete` | `pendingDelete` | Dropping in ~5 days |
| `client hold` | `clientHold` | Registrar suspended |
| `server hold` | `serverHold` | Registry suspended |
| `auto renew period` | `autoRenewPeriod` | In grace period |
| `client renew prohibited` | `clientRenewProhibited` | Renewal blocked |
| `pending transfer` | `pendingTransfer` | Being transferred |
| `client transfer prohibited` | `clientTransferProhibited` | Transfer locked |

### RDAP Bootstrap Servers by TLD

| TLD | RDAP Server |
|-----|-------------|
| .com | `https://rdap.verisign.com/com/v1/` |
| .net | `https://rdap.verisign.com/net/v1/` |
| .org | `https://rdap.publicinterestregistry.org/rdap/` |
| .io | `https://rdap.nic.io/` |
| .ai | `https://rdap.nic.ai/` |
| .dev | `https://rdap.nic.google/` |
| .app | `https://rdap.nic.google/` |

### Verdict: RDAP vs WHOIS for This Project

**Use RDAP as primary, WHOIS as fallback.** Reasons:

1. RDAP returns structured JSON -- no fragile text parsing
2. Status codes are standardized -- `redemption period` and `pending delete` are unambiguous
3. Event dates (registration, expiration, last changed) are machine-parseable ISO 8601
4. Free, no API key needed
5. More permissive rate limits than WHOIS
6. WHOIS is being sunset by ICANN -- RDAP is the future

### Python RDAP Client

```python
"""RDAP client for domain status monitoring.

Uses IANA bootstrap to discover RDAP servers, then queries for domain data.
Returns structured JSON with status codes, events, and nameservers.
"""
import httpx
from typing import Any

# Pre-mapped RDAP servers for common TLDs (avoid bootstrap lookup)
_RDAP_SERVERS: dict[str, str] = {
    "com": "https://rdap.verisign.com/com/v1/domain/",
    "net": "https://rdap.verisign.com/net/v1/domain/",
    "org": "https://rdap.publicinterestregistry.org/rdap/domain/",
    "io": "https://rdap.nic.io/domain/",
    "ai": "https://rdap.nic.ai/domain/",
    "dev": "https://rdap.nic.google/rdap/domain/",
    "app": "https://rdap.nic.google/rdap/domain/",
    "co": "https://rdap.nic.co/rdap/domain/",
    "me": "https://rdap.nic.me/rdap/domain/",
    "info": "https://rdap.afilias.net/rdap/info/domain/",
    "biz": "https://rdap.nic.biz/rdap/domain/",
}
_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
_TIMEOUT = 15

async def rdap_lookup(domain: str) -> dict[str, Any]:
    """Query RDAP for domain registration data."""
    assert "." in domain, f"Invalid domain: {domain}"
    tld = domain.rsplit(".", 1)[-1].lower()
    base_url = _RDAP_SERVERS.get(tld)

    if not base_url:
        # Bootstrap lookup for unknown TLDs
        base_url = await _bootstrap_lookup(tld)

    url = f"{base_url}{domain}"
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers={"Accept": "application/rdap+json"})
        if resp.status_code == 404:
            return {"status": ["not found"], "available": True}
        resp.raise_for_status()
        return resp.json()

async def _bootstrap_lookup(tld: str) -> str:
    """Look up RDAP server URL via IANA bootstrap."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_BOOTSTRAP_URL)
        resp.raise_for_status()
        data = resp.json()
    for entry in data.get("services", []):
        tlds, urls = entry[0], entry[1]
        if tld in tlds:
            return urls[0] + "domain/"
    raise ValueError(f"No RDAP server found for TLD: .{tld}")

def extract_status(rdap_data: dict[str, Any]) -> list[str]:
    """Extract status codes from RDAP response."""
    return rdap_data.get("status", [])

def extract_expiry(rdap_data: dict[str, Any]) -> str:
    """Extract expiration date from RDAP events."""
    for event in rdap_data.get("events", []):
        if event.get("eventAction") == "expiration":
            return event.get("eventDate", "")[:10]
    return ""

def is_dropping(rdap_data: dict[str, Any]) -> bool:
    """Check if domain is in a drop-related status."""
    statuses = extract_status(rdap_data)
    drop_indicators = {"redemption period", "pending delete", "auto renew period"}
    return bool(set(statuses) & drop_indicators)
```

---

## 6. DataForSEO Domain WHOIS API

### Overview

DataForSEO offers a WHOIS API as part of their Domain Analytics product. You already have DataForSEO credentials in your `.env` file (`support@zovo.one`).

### Endpoint

```
POST https://api.dataforseo.com/v3/domain_analytics/whois/live
```

### Request

```json
[{
  "target": "example.com"
}]
```

### Response Fields

| Field | Description |
|-------|-------------|
| `domain` | Domain name |
| `registrar` | Registrar name |
| `registration_date` | ISO 8601 creation date |
| `expiration_date` | ISO 8601 expiry date |
| `updated_date` | Last WHOIS update |
| `first_seen` | DataForSEO first saw this domain |
| `epp_status_codes` | Array of EPP status codes |
| `nameservers` | Array of nameserver hostnames |
| `registered` | Boolean -- is the domain currently registered? |

### Pricing

DataForSEO WHOIS API pricing (as of 2025):

| Plan | Cost per Request | Requests/Month | Monthly Cost |
|------|-----------------|----------------|-------------|
| Standard | $0.0003 | Included in plan | Part of domain analytics plan |
| Domain Analytics plan | $0.0003/WHOIS | Up to 30M | Starts at $50/mo |

**For your use case (40 domains daily):** ~$0.36/month. Negligible.

### Bulk WHOIS Endpoint

```
POST https://api.dataforseo.com/v3/domain_analytics/whois/overview/live
```

Accepts up to 1000 domains per request. Returns WHOIS summary for all.

### Python Integration

Since you already have a `DataForSEOClient` at `/Users/mike/Desktop/domainhunter/clients/dataforseo.py`, add a WHOIS method:

```python
_WHOIS_URL = "https://api.dataforseo.com/v3/domain_analytics/whois/live"

async def get_whois(self, domain: str) -> dict[str, Any]:
    """Get WHOIS data for a domain via DataForSEO."""
    headers = {
        "Authorization": self._build_auth_header(),
        "Content-Type": "application/json",
    }
    post_body = [{"target": domain}]
    async with aiohttp.ClientSession(timeout=self._timeout) as session:
        async with session.post(_WHOIS_URL, headers=headers, json=post_body) as resp:
            resp.raise_for_status()
            data = await resp.json()
    tasks = data.get("tasks", [])
    if tasks and tasks[0].get("result"):
        return tasks[0]["result"][0]
    return {}
```

---

## 7. Python Libraries for WHOIS Lookups

### Library Comparison

| Library | PyPI | Last Update | Stars | Protocol | Async? | Status Parsing? |
|---------|------|-------------|-------|----------|--------|----------------|
| **python-whois** | `python-whois` | 2024 | 1.8K | WHOIS (socket) | No | Basic |
| **whois** (alternate) | `whois` | 2024 | 300 | WHOIS (socket) | No | Basic |
| **whoisit** | `whoisit` | 2023 | 50 | RDAP | No | Yes (structured) |
| **whodap** | `whodap` | 2024 | 150 | RDAP | Yes (aiohttp) | Yes (structured) |
| **asyncwhois** | `asyncwhois` | 2024 | 100 | Both | Yes | Yes |
| **whoisdomain** | `whoisdomain` | 2024 | 40 | WHOIS | No | Yes |

### python-whois (Most Popular)

```bash
pip install python-whois
```

```python
import whois

w = whois.whois("example.com")
print(w.status)          # ['clientDeleteProhibited', ...]
print(w.expiration_date) # datetime(2026, 8, 13, ...)
print(w.registrar)       # 'RESERVED-Internet Assigned Numbers Authority'
print(w.name_servers)    # ['A.IANA-SERVERS.NET', ...]
print(w.creation_date)   # datetime(1995, 8, 14, ...)
```

**Pros:** Simple, well-documented, parses dates into datetime objects.
**Cons:** Synchronous only, inconsistent parsing across registrars, no RDAP support.

### whodap (Best for This Project -- Async RDAP)

```bash
pip install whodap
```

```python
import whodap
import asyncio

async def check_domain(domain: str):
    response = await whodap.lookup_domain(domain)
    print(response.status)           # ['client transfer prohibited', ...]
    print(response.expiration_date)  # '2026-08-13T04:00:00Z'
    print(response.registrar)        # 'RESERVED-IANA'
    return response

asyncio.run(check_domain("example.com"))
```

**Pros:** Async, uses RDAP (structured JSON), good status parsing, modern Python.
**Cons:** Smaller community, some ccTLDs not supported.

### asyncwhois (Hybrid -- Both WHOIS and RDAP)

```bash
pip install asyncwhois
```

```python
import asyncwhois
import asyncio

async def check(domain: str):
    # RDAP lookup
    result = await asyncwhois.aio_rdap_domain(domain)
    print(result.parser_output)  # Structured dict

    # Traditional WHOIS fallback
    result2 = await asyncwhois.aio_whois_domain(domain)
    print(result2.parser_output)

asyncio.run(check("example.com"))
```

**Pros:** Supports both RDAP and WHOIS, async, good fallback logic.
**Cons:** Complex API surface.

### Recommendation for Domain Hunter

Use **whodap** as primary (async RDAP) with **system whois command** as fallback (already implemented). Rationale:

1. Your codebase is already async (aiohttp/httpx everywhere)
2. RDAP gives structured status codes -- no text parsing needed
3. whodap is lightweight, no heavy dependencies
4. System `whois` fallback already works in `watchlist_monitor.py`

---

## 8. Cron-Based Monitoring System Design

### Current System

You already have:
- `run_daily.sh` -- daily cron wrapper for the main pipeline
- `tools/whois_monitor.sh` -- weekly bash-based WHOIS checker for 7 domains
- `scripts/watchlist_monitor.py` -- Python-based monitor for 41 domains with SQLite persistence

### Proposed Enhanced System

#### Tiered Monitoring Schedule

| Priority | Domains | Check Frequency | Method |
|----------|---------|-----------------|--------|
| CRITICAL (expired/grace) | 3-5 domains | Every 6 hours | RDAP + WHOIS |
| HIGH (expiring <60 days) | 8-10 domains | Daily | RDAP |
| MEDIUM (expiring <180 days) | 15-20 domains | Every 3 days | RDAP |
| LOW (long-dated) | 10-15 domains | Weekly | RDAP |

#### Cron Schedule

```cron
# CRITICAL: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
0 */6 * * * cd /Users/mike/Desktop/domainhunter && python3 scripts/drop_monitor.py --priority critical

# HIGH: Daily at 07:00 UTC
0 7 * * * cd /Users/mike/Desktop/domainhunter && python3 scripts/drop_monitor.py --priority high

# MEDIUM: Every 3 days at 08:00 UTC
0 8 */3 * * cd /Users/mike/Desktop/domainhunter && python3 scripts/drop_monitor.py --priority medium

# LOW: Weekly on Sunday at 09:00 UTC
0 9 * * 0 cd /Users/mike/Desktop/domainhunter && python3 scripts/drop_monitor.py --priority low

# FULL PIPELINE: Daily at 06:00 UTC
0 6 * * * /Users/mike/Desktop/domainhunter/run_daily.sh
```

#### Data Flow

```
RDAP Lookup -> Parse Status -> Compare with Previous -> Detect Change?
                                                            |
                                            +---------------+--------------+
                                            |               |              |
                                     No Change        Minor Change    Critical Change
                                            |               |              |
                                      Log only         Log + Email    Log + Slack +
                                                                     Auto-Backorder
                                                                     (Dynadot API)
```

---

## 9. Alert Systems -- Status Change Notifications

### Current System

Your `notifications/notifier.py` already supports:
- Slack webhooks (via httpx)
- Email via Resend (for BUY_NOW verdicts)

### Enhanced Alert Matrix

| Status Change | Slack | Email | SMS (optional) | Auto-Action |
|--------------|-------|-------|----------------|-------------|
| REGISTERED -> EXPIRING_SOON | Low | No | No | Add to daily monitoring |
| REGISTERED -> GRACE_PERIOD | Medium | Yes | No | Increase check frequency |
| GRACE_PERIOD -> REDEMPTION | High | Yes | No | Place Dynadot backorder |
| REDEMPTION -> PENDING_DELETE | CRITICAL | Yes | Yes | Place ALL backorders (Dynadot, DropCatch alert, SnapNames alert) |
| PENDING_DELETE -> AVAILABLE | CRITICAL | Yes | Yes | Check catch status, register if missed |
| Any -> RENEWED | Info | No | No | Move to LOW priority |

### Slack Message Format for Domain Alerts

```python
def format_domain_alert(domain: str, old_status: str, new_status: str,
                        expiry: str, priority: str) -> str:
    icons = {
        "PENDING_DELETE": ":rotating_light:",
        "REDEMPTION": ":warning:",
        "GRACE_PERIOD": ":eyes:",
        "AVAILABLE": ":tada:",
    }
    icon = icons.get(new_status, ":information_source:")

    return (
        f"{icon} *Domain Status Change*\n\n"
        f"*Domain:* `{domain}`\n"
        f"*Status:* {old_status} -> *{new_status}*\n"
        f"*Expiry:* {expiry}\n"
        f"*Priority:* {priority}\n\n"
        f"{'*ACTION: Place backorders NOW*' if new_status == 'PENDING_DELETE' else ''}"
    )
```

### Adding SMS via Twilio (Optional)

```python
# pip install twilio
from twilio.rest import Client

def send_sms_alert(phone: str, message: str) -> bool:
    client = Client("ACCOUNT_SID", "AUTH_TOKEN")
    msg = client.messages.create(
        body=message[:160],
        from_="+1TWILIO_NUMBER",
        to=phone,
    )
    return msg.sid is not None
```

### Adding Pushover (Simpler Alternative to SMS)

```python
# pip install python-pushover
import httpx

async def send_pushover(user_key: str, app_token: str, title: str, message: str) -> bool:
    """Send push notification via Pushover ($5 one-time fee, 10K msgs/mo free)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": app_token,
                "user": user_key,
                "title": title,
                "message": message,
                "priority": 1,  # High priority
                "sound": "siren",
            },
        )
        return resp.status_code == 200
```

---

## 10. Rate-Limiting Best Practices -- Don't Get Banned

### WHOIS Rate Limits by Registry

| Registry/TLD | Rate Limit | Ban Duration | Notes |
|-------------|------------|--------------|-------|
| Verisign (.com/.net) | ~10 queries/min | 24hr IP ban | Most aggressive |
| PIR (.org) | ~20 queries/min | 1hr ban | Moderate |
| Afilias (.info/.biz) | ~15 queries/min | Variable | Can whitelist |
| Nominet (.uk) | ~6 queries/min | 24hr ban | Very strict |
| ARIN (IP WHOIS) | 50 queries/5min | 1hr ban | For IP lookups |

### RDAP Rate Limits (Generally More Permissive)

| RDAP Server | Approximate Limit | Notes |
|-------------|-------------------|-------|
| Verisign (.com/.net) | ~30 queries/min | 2-3x more permissive than WHOIS |
| Google (.dev/.app) | ~60 queries/min | Very permissive |
| PIR (.org) | ~30 queries/min | Moderate |

### Implementation Strategy

```python
import asyncio
import time
from collections import defaultdict

class RateLimiter:
    """Token bucket rate limiter per TLD."""

    def __init__(self, default_rate: float = 5.0, default_burst: int = 3) -> None:
        self._rates: dict[str, float] = {
            "com": 5.0,   # 5 queries per minute for .com
            "net": 5.0,
            "org": 10.0,
            "io": 10.0,
            "ai": 10.0,
        }
        self._default_rate = default_rate
        self._burst = default_burst
        self._last_query: dict[str, float] = defaultdict(float)
        self._query_count: dict[str, int] = defaultdict(int)

    async def acquire(self, tld: str) -> None:
        """Wait until rate limit allows a query for this TLD."""
        rate = self._rates.get(tld, self._default_rate)
        interval = 60.0 / rate  # seconds between queries

        elapsed = time.monotonic() - self._last_query[tld]
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

        self._last_query[tld] = time.monotonic()
        self._query_count[tld] += 1
```

### Best Practices

1. **Stagger queries across TLDs** -- don't query 20 .com domains in a row
2. **Cache aggressively** -- WHOIS data rarely changes more than daily
3. **Use RDAP first** -- more permissive limits, structured data
4. **Implement exponential backoff** on 429/ban responses
5. **Rotate timing** -- don't always query at the exact same time
6. **Respect the 43-domain Verisign rule** -- Verisign limits to ~43 .com WHOIS queries per 5-minute window per IP
7. **Use your ISP's WHOIS proxy if available** -- some ISPs run WHOIS caches
8. **Never parallelize WHOIS queries to same registry** -- always serial per TLD
9. **Sleep 3-5 seconds between queries** (your `whois_monitor.sh` uses `sleep 3` -- good)
10. **Consider a WHOIS API for bulk operations** -- WhoisFreaks, DataForSEO cost pennies and have high limits

---

## 11. Recommended Architecture for Domain Hunter

### System Overview

```
+-------------------+     +------------------+     +-------------------+
|  Cron Scheduler   |---->|  Drop Monitor    |---->|  RDAP/WHOIS       |
|  (tiered by       |     |  (Python async)  |     |  Lookup Layer     |
|   priority)       |     |                  |     |  (rate-limited)   |
+-------------------+     +--------+---------+     +-------------------+
                                   |
                          +--------v---------+
                          |  Status Change   |
                          |  Detector        |
                          |  (SQLite history)|
                          +--------+---------+
                                   |
                    +--------------+---------------+
                    |              |                |
             No Change      Minor Change     Critical Change
                    |              |                |
               Log only      Slack alert     +-----------+
                                             |           |
                                        Slack+Email  Auto-Backorder
                                             |       (Dynadot API)
                                             |
                                    +--------v---------+
                                    |  DeepSeek        |
                                    |  Classifier      |
                                    |  (domain value)  |
                                    +------------------+
```

### Component Breakdown

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| RDAP Client | `clients/rdap_client.py` | NEW | Async RDAP lookups with TLD-specific servers |
| Dynadot Client | `clients/dynadot.py` | NEW | Backorder placement via API |
| Drop Monitor | `scripts/drop_monitor.py` | NEW (replaces watchlist_monitor.py) | Unified RDAP + WHOIS + auto-backorder |
| Rate Limiter | `clients/rate_limiter.py` | NEW | Per-TLD token bucket |
| Notifier | `notifications/notifier.py` | EXISTING | Add domain status alert methods |
| DeepSeek | `clients/deepseek.py` | EXISTING | Classify domain value when status changes |
| DataForSEO WHOIS | `clients/dataforseo.py` | EXTEND | Add WHOIS endpoint method |
| SQLite DB | `scripts/watchlist.db` | EXISTING | Add drop timeline tracking |
| Cron wrapper | `run_drop_monitor.sh` | NEW | Tiered scheduling |

### New Settings Needed

Add to `.env`:

```env
# DYNADOT (backorders)
DYNADOT_API_KEY=your_dynadot_api_key_here

# DROP MONITOR
DROP_MONITOR_ENABLED=true
DROP_MONITOR_AUTO_BACKORDER=false
DROP_MONITOR_CRITICAL_INTERVAL_HOURS=6
DROP_MONITOR_HIGH_INTERVAL_HOURS=24
DROP_MONITOR_MEDIUM_INTERVAL_HOURS=72
DROP_MONITOR_LOW_INTERVAL_HOURS=168

# NOTIFICATIONS
PUSHOVER_USER_KEY=
PUSHOVER_APP_TOKEN=
TWILIO_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE=
ALERT_PHONE=
```

---

## 12. Integration Plan with Existing Pipeline

### Phase 1: RDAP Client (Day 1)

Create `clients/rdap_client.py` with:
- Async RDAP lookups via httpx
- TLD-specific server mapping (pre-bootstrapped for .com/.net/.org/.io/.ai)
- Status extraction and classification
- Expiry date extraction
- Rate limiting per TLD
- Fallback to system `whois` command

### Phase 2: Dynadot Client (Day 1)

Create `clients/dynadot.py` with:
- Backorder placement
- Backorder deletion
- Backorder list retrieval
- Domain search/availability
- Error handling and retry logic

### Phase 3: Enhanced Drop Monitor (Day 2)

Create `scripts/drop_monitor.py` to replace/enhance `scripts/watchlist_monitor.py`:
- Use RDAP as primary lookup (structured JSON, no parsing)
- Priority-based monitoring schedule
- Auto-backorder via Dynadot when pendingDelete detected
- DeepSeek classification for new domains entering the watchlist
- Enhanced SQLite schema with timeline tracking
- Structured logging

### Phase 4: Alert Enhancements (Day 2)

Extend `notifications/notifier.py`:
- Add `send_domain_status_alert()` method
- Add Pushover support for mobile alerts
- Priority-based alert routing (CRITICAL -> all channels)

### Phase 5: Cron Setup (Day 3)

- Create `run_drop_monitor.sh` wrapper
- Set up tiered cron schedule
- Test with `--dry-run` mode
- Monitor for 1 week, adjust rate limits as needed

### Phase 6: DeepSeek Integration (Day 3)

When a new domain enters the watchlist or changes status:
- Auto-classify via DeepSeek (niche, site_type, tool_idea, quality)
- Attach classification to the domain record
- Use classification in backorder decision logic (only auto-backorder high-quality domains)

---

## Key Takeaways

1. **DropCatch has NO API** -- must be manual or browser-automated (risky). Use for high-value domains only.
2. **Dynadot has a full API** -- cheapest backorders ($10.99), easy to automate. Make this the primary automated backorder channel.
3. **RDAP is strictly better than WHOIS** for this use case -- structured JSON, standardized status codes, more permissive rate limits, free.
4. **Your existing `watchlist_monitor.py` is 80% of the way there** -- it just needs RDAP instead of raw WHOIS parsing, auto-backorder integration, and tiered scheduling.
5. **Rate limiting is critical** -- Verisign bans at ~10 WHOIS/min. RDAP is ~30/min. For 41 domains, even daily checks are safe at 3-second intervals.
6. **DataForSEO WHOIS is pennies** -- $0.0003/request. For 41 domains daily, that's $4.50/year. Use for bulk checks when needed.
7. **The DeepSeek integration is the value-add** -- automatically classifying domain value when status changes, so you only place backorders on domains worth catching.

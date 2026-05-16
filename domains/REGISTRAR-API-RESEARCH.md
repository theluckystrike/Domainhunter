# Registrar API Research: Automated Domain Search & Purchase

**Date:** 2026-05-02
**Goal:** Go from "find domain" to "buy domain" entirely via API call, zero browser interaction.

---

## Table of Contents

1. [Porkbun API (PRIMARY)](#1-porkbun-api-primary)
2. [Namecheap API](#2-namecheap-api)
3. [Dynadot API](#3-dynadot-api)
4. [GoDaddy API](#4-godaddy-api)
5. [Cloudflare Registrar API](#5-cloudflare-registrar-api)
6. [Comparison Matrix](#6-comparison-matrix)
7. [Recommended Workflow](#7-recommended-workflow)

---

## 1. Porkbun API (PRIMARY)

**Base URL:** `https://api.porkbun.com/api/json/v3`
(Changed from porkbun.com to api.porkbun.com in 2025)

**Docs:** https://porkbun.com/api/json/v3/documentation

### Authentication

- **Method:** API Key + Secret Key in every request body (JSON POST)
- **How to get keys:**
  1. Log into Porkbun > Account > API Access
  2. Create a name for API key, click "Create API Key"
  3. Save both **API Key** and **Secret Key** immediately (secret shown only once)
- **Per-domain toggle:** After creating keys, go to Domain Management > Details > toggle "API Access" on for each domain you want to manage

### Endpoints

#### Ping (Test Auth)
```
POST https://api.porkbun.com/api/json/v3/ping
```
```bash
curl -s -X POST https://api.porkbun.com/api/json/v3/ping \
  -H "Content-Type: application/json" \
  -d '{
    "apikey": "pk1_xxxxxxxxxxxxxxxx",
    "secretapikey": "sk1_xxxxxxxxxxxxxxxx"
  }'
```
Response:
```json
{
  "status": "SUCCESS",
  "yourIp": "203.0.113.42"
}
```

#### Check Domain Availability
```
POST https://api.porkbun.com/api/json/v3/domain/check/{domain}
```
```bash
curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/check/example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "apikey": "pk1_xxxxxxxxxxxxxxxx",
    "secretapikey": "sk1_xxxxxxxxxxxxxxxx"
  }'
```
Response (available):
```json
{
  "status": "SUCCESS",
  "avail": "yes",
  "pricing": {
    "registration": "9.68",
    "renewal": "9.68"
  }
}
```
Response (taken):
```json
{
  "status": "SUCCESS",
  "avail": "no"
}
```
**Premium detection:** Yes -- pricing in the response will reflect premium pricing if applicable.

#### Get Pricing (All TLDs)
```
POST https://api.porkbun.com/api/json/v3/pricing/get
```
```bash
curl -s -X POST https://api.porkbun.com/api/json/v3/pricing/get \
  -H "Content-Type: application/json" \
  -d '{
    "apikey": "pk1_xxxxxxxxxxxxxxxx",
    "secretapikey": "sk1_xxxxxxxxxxxxxxxx"
  }'
```
Response:
```json
{
  "status": "SUCCESS",
  "pricing": {
    "com": { "registration": "9.68", "renewal": "9.68", "transfer": "9.68" },
    "net": { "registration": "10.56", "renewal": "10.56", "transfer": "10.56" },
    "org": { "registration": "9.11", "renewal": "9.11", "transfer": "9.11" },
    "io":  { "registration": "36.68", "renewal": "36.68", "transfer": "36.68" }
  }
}
```

#### Register Domain (PURCHASE)
```
POST https://api.porkbun.com/api/json/v3/domain/register/{domain}
```
```bash
curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/register/mydomain.com" \
  -H "Content-Type: application/json" \
  -d '{
    "apikey": "pk1_xxxxxxxxxxxxxxxx",
    "secretapikey": "sk1_xxxxxxxxxxxxxxxx",
    "years": 1,
    "ns": ["ns1.porkbun.com", "ns2.porkbun.com"],
    "autoRenew": false
  }'
```
Note: Contact information uses the default profile on your Porkbun account. No need to pass contact info separately for standard registrations. If WHOIS privacy is available for the TLD, it is typically applied automatically.

Response:
```json
{
  "status": "SUCCESS",
  "domain": "mydomain.com",
  "message": "Domain registered successfully."
}
```

#### Domain Info
```
POST https://api.porkbun.com/api/json/v3/domain/info/{domain}
```

#### List All Domains
```
POST https://api.porkbun.com/api/json/v3/domain/listdomains
```

### Rate Limits

- **Domain availability check:** ~1 request per 10 seconds (strict)
- **General API:** Exponential backoff recommended (1-10 seconds between retries)
- **Default retry:** 5 attempts with exponential backoff

### Pricing (Sample .com)

| Operation    | Price  |
|-------------|--------|
| Registration | $9.68  |
| Renewal      | $9.68  |
| Transfer     | $9.68  |

WHOIS privacy: Free (included automatically on supported TLDs).

### Full Workflow: Check + Price + Buy

```bash
#!/bin/bash
DOMAIN="gemdomain.com"
API_KEY="pk1_xxxxxxxxxxxxxxxx"
SECRET="sk1_xxxxxxxxxxxxxxxx"

# Step 1: Check availability + get price
RESULT=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/check/$DOMAIN" \
  -H "Content-Type: application/json" \
  -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET\"}")

AVAIL=$(echo "$RESULT" | jq -r '.avail')
PRICE=$(echo "$RESULT" | jq -r '.pricing.registration // "N/A"')

echo "Domain: $DOMAIN"
echo "Available: $AVAIL"
echo "Price: \$$PRICE"

if [ "$AVAIL" = "yes" ]; then
  echo "Registering..."

  # Step 2: Register
  REG=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/register/$DOMAIN" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET\",\"years\":1}")

  echo "$REG" | jq .
else
  echo "Domain not available."
fi
```

---

## 2. Namecheap API

**Production URL:** `https://api.namecheap.com/xml.response`
**Sandbox URL:** `https://api.sandbox.namecheap.com/xml.response`

**Docs:** https://www.namecheap.com/support/api/methods/

### Authentication

- **Method:** Query parameters: `ApiUser`, `ApiKey`, `UserName`, `ClientIp`
- **Format:** XML (not JSON -- all requests and responses are XML)
- **IP Whitelisting:** REQUIRED. Must add your IP to whitelist in dashboard.
- **How to get keys:**
  1. Log into Namecheap > Profile > Tools > Namecheap API Access
  2. Toggle ON, read ToS, enter password
  3. API Key is displayed
  4. Add your IP to the whitelist

### Production Requirements (IMPORTANT)

You must meet ONE of these to get production API access:
- **20+ domains** on your account, OR
- **$50+ account balance**, OR
- **$50+ spent** within the last 2 years

Sandbox has no restrictions -- free signup and unlimited testing.

### Endpoints

#### Check Domain Availability (domains.check)
```
GET https://api.namecheap.com/xml.response
  ?ApiUser={user}
  &ApiKey={key}
  &UserName={user}
  &ClientIp={ip}
  &Command=namecheap.domains.check
  &DomainList={comma-separated-domains}
```
```bash
curl -s "https://api.namecheap.com/xml.response?\
ApiUser=myuser&\
ApiKey=xxxxxxxxxxxxxxxxxxxxxxxxx&\
UserName=myuser&\
ClientIp=203.0.113.42&\
Command=namecheap.domains.check&\
DomainList=example.com,example.net,example.io"
```
Response (XML):
```xml
<ApiResponse Status="OK">
  <CommandResponse Type="namecheap.domains.check">
    <DomainCheckResult Domain="example.com" Available="false" />
    <DomainCheckResult Domain="example.net" Available="true"
      IsPremiumName="false"
      PremiumRegistrationPrice="0"
      PremiumRenewalPrice="0"
      PremiumRestorePrice="0"
      PremiumTransferPrice="0"
      IcannFee="0.18"
      EapFee="0" />
  </CommandResponse>
</ApiResponse>
```
**Premium detection:** Yes -- `IsPremiumName`, `PremiumRegistrationPrice`, `PremiumRenewalPrice` fields.
**Bulk check:** Up to ~50 domains per request (comma-separated).

#### Register Domain (domains.create)
```
GET https://api.namecheap.com/xml.response
  ?ApiUser={user}
  &ApiKey={key}
  &UserName={user}
  &ClientIp={ip}
  &Command=namecheap.domains.create
  &DomainName={domain}
  &Years=1
  &RegistrantFirstName=John
  &RegistrantLastName=Doe
  &RegistrantAddress1=123 Main St
  &RegistrantCity=Austin
  &RegistrantStateProvince=TX
  &RegistrantPostalCode=78701
  &RegistrantCountry=US
  &RegistrantPhone=+1.5551234567
  &RegistrantEmailAddress=john@example.com
  &TechFirstName=John
  &TechLastName=Doe
  ... (repeat for Admin, AuxBilling contacts)
  &AddFreeWhoisguard=yes
  &WGEnabled=yes
```
```bash
curl -s "https://api.namecheap.com/xml.response?\
ApiUser=myuser&\
ApiKey=xxxxxxxxxxxxxxxxxxxxxxxxx&\
UserName=myuser&\
ClientIp=203.0.113.42&\
Command=namecheap.domains.create&\
DomainName=mydomain.com&\
Years=1&\
RegistrantFirstName=John&\
RegistrantLastName=Doe&\
RegistrantAddress1=123+Main+St&\
RegistrantCity=Austin&\
RegistrantStateProvince=TX&\
RegistrantPostalCode=78701&\
RegistrantCountry=US&\
RegistrantPhone=%2B1.5551234567&\
RegistrantEmailAddress=john%40example.com&\
TechFirstName=John&\
TechLastName=Doe&\
TechAddress1=123+Main+St&\
TechCity=Austin&\
TechStateProvince=TX&\
TechPostalCode=78701&\
TechCountry=US&\
TechPhone=%2B1.5551234567&\
TechEmailAddress=john%40example.com&\
AdminFirstName=John&\
AdminLastName=Doe&\
AdminAddress1=123+Main+St&\
AdminCity=Austin&\
AdminStateProvince=TX&\
AdminPostalCode=78701&\
AdminCountry=US&\
AdminPhone=%2B1.5551234567&\
AdminEmailAddress=john%40example.com&\
AuxBillingFirstName=John&\
AuxBillingLastName=Doe&\
AuxBillingAddress1=123+Main+St&\
AuxBillingCity=Austin&\
AuxBillingStateProvince=TX&\
AuxBillingPostalCode=78701&\
AuxBillingCountry=US&\
AuxBillingPhone=%2B1.5551234567&\
AuxBillingEmailAddress=john%40example.com&\
AddFreeWhoisguard=yes&\
WGEnabled=yes"
```

#### Get Pricing (users.getPricing)
```
GET https://api.namecheap.com/xml.response
  ?ApiUser={user}&ApiKey={key}&UserName={user}&ClientIp={ip}
  &Command=namecheap.users.getPricing
  &ProductType=DOMAIN
  &ActionName=REGISTER
```

### Rate Limits

- **General:** ~20 requests per minute (varies by endpoint)
- **Sandbox:** Unlimited
- Namecheap may throttle or block if abuse detected

### Pricing (Sample .com)

| Operation    | Price   |
|-------------|---------|
| Registration | ~$9.58  |
| Renewal      | ~$14.58 |
| Transfer     | ~$9.58  |

WhoisGuard: Free for life on most TLDs.

### Drawbacks

- XML only (no JSON API)
- Requires IP whitelisting (problematic if your IP changes)
- Verbose contact info required on every registration call (4x contact blocks)
- $50 balance or 20 domains required for production access

---

## 3. Dynadot API

**Base URL:** `https://api.dynadot.com`

**Docs:** https://www.dynadot.com/domain/api-document

### Authentication

- **Method:** Bearer token + HMAC-SHA256 signature for transactional requests
- **Headers:**
  - `Authorization: Bearer YOUR_API_KEY`
  - `X-Signature: {HMAC-SHA256 signature}` (for writes like registration)
  - `X-Request-ID: {UUID}` (optional but recommended)
- **How to get keys:**
  1. Log into Dynadot > My Account > API Settings
  2. Unlock API access
  3. Production Key, Sandbox Key, Secret Key, and Sandbox Secret Key are displayed
- **Signature construction:** `HMAC-SHA256(secretKey, apiKey + "\n" + fullPathAndQuery + "\n" + xRequestId + "\n" + requestBody)`

### Endpoints

#### Search Domain Availability
```
GET https://api.dynadot.com/restful/v2/domains/{domain_name}/search
```
```bash
curl -s -X GET "https://api.dynadot.com/restful/v2/domains/example.com/search?showPrice=yes&currency=USD" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/json" \
  -H "X-Request-ID: $(uuidgen)"
```
Response:
```json
{
  "Code": 200,
  "Message": "Success",
  "Data": {
    "DomainName": "example.com",
    "Available": false,
    "Price": "9.99"
  }
}
```

#### Register Domain
```
POST https://api.dynadot.com/restful/v2/domains/register
```
```bash
curl -s -X POST "https://api.dynadot.com/restful/v2/domains/register" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Signature: {computed_hmac_signature}" \
  -H "X-Request-ID: $(uuidgen)" \
  -d '{
    "domainName": "mydomain.com",
    "years": 1,
    "currency": "USD"
  }'
```
**Note:** Account must have sufficient balance pre-loaded. Dynadot uses account credit, not payment-on-demand.

#### TLD Pricing
```
GET https://api.dynadot.com/restful/v2/tlds/pricing
```
```bash
curl -s -X GET "https://api.dynadot.com/restful/v2/tlds/pricing?currency=USD" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/json"
```

### Rate Limits

| Account Level | Concurrent Threads | Requests/Min |
|--------------|-------------------|-------------|
| Regular       | 1                 | 60 (1/sec)  |
| Bulk          | 5                 | 600 (10/sec)|
| Super Bulk    | 35                | 6,000 (100/sec) |

Domain appraisal: 50-300/day depending on tier.

### Pricing (Sample .com)

| Operation    | Price  |
|-------------|--------|
| Registration | ~$7.99 |
| Renewal      | ~$8.99 |
| Transfer     | ~$7.99 |

### Drawbacks

- HMAC signature required for transactional endpoints (more complex auth)
- Must pre-fund account balance
- Regular accounts limited to 1 concurrent thread / 1 req/sec

---

## 4. GoDaddy API

**Production URL:** `https://api.godaddy.com`
**OTE (Test) URL:** `https://api.ote-godaddy.com`

**Docs:** https://developer.godaddy.com/doc/endpoint/domains

### Authentication

- **Method:** `Authorization: sso-key {API_KEY}:{API_SECRET}` header
- **How to get keys:**
  1. Go to https://developer.godaddy.com
  2. Create account or log in
  3. Go to API Keys > Create New API Key
  4. Select environment (OTE for testing, Production for live)
  5. Get API Key and Secret

### CRITICAL Restriction

**Production Availability API requires 50+ domains on the account.**
Management and DNS APIs require 1+ domain or an active Domain Pro plan.

### Endpoints

#### Check Domain Availability
```
GET https://api.godaddy.com/v1/domains/available?domain={domain}
```
```bash
curl -s -X GET "https://api.godaddy.com/v1/domains/available?domain=example.com" \
  -H "Authorization: sso-key YOUR_KEY:YOUR_SECRET" \
  -H "Accept: application/json"
```
Response:
```json
{
  "available": true,
  "domain": "example.com",
  "definitive": true,
  "price": 1199,
  "currency": "USD",
  "period": 1
}
```
Note: Price is in **microcurrency** (1199 = $11.99 for .com registration).

#### Check Multiple Domains
```
POST https://api.godaddy.com/v1/domains/available
  ?checkType=FAST
```
Body: array of domain names.

#### Get Purchase Schema (per TLD)
```
GET https://api.godaddy.com/v1/domains/purchase/schema/{tld}
```
Returns the JSON schema required for purchasing a domain under that TLD.

#### Get Agreements (Legal)
```
GET https://api.godaddy.com/v1/domains/agreements?tlds={tld}&privacy=false
```
Returns agreement keys needed for the consent block.

#### Purchase/Register Domain
```
POST https://api.godaddy.com/v1/domains/purchase
```
```bash
curl -s -X POST "https://api.godaddy.com/v1/domains/purchase" \
  -H "Authorization: sso-key YOUR_KEY:YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "domain": "mydomain.com",
    "consent": {
      "agreedAt": "2026-05-02T12:00:00Z",
      "agreedBy": "203.0.113.42",
      "agreementKeys": ["DNRA"]
    },
    "contactAdmin": {
      "addressMailing": {
        "address1": "123 Main St",
        "city": "Austin",
        "country": "US",
        "postalCode": "78701",
        "state": "TX"
      },
      "email": "admin@example.com",
      "nameFirst": "John",
      "nameLast": "Doe",
      "phone": "+1.5551234567"
    },
    "contactBilling": { "...same structure..." },
    "contactRegistrant": { "...same structure..." },
    "contactTech": { "...same structure..." },
    "period": 1,
    "privacy": false,
    "renewAuto": false
  }'
```

### Rate Limits

- **60 requests per minute** per endpoint
- HTTP 429 returned when exceeded

### Pricing (Sample .com)

| Operation    | Price   |
|-------------|---------|
| Registration | ~$11.99 |
| Renewal      | ~$22.99 |
| Transfer     | ~$11.99 |

Privacy: $9.99/year extra.

### Drawbacks

- **50-domain minimum** for availability API in production (deal-breaker for most)
- Most expensive renewal pricing
- Verbose contact info required (4 contact blocks)
- Privacy costs extra ($9.99/yr)

---

## 5. Cloudflare Registrar API

**Base URL:** `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/registrar`

**Docs:** https://developers.cloudflare.com/registrar/registrar-api/

### Authentication

- **Method:** Bearer token in Authorization header
- **How to get token:**
  1. Cloudflare Dashboard > My Profile > API Tokens
  2. "Create Token" > use template or custom
  3. Grant permissions: Account > Registrar > Edit
  4. Note your Account ID from the dashboard URL

### Endpoints

#### Domain Search (Discovery)
```
GET https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/registrar/domain-search?q={keyword}&limit={n}
```
```bash
curl -s -X GET \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/registrar/domain-search?q=acme%20corp&limit=5" \
  -H "Authorization: Bearer $CF_API_TOKEN"
```
Response: Array of suggested domain names with registrability status and pricing.
**Note:** Results are cached and for discovery only -- always verify with Check before purchasing.

#### Check Domain Availability (Real-Time)
```
POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/registrar/domain-check
```
```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/registrar/domain-check" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domains": ["mydomain.com", "mydomain.dev", "mydomain.io"]}'
```
Response:
```json
{
  "result": [
    {
      "name": "mydomain.com",
      "registrable": true,
      "tier": "standard",
      "pricing": {
        "currency": "USD",
        "registration_cost": "10.11",
        "renewal_cost": "10.11"
      }
    },
    {
      "name": "mydomain.dev",
      "registrable": true,
      "tier": "standard",
      "pricing": {
        "currency": "USD",
        "registration_cost": "10.18",
        "renewal_cost": "10.18"
      }
    }
  ]
}
```
**Bulk check:** Up to 20 domains per request.
**Premium detection:** When supported, premium domains show higher pricing and require explicit fee acknowledgement.

#### Register Domain (PURCHASE)
```
POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/registrar/registrations
```
```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/registrar/registrations" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_name": "mydomain.com"
  }'
```
Minimal request -- uses default registrant contact and default payment method on the account.

Full request with custom contact:
```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/registrar/registrations" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "domain_name": "mydomain.com",
    "contacts": {
      "registrant": {
        "email": "john@example.com",
        "phone": "+1.5551234567",
        "postal_info": {
          "name": "John Doe",
          "organization": "Zovo Inc",
          "address": {
            "street": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "country_code": "US"
          }
        }
      }
    }
  }'
```
Response codes:
- `201 Created` -- Registration completed (within ~10s wait window)
- `202 Accepted` -- Registration still in progress (poll for status)

#### Check Registration Status
```
GET https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/registrar/registrations/{domain}/registration-status
```
States: `in_progress`, `succeeded`, `failed`, `action_required`, `blocked`

### Rate Limits

Not explicitly documented. Standard Cloudflare API limits apply (~1,200 requests per 5 minutes).

### Pricing

**AT-COST / WHOLESALE** -- Cloudflare charges zero markup. You pay only the registry wholesale price + ICANN fee.

| TLD  | Registration | Renewal  |
|------|-------------|----------|
| .com | ~$10.11     | ~$10.11  |
| .net | ~$10.96     | ~$10.96  |
| .org | ~$10.11     | ~$10.11  |
| .io  | ~$37.00     | ~$37.00  |
| .dev | ~$10.18     | ~$10.18  |

Registration price = Renewal price (always, guaranteed).

### Drawbacks

- **Beta API** -- limited TLD support (not all TLDs available via API yet)
- **No renewals** via API yet
- **No transfers** via API yet
- **No contact updates** via API yet
- Registrations are **non-refundable** once completed
- Need Cloudflare account with payment method and default registrant contact configured

---

## 6. Comparison Matrix

| Feature | Porkbun | Namecheap | Dynadot | GoDaddy | Cloudflare |
|---------|---------|-----------|---------|---------|------------|
| **Format** | JSON POST | XML GET | JSON REST | JSON REST | JSON REST |
| **Auth** | Key+Secret in body | Query params + IP whitelist | Bearer + HMAC sig | sso-key header | Bearer token |
| **Check Avail** | Yes | Yes (bulk) | Yes | Yes (50+ domains req) | Yes (bulk up to 20) |
| **Register** | Yes | Yes | Yes | Yes (50+ domains req) | Yes |
| **Price in Check** | Yes | Yes (premium) | Yes | Yes | Yes |
| **Premium Detect** | Yes | Yes | Yes | Yes | Partial (beta) |
| **.com Reg Price** | $9.68 | ~$9.58 | ~$7.99 | ~$11.99 | ~$10.11 |
| **.com Renewal** | $9.68 | ~$14.58 | ~$8.99 | ~$22.99 | ~$10.11 |
| **WHOIS Privacy** | Free | Free | Varies | $9.99/yr | N/A (redaction) |
| **Rate Limit** | 1/10s (check) | ~20/min | 60/min (regular) | 60/min | ~240/min |
| **Bulk Check** | No (one at a time) | Yes (~50) | No | Yes | Yes (20) |
| **Pre-fund Required** | No (charges card) | No (charges card) | Yes (account balance) | No (charges card) | No (charges card) |
| **Min Account Req** | None | $50/20 domains | None | 50 domains (avail API) | CF account + payment |
| **API Complexity** | Low | Medium (XML) | High (HMAC) | Medium | Low |
| **Contact in Reg** | No (uses profile) | Yes (4 blocks, verbose) | Minimal | Yes (4 blocks, verbose) | No (uses default) |

---

## 7. Recommended Workflow

### Primary: Porkbun (simplest, cheapest, our registrar)

```bash
#!/bin/bash
# instant-buy.sh -- Find gem, buy gem, zero friction
# Usage: ./instant-buy.sh gemdomain.com

set -euo pipefail

DOMAIN="${1:?Usage: $0 domain.tld}"
API_KEY="${PORKBUN_API_KEY:?Set PORKBUN_API_KEY env var}"
SECRET="${PORKBUN_SECRET_KEY:?Set PORKBUN_SECRET_KEY env var}"
MAX_PRICE="${MAX_PRICE:-15.00}"  # Safety: don't auto-buy above this

AUTH="{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET\"}"

echo "=== Checking: $DOMAIN ==="

# Step 1: Check availability + price (single call)
CHECK=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/check/$DOMAIN" \
  -H "Content-Type: application/json" \
  -d "$AUTH")

STATUS=$(echo "$CHECK" | jq -r '.status')
AVAIL=$(echo "$CHECK" | jq -r '.avail // "unknown"')

if [ "$STATUS" != "SUCCESS" ]; then
  echo "ERROR: API call failed"
  echo "$CHECK" | jq .
  exit 1
fi

if [ "$AVAIL" != "yes" ]; then
  echo "UNAVAILABLE: $DOMAIN is taken."
  exit 0
fi

PRICE=$(echo "$CHECK" | jq -r '.pricing.registration // "0"')
echo "AVAILABLE: $DOMAIN @ \$$PRICE/yr"

# Step 2: Price guard
if (( $(echo "$PRICE > $MAX_PRICE" | bc -l) )); then
  echo "PRICE GUARD: \$$PRICE exceeds max \$$MAX_PRICE -- skipping auto-buy"
  echo "Run with MAX_PRICE=$PRICE $0 $DOMAIN to override"
  exit 0
fi

# Step 3: Register
echo "BUYING: $DOMAIN for \$$PRICE..."
REG=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/register/$DOMAIN" \
  -H "Content-Type: application/json" \
  -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET\",\"years\":1}")

REG_STATUS=$(echo "$REG" | jq -r '.status')
if [ "$REG_STATUS" = "SUCCESS" ]; then
  echo "PURCHASED: $DOMAIN -- \$$PRICE"
  echo "$REG" | jq .
else
  echo "REGISTRATION FAILED:"
  echo "$REG" | jq .
  exit 1
fi
```

### Secondary: Cloudflare (at-cost pricing, great for .dev/.io)

Use Cloudflare when:
- The TLD is supported and you want cheapest possible renewal
- You want automatic Cloudflare DNS/CDN integration
- Registration = Renewal price (no bait-and-switch)

### Batch Scanner + Auto-Buy Pipeline

```bash
#!/bin/bash
# batch-scan.sh -- Check a list of domains, report availability + prices
# Usage: echo "domain1.com\ndomain2.io" | ./batch-scan.sh

set -euo pipefail

API_KEY="${PORKBUN_API_KEY:?Set PORKBUN_API_KEY env var}"
SECRET="${PORKBUN_SECRET_KEY:?Set PORKBUN_SECRET_KEY env var}"

echo "domain,available,reg_price,renewal_price"

while IFS= read -r DOMAIN; do
  [ -z "$DOMAIN" ] && continue

  RESULT=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/domain/check/$DOMAIN" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET\"}")

  AVAIL=$(echo "$RESULT" | jq -r '.avail // "error"')
  REG=$(echo "$RESULT" | jq -r '.pricing.registration // "N/A"')
  REN=$(echo "$RESULT" | jq -r '.pricing.renewal // "N/A"')

  echo "$DOMAIN,$AVAIL,$REG,$REN"

  # Respect rate limit: 1 check per 10 seconds
  sleep 10
done
```

### Environment Setup

Add to `~/.zshrc`:
```bash
export PORKBUN_API_KEY="pk1_xxxxxxxxxxxxxxxx"
export PORKBUN_SECRET_KEY="sk1_xxxxxxxxxxxxxxxx"
export CF_API_TOKEN="xxxxxxxxxxxxxxxx"
export CF_ACCOUNT_ID="xxxxxxxxxxxxxxxx"
```

---

## Summary

**For our use case (find gem -> buy instantly), Porkbun is the clear winner:**

1. **Simplest auth** -- just API key + secret in POST body
2. **Single call** returns availability AND pricing (no separate pricing lookup needed)
3. **Registration uses account profile** -- no verbose contact blocks to pass
4. **Cheapest .com** -- $9.68 reg AND renewal (same price, no bait-and-switch)
5. **Free WHOIS privacy** -- automatic on supported TLDs
6. **No account minimums** -- works immediately
7. **JSON API** -- easy to parse with jq

**Cloudflare as secondary** for at-cost pricing on supported TLDs and automatic CDN integration.

**Avoid GoDaddy** -- 50-domain minimum for availability API, most expensive renewals, privacy costs extra.

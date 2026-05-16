# ClaudeChrome Task: DropCatch/NameBright API Setup

## Goal

Get DropCatch API credentials (CLIENT_ID + CLIENT_SECRET) so the Domain Hunter pipeline can place automated backorders on dropping domains.

---

## Steps (in order)

### Step 1: NameBright Account — Accept Terms & Conditions

1. Go to https://www.namebright.com
2. Log in (or create account if needed)
3. There should be a Terms & Conditions modal/banner — **ACCEPT IT**
4. Complete any profile requirements (name, address, payment method)

### Step 2: NameBright API — Apply for Access

1. Go to https://www.namebright.com/Settings#/api (or find "API Management" in account settings)
2. Click "Apply for API Access" or "Request API Key"
3. Fill in the application:
   - **Use case**: "Automated domain backorder management via REST API. Placing backorders on expiring/dropping .com domains for a small portfolio (< 50 backorders/month)."
   - **Expected volume**: "Low — under 30 requests per day"
   - **Company/Project**: "Domain Hunter (personal project)"
4. Submit the application
5. Wait for approval (may be instant or take 1-2 business days)

### Step 3: Get OAuth2 Credentials

Once approved:
1. Go back to API Management page
2. Create a new "Application" or "API Client"
3. Copy the **CLIENT_ID** and **CLIENT_SECRET**
4. Note the OAuth2 token endpoint: `https://api.namebright.com/auth/token`

### Step 4: Report Back

Tell me these values:
- CLIENT_ID: `___________`
- CLIENT_SECRET: `___________`

I will add them to the `.env` file and test the connection.

---

## If Setup Is Blocked

If any of these happen, report back:

- **"API access requires KYC/government ID"** — Note what's required
- **"Application pending review"** — Note estimated timeline
- **"Payment method required first"** — Add a card, then retry
- **"Contact support"** — Use the Contact Us form with this message:

> Subject: API Access Request — DropCatch Backorder Integration
>
> Hi,
>
> I'd like to request API access to use the DropCatch/NameBright REST API for automated domain backorder management. I have a small portfolio and plan to place under 50 backorders per month via your v2 API.
>
> Could you please enable API access on my account or let me know what additional steps are needed?
>
> Thank you.

---

## Context (why this matters)

- DropCatch has ~1,200 ICANN accreditations vs Dynadot's ~15
- Catch rate: DropCatch ~40-60% vs Dynadot ~1-3% for contested .com
- Our top targets (cytheris.com, ghostautonomy.com, bside.com) will enter pendingDelete in Aug-Sep 2026
- We need credentials BEFORE then to place backorders in advance
- **Rate limit**: 30 requests per 30 seconds — already handled in our code

---

## Also: Top Up Dynadot Balance

While on NameBright, also go to https://www.dynadot.com and top up the account balance:
- Current balance: **$3.24** (insufficient for backorders at $10.99/catch)
- Recommended top-up: **$25-$50**
- Dynadot backorders are insurance (low catch rate) alongside DropCatch

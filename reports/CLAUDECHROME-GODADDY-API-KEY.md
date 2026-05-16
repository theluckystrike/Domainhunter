# ClaudeChrome Task: Create GoDaddy API Key

## Goal

Create a GoDaddy Production API key at developer.godaddy.com/keys (tab already open).

---

## Steps

### Step 1: Create the API Key

1. You should already have the tab open: https://developer.godaddy.com/keys
2. Click **"Create New API Key"** button
3. Fill in:
   - **Name/Label**: `DomainHunter` (or any descriptive name)
   - **Environment**: Select **Production** (NOT "Test/OTE")
4. Click **Create** or **Submit**

### Step 2: Copy Credentials

Once created, you'll see:
- **API Key** (also called "Key"): a long alphanumeric string
- **API Secret** (also called "Secret"): shown ONCE — copy it immediately

**IMPORTANT**: The Secret is only shown once at creation time. Copy both values.

### Step 3: Report Back

Tell me:
```
API Key: ___________
API Secret: ___________
```

I will add them to the `.env` file for the GoDaddy inventory automation.

---

## Context

- Auth header format: `Authorization: sso-key {API_KEY}:{API_SECRET}`
- Rate limit: 60 requests/minute, 20K calls/month
- We'll use this for: domain availability checks, auction monitoring automation
- The free inventory files (no auth) handle most monitoring — API key is for future bidding automation

---

## If Issues

- **"You need domains in your account"** — Some endpoints require 50+ domains. Note this and move on; we primarily use the free inventory files.
- **"OTE only available"** — Make sure to select "Production" environment.
- **Email verification required** — Complete it and retry.

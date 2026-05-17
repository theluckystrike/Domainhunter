# Sprint 33 — Human Actions Guide

**Created**: 2026-05-17
**Total time**: ~10 minutes
**Actions**: 6 (4 require action, 1 verify-only, 1 already done)

---

## Do Now (5 minutes)

These are blocking. Without them, you cannot bid on auctions or catch dropping domains.

### 1. Dynadot Top-up — CRITICAL

**Why**: Balance is $3.24. Cannot catch guerrameats.com at $10.99 renewal cost.
**Time**: ~1 minute

- [ ] Go to [dynadot.com](https://www.dynadot.com)
- [ ] Log in
- [ ] Click **My Account** (top-right) → **Account Balance** → **Add Funds**
- [ ] Select **Credit Card** as payment method
- [ ] Enter **$50.00**
- [ ] Click **Submit Payment**
- [ ] Verify balance now shows **$53.24** (or close, after any processing fees)

### 2. NameBright / DropCatch Top-up — CRITICAL

**Why**: Balance is $0.00. DropCatch backorders cost $59/domain. Cannot place any backorders without funds. 8 imminent targets are waiting.
**Time**: ~2 minutes

- [ ] Go to [namebright.com](https://www.namebright.com)
- [ ] Log in
- [ ] Click **Account** → **Add Funds**
- [ ] Add **$300 - $500** via credit card (enough for 5-8 DropCatch backorders at $59 each)
- [ ] Verify the balance updates in your account dashboard
- [ ] After funding, return to terminal and run:
  ```bash
  cd /Users/mike/Desktop/domainhunter
  python3 scripts/catch_orchestrator.py
  ```
  This places live backorders on the 8 imminent drop targets.

### 3. GoDaddy SMS Alerts — MEDIUM

**Why**: Get real-time outbid and auction-ending notifications so you never miss a snipe window.
**Time**: ~1 minute

- [ ] Go to [auctions.godaddy.com/beta/settings](https://auctions.godaddy.com/beta/settings)
- [ ] Log in if prompted
- [ ] Find **Notification Preferences** section
- [ ] Enable **"Outbid notification"** via SMS
- [ ] Enable **"Auction ending in 1 hour"** via SMS
- [ ] Enter your phone number if not already on file
- [ ] Save settings

---

## Do This Week (5 minutes)

These have longer deadlines but must be done before specific auction dates.

### 4. GoDaddy Identity Verification — CRITICAL

**Why**: You are capped at **2 simultaneous bids / $1,500 max bid** until verified. bside.com auction is estimated around Jul 19. Verification takes 1-3 business days to process, so submit by **May 28** at the latest (10 business days buffer).
**Time**: ~3 minutes

- [ ] Go to [auctions.godaddy.com](https://auctions.godaddy.com)
- [ ] Log in
- [ ] Click your **Account** / **Profile** (top-right menu)
- [ ] Find **Identity Verification** section
- [ ] Click **Start Verification** (or similar)
- [ ] Upload a clear photo of your **government-issued ID** (passport, driver's license, or national ID card)
- [ ] Confirm your name and address match your GoDaddy account
- [ ] Click **Submit**
- [ ] Wait 1-3 business days for approval email
- [ ] After approval, verify your bid limits have been raised (no more 2-bid / $1,500 cap)

**Deadline**: May 28, 2026 (hard)

### 5. Daemon Login Items — Verify Only

**Why**: The daemon should already auto-start on reboot via launchd. Just confirm it is loaded.
**Time**: ~1 minute

- [ ] Open Terminal
- [ ] Run:
  ```bash
  launchctl list | grep domainhunter
  ```
- [ ] **If output appears** (shows PID and label `com.domainhunter.daemon`): Already persistent. No action needed. You are done.
- [ ] **If no output**: The LaunchAgent is not loaded. Run:
  ```bash
  launchctl load ~/Library/LaunchAgents/com.domainhunter.daemon.plist
  ```
  Then re-run the check command above to confirm it loaded.

---

## Already Done

### 6. NameBright API — DONE

Completed in Sprint 32. API keys created, OAuth2 working, 6/6 connectivity checks GREEN.

- [x] No action needed.

---

## Quick Summary

| # | Action | Priority | Time | Deadline |
|---|--------|----------|------|----------|
| 1 | Dynadot top-up ($50) | CRITICAL | 1 min | Now |
| 2 | NameBright top-up ($300-500) + run catch_orchestrator | CRITICAL | 2 min | Now |
| 3 | GoDaddy SMS alerts | MEDIUM | 1 min | Now |
| 4 | GoDaddy identity verification | CRITICAL | 3 min | May 28 |
| 5 | Daemon persistence check | HIGH | 1 min | This week |
| 6 | NameBright API | DONE | 0 min | -- |

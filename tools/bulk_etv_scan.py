#!/usr/bin/env python3
"""
Sprint 14 - BULK TRAFFIC SCAN (Agent 6)
Scans domains through DataForSEO domain_rank_overview to find verified organic traffic (ETV).
Looking for hidden whales like olive.com ($2,923 ETV) or globalgeopark.org ($626 ETV).
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error
import base64
from datetime import datetime

# === CONFIG ===
API_LOGIN = "support@zovo.one"
API_PASSWORD = "f9f943da5a9ef3e9"
API_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"
COST_PER_CALL = 0.01
MAX_BUDGET = 20.00  # $5 already spent on first (failed) run, keeping total under $25
MAX_DOMAINS = 2000  # Hard cap
DELAY_BETWEEN_CALLS = 0.2  # 5/sec rate limit
SAVE_EVERY = 100
PRINT_EVERY = 50

DATA_DIR = "/Users/mike/Desktop/domainhunter/data"
OUTPUT_FILE = os.path.join(DATA_DIR, "sprint14_bulk_scan.json")

# Domains already verified by Agent 10 — exclude these
EXCLUDED = {
    "decoder.com", "gamepicker.com", "beautifier.com", "fileconverter.com",
    "fileshare.com", "cookingtool.com", "ghostautonomy.com", "noogata.com",
    "goforward.com", "olive.com", "bestdevtools.com", "taskplanner.com",
    "sushifaq.com", "builder.ai", "canoo.com", "reviewer.com",
    "ingredientcalculator.com", "pictureeditor.net", "recipetool.net",
    "saasmetrics.com", "codehelper.com", "codeanalyzer.com", "codingtools.com",
    "sitegrader.com", "imageeditor.net", "debtcalc.com", "aitoolkit.com",
    "globalgeopark.org"
}

# Auth header
auth_string = base64.b64encode(f"{API_LOGIN}:{API_PASSWORD}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {auth_string}",
    "Content-Type": "application/json"
}


def load_all_domains():
    """Load domains from all 5 JSON files, deduplicate, and return with metadata."""
    all_domains = {}  # domain -> metadata dict

    # 1. Source domains (1,310)
    with open(os.path.join(DATA_DIR, "sprint14_source_domains.json")) as f:
        data = json.load(f)
    for d in data.get("domains", []):
        domain = d["domain"].lower().strip()
        if domain not in all_domains:
            all_domains[domain] = {
                "source_file": "source",
                "estimated_value": d.get("estimated_value", 0),
                "age_years": d.get("age_years", 0),
                "da": 0,
                "priority": "standard",
                "funding": ""
            }

    # 2. Startup domains (205)
    with open(os.path.join(DATA_DIR, "sprint14_startup_domains.json")) as f:
        data = json.load(f)
    for d in data.get("domains", []):
        domain = d["domain"].lower().strip()
        if domain not in all_domains:
            all_domains[domain] = {
                "source_file": "startup",
                "estimated_value": 0,
                "age_years": 0,
                "da": 0,
                "priority": "standard",
                "funding": d.get("funding", "")
            }
        else:
            all_domains[domain]["funding"] = d.get("funding", "")
            all_domains[domain]["source_file"] += "+startup"

    # 3. Auction domains (419)
    with open(os.path.join(DATA_DIR, "sprint14_auction_domains.json")) as f:
        data = json.load(f)
    for d in data.get("domains", []):
        domain = d["domain"].lower().strip()
        if domain not in all_domains:
            all_domains[domain] = {
                "source_file": "auction",
                "estimated_value": 0,
                "age_years": 0,
                "da": 0,
                "priority": "standard",
                "funding": ""
            }
        else:
            all_domains[domain]["source_file"] += "+auction"

    # 4. Existing pipeline (1,345)
    with open(os.path.join(DATA_DIR, "sprint14_existing_domains.json")) as f:
        data = json.load(f)
    for d in data.get("domains", []):
        domain = d["domain"].lower().strip()
        priority = d.get("priority", "standard")
        if domain not in all_domains:
            all_domains[domain] = {
                "source_file": "existing",
                "estimated_value": 0,
                "age_years": 0,
                "da": 0,
                "priority": priority,
                "funding": ""
            }
        else:
            all_domains[domain]["source_file"] += "+existing"
            # Upgrade priority if existing has better
            prio_order = ["eliminated", "standard", "high", "registered", "whale", "crown_jewel"]
            cur = all_domains[domain]["priority"]
            if prio_order.index(priority) > prio_order.index(cur) if cur in prio_order else True:
                all_domains[domain]["priority"] = priority

    # 5. Nonprofit domains (173) — complex structure with multiple tiers
    with open(os.path.join(DATA_DIR, "sprint14_nonprofit_domains.json")) as f:
        data = json.load(f)

    # Extract from all tiers
    tier_keys = [k for k in data.keys() if k.startswith("tier")]
    for tier_key in tier_keys:
        tier_data = data[tier_key]
        for d in tier_data.get("domains", []):
            domain = d["domain"].lower().strip()
            da = d.get("da", 0)
            if domain not in all_domains:
                all_domains[domain] = {
                    "source_file": "nonprofit",
                    "estimated_value": 0,
                    "age_years": 0,
                    "da": da,
                    "priority": "standard",
                    "funding": ""
                }
            else:
                all_domains[domain]["source_file"] += "+nonprofit"
                if da > all_domains[domain]["da"]:
                    all_domains[domain]["da"] = da

    # Also check additional_discovery_domains
    if "additional_discovery_domains" in data:
        add_data = data["additional_discovery_domains"]
        for d in add_data.get("domains", []):
            domain = d["domain"].lower().strip()
            da = d.get("da", 0)
            if domain not in all_domains:
                all_domains[domain] = {
                    "source_file": "nonprofit_additional",
                    "estimated_value": 0,
                    "age_years": 0,
                    "da": da,
                    "priority": "standard",
                    "funding": ""
                }

    # Also check top_10_for_immediate_action (list of domain strings)
    if "top_10_for_immediate_action" in data:
        for item in data["top_10_for_immediate_action"]:
            if isinstance(item, str):
                domain = item.lower().strip()
                if domain not in all_domains:
                    all_domains[domain] = {
                        "source_file": "nonprofit_top10",
                        "estimated_value": 0,
                        "age_years": 0,
                        "da": 0,
                        "priority": "high",
                        "funding": ""
                    }
            elif isinstance(item, dict) and "domain" in item:
                domain = item["domain"].lower().strip()
                if domain not in all_domains:
                    all_domains[domain] = {
                        "source_file": "nonprofit_top10",
                        "estimated_value": 0,
                        "age_years": 0,
                        "da": item.get("da", 0),
                        "priority": "high",
                        "funding": ""
                    }

    # Remove excluded domains
    for excl in EXCLUDED:
        all_domains.pop(excl.lower(), None)

    return all_domains


def parse_funding(funding_str):
    """Parse funding string like '$238M' to a numeric value for sorting."""
    if not funding_str:
        return 0
    funding_str = funding_str.replace("$", "").replace(",", "").strip()
    multiplier = 1
    if funding_str.endswith("B"):
        multiplier = 1_000_000_000
        funding_str = funding_str[:-1]
    elif funding_str.endswith("M"):
        multiplier = 1_000_000
        funding_str = funding_str[:-1]
    elif funding_str.endswith("K"):
        multiplier = 1_000
        funding_str = funding_str[:-1]
    try:
        return float(funding_str) * multiplier
    except ValueError:
        return 0


def prioritize_domains(all_domains):
    """Sort domains by priority tiers."""

    def sort_key(item):
        domain, meta = item
        da = meta.get("da", 0)
        funding = parse_funding(meta.get("funding", ""))
        is_org = domain.endswith(".org")
        is_premium_com = domain.endswith(".com") and len(domain.replace(".com", "")) <= 12
        priority = meta.get("priority", "standard")

        # Priority score (higher = scan first)
        score = 0

        # Priority tier from existing pipeline
        prio_scores = {"crown_jewel": 10000, "whale": 8000, "registered": 6000, "high": 4000, "standard": 0, "eliminated": -5000}
        score += prio_scores.get(priority, 0)

        # DA-based priority (highest weight)
        if da >= 50:
            score += 5000
        elif da >= 30:
            score += 3000
        elif da >= 20:
            score += 2000
        elif da >= 10:
            score += 1000

        # High funding startups
        if funding >= 100_000_000:
            score += 4000
        elif funding >= 50_000_000:
            score += 2000
        elif funding >= 10_000_000:
            score += 1000

        # .org domains
        if is_org:
            score += 1500

        # Estimated value from GoDaddy
        ev = meta.get("estimated_value", 0)
        if ev >= 10000:
            score += 3000
        elif ev >= 5000:
            score += 2000
        elif ev >= 1000:
            score += 1000

        # Premium keyword .com
        if is_premium_com:
            score += 500

        # Multi-source domains are more interesting
        source = meta.get("source_file", "")
        score += source.count("+") * 200

        return -score  # Negative for descending sort

    sorted_domains = sorted(all_domains.items(), key=sort_key)
    return [domain for domain, meta in sorted_domains]


def query_domain(domain):
    """Query DataForSEO for a single domain's rank overview."""
    payload = json.dumps([{
        "target": domain,
        "language_code": "en",
        "location_code": 2840
    }]).encode("utf-8")

    req = urllib.request.Request(API_URL, data=payload, headers=HEADERS, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"URL Error: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def extract_metrics(api_result, domain):
    """Extract key metrics from API response."""
    try:
        if "error" in api_result:
            return {"domain": domain, "etv": 0, "error": api_result["error"]}

        tasks = api_result.get("tasks", [])
        if not tasks:
            return {"domain": domain, "etv": 0, "error": "no tasks"}

        task = tasks[0]
        if task.get("status_code") != 20000:
            return {"domain": domain, "etv": 0, "error": f"status {task.get('status_code')}"}

        results = task.get("result", [])
        if not results or results[0] is None:
            return {"domain": domain, "etv": 0, "keywords": 0, "rank": 0}

        r = results[0]

        # Data is nested under items[0].metrics
        items = r.get("items", [])
        if items and items[0] is not None:
            metrics = items[0].get("metrics", {})
        else:
            metrics = r.get("metrics", {})

        organic = metrics.get("organic", {})
        paid = metrics.get("paid", {})

        return {
            "domain": domain,
            "etv": organic.get("etv", 0) or 0,
            "keywords": organic.get("count", 0) or 0,
            "pos_1": organic.get("pos_1", 0) or 0,
            "pos_2_3": organic.get("pos_2_3", 0) or 0,
            "pos_4_10": organic.get("pos_4_10", 0) or 0,
            "pos_11_20": organic.get("pos_11_20", 0) or 0,
            "pos_21_30": organic.get("pos_21_30", 0) or 0,
            "pos_31_40": organic.get("pos_31_40", 0) or 0,
            "pos_41_50": organic.get("pos_41_50", 0) or 0,
            "pos_51_60": organic.get("pos_51_60", 0) or 0,
            "pos_61_70": organic.get("pos_61_70", 0) or 0,
            "pos_71_100": organic.get("pos_71_100", 0) or 0,
            "impressions_etv": organic.get("impressions_etv", 0) or 0,
            "estimated_paid_traffic_cost": organic.get("estimated_paid_traffic_cost", 0) or 0,
            "is_new": organic.get("is_new", 0) or 0,
            "is_up": organic.get("is_up", 0) or 0,
            "is_down": organic.get("is_down", 0) or 0,
            "is_lost": organic.get("is_lost", 0) or 0,
            "paid_etv": paid.get("etv", 0) or 0,
            "paid_count": paid.get("count", 0) or 0,
            "rank": r.get("rank", 0) or 0,
        }
    except Exception as e:
        return {"domain": domain, "etv": 0, "error": str(e)}


def classify_tier(etv):
    """Classify domain by ETV tier."""
    if etv >= 1000:
        return "whale"
    elif etv >= 100:
        return "strong"
    elif etv >= 10:
        return "decent"
    else:
        return "zero"


def save_results(results, total_scanned, total_cost, scan_start):
    """Save current results to output JSON."""
    whale = [r for r in results if classify_tier(r.get("etv", 0)) == "whale"]
    strong = [r for r in results if classify_tier(r.get("etv", 0)) == "strong"]
    decent = [r for r in results if classify_tier(r.get("etv", 0)) == "decent"]
    zero_count = sum(1 for r in results if classify_tier(r.get("etv", 0)) == "zero")

    # Sort each tier by ETV descending
    whale.sort(key=lambda x: x.get("etv", 0), reverse=True)
    strong.sort(key=lambda x: x.get("etv", 0), reverse=True)
    decent.sort(key=lambda x: x.get("etv", 0), reverse=True)

    # Top 50 by ETV
    sorted_results = sorted(results, key=lambda x: x.get("etv", 0), reverse=True)
    top_50 = sorted_results[:50]

    # Full results sorted by ETV descending
    output = {
        "sprint": 14,
        "agent": "BULK TRAFFIC SCAN",
        "scan_date": "2026-05-08",
        "total_scanned": total_scanned,
        "total_cost": round(total_cost, 2),
        "scan_duration_seconds": round(time.time() - scan_start, 1),
        "tiers": {
            "whale": whale,
            "whale_count": len(whale),
            "strong": strong,
            "strong_count": len(strong),
            "decent": decent,
            "decent_count": len(decent),
            "zero_count": zero_count
        },
        "top_50_by_etv": top_50,
        "results": sorted_results
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)


def main():
    print("=" * 70)
    print("SPRINT 14 - BULK TRAFFIC SCAN (Agent 6)")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Load all domains
    print("[STEP 1] Loading domains from 5 JSON files...")
    all_domains = load_all_domains()
    print(f"  Total unique domains (after dedup + exclusion): {len(all_domains)}")

    # Step 2: Prioritize
    print("[STEP 2] Prioritizing scan order...")
    ordered_domains = prioritize_domains(all_domains)

    # Cap at MAX_DOMAINS
    if len(ordered_domains) > MAX_DOMAINS:
        print(f"  Capping at {MAX_DOMAINS} domains (from {len(ordered_domains)})")
        ordered_domains = ordered_domains[:MAX_DOMAINS]
    print(f"  Will scan: {len(ordered_domains)} domains")
    print(f"  Estimated cost: ${len(ordered_domains) * COST_PER_CALL:.2f}")
    print(f"  Estimated time: {len(ordered_domains) * DELAY_BETWEEN_CALLS / 60:.1f} minutes")
    print()

    # Step 3: Scan
    print("[STEP 3] Starting DataForSEO API scan...")
    print("-" * 70)

    results = []
    total_cost = 0.0
    errors = 0
    scan_start = time.time()

    for i, domain in enumerate(ordered_domains):
        # Budget check
        if total_cost + COST_PER_CALL > MAX_BUDGET:
            print(f"\n*** BUDGET LIMIT REACHED at domain #{i+1} (${total_cost:.2f}) ***")
            break

        # Query API
        api_result = query_domain(domain)
        total_cost += COST_PER_CALL

        # Extract metrics
        metrics = extract_metrics(api_result, domain)
        metrics["scan_order"] = i + 1
        metrics["source_file"] = all_domains[domain]["source_file"]
        results.append(metrics)

        etv = metrics.get("etv", 0)
        keywords = metrics.get("keywords", 0)

        # Check for errors
        if "error" in metrics:
            errors += 1

        # Print notable finds immediately
        if etv >= 100:
            tier = classify_tier(etv)
            print(f"  *** {tier.upper()} FOUND *** #{i+1} {domain}: ETV=${etv:,.0f}, {keywords} keywords")
        elif etv >= 10:
            print(f"  + DECENT #{i+1} {domain}: ETV=${etv:,.0f}, {keywords} keywords")

        # Progress update
        if (i + 1) % PRINT_EVERY == 0:
            elapsed = time.time() - scan_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            whales = sum(1 for r in results if r.get("etv", 0) >= 1000)
            strongs = sum(1 for r in results if 100 <= r.get("etv", 0) < 1000)
            decents = sum(1 for r in results if 10 <= r.get("etv", 0) < 100)
            print(f"  [{i+1}/{len(ordered_domains)}] ${total_cost:.2f} spent | "
                  f"{rate:.1f} domains/sec | "
                  f"Whales:{whales} Strong:{strongs} Decent:{decents} Errors:{errors}")

        # Save checkpoint
        if (i + 1) % SAVE_EVERY == 0:
            save_results(results, i + 1, total_cost, scan_start)
            print(f"  [SAVED checkpoint at {i+1} domains]")

        # Rate limit
        time.sleep(DELAY_BETWEEN_CALLS)

    # Final save
    total_scanned = len(results)
    save_results(results, total_scanned, total_cost, scan_start)

    # Step 4: Summary
    elapsed = time.time() - scan_start
    print()
    print("=" * 70)
    print("SCAN COMPLETE - FINAL SUMMARY")
    print("=" * 70)
    print(f"Total scanned: {total_scanned}")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Duration: {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")
    print(f"Errors: {errors}")
    print()

    # Tier breakdown
    whale = [r for r in results if r.get("etv", 0) >= 1000]
    strong = [r for r in results if 100 <= r.get("etv", 0) < 1000]
    decent = [r for r in results if 10 <= r.get("etv", 0) < 100]
    zero = [r for r in results if r.get("etv", 0) < 10]

    print(f"WHALES (ETV >= $1,000): {len(whale)}")
    for w in sorted(whale, key=lambda x: x.get("etv", 0), reverse=True):
        print(f"  {w['domain']}: ETV=${w.get('etv', 0):,.0f} | {w.get('keywords', 0)} keywords | rank={w.get('rank', 0)}")

    print(f"\nSTRONG (ETV $100-$999): {len(strong)}")
    for s in sorted(strong, key=lambda x: x.get("etv", 0), reverse=True):
        print(f"  {s['domain']}: ETV=${s.get('etv', 0):,.0f} | {s.get('keywords', 0)} keywords")

    print(f"\nDECENT (ETV $10-$99): {len(decent)}")
    for d in sorted(decent, key=lambda x: x.get("etv", 0), reverse=True)[:20]:
        print(f"  {d['domain']}: ETV=${d.get('etv', 0):,.0f} | {d.get('keywords', 0)} keywords")
    if len(decent) > 20:
        print(f"  ... and {len(decent) - 20} more")

    print(f"\nZERO (ETV < $10): {len(zero)}")
    print()

    # Top 10
    print("TOP 10 BY ETV:")
    sorted_all = sorted(results, key=lambda x: x.get("etv", 0), reverse=True)
    for i, r in enumerate(sorted_all[:10], 1):
        print(f"  {i}. {r['domain']}: ETV=${r.get('etv', 0):,.0f} | "
              f"{r.get('keywords', 0)} keywords | rank={r.get('rank', 0)} | "
              f"source={r.get('source_file', '')}")

    print(f"\nResults saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    # Force unbuffered output for real-time progress
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
    main()

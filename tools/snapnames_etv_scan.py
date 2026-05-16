#!/usr/bin/env python3
"""
Sprint 17 - SnapNames Hotpicks Full ETV Scan
Scans ALL domains from SnapNames DomainList.csv through DataForSEO.
Finds hidden whales with real organic traffic among auction domains.
"""

import csv
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
MAX_BUDGET = 10.00
DELAY_BETWEEN_CALLS = 0.25
SAVE_EVERY = 50

DATA_DIR = "/Users/mike/Desktop/domainhunter/data"
CSV_PATH = "/Users/mike/Downloads/DomainList.csv"
OUTPUT_FILE = os.path.join(DATA_DIR, "sprint17_snapnames_etv_scan.json")
REPORT_FILE = "/Users/mike/Desktop/DOMAINHUNTER-SPRINT17-SNAPNAMES-ETV-REPORT.md"

auth_string = base64.b64encode(f"{API_LOGIN}:{API_PASSWORD}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {auth_string}",
    "Content-Type": "application/json"
}


def load_csv_domains(path):
    """Parse SnapNames CSV export. Returns list of dicts."""
    domains = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Domain Name", "").strip().strip('"')
            if not name:
                continue
            bidders = 0
            try:
                bidders = int(row.get("Bidders", "0").strip().strip('"'))
            except ValueError:
                pass
            min_bid = 0
            try:
                min_bid = int(row.get("Minimum Bid", "0").strip().strip('"'))
            except ValueError:
                pass
            status = row.get("Status", "").strip().strip('"')
            order_by = row.get("Order By", "").strip().strip('"')
            domains.append({
                "domain": name.lower(),
                "bidders": bidders,
                "min_bid": min_bid,
                "status": status,
                "auction_end": order_by,
            })
    return domains


def query_domain(domain):
    """Query DataForSEO for a single domain."""
    payload = json.dumps([{
        "target": domain,
        "language_code": "en",
        "location_code": 2840
    }]).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
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
            return {"domain": domain, "etv": 0, "keywords": 0, "error": api_result["error"]}
        tasks = api_result.get("tasks", [])
        if not tasks:
            return {"domain": domain, "etv": 0, "keywords": 0, "error": "no tasks"}
        task = tasks[0]
        if task.get("status_code") != 20000:
            return {"domain": domain, "etv": 0, "keywords": 0, "error": f"status {task.get('status_code')}"}
        results = task.get("result", [])
        if not results or results[0] is None:
            return {"domain": domain, "etv": 0, "keywords": 0}
        r = results[0]
        items = r.get("items", [])
        if items and items[0] is not None:
            metrics = items[0].get("metrics", {})
        else:
            metrics = r.get("metrics", {})
        organic = metrics.get("organic", {})
        return {
            "domain": domain,
            "etv": organic.get("etv", 0) or 0,
            "keywords": organic.get("count", 0) or 0,
            "pos_1": organic.get("pos_1", 0) or 0,
            "pos_2_3": organic.get("pos_2_3", 0) or 0,
            "pos_4_10": organic.get("pos_4_10", 0) or 0,
            "impressions_etv": organic.get("impressions_etv", 0) or 0,
            "is_lost": organic.get("is_lost", 0) or 0,
        }
    except Exception as e:
        return {"domain": domain, "etv": 0, "keywords": 0, "error": str(e)}


def save_results(results, auction_data, total_scanned, total_cost, scan_start):
    """Save checkpoint to JSON."""
    for r in results:
        dom = r["domain"]
        if dom in auction_data:
            r["bidders"] = auction_data[dom]["bidders"]
            r["min_bid"] = auction_data[dom]["min_bid"]
            r["auction_status"] = auction_data[dom]["status"]
            r["auction_end"] = auction_data[dom]["auction_end"]

    sorted_results = sorted(results, key=lambda x: x.get("etv", 0), reverse=True)
    whales = [r for r in sorted_results if r.get("etv", 0) >= 1000]
    strong = [r for r in sorted_results if 100 <= r.get("etv", 0) < 1000]
    decent = [r for r in sorted_results if 10 <= r.get("etv", 0) < 100]
    nonzero = [r for r in sorted_results if r.get("etv", 0) > 0]

    output = {
        "sprint": 17,
        "agent": "SNAPNAMES HOTPICKS ETV SCAN",
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "SnapNames DomainList.csv",
        "total_domains_in_csv": len(auction_data),
        "total_scanned": total_scanned,
        "total_cost": round(total_cost, 2),
        "scan_duration_seconds": round(time.time() - scan_start, 1),
        "summary": {
            "whales_1000plus": len(whales),
            "strong_100_999": len(strong),
            "decent_10_99": len(decent),
            "nonzero_total": len(nonzero),
            "zero_etv": total_scanned - len(nonzero),
        },
        "whales": whales,
        "strong": strong,
        "decent": decent,
        "top_50": sorted_results[:50],
        "all_results": sorted_results,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)


def generate_report(results, auction_data, total_scanned, total_cost, scan_start):
    """Generate markdown report on Desktop."""
    sorted_results = sorted(results, key=lambda x: x.get("etv", 0), reverse=True)
    whales = [r for r in sorted_results if r.get("etv", 0) >= 1000]
    strong = [r for r in sorted_results if 100 <= r.get("etv", 0) < 1000]
    decent = [r for r in sorted_results if 10 <= r.get("etv", 0) < 100]
    nonzero = [r for r in sorted_results if r.get("etv", 0) > 0]
    elapsed = time.time() - scan_start

    lines = []
    lines.append("# Domain Hunter REVENANT -- Sprint 17 SnapNames ETV Scan Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Sprint:** 17 | **Source:** SnapNames Hotpicks CSV")
    lines.append(f"**Domains Scanned:** {total_scanned} | **Cost:** ${total_cost:.2f} | **Duration:** {elapsed:.0f}s ({elapsed/60:.1f}m)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## EXECUTIVE SUMMARY")
    lines.append("")
    lines.append(f"Scanned **{total_scanned}** SnapNames hotpick auction domains through DataForSEO ETV verification.")
    lines.append(f"- **Whales (ETV >= $1,000/mo):** {len(whales)}")
    lines.append(f"- **Strong (ETV $100-$999/mo):** {len(strong)}")
    lines.append(f"- **Decent (ETV $10-$99/mo):** {len(decent)}")
    lines.append(f"- **Non-zero ETV total:** {len(nonzero)}")
    lines.append(f"- **Zero ETV:** {total_scanned - len(nonzero)}")
    lines.append("")

    if whales:
        lines.append("---")
        lines.append("")
        lines.append("## WHALE DOMAINS (ETV >= $1,000/mo) -- ACTIONABLE")
        lines.append("")
        lines.append("| Domain | ETV/mo | Keywords | Top 10 | Bidders | Min Bid | Status | Auction End |")
        lines.append("|--------|--------|----------|--------|---------|---------|--------|-------------|")
        for w in whales:
            top10 = (w.get("pos_1", 0) or 0) + (w.get("pos_2_3", 0) or 0) + (w.get("pos_4_10", 0) or 0)
            lines.append(f"| **{w['domain']}** | **${w.get('etv', 0):,.0f}** | {w.get('keywords', 0):,} | {top10} | {w.get('bidders', 'N/A')} | ${w.get('min_bid', 'N/A')} | {w.get('auction_status', 'N/A')} | {w.get('auction_end', 'N/A')} |")
        lines.append("")

    if strong:
        lines.append("---")
        lines.append("")
        lines.append("## STRONG DOMAINS (ETV $100-$999/mo)")
        lines.append("")
        lines.append("| Domain | ETV/mo | Keywords | Top 10 | Bidders | Min Bid | Status |")
        lines.append("|--------|--------|----------|--------|---------|---------|--------|")
        for s in strong:
            top10 = (s.get("pos_1", 0) or 0) + (s.get("pos_2_3", 0) or 0) + (s.get("pos_4_10", 0) or 0)
            lines.append(f"| {s['domain']} | ${s.get('etv', 0):,.0f} | {s.get('keywords', 0):,} | {top10} | {s.get('bidders', 'N/A')} | ${s.get('min_bid', 'N/A')} | {s.get('auction_status', 'N/A')} |")
        lines.append("")

    if decent:
        lines.append("---")
        lines.append("")
        lines.append("## DECENT DOMAINS (ETV $10-$99/mo)")
        lines.append("")
        lines.append("| Domain | ETV/mo | Keywords | Bidders | Min Bid |")
        lines.append("|--------|--------|----------|---------|---------|")
        for d in decent:
            lines.append(f"| {d['domain']} | ${d.get('etv', 0):,.0f} | {d.get('keywords', 0):,} | {d.get('bidders', 'N/A')} | ${d.get('min_bid', 'N/A')} |")
        lines.append("")

    if not whales and not strong and not decent:
        lines.append("**NO DOMAINS WITH VERIFIED ETV FOUND.** All {total_scanned} SnapNames hotpicks are name bets with $0 organic traffic.")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## VERDICT")
    lines.append("")
    if whales:
        lines.append(f"**{len(whales)} WHALE(S) FOUND** in SnapNames hotpicks. These have real organic traffic and are worth bidding on.")
        for w in whales:
            lines.append(f"- **{w['domain']}**: ${w.get('etv', 0):,.0f}/mo ETV, currently at ${w.get('min_bid', '?')} with {w.get('bidders', '?')} bidders")
    elif strong:
        lines.append(f"No whales, but **{len(strong)} strong domains** with $100-$999/mo ETV. Worth monitoring but not priority targets.")
    else:
        lines.append("**The SnapNames hotpicks are noise.** Zero whales, zero strong domains. All name bets with no verified organic traffic.")
        lines.append("The real value remains in BACKORDERS on identified whale domains, not in SnapNames auctions.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by Domain Hunter REVENANT Sprint 17*")
    lines.append(f"*DataForSEO: {total_scanned} queries, ${total_cost:.2f} cost*")
    lines.append("")

    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to: {REPORT_FILE}")


def main():
    print("=" * 70)
    print("SPRINT 17 - SNAPNAMES HOTPICKS FULL ETV SCAN")
    print("=" * 70)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load CSV
    print("[1] Loading SnapNames CSV...")
    csv_domains = load_csv_domains(CSV_PATH)
    print(f"  Loaded {len(csv_domains)} domains from CSV")

    # Build auction lookup
    auction_data = {}
    for d in csv_domains:
        auction_data[d["domain"]] = d

    # Deduplicate domain list
    domain_list = list(dict.fromkeys(d["domain"] for d in csv_domains))
    print(f"  Unique domains: {len(domain_list)}")
    est_cost = len(domain_list) * COST_PER_CALL
    est_time = len(domain_list) * DELAY_BETWEEN_CALLS / 60
    print(f"  Estimated cost: ${est_cost:.2f}")
    print(f"  Estimated time: {est_time:.1f} minutes")
    print()

    # Scan
    print("[2] Scanning through DataForSEO API...")
    print("-" * 70)

    results = []
    total_cost = 0.0
    errors = 0
    scan_start = time.time()

    for i, domain in enumerate(domain_list):
        if total_cost + COST_PER_CALL > MAX_BUDGET:
            print(f"\n*** BUDGET LIMIT at #{i+1} (${total_cost:.2f}) ***")
            break

        api_result = query_domain(domain)
        total_cost += COST_PER_CALL
        metrics = extract_metrics(api_result, domain)
        results.append(metrics)

        etv = metrics.get("etv", 0)
        kw = metrics.get("keywords", 0)

        if "error" in metrics:
            errors += 1

        if etv >= 1000:
            print(f"  *** WHALE *** #{i+1} {domain}: ETV=${etv:,.0f}, {kw} kw")
        elif etv >= 100:
            print(f"  ** STRONG ** #{i+1} {domain}: ETV=${etv:,.0f}, {kw} kw")
        elif etv >= 10:
            print(f"  + decent #{i+1} {domain}: ETV=${etv:,.0f}, {kw} kw")

        if (i + 1) % 50 == 0:
            elapsed = time.time() - scan_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            wc = sum(1 for r in results if r.get("etv", 0) >= 1000)
            sc = sum(1 for r in results if 100 <= r.get("etv", 0) < 1000)
            dc = sum(1 for r in results if 10 <= r.get("etv", 0) < 100)
            print(f"  [{i+1}/{len(domain_list)}] ${total_cost:.2f} | {rate:.1f}/sec | W:{wc} S:{sc} D:{dc} E:{errors}")

        if (i + 1) % SAVE_EVERY == 0:
            save_results(results, auction_data, i + 1, total_cost, scan_start)

        time.sleep(DELAY_BETWEEN_CALLS)

    # Final save
    total_scanned = len(results)
    save_results(results, auction_data, total_scanned, total_cost, scan_start)

    # Summary
    elapsed = time.time() - scan_start
    print()
    print("=" * 70)
    print("SCAN COMPLETE")
    print("=" * 70)
    print(f"Scanned: {total_scanned} | Cost: ${total_cost:.2f} | Time: {elapsed:.0f}s ({elapsed/60:.1f}m) | Errors: {errors}")

    whales = [r for r in results if r.get("etv", 0) >= 1000]
    strong = [r for r in results if 100 <= r.get("etv", 0) < 1000]
    decent = [r for r in results if 10 <= r.get("etv", 0) < 100]

    print(f"\nWHALES: {len(whales)}")
    for w in sorted(whales, key=lambda x: x.get("etv", 0), reverse=True):
        print(f"  {w['domain']}: ETV=${w.get('etv', 0):,.0f} | {w.get('keywords', 0)} kw")
    print(f"STRONG: {len(strong)}")
    for s in sorted(strong, key=lambda x: x.get("etv", 0), reverse=True):
        print(f"  {s['domain']}: ETV=${s.get('etv', 0):,.0f} | {s.get('keywords', 0)} kw")
    print(f"DECENT: {len(decent)}")
    for d in sorted(decent, key=lambda x: x.get("etv", 0), reverse=True):
        print(f"  {d['domain']}: ETV=${d.get('etv', 0):,.0f} | {d.get('keywords', 0)} kw")

    # Generate report
    print("\n[3] Generating report...")
    generate_report(results, auction_data, total_scanned, total_cost, scan_start)

    print(f"\nJSON: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")
    print("DONE.")


if __name__ == "__main__":
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
    main()

#!/usr/bin/env python3
"""
Sprint 18 — 5-Gate Domain Verification Pipeline
Gate 1: Generic vs Brand classification
Gate 2: DataForSEO ETV scan ($0.01/domain)
Gate 3: Live SERP check on ETV > $100 ($0.01/keyword)
Gate 4: Ranked keywords on SERP-verified domains ($0.01/domain)
Gate 5: DNS resolution check (free)

NASA Power of 10 compliant. All loops bounded. All errors handled.
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error
import base64
import subprocess
from datetime import datetime

# === CONSTANTS ===
MAX_DOMAINS = 50
MAX_API_CALLS = 200
MAX_RETRIES = 2
API_TIMEOUT = 15
DELAY = 0.3

API_LOGIN = "support@zovo.one"
API_PASSWORD = "f9f943da5a9ef3e9"
ETV_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"
SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live"
KEYWORDS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"

DATA_DIR = "/Users/mike/Desktop/domainhunter/data"
REPORT_FILE = "/Users/mike/Desktop/DOMAINHUNTER-SPRINT18-LASTCHANCE-PIPELINE.md"
JSON_FILE = os.path.join(DATA_DIR, "sprint18_lastchance_pipeline.json")

AUTH = base64.b64encode(f"{API_LOGIN}:{API_PASSWORD}".encode()).decode()
HEADERS = {"Authorization": f"Basic {AUTH}", "Content-Type": "application/json"}

# === INPUT: SnapNames Last Chance domains ===
DOMAINS = [
    {"domain": "qf.org", "age": 28, "bidders": 108, "min_bid": 12119, "status": "In Auction"},
    {"domain": "smartresearch.com", "age": 27, "bidders": 94, "min_bid": 475, "status": "In Auction"},
    {"domain": "ussc.com", "age": 32, "bidders": 76, "min_bid": 5809, "status": "In Auction"},
    {"domain": "tempstaffing.com", "age": 28, "bidders": 51, "min_bid": 69, "status": "Available Soon"},
    {"domain": "temporarystaffing.com", "age": 28, "bidders": 33, "min_bid": 69, "status": "Available Soon"},
    {"domain": "arben.com", "age": 30, "bidders": 21, "min_bid": 69, "status": "Available Soon"},
    {"domain": "izbd.com", "age": 19, "bidders": 17, "min_bid": 130, "status": "In Auction"},
    {"domain": "locopay.com", "age": 20, "bidders": 17, "min_bid": 115, "status": "In Auction"},
    {"domain": "hpks.com", "age": 30, "bidders": 16, "min_bid": 69, "status": "Available Soon"},
    {"domain": "bizpartners.com", "age": 26, "bidders": 15, "min_bid": 69, "status": "Available Soon"},
    {"domain": "qualityrepair.com", "age": 29, "bidders": 14, "min_bid": 109, "status": "In Auction"},
    {"domain": "washtech.org", "age": 28, "bidders": 12, "min_bid": 1905, "status": "In Auction"},
    {"domain": "blondegirl.com", "age": 23, "bidders": 11, "min_bid": 84, "status": "In Auction"},
    {"domain": "norwegian.org", "age": 27, "bidders": 11, "min_bid": 69, "status": "Available Soon"},
    {"domain": "davora.com", "age": 26, "bidders": 10, "min_bid": 69, "status": "Available Soon"},
    {"domain": "iyds.com", "age": 21, "bidders": 9, "min_bid": 180, "status": "In Auction"},
    {"domain": "seriouswriter.com", "age": 11, "bidders": 9, "min_bid": 350, "status": "In Auction"},
    {"domain": "bugk.com", "age": 21, "bidders": 8, "min_bid": 69, "status": "Available Soon"},
    {"domain": "pilotstack.com", "age": 9, "bidders": 6, "min_bid": 83, "status": "In Auction"},
    {"domain": "cleandigital.com", "age": 21, "bidders": 5, "min_bid": 69, "status": "Available Soon"},
    {"domain": "ejsd.com", "age": 21, "bidders": 5, "min_bid": 69, "status": "Available Soon"},
    {"domain": "shamco.com", "age": 17, "bidders": 5, "min_bid": 82, "status": "In Auction"},
    {"domain": "arkaconsulting.com", "age": 20, "bidders": 5, "min_bid": 71, "status": "In Auction"},
    {"domain": "yugra.com", "age": 21, "bidders": 5, "min_bid": 81, "status": "In Auction"},
    {"domain": "ewmu.com", "age": 21, "bidders": 4, "min_bid": 69, "status": "Available Soon"},
]


def api_post(url, payload_obj):
    """POST to DataForSEO API. Returns parsed JSON or error dict."""
    assert isinstance(url, str) and url.startswith("https://"), "Invalid URL"
    assert isinstance(payload_obj, list) and len(payload_obj) <= 10, "Payload must be list, max 10 items"

    payload = json.dumps(payload_obj).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                assert isinstance(result, dict), "API returned non-dict"
                return result
        except urllib.error.HTTPError as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
                continue
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"error": f"URL Error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Max retries exceeded"}


def classify_domain(domain):
    """Gate 1: Classify domain as generic, brand, or acronym."""
    assert isinstance(domain, str) and len(domain) > 0, "Empty domain"

    name = domain.split(".")[0].lower()
    tld = domain.split(".")[-1]

    # Acronym detection: all consonants or <=4 chars with no vowels pattern
    if len(name) <= 4 and not any(c in name for c in "aeiou"):
        return "acronym"
    if len(name) <= 4 and name.isalpha():
        return "short-brandable"

    # Known brand patterns
    brand_signals = ["consulting", "partners", "pay", "stack", "digital"]
    for signal in brand_signals:
        if signal in name:
            return "brand-compound"

    # Generic dictionary words
    generic_words = [
        "smart", "research", "temp", "staffing", "temporary", "quality",
        "repair", "wash", "tech", "blonde", "girl", "norwegian", "serious",
        "writer", "clean", "pilot", "biz", "partners",
    ]
    word_count = sum(1 for w in generic_words if w in name)
    if word_count >= 1:
        return "generic"

    return "brandable"


def gate2_etv(domain):
    """Gate 2: DataForSEO ETV check. Returns metrics dict."""
    assert isinstance(domain, str), "Domain must be string"

    result = api_post(ETV_URL, [{"target": domain, "language_code": "en", "location_code": 2840}])

    if "error" in result:
        return {"domain": domain, "etv": 0, "keywords": 0, "error": result["error"]}

    tasks = result.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        return {"domain": domain, "etv": 0, "keywords": 0}

    items = tasks[0].get("result", [{}])[0].get("items", [])
    if not items or items[0] is None:
        return {"domain": domain, "etv": 0, "keywords": 0}

    organic = items[0].get("metrics", {}).get("organic", {})
    etv = organic.get("etv", 0) or 0
    kw = organic.get("count", 0) or 0
    top10 = (organic.get("pos_1", 0) or 0) + (organic.get("pos_2_3", 0) or 0) + (organic.get("pos_4_10", 0) or 0)

    return {"domain": domain, "etv": round(etv, 2), "keywords": kw, "top10": top10}


def gate3_serp(keyword):
    """Gate 3: Live SERP check for a keyword. Returns top 10 domains."""
    assert isinstance(keyword, str) and len(keyword) > 0, "Empty keyword"

    result = api_post(SERP_URL, [{"keyword": keyword, "location_code": 2840, "language_code": "en", "depth": 10}])

    if "error" in result:
        return {"keyword": keyword, "error": result["error"], "results": []}

    tasks = result.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        return {"keyword": keyword, "error": "bad status", "results": []}

    items_list = tasks[0].get("result", [{}])[0].get("items", [])
    serp_results = []
    for i, item in enumerate(items_list[:20]):
        if item.get("type") == "organic":
            serp_results.append({
                "position": item.get("rank_absolute", 0),
                "domain": item.get("domain", ""),
                "title": item.get("title", "")[:80],
            })
    return {"keyword": keyword, "results": serp_results}


def gate4_keywords(domain):
    """Gate 4: Get ranked keywords for domain. Returns keyword list."""
    assert isinstance(domain, str), "Domain must be string"

    result = api_post(KEYWORDS_URL, [{"target": domain, "language_code": "en", "location_code": 2840, "limit": 20}])

    if "error" in result:
        return {"domain": domain, "error": result["error"], "keywords": []}

    tasks = result.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        return {"domain": domain, "keywords": []}

    items = tasks[0].get("result", [{}])[0].get("items", [])
    keywords = []
    for item in items[:20]:
        kw_data = item.get("keyword_data", {})
        kw_info = kw_data.get("keyword_info", {})
        serp = item.get("ranked_serp_element", {}).get("serp_item", {})
        keyword = kw_data.get("keyword", "")
        vol = kw_info.get("search_volume", 0) or 0
        cpc = kw_info.get("cpc", 0) or 0
        pos = serp.get("rank_absolute", 0) or 0
        etv = serp.get("etv", 0) or 0

        # Brand check
        name = domain.split(".")[0].lower()
        is_brand = name in keyword.replace(" ", "").lower()

        keywords.append({
            "keyword": keyword, "volume": vol, "cpc": cpc,
            "position": pos, "etv": round(etv, 2), "is_brand": is_brand,
        })

    return {"domain": domain, "keywords": keywords}


def gate5_dns(domain):
    """Gate 5: DNS resolution check. Returns status."""
    assert isinstance(domain, str), "Domain must be string"

    try:
        result = subprocess.run(
            ["dig", "+short", domain, "A"],
            capture_output=True, text=True, timeout=5
        )
        a_record = result.stdout.strip()
        if a_record:
            return {"domain": domain, "resolves": True, "ip": a_record.split("\n")[0]}
        return {"domain": domain, "resolves": False, "ip": None}
    except Exception as e:
        return {"domain": domain, "resolves": False, "ip": None, "error": str(e)}


def generate_report(pipeline_results):
    """Generate comprehensive markdown report."""
    assert isinstance(pipeline_results, list), "Results must be list"

    lines = []
    lines.append("# Domain Hunter REVENANT — Sprint 18 Last Chance Pipeline Report")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')} | **Sprint:** 18 | **Source:** SnapNames Last Chance (24h)")
    lines.append(f"**Domains Analyzed:** {len(pipeline_results)} | **Pipeline:** 5-Gate Verification")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Separate by verdict
    buys = [r for r in pipeline_results if r.get("verdict") == "BUY"]
    investigates = [r for r in pipeline_results if r.get("verdict") == "INVESTIGATE"]
    skips = [r for r in pipeline_results if r.get("verdict") == "SKIP"]

    lines.append("## EXECUTIVE VERDICT")
    lines.append("")
    lines.append(f"- **BUY:** {len(buys)} domains")
    lines.append(f"- **INVESTIGATE:** {len(investigates)} domains")
    lines.append(f"- **SKIP:** {len(skips)} domains")
    lines.append("")

    if buys:
        lines.append("---")
        lines.append("")
        lines.append("## BUY — Verified Traffic, Generic Keywords")
        lines.append("")
        lines.append("| Domain | ETV/mo | Keywords | Top 10 | DNS | Bidders | Min Bid | Classification |")
        lines.append("|--------|--------|----------|--------|-----|---------|---------|---------------|")
        for r in sorted(buys, key=lambda x: x.get("etv", 0), reverse=True):
            dns = "LIVE" if r.get("dns_resolves") else "DEAD"
            lines.append(f"| **{r['domain']}** | **${r.get('etv', 0):,.0f}** | {r.get('keywords', 0)} | {r.get('top10', 0)} | {dns} | {r.get('bidders', 0)} | ${r.get('min_bid', 0):,} | {r.get('classification', '')} |")
        lines.append("")

        for r in buys:
            lines.append(f"### {r['domain']}")
            lines.append("")
            if r.get("ranked_keywords"):
                lines.append("**Top Keywords:**")
                lines.append("")
                lines.append("| Pos | Keyword | Volume | CPC | ETV | Brand? |")
                lines.append("|-----|---------|--------|-----|-----|--------|")
                for kw in r["ranked_keywords"][:10]:
                    tag = "BRAND" if kw.get("is_brand") else "GENERIC"
                    lines.append(f"| #{kw.get('position', 0)} | {kw.get('keyword', '')} | {kw.get('volume', 0):,}/mo | ${kw.get('cpc', 0):.2f} | ${kw.get('etv', 0):,.2f} | {tag} |")
                lines.append("")
            if r.get("serp_verified"):
                lines.append(f"**Live SERP:** CONFIRMED at position #{r.get('serp_position', '?')}")
            elif r.get("serp_checked"):
                lines.append(f"**Live SERP:** NOT FOUND in top 20 — ETV is PHANTOM")
            lines.append("")

    if investigates:
        lines.append("---")
        lines.append("")
        lines.append("## INVESTIGATE — Potential Value, Needs Manual Review")
        lines.append("")
        lines.append("| Domain | ETV/mo | Keywords | DNS | Bidders | Min Bid | Notes |")
        lines.append("|--------|--------|----------|-----|---------|---------|-------|")
        for r in sorted(investigates, key=lambda x: x.get("etv", 0), reverse=True):
            dns = "LIVE" if r.get("dns_resolves") else "DEAD"
            notes = r.get("notes", "")
            lines.append(f"| {r['domain']} | ${r.get('etv', 0):,.0f} | {r.get('keywords', 0)} | {dns} | {r.get('bidders', 0)} | ${r.get('min_bid', 0):,} | {notes} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## SKIP — No Verified Traffic Value")
    lines.append("")
    lines.append("| Domain | ETV/mo | Classification | DNS | Bidders | Min Bid | Skip Reason |")
    lines.append("|--------|--------|---------------|-----|---------|---------|-------------|")
    for r in sorted(skips, key=lambda x: x.get("bidders", 0), reverse=True):
        dns = "LIVE" if r.get("dns_resolves") else "DEAD"
        lines.append(f"| {r['domain']} | ${r.get('etv', 0):,.0f} | {r.get('classification', '')} | {dns} | {r.get('bidders', 0)} | ${r.get('min_bid', 0):,} | {r.get('skip_reason', '')} |")
    lines.append("")

    # Cost summary
    lines.append("---")
    lines.append("")
    lines.append("## PIPELINE COST")
    lines.append("")
    total_api = sum(1 for r in pipeline_results if r.get("etv_checked"))
    serp_checks = sum(1 for r in pipeline_results if r.get("serp_checked"))
    kw_checks = sum(1 for r in pipeline_results if r.get("ranked_keywords"))
    total_cost = (total_api * 0.01) + (serp_checks * 0.01) + (kw_checks * 0.01)
    lines.append(f"| Gate | Queries | Cost |")
    lines.append(f"|------|---------|------|")
    lines.append(f"| Gate 1: Classification | {len(pipeline_results)} | $0.00 (logic) |")
    lines.append(f"| Gate 2: ETV Scan | {total_api} | ${total_api * 0.01:.2f} |")
    lines.append(f"| Gate 3: Live SERP | {serp_checks} | ${serp_checks * 0.01:.2f} |")
    lines.append(f"| Gate 4: Keywords | {kw_checks} | ${kw_checks * 0.01:.2f} |")
    lines.append(f"| Gate 5: DNS | {len(pipeline_results)} | $0.00 (free) |")
    lines.append(f"| **Total** | | **${total_cost:.2f}** |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by Domain Hunter REVENANT Sprint 18 — 5-Gate Pipeline*")
    lines.append("")

    report = "\n".join(lines)
    assert len(report) > 100, "Report too short — generation failed"
    return report


def main():
    print("=" * 70)
    print("SPRINT 18 — 5-GATE DOMAIN VERIFICATION PIPELINE")
    print(f"SnapNames Last Chance | {len(DOMAINS)} domains | {datetime.now()}")
    print("=" * 70)
    print()

    results = []
    api_calls = 0

    # === GATE 1: Classification ===
    print("[GATE 1] Classifying domains (generic vs brand)...")
    for d in DOMAINS:
        d["classification"] = classify_domain(d["domain"])
        print(f"  {d['domain']:30s} → {d['classification']}")
    print()

    # === GATE 5: DNS (run early, it's free) ===
    print("[GATE 5] DNS resolution checks...")
    dns_results = {}
    for d in DOMAINS:
        dns = gate5_dns(d["domain"])
        dns_results[d["domain"]] = dns
        status = f"LIVE ({dns['ip']})" if dns["resolves"] else "DEAD"
        print(f"  {d['domain']:30s} → {status}")
    print()

    # === GATE 2: ETV scan on ALL domains ===
    print("[GATE 2] DataForSEO ETV scan...")
    etv_results = {}
    for i, d in enumerate(DOMAINS):
        if api_calls >= MAX_API_CALLS:
            print("  *** API call limit reached ***")
            break

        etv = gate2_etv(d["domain"])
        etv_results[d["domain"]] = etv
        api_calls += 1

        etv_val = etv.get("etv", 0)
        kw = etv.get("keywords", 0)
        if etv_val >= 1000:
            print(f"  *** WHALE *** {d['domain']:30s} ETV=${etv_val:,.0f} | {kw} kw")
        elif etv_val >= 100:
            print(f"  ** STRONG ** {d['domain']:30s} ETV=${etv_val:,.0f} | {kw} kw")
        elif etv_val > 0:
            print(f"  + {d['domain']:30s} ETV=${etv_val:,.0f} | {kw} kw")
        else:
            print(f"    {d['domain']:30s} ETV=$0")

        time.sleep(DELAY)
    print()

    # === GATE 3 & 4: Live SERP + Keywords on ETV > $100 ===
    etv_threshold = 100
    gate3_targets = [d for d in DOMAINS if etv_results.get(d["domain"], {}).get("etv", 0) >= etv_threshold]

    print(f"[GATE 3+4] Live SERP + Keywords on {len(gate3_targets)} domains with ETV >= ${etv_threshold}...")

    serp_data = {}
    keyword_data = {}

    for d in gate3_targets:
        domain = d["domain"]
        etv_info = etv_results.get(domain, {})

        # Gate 4: Get keywords first to know what to SERP-check
        if api_calls < MAX_API_CALLS:
            kw_result = gate4_keywords(domain)
            keyword_data[domain] = kw_result
            api_calls += 1
            time.sleep(DELAY)

            # Find top keyword by ETV
            kws = kw_result.get("keywords", [])
            if kws:
                top_kw = max(kws, key=lambda x: x.get("etv", 0))
                print(f"  {domain}: top keyword = \"{top_kw['keyword']}\" (vol:{top_kw['volume']}, pos:#{top_kw['position']}, ETV:${top_kw['etv']:,.0f})")

                # Gate 3: Live SERP check on top keyword
                if api_calls < MAX_API_CALLS and top_kw.get("etv", 0) > 10:
                    serp = gate3_serp(top_kw["keyword"])
                    api_calls += 1
                    time.sleep(DELAY)

                    # Check if domain appears
                    found = False
                    found_pos = 0
                    for sr in serp.get("results", []):
                        if domain in sr.get("domain", ""):
                            found = True
                            found_pos = sr.get("position", 0)
                            break

                    serp_data[domain] = {
                        "keyword": top_kw["keyword"],
                        "verified": found,
                        "position": found_pos,
                        "serp_results": serp.get("results", [])[:5],
                    }

                    if found:
                        print(f"    SERP CONFIRMED at #{found_pos}")
                    else:
                        top3 = [sr["domain"] for sr in serp.get("results", [])[:3]]
                        print(f"    SERP FAILED — top 3: {', '.join(top3)}")
    print()

    # === COMPILE RESULTS ===
    print("[COMPILE] Building results...")
    for d in DOMAINS:
        domain = d["domain"]
        etv_info = etv_results.get(domain, {})
        dns_info = dns_results.get(domain, {})
        kw_info = keyword_data.get(domain, {})
        serp_info = serp_data.get(domain, {})

        etv_val = etv_info.get("etv", 0)
        kw_count = etv_info.get("keywords", 0)
        top10 = etv_info.get("top10", 0)
        resolves = dns_info.get("resolves", False)

        entry = {
            "domain": domain,
            "age": d["age"],
            "bidders": d["bidders"],
            "min_bid": d["min_bid"],
            "auction_status": d["status"],
            "classification": d["classification"],
            "etv": etv_val,
            "keywords": kw_count,
            "top10": top10,
            "dns_resolves": resolves,
            "dns_ip": dns_info.get("ip"),
            "etv_checked": True,
        }

        # Add keyword data if available
        if kw_info.get("keywords"):
            entry["ranked_keywords"] = kw_info["keywords"]
            brand_etv = sum(k["etv"] for k in kw_info["keywords"] if k.get("is_brand"))
            total_kw_etv = sum(k["etv"] for k in kw_info["keywords"])
            entry["brand_pct"] = round((brand_etv / total_kw_etv * 100) if total_kw_etv > 0 else 0, 1)

        # Add SERP data if available
        if serp_info:
            entry["serp_checked"] = True
            entry["serp_verified"] = serp_info.get("verified", False)
            entry["serp_position"] = serp_info.get("position", 0)
            entry["serp_keyword"] = serp_info.get("keyword", "")

        # === VERDICT LOGIC ===
        if etv_val == 0:
            entry["verdict"] = "SKIP"
            entry["skip_reason"] = "$0 ETV — name bet only"
        elif etv_val < 100:
            entry["verdict"] = "SKIP"
            entry["skip_reason"] = f"ETV ${etv_val:.0f} too low for auction price"
        elif not resolves:
            entry["verdict"] = "INVESTIGATE"
            entry["notes"] = f"ETV ${etv_val:.0f} but DNS DEAD — likely phantom"
        elif serp_info and not serp_info.get("verified", False):
            entry["verdict"] = "SKIP"
            entry["skip_reason"] = f"ETV ${etv_val:.0f} but FAILED live SERP — phantom rankings"
        elif entry.get("brand_pct", 0) > 60:
            entry["verdict"] = "SKIP"
            entry["skip_reason"] = f"ETV ${etv_val:.0f} but {entry['brand_pct']:.0f}% brand traffic"
        elif etv_val >= 100 and serp_info.get("verified"):
            entry["verdict"] = "BUY"
        elif etv_val >= 100:
            entry["verdict"] = "INVESTIGATE"
            entry["notes"] = f"ETV ${etv_val:.0f} — needs SERP verification"
        else:
            entry["verdict"] = "SKIP"
            entry["skip_reason"] = "No clear value signal"

        results.append(entry)

    # === SAVE JSON ===
    with open(JSON_FILE, "w") as f:
        json.dump({"sprint": 18, "date": datetime.now().isoformat(), "results": results}, f, indent=2)
    print(f"  JSON saved: {JSON_FILE}")

    # === GENERATE REPORT ===
    print("[REPORT] Generating markdown report...")
    report = generate_report(results)
    with open(REPORT_FILE, "w") as f:
        f.write(report)
    print(f"  Report saved: {REPORT_FILE}")

    # === FINAL SUMMARY ===
    print()
    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    buys = [r for r in results if r["verdict"] == "BUY"]
    invs = [r for r in results if r["verdict"] == "INVESTIGATE"]
    skips = [r for r in results if r["verdict"] == "SKIP"]
    print(f"BUY: {len(buys)} | INVESTIGATE: {len(invs)} | SKIP: {len(skips)}")
    print(f"API calls: {api_calls} | Est. cost: ${api_calls * 0.01:.2f}")

    for r in buys:
        print(f"  BUY: {r['domain']} — ETV=${r['etv']:,.0f}, {r['keywords']} kw, SERP verified")
    for r in invs:
        print(f"  INVESTIGATE: {r['domain']} — ETV=${r['etv']:,.0f}, {r.get('notes', '')}")

    print("\nDONE.")


if __name__ == "__main__":
    sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)
    main()

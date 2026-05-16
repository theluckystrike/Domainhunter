#!/usr/bin/env python3
"""
Sprint 16 — Dead Startup WHOIS Sweep
Agent 8: REVENANT Project
Checks all 205 dead startup domains from Sprint 13+14 data via WHOIS.
"""

import json
import subprocess
import time
import re
import sys
from datetime import datetime, timedelta

INPUT_FILE = "/Users/mike/Desktop/domainhunter/data/sprint14_startup_domains.json"
OUTPUT_FILE = "/Users/mike/Desktop/domainhunter/data/sprint16_startup_whois.json"

# High-priority domains to check first (high funding, most likely valuable)
PRIORITY_DOMAINS = [
    "sunpower.com", "getaround.com", "boweryfarming.com", "invisionapp.com",
    "bird.co", "convoy.com", "proterra.com", "lilium.com", "northvolt.com",
    "wework.com", "byjus.com", "theranos.com", "katerra.com", "olive.com",
    "arrival.com", "fisker.com", "canoo.com", "quibi.com", "jawbone.com",
    "solyndra.com", "veev.com", "view.com", "builder.ai", "humane.com",
    "lordstownmotors.com", "nikolamotor.com"
]

# Known parking/expired nameservers
PARKING_NS = [
    "parkingcrew", "sedoparking", "bodis", "hugedomains", "dan.com",
    "afternic", "uniregistry", "pendingrenew", "expired", "registrar-servers",
    "domaincontrol", "above.com", "undeveloped", "porkbun.com"
]

def parse_funding(funding_str):
    """Parse funding string to numeric value for bid recommendations."""
    if not funding_str or funding_str == "N/A":
        return 0
    s = funding_str.upper().replace("$", "").replace("+", "").replace(",", "")
    s = s.split("(")[0].strip().split(" ")[0].strip()
    try:
        if "B" in s:
            return float(s.replace("B", "")) * 1_000_000_000
        elif "M" in s:
            return float(s.replace("M", "")) * 1_000_000
        elif "K" in s:
            return float(s.replace("K", "")) * 1_000
        else:
            return float(s)
    except:
        return 0

def run_whois(domain):
    """Run whois command and return raw output."""
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {str(e)}"

def parse_whois(raw):
    """Parse WHOIS output to extract key fields."""
    info = {
        "registrar": None,
        "expiry": None,
        "creation_date": None,
        "status": [],
        "nameservers": [],
        "raw_snippet": None
    }

    if not raw or raw == "TIMEOUT" or raw.startswith("ERROR"):
        return info

    lines = raw.split("\n")

    # Track whether we're past the IANA TLD section into the actual registrar data
    past_iana = False
    iana_ns = []
    registrar_ns = []

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Detect transition past IANA section (look for "# whois." or "Domain Name:")
        if line_stripped.startswith("# whois.") or (line_lower.startswith("domain name:") and not past_iana):
            past_iana = True

        # Registrar - only from the registrar section
        if past_iana and ("registrar:" in line_lower or "registrar name:" in line_lower) and not info["registrar"]:
            # Skip "Registrar WHOIS Server" and similar
            key_part = line_stripped.split(":")[0].strip().lower()
            if key_part in ["registrar", "registrar name"]:
                val = line_stripped.split(":", 1)[-1].strip()
                if val and len(val) > 1:
                    info["registrar"] = val

        # Expiry date - multiple formats
        if any(k in line_lower for k in [
            "expir", "registry expiry", "registrar registration expiration",
            "paid-till", "renewal date", "expire"
        ]):
            # Try to extract date
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                info["expiry"] = date_match.group(1)
            else:
                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                if date_match:
                    parts = date_match.group(1).split("/")
                    info["expiry"] = f"{parts[2]}-{parts[0]}-{parts[1]}"
                else:
                    date_match = re.search(r'(\d{2}-\w{3}-\d{4})', line)
                    if date_match:
                        try:
                            dt = datetime.strptime(date_match.group(1), "%d-%b-%Y")
                            info["expiry"] = dt.strftime("%Y-%m-%d")
                        except:
                            pass

        # Creation date
        if any(k in line_lower for k in ["creation date", "created on", "registered on"]):
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                info["creation_date"] = date_match.group(1)

        # Status - prefer Domain Status from registrar section
        if "domain status:" in line_lower or ("status:" in line_lower and past_iana):
            val = line_stripped.split(":", 1)[-1].strip()
            # May contain URL after status
            status_val = val.split(" ")[0].strip() if val else ""
            if status_val and status_val not in info["status"]:
                info["status"].append(status_val)

        # Nameservers - distinguish IANA nservers from actual domain NS
        if line_lower.startswith("nserver:") and not past_iana:
            # IANA TLD nservers, skip these
            pass
        elif line_lower.startswith("name server:") or line_lower.startswith("nameserver:"):
            ns = line_stripped.split(":", 1)[-1].strip().lower()
            if ns and ns not in registrar_ns:
                registrar_ns.append(ns)
        elif line_lower.startswith("nserver:") and past_iana:
            ns = line_stripped.split(":", 1)[-1].strip().lower().split(" ")[0]
            if ns and ns not in registrar_ns:
                registrar_ns.append(ns)

    info["nameservers"] = registrar_ns

    # Take a snippet of the raw output for debugging
    info["raw_snippet"] = raw[:500] if raw else None

    return info

def classify_domain(info, domain):
    """Classify domain based on WHOIS data."""
    status_str = " ".join(info["status"]).lower()
    ns_str = " ".join(info["nameservers"]).lower()

    signals = []

    # DROPPING signals
    dropping_signals = [
        "pendingdelete", "redemptionperiod", "pendingrelease",
        "clientrenewprohibited"
    ]
    for sig in dropping_signals:
        if sig in status_str:
            signals.append(f"STATUS:{sig}")

    if signals:
        return "DROPPING", signals

    # DISTRESSED signals
    distressed_signals = []

    # Check for holds
    if "clienthold" in status_str:
        distressed_signals.append("STATUS:clientHold")
    if "serverhold" in status_str:
        distressed_signals.append("STATUS:serverHold")
    if "inactive" in status_str:
        distressed_signals.append("STATUS:inactive")

    # Check expiry within 6 months
    if info["expiry"]:
        try:
            exp_date = datetime.strptime(info["expiry"], "%Y-%m-%d")
            now = datetime.now()
            months_left = (exp_date - now).days / 30.0
            if months_left < 0:
                distressed_signals.append(f"EXPIRED:{info['expiry']}")
            elif months_left < 6:
                distressed_signals.append(f"EXPIRING_SOON:{info['expiry']}({months_left:.1f}mo)")
        except:
            pass

    # Check for parking nameservers
    for pns in PARKING_NS:
        if pns in ns_str:
            distressed_signals.append(f"PARKING_NS:{pns}")

    # No nameservers at all
    if not info["nameservers"]:
        distressed_signals.append("NO_NAMESERVERS")

    if distressed_signals:
        return "DISTRESSED", distressed_signals

    # If we got valid WHOIS data, it's ACTIVE
    if info["registrar"] or info["expiry"] or info["status"]:
        return "ACTIVE", ["normal_registration"]

    return "ERROR", ["no_whois_data_parsed"]

def recommend_action(domain, funding_num, signals):
    """Generate backorder recommendation for DROPPING domains."""
    # Calculate max bid based on funding and brand value
    if funding_num >= 1_000_000_000:  # $1B+
        max_bid = min(funding_num * 0.001, 50000)  # Up to $50K
        tier = "WHALE"
    elif funding_num >= 500_000_000:
        max_bid = min(funding_num * 0.002, 25000)
        tier = "HIGH"
    elif funding_num >= 100_000_000:
        max_bid = min(funding_num * 0.005, 10000)
        tier = "MEDIUM"
    elif funding_num >= 50_000_000:
        max_bid = 5000
        tier = "LOW-MEDIUM"
    else:
        max_bid = 2000
        tier = "LOW"

    return {
        "tier": tier,
        "max_bid": int(max_bid),
        "platforms": [
            "DropCatch.com",
            "NameJet.com",
            "SnapNames.com",
            "GoDaddy Closeouts",
            "Dynadot Backorder"
        ],
        "strategy": f"Place backorders on ALL platforms. {tier} tier domain from ${funding_num/1e6:.0f}M funded startup. Watch auction closely.",
        "urgency": "IMMEDIATE" if "pendingdelete" in " ".join(signals).lower() else "HIGH"
    }

def main():
    # Load domains
    with open(INPUT_FILE) as f:
        data = json.load(f)

    domains = data["domains"]
    print(f"Loaded {len(domains)} domains from Sprint 14 data")

    # Build lookup
    domain_info = {}
    for d in domains:
        domain_info[d["domain"]] = d

    # Sort: priority domains first, then by funding descending
    all_domain_names = [d["domain"] for d in domains]
    priority_set = set(PRIORITY_DOMAINS)

    sorted_domains = []
    # Priority first
    for d in PRIORITY_DOMAINS:
        if d in domain_info:
            sorted_domains.append(d)
    # Then rest by funding
    rest = [d for d in all_domain_names if d not in priority_set]
    rest.sort(key=lambda x: parse_funding(domain_info[x].get("funding", "0")), reverse=True)
    sorted_domains.extend(rest)

    # Results
    results = {
        "sprint": 16,
        "agent": "STARTUP WHOIS SWEEP",
        "scan_date": "2026-05-08",
        "total_checked": 0,
        "summary": {},
        "dropping": [],
        "distressed": [],
        "active": [],
        "error": []
    }

    total = len(sorted_domains)
    for i, domain in enumerate(sorted_domains):
        dinfo = domain_info[domain]
        funding = dinfo.get("funding", "N/A")
        company = dinfo.get("company", "Unknown")
        sector = dinfo.get("sector", "Unknown")
        funding_num = parse_funding(funding)

        print(f"[{i+1}/{total}] WHOIS: {domain} ({company}, {funding})...", end=" ", flush=True)

        raw = run_whois(domain)
        parsed = parse_whois(raw)
        classification, signals = classify_domain(parsed, domain)

        print(f"=> {classification} | {', '.join(signals[:3])}")

        entry = {
            "domain": domain,
            "company": company,
            "funding": funding,
            "funding_numeric": funding_num,
            "sector": sector,
            "shutdown_year": dinfo.get("shutdown_year"),
            "registrar": parsed["registrar"],
            "expiry": parsed["expiry"],
            "creation_date": parsed["creation_date"],
            "status": parsed["status"],
            "nameservers": parsed["nameservers"],
            "signal": signals,
            "classification": classification
        }

        # For DROPPING: add recommendation
        if classification == "DROPPING":
            entry["recommendation"] = recommend_action(domain, funding_num, signals)

        # Append to appropriate list
        if classification == "DROPPING":
            results["dropping"].append(entry)
        elif classification == "DISTRESSED":
            results["distressed"].append(entry)
        elif classification == "ACTIVE":
            results["active"].append(entry)
        else:
            results["error"].append(entry)

        results["total_checked"] = i + 1

        # Rate limit: 1 per second
        if i < total - 1:
            time.sleep(1.0)

    # Summary
    results["summary"] = {
        "dropping": len(results["dropping"]),
        "distressed": len(results["distressed"]),
        "active": len(results["active"]),
        "error": len(results["error"]),
        "high_value_dropping": [d["domain"] for d in results["dropping"] if d["funding_numeric"] >= 100_000_000],
        "high_value_distressed": [d["domain"] for d in results["distressed"] if d["funding_numeric"] >= 100_000_000]
    }

    # Remove raw snippets to keep output clean
    for category in ["dropping", "distressed", "active", "error"]:
        for entry in results[category]:
            entry.pop("raw_snippet", None)

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"WHOIS SWEEP COMPLETE")
    print(f"{'='*60}")
    print(f"Total checked: {results['total_checked']}")
    print(f"DROPPING:   {len(results['dropping'])}")
    print(f"DISTRESSED: {len(results['distressed'])}")
    print(f"ACTIVE:     {len(results['active'])}")
    print(f"ERROR:      {len(results['error'])}")
    if results["dropping"]:
        print(f"\n*** DROPPING DOMAINS ***")
        for d in results["dropping"]:
            print(f"  {d['domain']} ({d['funding']}) - {', '.join(d['signal'])}")
    if results["summary"]["high_value_distressed"]:
        print(f"\n*** HIGH-VALUE DISTRESSED ***")
        for domain in results["summary"]["high_value_distressed"]:
            matching = [d for d in results["distressed"] if d["domain"] == domain]
            if matching:
                d = matching[0]
                print(f"  {d['domain']} ({d['funding']}) - {', '.join(d['signal'])}")

    print(f"\nResults saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
    main()

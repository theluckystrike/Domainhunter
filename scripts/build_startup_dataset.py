#!/usr/bin/env python3
"""
Build dead/failed startup dataset from multiple sources.
Sources:
  1. Crunchbase (via GitHub mirror) - 54K companies, ~2600 closed
  2. YC API (yc-oss) - 5900+ companies, ~1000 inactive
  3. Existing curated entries (kaggle_startups.csv)

Output: data/kaggle_startups.csv
Schema: company_name,domain,funding_usd,status,sector,shutdown_date,notes

NASA P10: functions <60 lines, bounded loops, assertions.
"""

import csv
import json
import os
import re
import sys
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "kaggle_startups.csv")

CRUNCHBASE_FILE = "/tmp/crunchbase_vc.csv"
YC_FILE = "/tmp/yc_all.json"

MAX_ROWS = 100000  # Bounded loop limit


def extract_domain(url):
    """Extract clean domain from URL. Returns None if invalid."""
    assert isinstance(url, str), "url must be string"
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        # Basic validation
        if "." not in domain or len(domain) < 4:
            return None
        # Skip social media / generic domains
        skip = ("facebook.com", "twitter.com", "linkedin.com", "github.com",
                "angel.co", "crunchbase.com", "bloomberg.com", "google.com",
                "youtube.com", "medium.com", "wordpress.com", "blogspot.com",
                "tumblr.com", "wix.com", "squarespace.com", "weebly.com")
        if domain in skip or any(domain.endswith("." + s) for s in skip):
            return None
        return domain
    except Exception:
        return None


def parse_crunchbase_funding(raw):
    """Parse Crunchbase funding string like ' 17,50,000 ' to integer."""
    assert isinstance(raw, str), "raw must be string"
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    if not cleaned or cleaned == "-":
        return 0
    try:
        return int(cleaned)
    except ValueError:
        return 0


def format_funding(amount_usd):
    """Format integer funding to human-readable string like $1.2M."""
    assert isinstance(amount_usd, (int, float)), "amount must be numeric"
    if amount_usd <= 0:
        return ""
    if amount_usd >= 1_000_000_000:
        return f"${amount_usd / 1_000_000_000:.1f}B"
    if amount_usd >= 1_000_000:
        return f"${amount_usd / 1_000_000:.1f}M"
    if amount_usd >= 1_000:
        return f"${amount_usd / 1_000:.0f}K"
    return f"${amount_usd}"


def clean_market(raw):
    """Clean Crunchbase market/category field."""
    assert isinstance(raw, str), "raw must be string"
    cleaned = raw.strip().lower()
    # Map common categories to simpler sector names
    sector_map = {
        "software": "saas", "enterprise software": "saas",
        "e-commerce": "ecommerce", "mobile": "mobile",
        "advertising": "adtech", "analytics": "analytics",
        "social media": "social", "health care": "healthtech",
        "health and wellness": "healthtech", "finance": "fintech",
        "financial services": "fintech", "education": "edtech",
        "biotechnology": "biotech", "clean technology": "cleantech",
        "real estate": "proptech", "games": "gaming",
        "hardware": "hardware", "security": "security",
        "food and beverages": "food", "travel": "travel",
        "media": "media", "music": "music", "video": "media",
        "messaging": "messaging", "transportation": "logistics",
        "logistics": "logistics", "semiconductors": "hardware",
        "consulting": "services", "internet": "internet",
        "news": "media", "fashion": "ecommerce",
    }
    return sector_map.get(cleaned, cleaned[:30] if cleaned else "other")


def load_crunchbase():
    """Load closed companies from Crunchbase CSV. Returns list of dicts."""
    if not os.path.exists(CRUNCHBASE_FILE):
        print(f"WARN: {CRUNCHBASE_FILE} not found, skipping Crunchbase")
        return []

    results = []
    seen_domains = set()

    with open(CRUNCHBASE_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        row_count = 0
        for row in reader:
            row_count += 1
            assert row_count < MAX_ROWS, "Exceeded max rows"

            status = row.get("status", "").strip()
            if status != "closed":
                continue

            url = row.get("homepage_url", "").strip()
            domain = extract_domain(url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            name = row.get("name", "").strip()
            if not name:
                continue

            funding_raw = row.get(" funding_total_usd ", "").strip()
            funding_int = parse_crunchbase_funding(funding_raw)
            funding_str = format_funding(funding_int)

            market = row.get(" market ", "").strip()
            sector = clean_market(market)

            # Use last_funding_at as approximate shutdown indicator
            last_funding = row.get("last_funding_at", "").strip()
            founded = row.get("founded_at", "").strip()

            note_parts = []
            if market:
                note_parts.append(f"Market: {market.strip()}")
            country = row.get("country_code", "").strip()
            if country:
                note_parts.append(country)
            note_parts.append("Source: Crunchbase")

            results.append({
                "company_name": name,
                "domain": domain,
                "funding_usd": funding_str,
                "funding_int": funding_int,  # For sorting
                "status": "closed",
                "sector": sector,
                "shutdown_date": "",
                "notes": "; ".join(note_parts),
            })

    print(f"Crunchbase: {len(results)} closed companies with domains")
    return results


def load_yc():
    """Load inactive companies from YC API JSON. Returns list of dicts."""
    if not os.path.exists(YC_FILE):
        print(f"WARN: {YC_FILE} not found, skipping YC")
        return []

    with open(YC_FILE, "r") as f:
        companies = json.load(f)
    assert isinstance(companies, list), "YC data must be a list"

    results = []
    seen_domains = set()

    for i, comp in enumerate(companies):
        assert i < MAX_ROWS, "Exceeded max rows"

        status = comp.get("status", "")
        if status != "Inactive":
            continue

        url = comp.get("website", "")
        if not url:
            continue
        domain = extract_domain(url)
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)

        name = comp.get("name", "").strip()
        if not name:
            continue

        # YC data doesn't have funding amounts directly
        industries = comp.get("industries", [])
        sector = industries[0].lower() if industries else "other"
        # Map YC industries to simpler names
        sector_simple = sector.replace(" and ", "/").replace(" ", "-")[:30]

        batch = comp.get("batch", "")
        one_liner = comp.get("one_liner", "")

        note_parts = []
        if one_liner:
            # Escape commas in notes
            one_liner_clean = one_liner.replace(",", ";").strip()[:100]
            note_parts.append(one_liner_clean)
        if batch:
            note_parts.append(f"YC {batch}")
        note_parts.append("Source: YC")

        results.append({
            "company_name": name,
            "domain": domain,
            "funding_usd": "",
            "funding_int": 0,
            "status": "inactive",
            "sector": sector_simple,
            "shutdown_date": "",
            "notes": "; ".join(note_parts),
        })

    print(f"YC: {len(results)} inactive companies with domains")
    return results


def load_existing():
    """Load existing curated entries from kaggle_startups.csv."""
    existing_file = OUTPUT_FILE
    if not os.path.exists(existing_file):
        return []

    results = []
    with open(existing_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("company_name", "").strip():
                continue
            results.append({
                "company_name": row.get("company_name", "").strip(),
                "domain": row.get("domain", "").strip(),
                "funding_usd": row.get("funding_usd", "").strip(),
                "funding_int": 0,  # Already formatted
                "status": row.get("status", "").strip(),
                "sector": row.get("sector", "").strip(),
                "shutdown_date": row.get("shutdown_date", "").strip(),
                "notes": row.get("notes", "").strip() + "; Source: curated",
            })

    print(f"Existing: {len(results)} curated entries")
    return results


def deduplicate(entries):
    """Deduplicate by domain, preferring entries with more data."""
    assert isinstance(entries, list), "entries must be list"
    by_domain = {}
    for entry in entries:
        domain = entry["domain"]
        if domain not in by_domain:
            by_domain[domain] = entry
        else:
            # Prefer entry with funding data
            existing = by_domain[domain]
            if not existing["funding_usd"] and entry["funding_usd"]:
                by_domain[domain] = entry
    result = list(by_domain.values())
    print(f"After dedup: {len(result)} unique domains")
    return result


def write_csv(entries):
    """Write entries to output CSV, sorted by funding (highest first)."""
    assert isinstance(entries, list), "entries must be list"
    assert len(entries) > 0, "No entries to write"

    # Sort: curated first, then by funding descending
    def sort_key(e):
        is_curated = 1 if "curated" in e.get("notes", "") else 0
        funding = e.get("funding_int", 0)
        return (-is_curated, -funding)

    entries.sort(key=sort_key)

    fieldnames = ["company_name", "domain", "funding_usd", "status",
                  "sector", "shutdown_date", "notes"]

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            row = {k: entry.get(k, "") for k in fieldnames}
            # Clean up notes - remove commas that could break CSV
            row["notes"] = row["notes"].replace('"', "'")
            writer.writerow(row)

    print(f"Wrote {len(entries)} entries to {OUTPUT_FILE}")


def print_stats(entries):
    """Print dataset quality statistics."""
    total = len(entries)
    with_funding = sum(1 for e in entries if e.get("funding_usd"))
    with_sector = sum(1 for e in entries if e.get("sector") and e["sector"] != "other")

    sources = {}
    for e in entries:
        notes = e.get("notes", "")
        if "curated" in notes:
            sources["curated"] = sources.get("curated", 0) + 1
        elif "Crunchbase" in notes:
            sources["Crunchbase"] = sources.get("Crunchbase", 0) + 1
        elif "YC" in notes:
            sources["YC"] = sources.get("YC", 0) + 1
        else:
            sources["unknown"] = sources.get("unknown", 0) + 1

    sectors = {}
    for e in entries:
        s = e.get("sector", "other")
        sectors[s] = sectors.get(s, 0) + 1

    print(f"\n{'='*60}")
    print(f"DATASET STATISTICS")
    print(f"{'='*60}")
    print(f"Total entries:     {total}")
    print(f"With funding data: {with_funding} ({100*with_funding//total}%)")
    print(f"With sector:       {with_sector} ({100*with_sector//total}%)")
    print(f"\nBy source:")
    for k, v in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"\nTop 15 sectors:")
    for k, v in sorted(sectors.items(), key=lambda x: -x[1])[:15]:
        print(f"  {k}: {v}")
    print(f"{'='*60}")


def main():
    """Main entry point."""
    assert os.path.isdir(DATA_DIR), f"Data dir not found: {DATA_DIR}"

    # Load from all sources
    existing = load_existing()
    crunchbase = load_crunchbase()
    yc = load_yc()

    # Merge: existing first, then Crunchbase, then YC
    all_entries = existing + crunchbase + yc
    print(f"\nTotal before dedup: {len(all_entries)}")

    # Deduplicate
    deduped = deduplicate(all_entries)

    # Write output
    write_csv(deduped)

    # Stats
    print_stats(deduped)

    return 0


if __name__ == "__main__":
    sys.exit(main())

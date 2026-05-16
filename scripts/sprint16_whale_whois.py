#!/usr/bin/env python3
"""
Sprint 16 - Agent 1: WHALE WHOIS BLITZ
WHOIS-check ALL 98 whale domains (ETV >= $1,000/mo) from Sprint 14's bulk scan.
Classifies each domain as DROPPING, DISTRESSED, ACTIVE, or ERROR.
"""

import json
import subprocess
import re
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Paths
INPUT_FILE = Path("/Users/mike/Desktop/domainhunter/data/sprint14_bulk_scan.json")
OUTPUT_FILE = Path("/Users/mike/Desktop/domainhunter/data/sprint16_whale_whois.json")

# Parking/dead nameservers (common indicators of distressed domains)
PARKING_NS_PATTERNS = [
    r'parkingcrew', r'sedoparking', r'bodis', r'afternic', r'hugedomains',
    r'dan\.com', r'undeveloped', r'domaincontrol', r'parking',
    r'ns1\.suspended', r'ns2\.suspended', r'pendingrenew',
    r'registrar-servers\.com',  # Namecheap default (not always parking but worth noting)
]

# Status flags indicating dropping
DROPPING_STATUSES = [
    'pendingDelete',
    'redemptionPeriod',
    'clientRenewProhibited',
]

# Status flags indicating distressed (clientTransferProhibited is normal/standard, NOT distressed)
DISTRESSED_STATUSES = [
    'clientHold',
    'serverHold',
    'inactive',
]

def load_whale_domains():
    """Load whale domains from Sprint 14 bulk scan."""
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    whales = data['tiers']['whale']
    print(f"Loaded {len(whales)} whale domains from Sprint 14")
    return whales

def run_whois(domain, timeout=30):
    """Run whois command for a domain and return raw output."""
    try:
        result = subprocess.run(
            ['whois', domain],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        if not output.strip():
            return None, "Empty WHOIS response"
        return output, None
    except subprocess.TimeoutExpired:
        return None, "WHOIS timeout"
    except FileNotFoundError:
        return None, "whois command not found"
    except Exception as e:
        return None, str(e)

def parse_whois(raw_text, domain):
    """Parse WHOIS output to extract key fields.

    IMPORTANT: macOS whois returns a multi-section response:
    1. IANA header with TLD root nservers (gtld-servers.net) - IGNORE these
    2. Verisign/registry section with Domain Name, Registrar, etc.
    3. Registrar-specific section with more details

    We parse from the first "Domain Name:" line onward to skip TLD root data.
    For nameservers, we collect ALL after the Domain Name marker, then also
    look for a second set (registrar-specific) and prefer those if found.
    """
    result = {
        'registrar': None,
        'expiry': None,
        'creation_date': None,
        'updated_date': None,
        'status': [],
        'nameservers': [],
        'raw_status_lines': [],
    }

    if not raw_text:
        return result

    lines = raw_text.split('\n')

    # Find the first "Domain Name:" line to skip IANA header
    start_idx = 0
    for i, line in enumerate(lines):
        if re.match(r'^\s*Domain Name:\s*', line, re.IGNORECASE):
            start_idx = i
            break

    # Also track sections: some WHOIS outputs have two Domain Name blocks
    # (registry thin WHOIS + registrar thick WHOIS). Collect NS from each section.
    ns_sections = []  # list of lists
    current_ns_section = []

    for line in lines[start_idx:]:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Detect section boundary (new Domain Name block)
        if re.match(r'^\s*Domain Name:\s*', line_stripped, re.IGNORECASE):
            if current_ns_section:
                ns_sections.append(current_ns_section)
                current_ns_section = []

        # Registrar
        if result['registrar'] is None:
            if re.match(r'^registrar:\s*', line_stripped, re.IGNORECASE):
                result['registrar'] = re.sub(r'^registrar:\s*', '', line_stripped, flags=re.IGNORECASE).strip()
            elif re.match(r'^registrar name:\s*', line_stripped, re.IGNORECASE):
                result['registrar'] = re.sub(r'^registrar name:\s*', '', line_stripped, flags=re.IGNORECASE).strip()
            elif re.match(r'^sponsoring registrar:\s*', line_stripped, re.IGNORECASE):
                result['registrar'] = re.sub(r'^sponsoring registrar:\s*', '', line_stripped, flags=re.IGNORECASE).strip()

        # Expiry date - try multiple patterns (take the LAST match to prefer registrar section)
        expiry_patterns = [
            r'^(?:registry expiry date|registrar registration expiration date|expir(?:y|ation) date|expires on|expires|paid-till|expiry):\s*(.+)',
        ]
        for pat in expiry_patterns:
            m = re.match(pat, line_stripped, re.IGNORECASE)
            if m:
                result['expiry'] = m.group(1).strip()
                break

        # Creation date
        if result['creation_date'] is None:
            if re.match(r'^(?:creation date|created|created on|registration date):\s*', line_stripped, re.IGNORECASE):
                val = re.split(r':\s*', line_stripped, maxsplit=1)
                if len(val) > 1:
                    result['creation_date'] = val[1].strip()

        # Updated date
        if result['updated_date'] is None:
            if re.match(r'^(?:updated date|last updated|modified):\s*', line_stripped, re.IGNORECASE):
                val = re.split(r':\s*', line_stripped, maxsplit=1)
                if len(val) > 1:
                    result['updated_date'] = val[1].strip()

        # Status flags
        if re.match(r'^(?:domain )?status:\s*', line_stripped, re.IGNORECASE):
            status_val = re.sub(r'^(?:domain )?status:\s*', '', line_stripped, flags=re.IGNORECASE).strip()
            # Often has URL after the status, strip it
            status_clean = status_val.split(' ')[0] if status_val else status_val
            if status_clean:
                result['status'].append(status_clean)
                result['raw_status_lines'].append(status_val)

        # Nameservers (collect into current section)
        if re.match(r'^(?:name server|nserver|nameserver):\s*', line_stripped, re.IGNORECASE):
            ns_val = re.sub(r'^(?:name server|nserver|nameserver):\s*', '', line_stripped, flags=re.IGNORECASE).strip()
            if ns_val:
                # Extract just the hostname (first token), ignore IP addresses
                ns_host = ns_val.split()[0].lower().rstrip('.')
                if ns_host and not re.match(r'^\d+\.\d+\.\d+\.\d+$', ns_host):
                    current_ns_section.append(ns_host)

    # Finalize NS sections
    if current_ns_section:
        ns_sections.append(current_ns_section)

    # Use the LAST section's nameservers (registrar-specific, most detailed)
    # If there are multiple sections, the last one is typically from the registrar
    if ns_sections:
        result['nameservers'] = list(dict.fromkeys(ns_sections[-1]))

    # Deduplicate status
    result['status'] = list(dict.fromkeys(result['status']))

    return result

def parse_expiry_date(expiry_str):
    """Try to parse an expiry date string into a datetime object."""
    if not expiry_str:
        return None

    # Common date formats in WHOIS
    formats = [
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%d-%b-%Y',
        '%d %b %Y',
        '%Y/%m/%d',
        '%d/%m/%Y',
        '%Y.%m.%d',
        '%d.%m.%Y',
        '%B %d, %Y',
        '%d-%m-%Y',
        '%Y%m%d',
    ]

    # Clean up the string
    clean = expiry_str.strip().rstrip('.')
    # Remove timezone info like +0000 or UTC
    clean = re.sub(r'\s*\(.*?\)\s*$', '', clean)
    clean = re.sub(r'\s+UTC\s*$', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+GMT\s*$', '', clean, flags=re.IGNORECASE)

    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue

    # Try dateutil as fallback
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(clean)
    except:
        pass

    return None

def is_parking_ns(nameservers):
    """Check if nameservers match known parking/dead patterns."""
    ns_str = ' '.join(nameservers).lower()
    for pattern in PARKING_NS_PATTERNS:
        if re.search(pattern, ns_str, re.IGNORECASE):
            return True
    return False

def classify_domain(parsed, domain):
    """
    Classify a domain based on WHOIS data.
    Returns: (classification, signal, action)
    """
    statuses = [s.lower() for s in parsed['status']]
    status_str = ' '.join(statuses)

    # Check for DROPPING signals
    for drop_status in DROPPING_STATUSES:
        if drop_status.lower() in status_str:
            return 'dropping', f"Status: {drop_status}", "IMMEDIATE: Monitor for auction/drop"

    if 'pendingdelete' in status_str:
        return 'dropping', "Status: pendingDelete", "URGENT: Domain dropping imminently"

    if 'redemptionperiod' in status_str:
        return 'dropping', "Status: redemptionPeriod", "WATCH: Domain in redemption, may drop soon"

    # Check for DISTRESSED signals
    distressed_signals = []

    for dist_status in DISTRESSED_STATUSES:
        if dist_status.lower() in status_str:
            distressed_signals.append(f"Status: {dist_status}")

    # Check expiry within 6 months
    expiry_date = parse_expiry_date(parsed['expiry'])
    if expiry_date:
        now = datetime.now()
        # Handle timezone-aware datetimes
        if expiry_date.tzinfo:
            expiry_date = expiry_date.replace(tzinfo=None)

        months_until_expiry = (expiry_date - now).days / 30.0

        if months_until_expiry < 0:
            return 'dropping', f"EXPIRED: {parsed['expiry']}", "URGENT: Domain past expiry date"
        elif months_until_expiry < 6:
            distressed_signals.append(f"Expiring in {months_until_expiry:.1f} months ({parsed['expiry']})")

    # Check for parking nameservers
    if is_parking_ns(parsed['nameservers']):
        distressed_signals.append(f"Parking NS: {', '.join(parsed['nameservers'][:3])}")

    # Check for no nameservers (possible sign of abandonment)
    if not parsed['nameservers']:
        distressed_signals.append("No nameservers found")

    if distressed_signals:
        return 'distressed', '; '.join(distressed_signals), "MONITOR: Check if domain becomes available"

    # ACTIVE
    return 'active', "Normal registration", "No action needed - actively registered"

def main():
    print("=" * 70)
    print("Sprint 16 - Agent 1: WHALE WHOIS BLITZ")
    print("=" * 70)
    print()

    # Step 1: Load whale domains
    whales = load_whale_domains()

    # Step 2 & 3: WHOIS check and classify each domain
    results = {
        'sprint': 16,
        'agent': 'WHALE WHOIS BLITZ',
        'scan_date': '2026-05-08',
        'total_checked': 0,
        'dropping': [],
        'distressed': [],
        'active': [],
        'error': [],
        'summary': {
            'dropping_count': 0,
            'distressed_count': 0,
            'active_count': 0,
            'error_count': 0,
        }
    }

    total = len(whales)

    for i, whale in enumerate(whales):
        domain = whale['domain']
        etv = whale['etv']
        keywords = whale['keywords']

        progress = f"[{i+1}/{total}]"
        print(f"{progress} WHOIS: {domain} (ETV: ${etv:,.0f}/mo, {keywords:,} kw)...", end=' ', flush=True)

        # Run WHOIS
        raw_output, error = run_whois(domain)

        if error:
            print(f"ERROR: {error}")
            results['error'].append({
                'domain': domain,
                'etv': etv,
                'keywords': keywords,
                'error': error,
            })
            results['summary']['error_count'] += 1
        else:
            # Parse WHOIS
            parsed = parse_whois(raw_output, domain)

            # Classify
            classification, signal, action = classify_domain(parsed, domain)

            entry = {
                'domain': domain,
                'etv': etv,
                'keywords': keywords,
                'expiry': parsed['expiry'],
                'registrar': parsed['registrar'],
                'status': parsed['status'],
                'nameservers': parsed['nameservers'][:4],  # Keep top 4
                'signal': signal,
                'action': action,
            }

            if classification == 'dropping':
                results['dropping'].append(entry)
                results['summary']['dropping_count'] += 1
                print(f"*** DROPPING *** {signal}")
            elif classification == 'distressed':
                results['distressed'].append(entry)
                results['summary']['distressed_count'] += 1
                print(f"!! DISTRESSED !! {signal}")
            else:
                results['active'].append(entry)
                results['summary']['active_count'] += 1
                print(f"Active (expires: {parsed['expiry'] or 'unknown'})")

        results['total_checked'] = i + 1

        # Rate limiting: 1 second between requests to avoid WHOIS blocks
        if i < total - 1:
            time.sleep(1.0)

    # Sort dropping and distressed by ETV descending (highest value first)
    results['dropping'].sort(key=lambda x: x['etv'], reverse=True)
    results['distressed'].sort(key=lambda x: x['etv'], reverse=True)

    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print()
    print("=" * 70)
    print("WHALE WHOIS BLITZ - SUMMARY")
    print("=" * 70)
    print(f"Total checked: {results['total_checked']}")
    print(f"  DROPPING:   {results['summary']['dropping_count']}")
    print(f"  DISTRESSED: {results['summary']['distressed_count']}")
    print(f"  ACTIVE:     {results['summary']['active_count']}")
    print(f"  ERROR:      {results['summary']['error_count']}")
    print()

    if results['dropping']:
        print("*** DROPPING WHALES ***")
        for d in results['dropping']:
            print(f"  {d['domain']} - ETV: ${d['etv']:,.0f}/mo - {d['signal']}")
        print()

    if results['distressed']:
        print("!! DISTRESSED WHALES !!")
        for d in results['distressed']:
            print(f"  {d['domain']} - ETV: ${d['etv']:,.0f}/mo - {d['signal']}")
        print()

    print(f"Results saved to: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()

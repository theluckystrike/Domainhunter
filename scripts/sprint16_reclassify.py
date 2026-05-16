#!/usr/bin/env python3
"""
Sprint 16 - Reclassify whale WHOIS results.
Fix: clientTransferProhibited is NORMAL, not a distress signal.
Only clientHold, serverHold, expired, short expiry, or parking NS = distressed.
"""

import json
import re
from datetime import datetime
from pathlib import Path

INPUT_FILE = Path("/Users/mike/Desktop/domainhunter/data/sprint16_whale_whois.json")
OUTPUT_FILE = INPUT_FILE  # Overwrite

PARKING_NS_PATTERNS = [
    r'parkingcrew', r'sedoparking', r'bodis', r'afternic', r'hugedomains',
    r'dan\.com', r'undeveloped', r'parking',
    r'ns1\.suspended', r'ns2\.suspended', r'pendingrenew',
]

def parse_expiry_date(expiry_str):
    if not expiry_str:
        return None
    formats = [
        '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%b-%Y', '%d %b %Y',
        '%Y/%m/%d', '%d/%m/%Y', '%Y.%m.%d', '%d.%m.%Y', '%B %d, %Y',
        '%d-%m-%Y', '%Y%m%d',
    ]
    clean = expiry_str.strip().rstrip('.')
    clean = re.sub(r'\s*\(.*?\)\s*$', '', clean)
    clean = re.sub(r'\s+UTC\s*$', '', clean, re.IGNORECASE)
    clean = re.sub(r'\s+GMT\s*$', '', clean, re.IGNORECASE)
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(clean)
    except:
        pass
    return None

def is_parking_ns(nameservers):
    """Check if nameservers match known parking/dead patterns.
    Note: gtld-servers.net are TLD root servers, not parking.
    They appear when there are no delegated nameservers - which IS a distress signal."""
    ns_str = ' '.join(nameservers).lower()
    for pattern in PARKING_NS_PATTERNS:
        if re.search(pattern, ns_str, re.IGNORECASE):
            return True
    return False

def has_no_real_nameservers(nameservers):
    """Check if domain has no real nameservers (empty list)."""
    if not nameservers:
        return True
    return False

def reclassify(entry):
    """Reclassify a domain entry. Returns (classification, signal, action)."""
    statuses = [s.lower() for s in entry.get('status', [])]
    status_str = ' '.join(statuses)
    nameservers = entry.get('nameservers', [])

    # DROPPING: clientRenewProhibited, pendingDelete, redemptionPeriod
    dropping_flags = ['clientrenewprohibited', 'pendingdelete', 'redemptionperiod']
    for flag in dropping_flags:
        if flag in status_str:
            status_name = {
                'clientrenewprohibited': 'clientRenewProhibited',
                'pendingdelete': 'pendingDelete',
                'redemptionperiod': 'redemptionPeriod'
            }.get(flag, flag)
            return 'dropping', f"Status: {status_name}", "IMMEDIATE: Monitor for auction/drop"

    # DISTRESSED signals
    distressed_signals = []

    # clientHold / serverHold
    if 'clienthold' in status_str:
        distressed_signals.append("Status: clientHold (suspended by registrar)")
    if 'serverhold' in status_str:
        distressed_signals.append("Status: serverHold (suspended by registry)")

    # Expired or expiring within 6 months
    expiry_str = entry.get('expiry')
    expiry_date = parse_expiry_date(expiry_str)
    if expiry_date:
        now = datetime.now()
        if expiry_date.tzinfo:
            expiry_date = expiry_date.replace(tzinfo=None)
        months_until = (expiry_date - now).days / 30.0
        if months_until < 0:
            return 'dropping', f"EXPIRED: {expiry_str}", "URGENT: Domain past expiry date"
        elif months_until < 3:
            distressed_signals.append(f"Expiring SOON in {months_until:.1f} months ({expiry_str})")
        elif months_until < 6:
            distressed_signals.append(f"Expiring in {months_until:.1f} months ({expiry_str})")

    # No real nameservers (only TLD root servers)
    if has_no_real_nameservers(nameservers):
        distressed_signals.append("No delegated nameservers (TLD root only or none)")

    # Known parking NS
    if is_parking_ns(nameservers):
        distressed_signals.append(f"Parking NS detected")

    if distressed_signals:
        return 'distressed', '; '.join(distressed_signals), "MONITOR: Check if domain becomes available"

    # ACTIVE
    expiry_info = f" (expires: {expiry_str})" if expiry_str else ""
    return 'active', f"Normal registration{expiry_info}", "No action needed - actively registered"

def main():
    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    # Collect all entries from all categories
    all_entries = []
    for cat in ['dropping', 'distressed', 'active']:
        for entry in data.get(cat, []):
            all_entries.append(entry)

    # Keep error entries separate
    errors = data.get('error', [])

    # Reclassify
    new_dropping = []
    new_distressed = []
    new_active = []

    for entry in all_entries:
        classification, signal, action = reclassify(entry)
        entry['signal'] = signal
        entry['action'] = action

        if classification == 'dropping':
            new_dropping.append(entry)
        elif classification == 'distressed':
            new_distressed.append(entry)
        else:
            new_active.append(entry)

    # Sort by ETV descending
    new_dropping.sort(key=lambda x: x['etv'], reverse=True)
    new_distressed.sort(key=lambda x: x['etv'], reverse=True)
    new_active.sort(key=lambda x: x['etv'], reverse=True)

    data['dropping'] = new_dropping
    data['distressed'] = new_distressed
    data['active'] = new_active
    data['error'] = errors
    data['summary'] = {
        'dropping_count': len(new_dropping),
        'distressed_count': len(new_distressed),
        'active_count': len(new_active),
        'error_count': len(errors),
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    # Print summary
    print("=" * 70)
    print("WHALE WHOIS BLITZ - RECLASSIFIED RESULTS")
    print("=" * 70)
    print(f"Total: {len(all_entries) + len(errors)}")
    print(f"  DROPPING:   {len(new_dropping)}")
    print(f"  DISTRESSED: {len(new_distressed)}")
    print(f"  ACTIVE:     {len(new_active)}")
    print(f"  ERROR:      {len(errors)}")
    print()

    if new_dropping:
        print("*** DROPPING WHALES (clientRenewProhibited / pendingDelete / expired) ***")
        for d in new_dropping:
            print(f"  {d['domain']:40s} ETV: ${d['etv']:>12,.0f}/mo  {d['signal']}")
        print()

    if new_distressed:
        print("!! DISTRESSED WHALES (clientHold, short expiry, no NS, parking) !!")
        for d in new_distressed:
            print(f"  {d['domain']:40s} ETV: ${d['etv']:>12,.0f}/mo  {d['signal']}")
        print()

    if new_active:
        print("ACTIVE WHALES (normal registration, healthy)")
        for d in new_active:
            exp = d.get('expiry', 'unknown')
            print(f"  {d['domain']:40s} ETV: ${d['etv']:>12,.0f}/mo  expires: {exp}")
        print()

    print(f"Results saved to: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()

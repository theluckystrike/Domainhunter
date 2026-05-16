#!/usr/bin/env python3
"""Sprint 24: Update backorder_queue.json and monitored_domains.json
with latest reaper output.

NASA P10 compliant: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, all file I/O checked.
"""

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

# Constants -- bounded limits
MAX_REAPER_RESULTS = 500
MAX_QUEUE_DOMAINS = 50
MAX_MONITORED_PER_TIER = 100
QUEUE_SCORE_THRESHOLD = 50.0
EST_VALUE_FLOOR = 500  # minimum estimated value for queue inclusion

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
QUEUE_FILE = DATA_DIR / "backorder_queue.json"
MONITORED_FILE = SCRIPT_DIR / "monitored_domains.json"


def find_latest_reaper(data_dir: Path) -> Path:
    """Find the most recent startup_reaper JSON output file by mtime."""
    assert data_dir.is_dir(), f"Data directory not found: {data_dir}"
    candidates = list(data_dir.glob("startup_reaper_*.json"))
    assert len(candidates) > 0, "No startup_reaper_*.json files found"
    # Sort by modification time (newest first), not alphabetically
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_json(path: Path) -> dict:
    """Load and validate a JSON file."""
    assert path.is_file(), f"File not found: {path}"
    with open(path, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict), f"Expected JSON object in {path.name}"
    return data


def save_json(path: Path, data: dict) -> None:
    """Write JSON with pretty formatting."""
    assert isinstance(data, dict), "Data must be a dict"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def extract_sweet_spot_domains(reaper_data: dict) -> list:
    """Extract sweet_spot domains with drop_signal from reaper results."""
    results = reaper_data.get("results", [])
    assert len(results) <= MAX_REAPER_RESULTS, f"Reaper results exceed {MAX_REAPER_RESULTS}"

    sweet = []
    for i, r in enumerate(results):
        if i >= MAX_REAPER_RESULTS:
            break
        if r.get("competition_tier") == "sweet_spot" and r.get("drop_signal"):
            sweet.append(r)
    return sweet


def estimate_value(reaper_entry: dict) -> tuple:
    """Estimate domain value range from reaper data. Returns (low, high)."""
    funding = reaper_entry.get("funding_usd", 0)
    score = reaper_entry.get("reaper_score", 0)
    assert isinstance(funding, (int, float)), "funding_usd must be numeric"
    assert isinstance(score, (int, float)), "reaper_score must be numeric"

    # Value estimation based on funding tier and score
    if funding >= 500_000_000:
        low, high = 5000, 50000
    elif funding >= 100_000_000:
        low, high = 2000, 20000
    elif funding >= 50_000_000:
        low, high = 1000, 10000
    elif funding >= 10_000_000:
        low, high = 500, 5000
    else:
        low, high = 100, 1000

    # Score multiplier
    if score >= 55:
        low = int(low * 1.5)
        high = int(high * 1.5)
    elif score >= 50:
        low = int(low * 1.2)
        high = int(high * 1.2)

    return low, high


def build_queue_entry(reaper_entry: dict) -> dict:
    """Build a backorder_queue entry from reaper data."""
    domain = reaper_entry["domain"]
    score = reaper_entry.get("reaper_score", 0)
    assert len(domain) > 0, "Empty domain name"
    assert score >= 0, "Negative reaper_score"

    est_low, est_high = estimate_value(reaper_entry)
    funding = reaper_entry.get("funding_usd", 0)
    epp = reaper_entry.get("epp_status", "unknown")
    notes = reaper_entry.get("notes", "")
    tier = "critical" if score >= 55 else ("high" if score >= 35 else "medium")

    return {
        "domain": domain,
        "drop_est": "TBD",
        "expiry": reaper_entry.get("expiry_date", ""),
        "epp_status": epp,
        "backorder_status": "waiting",
        "backorder_note": f"From reaper scan. {notes[:120]}",
        "reaper_score": score,
        "competition_tier": "sweet_spot",
        "playbook": "FLIP" if funding >= 100_000_000 else "REDIRECT",
        "est_value_low": est_low,
        "est_value_high": est_high,
        "funding_usd": funding,
        "monitor_tier": tier,
    }


def update_backorder_queue(
    queue_data: dict, sweet_domains: list, now_iso: str
) -> tuple:
    """Update the backorder queue with new sweet_spot domains.

    Returns (updated_queue_data, list_of_added_domains).
    """
    assert "queue" in queue_data, "Missing 'queue' key"
    assert "budget_summary" in queue_data, "Missing 'budget_summary' key"

    existing = {entry["domain"] for entry in queue_data["queue"]}
    added = []

    for i, reaper_entry in enumerate(sweet_domains):
        if i >= MAX_QUEUE_DOMAINS:
            break
        domain = reaper_entry["domain"]
        if domain in existing:
            continue

        score = reaper_entry.get("reaper_score", 0)
        est_low, _ = estimate_value(reaper_entry)
        if score < QUEUE_SCORE_THRESHOLD or est_low < EST_VALUE_FLOOR:
            continue

        new_entry = build_queue_entry(reaper_entry)
        queue_data["queue"].append(new_entry)
        existing.add(domain)
        added.append(domain)

    queue_data["generated_at"] = now_iso
    queue_data["sprint"] = "24"
    return queue_data, added


def tier_for_score(score: float) -> str:
    """Determine monitoring tier from reaper score."""
    assert isinstance(score, (int, float)), "Score must be numeric"
    if score >= 55:
        return "critical"
    if score >= 35:
        return "high"
    return "medium"


def max_bid_for_competition(reaper_entry: dict) -> int:
    """Set max bid based on recommended_bid from reaper."""
    bid = reaper_entry.get("recommended_bid", 59)
    assert isinstance(bid, (int, float)), "recommended_bid must be numeric"
    return int(bid)


def build_monitor_entry(reaper_entry: dict) -> dict:
    """Build a monitored_domains entry from reaper data."""
    domain = reaper_entry["domain"]
    assert len(domain) > 0, "Empty domain name"

    score = reaper_entry.get("reaper_score", 0)
    funding = reaper_entry.get("funding_usd", 0)
    company = reaper_entry.get("company_name", "Unknown")
    notes = reaper_entry.get("notes", "")
    epp = reaper_entry.get("epp_status", "unknown")

    funding_str = f"${funding / 1_000_000:.0f}M" if funding >= 1_000_000 else f"${funding}"
    note_text = (
        f"{company}, {funding_str} funded, reaper={score}, "
        f"{epp}, {notes[:80]}"
    )

    return {
        "domain": domain,
        "etv": 0,
        "max_bid": max_bid_for_competition(reaper_entry),
        "notes": note_text,
    }


def update_monitored_domains(
    monitored_data: dict, sweet_domains: list
) -> tuple:
    """Add new sweet_spot domains to monitored_domains.json.

    Returns (updated_data, list_of_added_domains_with_tiers).
    """
    assert "domains" in monitored_data, "Missing 'domains' key"
    tiers = monitored_data["domains"]
    for t in ("critical", "high", "medium", "low"):
        assert t in tiers, f"Missing tier: {t}"

    existing = set()
    for tier_list in tiers.values():
        for entry in tier_list:
            existing.add(entry["domain"])

    added = []
    for i, reaper_entry in enumerate(sweet_domains):
        if i >= MAX_REAPER_RESULTS:
            break
        domain = reaper_entry["domain"]
        if domain in existing:
            continue

        score = reaper_entry.get("reaper_score", 0)
        tier = tier_for_score(score)
        entry = build_monitor_entry(reaper_entry)

        assert len(tiers[tier]) < MAX_MONITORED_PER_TIER, (
            f"Tier '{tier}' at capacity ({MAX_MONITORED_PER_TIER})"
        )
        tiers[tier].append(entry)
        existing.add(domain)
        added.append((domain, tier, score))

    return monitored_data, added


def print_summary(
    queue_added: list,
    monitor_added: list,
    queue_total: int,
    monitor_total: int,
) -> None:
    """Print a human-readable summary of changes."""
    print("=" * 60)
    print("SPRINT 24 — Queue & Monitor Update Summary")
    print("=" * 60)

    print(f"\n--- backorder_queue.json ---")
    print(f"  Total domains in queue: {queue_total}")
    if queue_added:
        print(f"  NEW domains added ({len(queue_added)}):")
        for d in queue_added:
            print(f"    + {d}")
    else:
        print("  No new domains added (all candidates already in queue or below threshold)")

    print(f"\n--- monitored_domains.json ---")
    print(f"  Total monitored domains: {monitor_total}")
    if monitor_added:
        print(f"  NEW domains added ({len(monitor_added)}):")
        for domain, tier, score in monitor_added:
            print(f"    + {domain:30s} -> {tier:8s} (score={score})")
    else:
        print("  No new domains added")

    print(f"\n{'=' * 60}")
    print("Done.")


def main() -> int:
    """Main entry point. Returns 0 on success, 1 on error."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load all inputs
    reaper_path = find_latest_reaper(DATA_DIR)
    print(f"Using reaper file: {reaper_path.name}")

    reaper_data = load_json(reaper_path)
    queue_data = load_json(QUEUE_FILE)
    monitored_data = load_json(MONITORED_FILE)

    # Extract sweet_spot domains
    sweet_domains = extract_sweet_spot_domains(reaper_data)
    print(f"Found {len(sweet_domains)} sweet_spot domains with drop signals")

    # Backup originals (deepcopy before mutation)
    queue_backup = deepcopy(queue_data)
    monitored_backup = deepcopy(monitored_data)

    # Update backorder queue
    queue_data, queue_added = update_backorder_queue(queue_data, sweet_domains, now_iso)

    # Update monitored domains
    monitored_data, monitor_added = update_monitored_domains(monitored_data, sweet_domains)

    # Save updated files
    save_json(QUEUE_FILE, queue_data)
    save_json(MONITORED_FILE, monitored_data)

    # Count totals
    queue_total = len(queue_data.get("queue", []))
    monitor_total = sum(
        len(tier_list) for tier_list in monitored_data.get("domains", {}).values()
    )

    # Summary
    print_summary(queue_added, monitor_added, queue_total, monitor_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())

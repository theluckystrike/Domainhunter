#!/usr/bin/env python3
"""Sprint 25 queue updater: applies rescored data to backorder_queue.json and monitored_domains.json.

NASA P10: functions <60 lines, 2+ assertions per function, bounded loops.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCRIPTS_DIR = Path(__file__).resolve().parent
RESCORED_PATH = DATA_DIR / "sprint24_rescored_2026-05-15.json"
QUEUE_PATH = DATA_DIR / "backorder_queue.json"
MONITORED_PATH = SCRIPTS_DIR / "monitored_domains.json"

# Tier thresholds
CRITICAL_THRESHOLD = 75.0
HIGH_THRESHOLD = 55.0

MAX_DOMAINS = 500  # bounded loop guard


def load_json(path: Path) -> dict:
    """Load and validate a JSON file."""
    assert path.exists(), f"File not found: {path}"
    assert path.suffix == ".json", f"Not a JSON file: {path}"
    with open(path, "r") as f:
        data = json.load(f)
    return data


def save_json(path: Path, data: dict) -> None:
    """Save dict to JSON with pretty formatting."""
    assert isinstance(data, dict), "Data must be a dict"
    assert path.suffix == ".json", f"Not a JSON file: {path}"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def build_rescore_map(rescored: dict) -> dict:
    """Build domain -> {new_score, new_tier, old_score, delta} lookup from rescored data."""
    comparisons = rescored.get("comparisons", [])
    assert isinstance(comparisons, list), "comparisons must be a list"
    assert len(comparisons) > 0, "No comparisons found in rescored data"

    score_map = {}
    for i, comp in enumerate(comparisons):
        assert i < MAX_DOMAINS, f"Loop guard: exceeded {MAX_DOMAINS} comparisons"
        domain = comp["domain"]
        score_map[domain] = {
            "new_score": comp["new_score"],
            "new_tier": comp["new_tier"],
            "old_score": comp["old_score"],
            "delta": comp["delta"],
            "tier_changed": comp.get("tier_changed", False),
        }
    return score_map


def classify_monitor_tier(score: float) -> str:
    """Classify a domain into a monitor tier based on its reaper score."""
    assert isinstance(score, (int, float)), f"Score must be numeric, got {type(score)}"
    assert 0 <= score <= 100, f"Score out of range: {score}"

    if score >= CRITICAL_THRESHOLD:
        return "critical"
    elif score >= HIGH_THRESHOLD:
        return "high"
    else:
        return "high"  # keep in high if already tracked, never demote below high


def update_backorder_queue(queue: dict, score_map: dict) -> list:
    """Update backorder_queue entries with new scores. Returns list of change dicts."""
    changes = []
    queue["sprint"] = "25"
    queue["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entries = queue.get("queue", [])
    assert isinstance(entries, list), "queue.queue must be a list"

    for i, entry in enumerate(entries):
        assert i < MAX_DOMAINS, f"Loop guard: exceeded {MAX_DOMAINS} queue entries"
        domain = entry.get("domain", "")
        if domain in score_map:
            info = score_map[domain]
            old_score = entry.get("reaper_score", 0)
            old_tier = entry.get("competition_tier", "unknown")
            new_score = info["new_score"]
            new_tier = info["new_tier"]

            # Update fields
            entry["reaper_score"] = new_score
            entry["competition_tier"] = new_tier

            # Determine new monitor_tier based on score
            new_monitor = classify_monitor_tier(new_score)
            old_monitor = entry.get("monitor_tier", "high")
            if new_score >= CRITICAL_THRESHOLD and old_monitor != "critical":
                entry["monitor_tier"] = "critical"
            elif new_score < CRITICAL_THRESHOLD and old_monitor == "critical":
                # Only demote from critical if score dropped below threshold
                # and domain is not in the first 4 (manually curated critical)
                if i >= 4:
                    entry["monitor_tier"] = "high"

            change = {
                "domain": domain,
                "old_score": old_score,
                "new_score": new_score,
                "delta": round(new_score - old_score, 1),
                "old_tier": old_tier,
                "new_tier": new_tier,
                "tier_changed": old_tier != new_tier,
                "old_monitor": old_monitor,
                "new_monitor": entry.get("monitor_tier", "high"),
                "monitor_changed": old_monitor != entry.get("monitor_tier", "high"),
            }
            changes.append(change)

    return changes


def update_monitored_domains(monitored: dict, score_map: dict) -> list:
    """Promote/demote domains between tiers in monitored_domains.json. Returns changes."""
    changes = []
    tiers = monitored.get("domains", {})
    assert isinstance(tiers, dict), "domains must be a dict"

    # Build flat lookup: domain -> (tier, entry)
    all_domains = {}
    for tier_name in ["critical", "high", "medium", "low"]:
        tier_list = tiers.get(tier_name, [])
        for i, entry in enumerate(tier_list):
            assert i < MAX_DOMAINS, f"Loop guard: exceeded {MAX_DOMAINS} in tier {tier_name}"
            all_domains[entry["domain"]] = {"tier": tier_name, "entry": entry}

    # Track promotions and demotions
    promotions_to_critical = []
    demotions_from_critical = []

    for domain, info in score_map.items():
        assert len(promotions_to_critical) + len(demotions_from_critical) < MAX_DOMAINS
        new_score = info["new_score"]
        old_score = info["old_score"]

        if domain not in all_domains:
            continue

        current = all_domains[domain]
        current_tier = current["tier"]
        entry = current["entry"]

        # Determine target tier
        if new_score >= CRITICAL_THRESHOLD:
            target_tier = "critical"
        elif new_score >= HIGH_THRESHOLD:
            target_tier = "high"
        else:
            target_tier = current_tier  # don't demote below high for tracked domains

        # Update notes with new score
        old_notes = entry.get("notes", "")
        # Replace old reaper score in notes if present
        if f"reaper={old_score}" in old_notes:
            entry["notes"] = old_notes.replace(
                f"reaper={old_score}", f"reaper={new_score}"
            )
        elif "reaper=" in old_notes:
            # Try to replace any reaper= pattern
            import re
            entry["notes"] = re.sub(
                r"reaper=[\d.]+", f"reaper={new_score}", old_notes
            )

        if target_tier != current_tier:
            change = {
                "domain": domain,
                "from_tier": current_tier,
                "to_tier": target_tier,
                "old_score": old_score,
                "new_score": new_score,
            }
            changes.append(change)

            if target_tier == "critical":
                promotions_to_critical.append((domain, entry))
            elif current_tier == "critical":
                demotions_from_critical.append((domain, entry, target_tier))

    # Apply promotions: move from current tier to critical
    for domain, entry in promotions_to_critical:
        current_tier = all_domains[domain]["tier"]
        tiers[current_tier] = [e for e in tiers.get(current_tier, []) if e["domain"] != domain]
        tiers.setdefault("critical", []).append(entry)

    # Apply demotions: move from critical to target tier
    for domain, entry, target_tier in demotions_from_critical:
        tiers["critical"] = [e for e in tiers.get("critical", []) if e["domain"] != domain]
        tiers.setdefault(target_tier, []).append(entry)

    return changes


def print_summary(queue_changes: list, monitor_changes: list) -> None:
    """Print a human-readable summary of all changes."""
    assert isinstance(queue_changes, list), "queue_changes must be a list"
    assert isinstance(monitor_changes, list), "monitor_changes must be a list"

    print("=" * 70)
    print("SPRINT 25 QUEUE UPDATE SUMMARY")
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    # Score changes
    print(f"\n--- BACKORDER QUEUE: {len(queue_changes)} domains rescored ---\n")
    score_ups = [c for c in queue_changes if c["delta"] > 0]
    score_downs = [c for c in queue_changes if c["delta"] < 0]
    score_same = [c for c in queue_changes if c["delta"] == 0]

    print(f"  Score increases: {len(score_ups)}")
    print(f"  Score decreases: {len(score_downs)}")
    print(f"  Unchanged:       {len(score_same)}")

    # Top movers
    if score_ups:
        print("\n  TOP SCORE INCREASES:")
        for c in sorted(score_ups, key=lambda x: -x["delta"])[:10]:
            print(f"    {c['domain']:30s}  {c['old_score']:5.1f} -> {c['new_score']:5.1f}  (+{c['delta']:5.1f})")

    if score_downs:
        print("\n  SCORE DECREASES:")
        for c in sorted(score_downs, key=lambda x: x["delta"]):
            print(f"    {c['domain']:30s}  {c['old_score']:5.1f} -> {c['new_score']:5.1f}  ({c['delta']:5.1f})")

    # Competition tier changes
    tier_changes = [c for c in queue_changes if c["tier_changed"]]
    if tier_changes:
        print(f"\n  COMPETITION TIER CHANGES ({len(tier_changes)}):")
        for c in tier_changes:
            print(f"    {c['domain']:30s}  {c['old_tier']} -> {c['new_tier']}")

    # Monitor tier changes
    mon_changes = [c for c in queue_changes if c["monitor_changed"]]
    if mon_changes:
        print(f"\n  MONITOR TIER CHANGES ({len(mon_changes)}):")
        for c in mon_changes:
            print(f"    {c['domain']:30s}  {c['old_monitor']} -> {c['new_monitor']}")

    # Monitored domains changes
    if monitor_changes:
        print(f"\n--- MONITORED DOMAINS: {len(monitor_changes)} tier changes ---\n")
        for c in monitor_changes:
            direction = "PROMOTED" if c["to_tier"] == "critical" else "DEMOTED"
            print(f"  {direction}: {c['domain']:30s}  {c['from_tier']} -> {c['to_tier']}  (score: {c['old_score']:.1f} -> {c['new_score']:.1f})")
    else:
        print("\n--- MONITORED DOMAINS: No tier changes ---")

    # New critical domains (score >= 75)
    critical_domains = [c for c in queue_changes if c["new_score"] >= CRITICAL_THRESHOLD]
    if critical_domains:
        print(f"\n--- CRITICAL TIER (score >= {CRITICAL_THRESHOLD}): {len(critical_domains)} domains ---\n")
        for c in sorted(critical_domains, key=lambda x: -x["new_score"]):
            print(f"  {c['domain']:30s}  score={c['new_score']:5.1f}")

    # High tier domains (score >= 55, < 75)
    high_domains = [c for c in queue_changes if HIGH_THRESHOLD <= c["new_score"] < CRITICAL_THRESHOLD]
    if high_domains:
        print(f"\n--- HIGH TIER ({HIGH_THRESHOLD} <= score < {CRITICAL_THRESHOLD}): {len(high_domains)} domains ---\n")
        for c in sorted(high_domains, key=lambda x: -x["new_score"]):
            print(f"  {c['domain']:30s}  score={c['new_score']:5.1f}")

    print("\n" + "=" * 70)
    print("Files updated:")
    print(f"  {QUEUE_PATH}")
    print(f"  {MONITORED_PATH}")
    print("=" * 70)


def main() -> int:
    """Main entry point."""
    # Load all data
    rescored = load_json(RESCORED_PATH)
    queue = load_json(QUEUE_PATH)
    monitored = load_json(MONITORED_PATH)

    # Build rescore lookup
    score_map = build_rescore_map(rescored)
    print(f"Loaded {len(score_map)} rescored domains from sprint24_rescored_2026-05-15.json")

    # Update backorder queue
    queue_changes = update_backorder_queue(queue, score_map)
    print(f"Updated {len(queue_changes)} domains in backorder_queue.json")

    # Update monitored domains
    monitor_changes = update_monitored_domains(monitored, score_map)
    print(f"Applied {len(monitor_changes)} tier changes in monitored_domains.json")

    # Save
    save_json(QUEUE_PATH, queue)
    save_json(MONITORED_PATH, monitored)

    # Print summary
    print_summary(queue_changes, monitor_changes)

    return 0


if __name__ == "__main__":
    sys.exit(main())

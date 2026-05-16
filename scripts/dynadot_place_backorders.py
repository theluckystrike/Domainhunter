#!/usr/bin/env python3
"""Dynadot backorder placement — batch or single domain.

Loads monitored domains, filters by tier, places backorders via Dynadot API.
Supports --dry-run, --tier, and --domain flags.

NASA P10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# -- Resolve project root so imports work from scripts/ --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from clients.dynadot_client import BackorderResult, DynadotAuthError, DynadotClient  # noqa: E402
from config.settings import Settings  # noqa: E402

_VALID_TIERS: tuple[str, ...] = ("critical", "high", "medium", "low", "all")
_MAX_DOMAINS: int = 200
_RESULTS_PATH: Path = _PROJECT_ROOT / "data" / "dynadot_backorders.json"
_MONITORED_PATH: Path = _PROJECT_ROOT / "scripts" / "monitored_domains.json"

_API_KEY_HELP: str = """
DYNADOT_API_KEY not set. To get your key:
  1. Log in to https://www.dynadot.com/account/domain/setting/api.html
  2. Enable API access (if not already enabled)
  3. Copy the API key shown on that page
  4. Add to .env:  DYNADOT_API_KEY=your_key_here
"""


# --- Frozen result ---

@dataclass(frozen=True)
class OrderAttempt:
    """Single backorder attempt outcome."""
    domain: str
    tier: str
    max_bid: int
    success: bool
    message: str


# --- Pure functions ---


def load_monitored_domains(path: Path) -> dict[str, Any]:
    """Load and validate monitored_domains.json."""
    assert path.exists(), f"File not found: {path}"
    assert path.suffix == ".json", "Expected a .json file"
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    assert "domains" in raw, "JSON must have a 'domains' key"
    return raw


def filter_domains(
    data: dict[str, Any], tier: str, single_domain: str | None
) -> list[tuple[str, dict[str, Any]]]:
    """Return (tier, entry) pairs filtered by tier and max_bid > 0."""
    assert tier in _VALID_TIERS, f"Invalid tier: {tier}"
    assert isinstance(data, dict) and "domains" in data, "Invalid data structure"

    tiers: list[str] = (
        list(data["domains"].keys()) if tier == "all"
        else [tier] if tier in data["domains"] else []
    )
    results: list[tuple[str, dict[str, Any]]] = []
    for t in tiers:
        entries: list[dict[str, Any]] = data["domains"].get(t, [])
        for idx, entry in enumerate(entries):
            if idx >= _MAX_DOMAINS:
                break
            if single_domain and entry["domain"] != single_domain:
                continue
            if entry.get("max_bid", 0) > 0:
                results.append((t, entry))
    return results


def build_status_table(attempts: list[OrderAttempt]) -> str:
    """Format attempts as an aligned ASCII table."""
    assert isinstance(attempts, list), "attempts must be a list"
    assert all(isinstance(a, OrderAttempt) for a in attempts), "all must be OrderAttempt"

    if not attempts:
        return "  (no domains matched filters)\n"

    hdr: str = f"  {'Domain':<30} {'Tier':<10} {'Bid':>6}  {'Status':<8} Message"
    sep: str = "  " + "-" * 90
    lines: list[str] = [hdr, sep]
    for idx, a in enumerate(attempts):
        if idx >= _MAX_DOMAINS:
            break
        tag: str = "OK" if a.success else "FAIL"
        lines.append(
            f"  {a.domain:<30} {a.tier:<10} ${a.max_bid:>5}  {tag:<8} {a.message}"
        )
    lines.append(sep)
    return "\n".join(lines) + "\n"


def save_results(attempts: list[OrderAttempt], path: Path) -> None:
    """Persist results to JSON for audit trail."""
    assert isinstance(attempts, list), "attempts must be a list"
    assert path.parent.exists(), f"Directory not found: {path.parent}"

    records: list[dict[str, Any]] = [
        {"domain": a.domain, "tier": a.tier, "max_bid": a.max_bid,
         "success": a.success, "message": a.message}
        for a in attempts
    ]
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"\n  Results saved to {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Place Dynadot backorders for monitored domains."
    )
    parser.add_argument(
        "--tier", default="all", choices=list(_VALID_TIERS),
        help="Filter by priority tier (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without calling API")
    parser.add_argument("--domain", default=None, help="Backorder a single specific domain")
    args: argparse.Namespace = parser.parse_args(argv)
    assert isinstance(args.tier, str), "tier must be a string"
    assert isinstance(args.dry_run, bool), "dry_run must be a boolean"
    return args


# --- Async core ---


async def place_backorders(
    client: DynadotClient, targets: list[tuple[str, dict[str, Any]]]
) -> list[OrderAttempt]:
    """Place backorders sequentially (respects Dynadot 10 req/min rate limit)."""
    assert isinstance(targets, list), "targets must be a list"
    assert len(targets) <= _MAX_DOMAINS, f"Too many targets: {len(targets)}"

    attempts: list[OrderAttempt] = []
    for idx, (tier, entry) in enumerate(targets):
        if idx >= _MAX_DOMAINS:
            break
        domain: str = entry["domain"]
        max_bid: int = int(entry.get("max_bid", 0))
        try:
            result: BackorderResult = await client.backorder(domain)
            attempts.append(OrderAttempt(
                domain=domain, tier=tier, max_bid=max_bid,
                success=result.success, message=result.message,
            ))
        except Exception as exc:
            attempts.append(OrderAttempt(
                domain=domain, tier=tier, max_bid=max_bid,
                success=False, message=str(exc)[:120],
            ))
    return attempts


# --- Entry point ---


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on error."""
    args: argparse.Namespace = parse_args(argv)

    # Load settings, check API key
    try:
        settings: Settings = Settings()
    except Exception as exc:
        print(f"  Settings error: {exc}", file=sys.stderr)
        return 1

    if not settings.dynadot_api_key:
        print(_API_KEY_HELP)
        return 1

    # Load and filter domains
    data: dict[str, Any] = load_monitored_domains(_MONITORED_PATH)
    targets: list[tuple[str, dict[str, Any]]] = filter_domains(
        data, args.tier, args.domain
    )

    mode: str = "[DRY RUN] " if args.dry_run else ""
    print(f"\n  {mode}Dynadot Backorder — tier={args.tier}, {len(targets)} domain(s)\n")

    if not targets:
        print("  No domains matched filters (check tier/domain and max_bid > 0).\n")
        return 0

    # Place backorders
    try:
        client: DynadotClient = DynadotClient(settings, dry_run=args.dry_run)
    except DynadotAuthError as exc:
        print(f"  Auth error: {exc}")
        print(_API_KEY_HELP)
        return 1

    attempts: list[OrderAttempt] = asyncio.run(place_backorders(client, targets))

    # Report
    print(build_status_table(attempts))
    save_results(attempts, _RESULTS_PATH)

    ok_count: int = sum(1 for a in attempts if a.success)
    fail_count: int = len(attempts) - ok_count
    print(f"  Summary: {ok_count} succeeded, {fail_count} failed\n")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

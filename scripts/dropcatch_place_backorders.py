#!/usr/bin/env python3
"""Place DropCatch backorders for Tier A+ domains.

Reads from monitored_domains.json, filters by tier, and places
backorders via the DropCatch v2 API. Falls back to browser-based
backorder if API credentials are not configured.

Usage:
    python3 scripts/dropcatch_place_backorders.py --dry-run     # Preview only
    python3 scripts/dropcatch_place_backorders.py               # Place backorders
    python3 scripts/dropcatch_place_backorders.py --tier critical  # Critical only
    python3 scripts/dropcatch_place_backorders.py --domain ghostautonomy.com

NASA Power of 10: functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# -- Resolve project root so imports work from scripts/ --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from clients.dropcatch_client import (  # noqa: E402
    BackorderResult,
    BulkBackorderResult,
    DropCatchAuthError,
    DropCatchClient,
    DropCatchError,
)

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
_VALID_TIERS: Final[tuple[str, ...]] = ("critical", "high", "medium", "low", "all")
_MAX_DOMAINS: Final[int] = 100  # DropCatch v2 API bulk limit
_STANDARD_PRICE: Final[float] = 59.00
_BUDGET_CAP_USD: Final[float] = 5000.00  # Maximum total backorder commitment
_DROPCATCH_BROWSE_URL: Final[str] = "https://www.dropcatch.com/snap/listing/{domain}"

_MONITORED_PATH: Final[Path] = _PROJECT_ROOT / "scripts" / "monitored_domains.json"
_RESULTS_PATH: Final[Path] = _PROJECT_ROOT / "data" / "sprint29_dropcatch_backorders.json"
_LOG_PATH: Final[Path] = _PROJECT_ROOT / "logs" / "dropcatch_backorders.log"

_CREDS_HELP: Final[str] = """
DropCatch API credentials not configured. To set up:
  1. Create NameBright account: https://www.namebright.com/NewAccount
  2. Enable API access: https://www.namebright.com/Settings#Api
  3. Grant "Register Domains" permission
  4. Log into DropCatch.com with NameBright credentials at least once
  5. Add to .env:
       DROPCATCH_CLIENT_ID=accountname:appname
       DROPCATCH_CLIENT_SECRET=your_secret_here
"""

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
_LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(message)s"


def _setup_logging() -> logging.Logger:
    """Configure file + console logging. Returns bound logger."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("dropcatch_backorders")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(str(_LOG_PATH), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(ch)

    assert len(logger.handlers) >= 2, "Logging handlers not attached"
    return logger


log: logging.Logger = _setup_logging()


# ---------------------------------------------------------------------------
# Data models (frozen)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BackorderTarget:
    """A domain eligible for DropCatch backorder."""
    domain: str
    tier: str
    max_bid: int
    etv: int
    notes: str

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.tier in ("critical", "high", "medium", "low"), (
            f"Invalid tier: {self.tier}"
        )


@dataclass(frozen=True)
class BackorderAttempt:
    """Result of a single backorder attempt."""
    domain: str
    tier: str
    max_bid: int
    success: bool
    message: str
    method: str  # "api", "browser", "dry_run"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_monitored_domains(path: Path) -> dict[str, Any]:
    """Load and validate monitored_domains.json."""
    assert path.exists(), f"File not found: {path}"
    assert path.suffix == ".json", "Expected a .json file"
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    tier_data = raw.get("active_targets") or raw.get("domains")
    assert tier_data is not None, "JSON must have 'active_targets' or 'domains' key"
    return raw


def filter_targets(
    data: dict[str, Any],
    tier_filter: str,
    single_domain: str | None,
) -> list[BackorderTarget]:
    """Filter monitored domains by tier and max_bid > 0."""
    assert isinstance(data, dict), "Data must be dict"
    assert tier_filter in _VALID_TIERS, f"Invalid tier: {tier_filter}"

    tier_data = data.get("active_targets") or data.get("domains", {})
    tiers_to_scan: list[str] = (
        ["critical", "high", "medium", "low"] if tier_filter == "all"
        else [tier_filter]
    )

    targets: list[BackorderTarget] = []
    for tier in tiers_to_scan:
        entries = tier_data.get(tier, [])
        for idx, entry in enumerate(entries):
            if idx >= _MAX_DOMAINS:
                break
            domain = entry.get("domain", "")
            if single_domain and domain.lower() != single_domain.lower():
                continue
            max_bid = int(entry.get("max_bid", 0))
            if max_bid <= 0:
                continue
            targets.append(BackorderTarget(
                domain=domain,
                tier=tier,
                max_bid=max_bid,
                etv=int(entry.get("etv", 0)),
                notes=entry.get("notes", "")[:120],
            ))

    assert len(targets) <= _MAX_DOMAINS, f"Too many targets: {len(targets)}"
    return targets


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------
def enforce_budget(
    targets: list[BackorderTarget],
    price_per_domain: float,
    budget_cap: float,
) -> list[BackorderTarget]:
    """Trim targets list to stay within budget cap."""
    assert price_per_domain > 0, "Price must be positive"
    assert budget_cap > 0, "Budget cap must be positive"

    max_count = int(budget_cap / price_per_domain)
    if len(targets) > max_count:
        log.warning(
            "Budget cap: trimming %d -> %d targets (cap=$%.0f, price=$%.2f)",
            len(targets), max_count, budget_cap, price_per_domain,
        )
        targets = targets[:max_count]
    return targets


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------
def _load_credentials() -> tuple[str, str]:
    """Load DropCatch credentials from .env via Settings.

    Returns (client_id, client_secret) tuple. Both may be empty.
    """
    try:
        from config.settings import Settings  # noqa: E402
        settings = Settings()
        client_id = settings.dropcatch_client_id or ""
        client_secret = settings.dropcatch_api_secret or ""
        assert isinstance(client_id, str), "client_id must be string"
        assert isinstance(client_secret, str), "client_secret must be string"
        return client_id, client_secret
    except Exception as exc:
        log.debug("Settings load failed: %s", exc)
        return "", ""


# ---------------------------------------------------------------------------
# Backorder placement
# ---------------------------------------------------------------------------
def place_via_api(
    client: DropCatchClient,
    targets: list[BackorderTarget],
    price: float,
) -> list[BackorderAttempt]:
    """Place backorders via DropCatch v2 API (bulk)."""
    assert len(targets) > 0, "No targets to backorder"
    assert len(targets) <= _MAX_DOMAINS, f"Too many: {len(targets)}"

    domains = [t.domain for t in targets]
    tier_map = {t.domain: t for t in targets}

    try:
        result: BulkBackorderResult = client.place_backorders(
            domains=domains,
            amount=price,
            backorder_type="Standard",
        )
    except DropCatchError as exc:
        log.error("Bulk backorder API error: %s", exc)
        return [
            BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=False, message=f"API error: {str(exc)[:100]}",
                method="api",
            )
            for t in targets
        ]

    attempts: list[BackorderAttempt] = []
    for br in result.results:
        target = tier_map.get(br.domain, targets[0])
        attempts.append(BackorderAttempt(
            domain=br.domain, tier=target.tier, max_bid=target.max_bid,
            success=br.success, message=br.message[:120],
            method="api",
        ))

    return attempts


def place_via_browser(
    targets: list[BackorderTarget],
) -> list[BackorderAttempt]:
    """Open DropCatch pages in browser as fallback."""
    assert len(targets) > 0, "No targets"
    assert len(targets) <= _MAX_DOMAINS, "Too many"

    attempts: list[BackorderAttempt] = []
    for idx, t in enumerate(targets):
        if idx >= _MAX_DOMAINS:
            break
        url = _DROPCATCH_BROWSE_URL.format(domain=t.domain)
        try:
            webbrowser.open(url)
            attempts.append(BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=True, message=f"Browser opened: {url}",
                method="browser",
            ))
        except Exception as exc:
            attempts.append(BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=False, message=f"Browser failed: {str(exc)[:80]}",
                method="browser",
            ))
    return attempts


def place_dry_run(targets: list[BackorderTarget]) -> list[BackorderAttempt]:
    """Simulate backorder placement without any side effects."""
    assert isinstance(targets, list), "targets must be list"
    assert len(targets) <= _MAX_DOMAINS, "Too many targets"

    return [
        BackorderAttempt(
            domain=t.domain, tier=t.tier, max_bid=t.max_bid,
            success=True,
            message=f"[DRY RUN] Would backorder at ${_STANDARD_PRICE:.2f}",
            method="dry_run",
        )
        for t in targets
    ]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def build_status_table(attempts: list[BackorderAttempt]) -> str:
    """Format attempts as an aligned ASCII table."""
    assert isinstance(attempts, list), "attempts must be list"
    if not attempts:
        return "  (no domains matched filters)\n"

    hdr = f"  {'Domain':<30} {'Tier':<10} {'Bid':>6}  {'Method':<8} {'Status':<6} Message"
    sep = "  " + "-" * 100
    lines: list[str] = [hdr, sep]
    for idx, a in enumerate(attempts):
        if idx >= _MAX_DOMAINS:
            break
        tag = "OK" if a.success else "FAIL"
        lines.append(
            f"  {a.domain:<30} {a.tier:<10} ${a.max_bid:>5}  "
            f"{a.method:<8} {tag:<6} {a.message[:60]}"
        )
    lines.append(sep)
    return "\n".join(lines) + "\n"


def save_results(attempts: list[BackorderAttempt], path: Path) -> None:
    """Persist results to JSON for audit trail."""
    assert isinstance(attempts, list), "attempts must be list"
    assert path.parent.exists(), f"Directory missing: {path.parent}"

    records = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(attempts),
        "success_count": sum(1 for a in attempts if a.success),
        "fail_count": sum(1 for a in attempts if not a.success),
        "results": [
            {
                "domain": a.domain,
                "tier": a.tier,
                "max_bid": a.max_bid,
                "success": a.success,
                "message": a.message,
                "method": a.method,
            }
            for a in attempts
        ],
    }
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    log.info("Results saved to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Place DropCatch backorders for monitored domains.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/dropcatch_place_backorders.py --dry-run\n"
            "  python3 scripts/dropcatch_place_backorders.py --tier critical\n"
            "  python3 scripts/dropcatch_place_backorders.py --domain ghostautonomy.com\n"
        ),
    )
    parser.add_argument(
        "--tier", default="all", choices=list(_VALID_TIERS),
        help="Filter by priority tier (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be placed without calling API",
    )
    parser.add_argument(
        "--domain", default=None,
        help="Place backorder for a single specific domain",
    )
    parser.add_argument(
        "--price", type=float, default=_STANDARD_PRICE,
        help=f"Bid amount per domain (default: ${_STANDARD_PRICE:.2f})",
    )
    parser.add_argument(
        "--budget-cap", type=float, default=_BUDGET_CAP_USD,
        help=f"Maximum total backorder commitment (default: ${_BUDGET_CAP_USD:.0f})",
    )
    parser.add_argument(
        "--browser-fallback", action="store_true",
        help="Open browser tabs if API credentials are missing",
    )
    args = parser.parse_args(argv)
    assert isinstance(args.dry_run, bool), "dry_run parse error"
    assert args.price > 0, "Price must be positive"
    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on error."""
    args = parse_args(argv)

    # Load and filter domains
    data = load_monitored_domains(_MONITORED_PATH)
    targets = filter_targets(data, args.tier, args.domain)

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"\n  {mode}DropCatch Backorder -- tier={args.tier}, "
          f"{len(targets)} domain(s), price=${args.price:.2f}\n")

    if not targets:
        print("  No domains matched filters (check tier/domain and max_bid > 0).\n")
        return 0

    # Budget enforcement
    targets = enforce_budget(targets, args.price, args.budget_cap)

    # Dry run: no API needed
    if args.dry_run:
        attempts = place_dry_run(targets)
        print(build_status_table(attempts))
        save_results(attempts, _RESULTS_PATH)
        return 0

    # Try API, fall back to browser
    attempts = _place_with_fallback(targets, args)
    print(build_status_table(attempts))
    save_results(attempts, _RESULTS_PATH)

    ok_count = sum(1 for a in attempts if a.success)
    fail_count = len(attempts) - ok_count
    print(f"  Summary: {ok_count} succeeded, {fail_count} failed\n")
    return 0 if fail_count == 0 else 1


def _place_with_fallback(
    targets: list[BackorderTarget],
    args: argparse.Namespace,
) -> list[BackorderAttempt]:
    """Attempt API placement, falling back to browser if no creds."""
    assert len(targets) > 0, "No targets"
    assert isinstance(args, argparse.Namespace), "Invalid args"

    client_id, client_secret = _load_credentials()

    if not client_id or not client_secret:
        log.warning("DropCatch credentials not set.")
        print(_CREDS_HELP)
        if args.browser_fallback:
            log.info("Falling back to browser-based backorder...")
            return place_via_browser(targets)
        log.info("Use --browser-fallback to open browser tabs instead.")
        return [
            BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=False, message="No API credentials (add to .env)",
                method="skipped",
            )
            for t in targets
        ]

    try:
        client = DropCatchClient(client_id, client_secret)
    except (DropCatchAuthError, AssertionError) as exc:
        log.error("DropCatch auth failed: %s", exc)
        if args.browser_fallback:
            log.info("Falling back to browser-based backorder...")
            return place_via_browser(targets)
        return [
            BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=False, message=f"Auth failed: {str(exc)[:80]}",
                method="api",
            )
            for t in targets
        ]

    try:
        return place_via_api(client, targets, args.price)
    except Exception as exc:
        log.error("API placement failed: %s", exc)
        if args.browser_fallback:
            log.info("Falling back to browser-based backorder...")
            return place_via_browser(targets)
        return [
            BackorderAttempt(
                domain=t.domain, tier=t.tier, max_bid=t.max_bid,
                success=False, message=f"API error: {str(exc)[:80]}",
                method="api",
            )
            for t in targets
        ]
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

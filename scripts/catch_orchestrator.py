#!/usr/bin/env python3
"""Catch Orchestrator -- Unified DropCatch + Dynadot + NameBright catch pipeline.

Mission control for the domain catch window. Reads monitored_domains.json,
identifies domains within the catch window, places multi-platform backorders,
monitors auction status, and dispatches notifications for critical events.

Run:     python scripts/catch_orchestrator.py
Dry-run: python scripts/catch_orchestrator.py --dry-run
Single:  python scripts/catch_orchestrator.py --domain cytheris.com
Status:  python scripts/catch_orchestrator.py --status
Tier:    python scripts/catch_orchestrator.py --tier critical

NASA Power of 10: functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, frozen dataclasses, all return values checked.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final

# -- Resolve project root so clients/ and config/ imports work --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
_SCRIPT_DIR: Final[Path] = Path(__file__).resolve().parent
_DATA_DIR: Final[Path] = _PROJECT_ROOT / "data"
_MONITORED_PATH: Final[Path] = _SCRIPT_DIR / "monitored_domains.json"
_CATCH_WINDOW_DAYS: Final[int] = 90
_MAX_DOMAINS: Final[int] = 200
_MAX_TIERS: Final[int] = 10
_VALID_TIERS: Final[tuple[str, ...]] = ("critical", "high", "medium", "low")
_DC_STANDARD_PRICE: Final[float] = 59.00
_DC_CRITICAL_PRICE: Final[float] = 69.00
_DY_BACKORDER_PRICE: Final[float] = 10.99
_GODADDY_AUCTION_URL: Final[str] = (
    "https://auctions.godaddy.com/trpItemListing.aspx"
    "?miession=searchitem&searchterm={domain}"
)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CatchTarget:
    """A single domain target in the catch window."""

    domain: str
    tier: str
    drop_est: str
    days_until_drop: int
    max_bid: float
    etv: float
    registrar: str
    notes: str

    def __post_init__(self) -> None:
        assert "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.tier in _VALID_TIERS, f"Invalid tier: {self.tier}"


@dataclass(frozen=True)
class PlatformStatus:
    """Status of a single backorder platform."""

    name: str
    available: bool
    status_text: str
    detail: str

    def __post_init__(self) -> None:
        assert len(self.name) > 0, "Platform name required"
        assert isinstance(self.available, bool), "available must be bool"


@dataclass(frozen=True)
class BackorderAction:
    """Record of a backorder action taken on a domain."""

    domain: str
    platform: str
    status: str  # "placed", "pending", "skipped", "failed", "dry_run"
    message: str
    price: float

    def __post_init__(self) -> None:
        assert "." in self.domain, f"Invalid domain: {self.domain}"
        assert self.platform in ("dropcatch", "dynadot", "godaddy"), (
            f"Unknown platform: {self.platform}"
        )


@dataclass
class OrchestratorState:
    """Mutable state accumulated during orchestration (not frozen)."""

    targets: list[CatchTarget] = field(default_factory=list)
    actions: list[BackorderAction] = field(default_factory=list)
    platform_statuses: list[PlatformStatus] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Config & data loading
# ---------------------------------------------------------------------------
def load_monitored_domains(path: Path) -> dict[str, Any]:
    """Load and validate monitored_domains.json."""
    assert path.exists(), f"Monitored domains file not found: {path}"
    assert path.suffix == ".json", f"Expected .json file: {path}"

    with open(path, "r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)

    assert "active_targets" in data, "Missing 'active_targets' key"
    assert isinstance(data["active_targets"], dict), "active_targets must be dict"
    return data


def parse_drop_date(drop_est: str) -> date | None:
    """Parse a drop_est string into a date object. Returns None for TBD/empty."""
    assert isinstance(drop_est, str), "drop_est must be a string"

    cleaned: str = drop_est.strip()
    if not cleaned or cleaned.upper() == "TBD":
        return None

    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        logger.warning("invalid_drop_date", drop_est=drop_est)
        return None


def build_catch_targets(
    data: dict[str, Any],
    today: date,
    window_days: int = _CATCH_WINDOW_DAYS,
    tier_filter: str | None = None,
    domain_filter: str | None = None,
) -> list[CatchTarget]:
    """Extract domains within the catch window from monitored_domains.json.

    Returns targets sorted by drop_est ascending (earliest first).
    """
    assert "active_targets" in data, "Missing active_targets"
    assert window_days > 0, f"window_days must be positive: {window_days}"

    targets: list[CatchTarget] = []
    active: dict[str, list[dict[str, Any]]] = data["active_targets"]

    tier_count: int = 0
    for tier_name, entries in active.items():
        if tier_count >= _MAX_TIERS:
            break
        tier_count += 1

        if tier_name not in _VALID_TIERS:
            continue
        if tier_filter and tier_name != tier_filter:
            continue

        entry_count: int = 0
        for entry in entries:
            if entry_count >= _MAX_DOMAINS:
                break
            entry_count += 1

            domain: str = entry.get("domain", "")
            if not domain or "." not in domain:
                continue
            if domain_filter and domain != domain_filter:
                continue

            drop_est_str: str = entry.get("drop_est", "")
            drop_date: date | None = parse_drop_date(drop_est_str)

            # Skip domains with no drop estimate (TBD or empty)
            if drop_date is None:
                continue

            days_until: int = (drop_date - today).days

            # Only include domains within the catch window
            if days_until > window_days:
                continue

            targets.append(CatchTarget(
                domain=domain,
                tier=tier_name,
                drop_est=drop_est_str,
                days_until_drop=days_until,
                max_bid=float(entry.get("max_bid", _DC_STANDARD_PRICE)),
                etv=float(entry.get("etv", 0)),
                registrar=entry.get("registrar", "unknown"),
                notes=entry.get("notes", ""),
            ))

    # Sort by days_until_drop ascending (earliest drops first)
    targets.sort(key=lambda t: t.days_until_drop)
    assert isinstance(targets, list), "targets must be a list"
    return targets


# ---------------------------------------------------------------------------
# Platform checks
# ---------------------------------------------------------------------------
def check_dropcatch_platform(settings: Settings) -> PlatformStatus:
    """Check DropCatch API availability and credentials."""
    assert isinstance(settings, Settings), "settings must be Settings"

    has_creds: bool = bool(
        settings.dropcatch_client_id and settings.dropcatch_api_secret
    )
    if not has_creds:
        return PlatformStatus(
            name="DropCatch",
            available=False,
            status_text="[SKIP] No credentials",
            detail="Set DROPCATCH_CLIENT_ID and DROPCATCH_API_SECRET",
        )

    # Try authenticating
    try:
        from clients.dropcatch_client import DropCatchClient

        with DropCatchClient(
            settings.dropcatch_client_id,
            settings.dropcatch_api_secret,
        ) as client:
            # Verify token works by listing backorders (lightweight call).
            # list_backorders() now always returns a list (unwraps dict
            # wrappers internally), but guard defensively here too.
            raw: Any = client.list_backorders(size=1)
            existing: list[dict[str, Any]] = raw if isinstance(raw, list) else []
            return PlatformStatus(
                name="DropCatch",
                available=True,
                status_text="[OK] Authenticated",
                detail=f"{len(existing)} existing backorder(s) found",
            )
    except Exception as exc:
        return PlatformStatus(
            name="DropCatch",
            available=False,
            status_text=f"[FAIL] {type(exc).__name__}",
            detail=str(exc)[:200],
        )


def check_dynadot_platform(settings: Settings) -> PlatformStatus:
    """Check Dynadot API availability and credentials."""
    assert isinstance(settings, Settings), "settings must be Settings"

    if not settings.dynadot_api_key:
        return PlatformStatus(
            name="Dynadot",
            available=False,
            status_text="[SKIP] No API key",
            detail="Set DYNADOT_API_KEY in .env",
        )

    return PlatformStatus(
        name="Dynadot",
        available=True,
        status_text="[OK] API key configured",
        detail=f"Key: {settings.dynadot_api_key[:6]}...{settings.dynadot_api_key[-4:]}",
    )


def check_godaddy_platform() -> PlatformStatus:
    """Check GoDaddy watchlist status (manual — no API for auctions)."""
    return PlatformStatus(
        name="GoDaddy Watch",
        available=True,
        status_text="[OK] Manual watchlist",
        detail="GoDaddy auctions require manual monitoring",
    )


# ---------------------------------------------------------------------------
# Backorder placement
# ---------------------------------------------------------------------------
def place_dropcatch_backorder(
    target: CatchTarget,
    settings: Settings,
    dry_run: bool,
) -> BackorderAction:
    """Place a DropCatch backorder for a single domain."""
    assert "." in target.domain, f"Invalid domain: {target.domain}"
    assert isinstance(dry_run, bool), "dry_run must be bool"

    if not settings.dropcatch_client_id or not settings.dropcatch_api_secret:
        return BackorderAction(
            domain=target.domain, platform="dropcatch",
            status="skipped", message="No credentials configured",
            price=0.0,
        )

    price: float = (
        _DC_CRITICAL_PRICE if target.tier == "critical" else _DC_STANDARD_PRICE
    )
    if target.max_bid > price:
        price = target.max_bid

    if dry_run:
        return BackorderAction(
            domain=target.domain, platform="dropcatch",
            status="dry_run", message=f"Would place backorder at ${price:.2f}",
            price=price,
        )

    try:
        from clients.dropcatch_client import DropCatchClient

        with DropCatchClient(
            settings.dropcatch_client_id,
            settings.dropcatch_api_secret,
        ) as client:
            result = client.place_backorders([target.domain], amount=price)
            if result.results and result.results[0].success:
                return BackorderAction(
                    domain=target.domain, platform="dropcatch",
                    status="placed", message=result.results[0].message,
                    price=price,
                )
            msg: str = (
                result.results[0].message if result.results
                else "No result returned"
            )
            return BackorderAction(
                domain=target.domain, platform="dropcatch",
                status="failed", message=msg, price=price,
            )
    except Exception as exc:
        return BackorderAction(
            domain=target.domain, platform="dropcatch",
            status="failed", message=f"{type(exc).__name__}: {str(exc)[:150]}",
            price=price,
        )


async def place_dynadot_backorder(
    target: CatchTarget,
    settings: Settings,
    dry_run: bool,
) -> BackorderAction:
    """Place a Dynadot backorder for a single domain."""
    assert "." in target.domain, f"Invalid domain: {target.domain}"
    assert isinstance(dry_run, bool), "dry_run must be bool"

    if not settings.dynadot_api_key:
        return BackorderAction(
            domain=target.domain, platform="dynadot",
            status="skipped", message="No API key configured",
            price=0.0,
        )

    if dry_run:
        return BackorderAction(
            domain=target.domain, platform="dynadot",
            status="dry_run",
            message=f"Would place backorder at ${_DY_BACKORDER_PRICE:.2f}",
            price=_DY_BACKORDER_PRICE,
        )

    try:
        from clients.dynadot_client import DynadotClient

        client = DynadotClient(settings, dry_run=False)
        result = await client.backorder(target.domain)
        status: str = "placed" if result.success else "failed"
        return BackorderAction(
            domain=target.domain, platform="dynadot",
            status=status, message=result.message,
            price=_DY_BACKORDER_PRICE,
        )
    except Exception as exc:
        return BackorderAction(
            domain=target.domain, platform="dynadot",
            status="failed", message=f"{type(exc).__name__}: {str(exc)[:150]}",
            price=_DY_BACKORDER_PRICE,
        )


def log_godaddy_watchlist(target: CatchTarget) -> BackorderAction:
    """Log a GoDaddy watchlist reminder (no API for auction backorders)."""
    assert "." in target.domain, f"Invalid domain: {target.domain}"

    registrar_lower: str = target.registrar.lower()
    is_godaddy: bool = "godaddy" in registrar_lower or "wild west" in registrar_lower

    if not is_godaddy:
        return BackorderAction(
            domain=target.domain, platform="godaddy",
            status="skipped", message=f"Registrar is {target.registrar}, not GoDaddy",
            price=0.0,
        )

    url: str = _GODADDY_AUCTION_URL.format(domain=target.domain)
    logger.info(
        "godaddy_watchlist_reminder",
        domain=target.domain,
        url=url,
        drop_est=target.drop_est,
    )
    return BackorderAction(
        domain=target.domain, platform="godaddy",
        status="pending",
        message=f"Add to GoDaddy watchlist: {url}",
        price=0.0,
    )


# ---------------------------------------------------------------------------
# Orchestration core
# ---------------------------------------------------------------------------
async def orchestrate_single_target(
    target: CatchTarget,
    settings: Settings,
    dry_run: bool,
) -> list[BackorderAction]:
    """Place backorders across all platforms for a single target."""
    assert "." in target.domain, f"Invalid domain: {target.domain}"
    assert isinstance(dry_run, bool), "dry_run must be bool"

    actions: list[BackorderAction] = []

    # 1. DropCatch backorder (synchronous)
    dc_action: BackorderAction = place_dropcatch_backorder(
        target, settings, dry_run
    )
    actions.append(dc_action)
    logger.info("dropcatch_action", domain=target.domain, status=dc_action.status)

    # 2. Dynadot backorder (async)
    dy_action: BackorderAction = await place_dynadot_backorder(
        target, settings, dry_run
    )
    actions.append(dy_action)
    logger.info("dynadot_action", domain=target.domain, status=dy_action.status)

    # 3. GoDaddy watchlist (log only)
    gd_action: BackorderAction = log_godaddy_watchlist(target)
    actions.append(gd_action)

    return actions


async def orchestrate_all(
    targets: list[CatchTarget],
    settings: Settings,
    dry_run: bool,
) -> OrchestratorState:
    """Run full catch orchestration for all targets."""
    assert isinstance(targets, list), "targets must be a list"
    assert len(targets) <= _MAX_DOMAINS, f"Too many targets: {len(targets)}"

    state = OrchestratorState(dry_run=dry_run)

    # Check platform availability
    state.platform_statuses.append(check_dropcatch_platform(settings))
    state.platform_statuses.append(check_dynadot_platform(settings))
    state.platform_statuses.append(check_godaddy_platform())

    state.targets = list(targets)

    # Process each target (bounded loop)
    for idx, target in enumerate(targets):
        if idx >= _MAX_DOMAINS:
            break
        try:
            actions: list[BackorderAction] = await orchestrate_single_target(
                target, settings, dry_run
            )
            state.actions.extend(actions)
        except Exception as exc:
            err_msg: str = f"{target.domain}: {type(exc).__name__}: {exc}"
            state.errors.append(err_msg)
            logger.error("orchestration_error", domain=target.domain, error=str(exc))

    return state


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def send_catch_notifications(state: OrchestratorState) -> None:
    """Send notifications for critical catch events."""
    assert isinstance(state, OrchestratorState), "state must be OrchestratorState"

    imminent: list[CatchTarget] = [
        t for t in state.targets if t.days_until_drop <= 7
    ]

    if not imminent:
        return

    try:
        from scripts.notify import send_alert, format_domain_alert

        for target in imminent:
            if target.days_until_drop <= 0:
                event: str = "DROP IMMINENT (past estimated date)"
            elif target.days_until_drop <= 3:
                event = f"DROPPING IN {target.days_until_drop} DAYS"
            else:
                event = f"Drop in {target.days_until_drop} days"

            subject, body = format_domain_alert(
                domain=target.domain,
                event=event,
                price=target.max_bid,
                extra=f"Tier: {target.tier} | Registrar: {target.registrar}",
            )
            priority: str = (
                "critical" if target.days_until_drop <= 3 else "high"
            )
            if not state.dry_run:
                send_alert(subject, body, priority=priority)
            else:
                logger.info(
                    "notification_dry_run",
                    domain=target.domain,
                    priority=priority,
                )
    except ImportError:
        logger.warning("notify_import_failed", msg="scripts.notify not available")
    except Exception as exc:
        logger.error("notification_error", error=str(exc))


# ---------------------------------------------------------------------------
# Status output
# ---------------------------------------------------------------------------
def format_backorder_status(
    actions: list[BackorderAction], domain: str, platform: str
) -> str:
    """Get a short status string for a domain on a platform."""
    assert isinstance(domain, str), "domain must be string"
    assert isinstance(platform, str), "platform must be string"

    for action in actions:
        if action.domain == domain and action.platform == platform:
            return action.status
    return "-"


def print_status_report(state: OrchestratorState, today: date) -> None:
    """Print the formatted catch orchestrator status report."""
    assert isinstance(state, OrchestratorState), "state must be OrchestratorState"
    assert isinstance(today, date), "today must be a date"

    mode_label: str = " (DRY RUN)" if state.dry_run else ""
    print(f"\nCATCH ORCHESTRATOR -- STATUS REPORT{mode_label}")
    print("=" * 72)
    print(f"Date: {today.isoformat()}  |  Catch Window: {_CATCH_WINDOW_DAYS} days")

    # Imminent drops
    if state.targets:
        print(f"\nIMMINENT DROPS (within {_CATCH_WINDOW_DAYS} days):")
        header: str = (
            f"  {'Domain':<25} {'Drop Est':<12} {'Days':<6} "
            f"{'Tier':<10} {'Registrar':<18} {'DC':<10} {'DY':<10}"
        )
        print(header)
        print("  " + "-" * 89)
        for target in state.targets:
            dc_st: str = format_backorder_status(
                state.actions, target.domain, "dropcatch"
            )
            dy_st: str = format_backorder_status(
                state.actions, target.domain, "dynadot"
            )
            registrar_short: str = target.registrar[:16]
            print(
                f"  {target.domain:<25} {target.drop_est:<12} "
                f"{target.days_until_drop:<6} {target.tier:<10} "
                f"{registrar_short:<18} {dc_st:<10} {dy_st:<10}"
            )
    else:
        print("\n  No domains currently in the catch window.")

    # Platform status
    print(f"\nPLATFORM STATUS:")
    for ps in state.platform_statuses:
        print(f"  {ps.name + ':':<16} {ps.status_text}  ({ps.detail})")

    # Actions summary
    dc_placed: int = sum(
        1 for a in state.actions
        if a.platform == "dropcatch" and a.status in ("placed", "dry_run")
    )
    dy_placed: int = sum(
        1 for a in state.actions
        if a.platform == "dynadot" and a.status in ("placed", "dry_run")
    )
    gd_watched: int = sum(
        1 for a in state.actions
        if a.platform == "godaddy" and a.status == "pending"
    )
    dc_failed: int = sum(
        1 for a in state.actions
        if a.platform == "dropcatch" and a.status == "failed"
    )
    dy_failed: int = sum(
        1 for a in state.actions
        if a.platform == "dynadot" and a.status == "failed"
    )

    print(f"\nACTIONS TAKEN:")
    print(f"  {dc_placed} DropCatch backorder(s) placed")
    print(f"  {dy_placed} Dynadot backorder(s) placed")
    print(f"  {gd_watched} GoDaddy watchlist reminder(s)")
    if dc_failed or dy_failed:
        print(f"  {dc_failed + dy_failed} backorder(s) FAILED")

    # Errors
    if state.errors:
        print(f"\nERRORS ({len(state.errors)}):")
        for err in state.errors[:20]:  # bounded output
            print(f"  - {err}")

    print("=" * 72)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def save_catch_status(state: OrchestratorState, today: date) -> Path:
    """Save catch status to data/catch_status_{date}.json."""
    assert isinstance(state, OrchestratorState), "state must be OrchestratorState"
    assert isinstance(today, date), "today must be a date"

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path: Path = _DATA_DIR / f"catch_status_{today.isoformat()}.json"

    targets_serialized: list[dict[str, Any]] = [
        {
            "domain": t.domain,
            "tier": t.tier,
            "drop_est": t.drop_est,
            "days_until_drop": t.days_until_drop,
            "max_bid": t.max_bid,
            "etv": t.etv,
            "registrar": t.registrar,
        }
        for t in state.targets
    ]

    actions_serialized: list[dict[str, Any]] = [
        {
            "domain": a.domain,
            "platform": a.platform,
            "status": a.status,
            "message": a.message,
            "price": a.price,
        }
        for a in state.actions
    ]

    platforms_serialized: list[dict[str, Any]] = [
        {
            "name": p.name,
            "available": p.available,
            "status_text": p.status_text,
        }
        for p in state.platform_statuses
    ]

    output: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": today.isoformat(),
        "dry_run": state.dry_run,
        "catch_window_days": _CATCH_WINDOW_DAYS,
        "summary": {
            "total_targets": len(state.targets),
            "total_actions": len(state.actions),
            "errors": len(state.errors),
        },
        "targets": targets_serialized,
        "actions": actions_serialized,
        "platforms": platforms_serialized,
        "errors": state.errors[:50],  # bounded
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    logger.info("catch_status_saved", path=str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Status-only mode
# ---------------------------------------------------------------------------
def show_current_status(today: date) -> int:
    """Show the most recent catch status file without running orchestration."""
    assert isinstance(today, date), "today must be a date"

    # Find the most recent catch_status file
    if not _DATA_DIR.exists():
        print("No data directory found. Run orchestration first.")
        return 1

    status_files: list[Path] = sorted(
        _DATA_DIR.glob("catch_status_*.json"), reverse=True
    )
    if not status_files:
        print("No catch status files found. Run orchestration first.")
        return 1

    latest: Path = status_files[0]
    print(f"Latest catch status: {latest.name}")
    print("-" * 60)

    with open(latest, "r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)

    print(f"Generated: {data.get('generated_at', 'unknown')}")
    print(f"Dry run:   {data.get('dry_run', False)}")

    summary: dict[str, Any] = data.get("summary", {})
    print(f"Targets:   {summary.get('total_targets', 0)}")
    print(f"Actions:   {summary.get('total_actions', 0)}")
    print(f"Errors:    {summary.get('errors', 0)}")

    targets_data: list[dict[str, Any]] = data.get("targets", [])
    if targets_data:
        print(f"\n{'Domain':<25} {'Drop Est':<12} {'Days':<6} {'Tier':<10}")
        print("-" * 53)
        for t in targets_data[:50]:  # bounded
            print(
                f"{t.get('domain', '?'):<25} {t.get('drop_est', '?'):<12} "
                f"{t.get('days_until_drop', '?'):<6} {t.get('tier', '?'):<10}"
            )

    actions_data: list[dict[str, Any]] = data.get("actions", [])
    if actions_data:
        print(f"\n{'Domain':<25} {'Platform':<12} {'Status':<10} {'Price':<8}")
        print("-" * 55)
        for a in actions_data[:100]:  # bounded
            price_str: str = (
                f"${a.get('price', 0):.2f}" if a.get("price", 0) > 0 else "-"
            )
            print(
                f"{a.get('domain', '?'):<25} {a.get('platform', '?'):<12} "
                f"{a.get('status', '?'):<10} {price_str:<8}"
            )

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Catch Orchestrator -- Unified backorder pipeline",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without placing real backorders",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Process a single domain only",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current catch status from last run",
    )
    parser.add_argument(
        "--tier",
        type=str,
        default=None,
        choices=list(_VALID_TIERS),
        help="Filter to a specific tier",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=_CATCH_WINDOW_DAYS,
        help=f"Catch window in days (default: {_CATCH_WINDOW_DAYS})",
    )

    assert parser is not None, "Parser creation failed"
    return parser


async def async_main(args: argparse.Namespace) -> int:
    """Async entry point for the orchestrator."""
    assert isinstance(args, argparse.Namespace), "args must be Namespace"

    today: date = date.today()

    # Status-only mode
    if args.status:
        return show_current_status(today)

    # Load settings
    settings = Settings()

    # Load monitored domains
    data: dict[str, Any] = load_monitored_domains(_MONITORED_PATH)

    # Build catch targets
    targets: list[CatchTarget] = build_catch_targets(
        data,
        today=today,
        window_days=args.window,
        tier_filter=args.tier,
        domain_filter=args.domain,
    )

    if not targets:
        print("\nNo domains currently in the catch window.")
        if args.domain:
            print(f"  Domain '{args.domain}' not found or has no drop estimate.")
        if args.tier:
            print(f"  Tier filter: {args.tier}")
        return 0

    # Run orchestration
    state: OrchestratorState = await orchestrate_all(
        targets, settings, dry_run=args.dry_run
    )

    # Print report
    print_status_report(state, today)

    # Save status
    output_path: Path = save_catch_status(state, today)
    print(f"\nStatus saved to: {output_path}")

    # Send notifications (skip in dry_run for imminent domains)
    send_catch_notifications(state)

    return 0


def main() -> int:
    """CLI entry point."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())

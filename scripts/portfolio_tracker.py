#!/usr/bin/env python3
"""Domain Hunter Portfolio Tracker.

Track domain acquisitions, listings, sales, and ROI.

Usage:
    python3 scripts/portfolio_tracker.py                          # Show portfolio
    python3 scripts/portfolio_tracker.py add DOMAIN --cost 10.99 --method direct_registration
    python3 scripts/portfolio_tracker.py list DOMAIN --price 1500 --platform afternic
    python3 scripts/portfolio_tracker.py sell DOMAIN --price 500 --buyer "John Doe"
    python3 scripts/portfolio_tracker.py stats                    # Portfolio statistics
    python3 scripts/portfolio_tracker.py show                     # ASCII table

NASA P10: functions <60 lines, min 2 assertions, fixed loop bounds, no global mutable state.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, List, Optional, Tuple

# ── Constants (immutable) ────────────────────────────────────────────
_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_PORTFOLIO_PATH: Final[str] = os.path.join(_ROOT, "data", "portfolio.json")
_MAX_DOMAINS: Final[int] = 500
_VALID_METHODS: Final[Tuple[str, ...]] = (
    "direct_registration", "backorder_catch", "auction_win",
)
_VALID_PLATFORMS: Final[Tuple[str, ...]] = (
    "afternic", "dan", "sedo", "manual",
)
_VALID_STRATEGIES: Final[Tuple[str, ...]] = ("FLIP", "DEVELOP", "HOLD")
_VALID_SOURCES: Final[Tuple[str, ...]] = (
    "kaggle_reaper", "drop_monitor", "manual", "startup_reaper",
    "godaddy_auction", "dropcatch", "snapnames", "dynadot",
)
_VALID_STATUSES: Final[Tuple[str, ...]] = (
    "OWNED", "FOR_SALE", "SOLD", "EXPIRED",
)


# ── Data I/O ─────────────────────────────────────────────────────────
def _load_portfolio() -> dict:
    """Load portfolio from JSON file."""
    assert isinstance(_PORTFOLIO_PATH, str), "Path must be str"
    assert _PORTFOLIO_PATH.endswith(".json"), "Must be .json file"

    if not os.path.isfile(_PORTFOLIO_PATH):
        return {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "schema_version": "1.0",
            "domains": [],
            "summary": {
                "total_invested": 0,
                "total_revenue": 0,
                "total_roi": 0,
                "domains_owned": 0,
                "domains_sold": 0,
                "domains_listed": 0,
            },
        }

    with open(_PORTFOLIO_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "Portfolio must be dict"
    return data


def _save_portfolio(data: dict) -> None:
    """Save portfolio to JSON file."""
    assert isinstance(data, dict), "Portfolio must be dict"
    assert "domains" in data, "Portfolio must have domains key"

    data["summary"] = _compute_summary(data["domains"])
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    os.makedirs(os.path.dirname(_PORTFOLIO_PATH), exist_ok=True)
    with open(_PORTFOLIO_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _compute_summary(domains: list) -> dict:
    """Recompute summary statistics from domain list."""
    assert isinstance(domains, list), "Domains must be list"

    total_invested = 0.0
    total_revenue = 0.0
    owned = 0
    sold = 0
    listed = 0

    for i, d in enumerate(domains):
        if i >= _MAX_DOMAINS:
            break
        total_invested += float(d.get("cost", 0))
        total_revenue += float(d.get("sale_price", 0))
        status = d.get("status", "OWNED")
        if status == "OWNED":
            owned += 1
        elif status == "FOR_SALE":
            owned += 1
            listed += 1
        elif status == "SOLD":
            sold += 1

    roi = total_revenue - total_invested
    assert isinstance(roi, float), "ROI must be numeric"
    return {
        "total_invested": round(total_invested, 2),
        "total_revenue": round(total_revenue, 2),
        "total_roi": round(roi, 2),
        "domains_owned": owned,
        "domains_sold": sold,
        "domains_listed": listed,
    }


# ── Find Domain ──────────────────────────────────────────────────────
def _find_domain(domains: list, domain: str) -> Optional[int]:
    """Find domain index in portfolio list. Returns None if not found."""
    assert isinstance(domain, str) and "." in domain, "Invalid domain"
    assert isinstance(domains, list), "Domains must be list"

    needle = domain.lower().strip()
    for i, d in enumerate(domains):
        if i >= _MAX_DOMAINS:
            break
        if d.get("domain", "").lower() == needle:
            return i
    return None


# ── Commands ─────────────────────────────────────────────────────────
def cmd_add(args: argparse.Namespace) -> int:
    """Add a domain to the portfolio."""
    assert hasattr(args, "domain"), "domain required"
    assert hasattr(args, "cost"), "cost required"

    domain = args.domain.lower().strip()
    cost = float(args.cost)
    method = args.method

    if method not in _VALID_METHODS:
        print(f"ERROR: Invalid method '{method}'. Valid: {_VALID_METHODS}")
        return 1

    portfolio = _load_portfolio()
    if _find_domain(portfolio["domains"], domain) is not None:
        print(f"ERROR: {domain} already in portfolio.")
        return 1

    entry: dict[str, Any] = {
        "domain": domain,
        "cost": round(cost, 2),
        "method": method,
        "date_acquired": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "OWNED",
        "strategy": getattr(args, "strategy", "FLIP") or "FLIP",
    }

    # Optional fields
    if getattr(args, "source", None):
        if args.source in _VALID_SOURCES:
            entry["source"] = args.source
        else:
            print(f"WARNING: Unknown source '{args.source}', using anyway.")
            entry["source"] = args.source

    if getattr(args, "score", None) is not None:
        entry["score"] = float(args.score)

    if getattr(args, "sector", None):
        entry["sector"] = args.sector

    strategy = getattr(args, "strategy", None)
    if strategy:
        if strategy in _VALID_STRATEGIES:
            entry["strategy"] = strategy
        else:
            print(f"WARNING: Unknown strategy '{strategy}', using FLIP.")
            entry["strategy"] = "FLIP"

    portfolio["domains"].append(entry)
    _save_portfolio(portfolio)
    print(f"ADDED: {domain} (cost=${cost:.2f}, method={method})")
    return 0


def cmd_list_domain(args: argparse.Namespace) -> int:
    """Mark a domain as listed for sale."""
    assert hasattr(args, "domain"), "domain required"
    assert hasattr(args, "price"), "price required"

    domain = args.domain.lower().strip()
    price = float(args.price)
    platform = args.platform.lower().strip()

    if platform not in _VALID_PLATFORMS:
        print(f"ERROR: Invalid platform '{platform}'. Valid: {_VALID_PLATFORMS}")
        return 1

    portfolio = _load_portfolio()
    idx = _find_domain(portfolio["domains"], domain)
    if idx is None:
        print(f"ERROR: {domain} not in portfolio. Add it first.")
        return 1

    entry = portfolio["domains"][idx]
    if entry.get("status") == "SOLD":
        print(f"ERROR: {domain} is already sold.")
        return 1

    entry["status"] = "FOR_SALE"
    entry["listing_price"] = round(price, 2)
    entry["listing_platform"] = platform
    entry["listing_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    portfolio["domains"][idx] = entry
    _save_portfolio(portfolio)
    print(f"LISTED: {domain} at ${price:,.2f} on {platform}")
    return 0


def cmd_sell(args: argparse.Namespace) -> int:
    """Record a domain sale."""
    assert hasattr(args, "domain"), "domain required"
    assert hasattr(args, "price"), "price required"

    domain = args.domain.lower().strip()
    price = float(args.price)

    portfolio = _load_portfolio()
    idx = _find_domain(portfolio["domains"], domain)
    if idx is None:
        print(f"ERROR: {domain} not in portfolio.")
        return 1

    entry = portfolio["domains"][idx]
    if entry.get("status") == "SOLD":
        print(f"ERROR: {domain} is already marked as sold.")
        return 1

    entry["status"] = "SOLD"
    entry["sale_price"] = round(price, 2)
    entry["sale_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if getattr(args, "buyer", None):
        entry["buyer"] = args.buyer

    sale_platform = getattr(args, "platform", None)
    if sale_platform:
        entry["sale_platform"] = sale_platform

    cost = float(entry.get("cost", 0))
    entry["roi"] = round(price - cost, 2)
    entry["roi_pct"] = round(((price - cost) / cost * 100) if cost > 0 else 0, 1)

    portfolio["domains"][idx] = entry
    _save_portfolio(portfolio)
    print(f"SOLD: {domain} for ${price:,.2f} (ROI: ${entry['roi']:,.2f}, {entry['roi_pct']}%)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    """Show portfolio statistics."""
    assert args is not None, "Args required"

    portfolio = _load_portfolio()
    domains = portfolio.get("domains", [])
    summary = _compute_summary(domains)

    total = len(domains)
    owned = summary["domains_owned"]
    sold = summary["domains_sold"]
    listed = summary["domains_listed"]
    invested = summary["total_invested"]
    revenue = summary["total_revenue"]
    roi = summary["total_roi"]
    roi_pct = (roi / invested * 100) if invested > 0 else 0.0

    print()
    print("=" * 50)
    print("  DOMAIN HUNTER -- PORTFOLIO STATS")
    print("=" * 50)
    print()
    print(f"  Total domains:     {total}")
    print(f"  Currently owned:   {owned}")
    print(f"  Listed for sale:   {listed}")
    print(f"  Sold:              {sold}")
    print()
    print(f"  Total invested:    ${invested:,.2f}")
    print(f"  Total revenue:     ${revenue:,.2f}")
    print(f"  Net ROI:           ${roi:,.2f} ({roi_pct:+.1f}%)")
    print()

    # Per-domain breakdown
    if total > 0:
        _print_domain_breakdown(domains)

    # Average hold time for sold domains
    _print_hold_times(domains)

    # Best/worst performers
    _print_performers(domains)

    print("=" * 50)
    return 0


def _print_domain_breakdown(domains: list) -> None:
    """Print per-domain cost/status breakdown."""
    assert isinstance(domains, list), "Domains must be list"
    assert len(domains) > 0, "Must have domains"

    print("  Per-Domain Breakdown:")
    print(f"  {'Domain':<28} {'Cost':>8} {'Status':<10} {'ROI':>10}")
    print(f"  {'-'*28} {'-'*8} {'-'*10} {'-'*10}")

    for i, d in enumerate(domains):
        if i >= _MAX_DOMAINS:
            break
        name = d.get("domain", "?")[:28]
        cost = float(d.get("cost", 0))
        status = d.get("status", "?")
        roi_val = float(d.get("sale_price", 0)) - cost if status == "SOLD" else -cost
        print(f"  {name:<28} ${cost:>7.2f} {status:<10} ${roi_val:>+9.2f}")
    print()


def _print_hold_times(domains: list) -> None:
    """Print average hold time for sold domains."""
    assert isinstance(domains, list), "Domains must be list"

    sold = [d for d in domains if d.get("status") == "SOLD"]
    if not sold:
        return

    total_days = 0
    counted = 0
    for d in sold[:_MAX_DOMAINS]:
        acq = d.get("date_acquired")
        sale = d.get("sale_date")
        if acq and sale:
            try:
                d_acq = datetime.strptime(acq, "%Y-%m-%d")
                d_sale = datetime.strptime(sale, "%Y-%m-%d")
                total_days += (d_sale - d_acq).days
                counted += 1
            except ValueError:
                continue

    if counted > 0:
        avg = total_days / counted
        print(f"  Average hold time (sold): {avg:.0f} days")
        print()


def _print_performers(domains: list) -> None:
    """Print best and worst performing domains."""
    assert isinstance(domains, list), "Domains must be list"

    sold = [d for d in domains if d.get("status") == "SOLD"]
    if not sold:
        return

    best = max(sold, key=lambda d: float(d.get("roi", 0)))
    worst = min(sold, key=lambda d: float(d.get("roi", 0)))

    best_roi = float(best.get("roi", 0))
    worst_roi = float(worst.get("roi", 0))

    print(f"  Best performer:  {best.get('domain', '?')} (${best_roi:+,.2f})")
    print(f"  Worst performer: {worst.get('domain', '?')} (${worst_roi:+,.2f})")
    print()


# ── ASCII Table ──────────────────────────────────────────────────────
def cmd_show(args: argparse.Namespace) -> int:
    """Display portfolio as ASCII table."""
    assert args is not None, "Args required"

    portfolio = _load_portfolio()
    domains = portfolio.get("domains", [])
    summary = _compute_summary(domains)

    if not domains:
        print("\n  Portfolio is empty. Use 'add' to add domains.\n")
        return 0

    # Column widths
    w_dom = 26
    w_cost = 11
    w_list = 12
    w_plat = 11
    w_stat = 10
    w_roi = 9

    # Borders
    top = (
        f"\u2554{'='*w_dom}\u2566{'='*w_cost}\u2566{'='*w_list}"
        f"\u2566{'='*w_plat}\u2566{'='*w_stat}\u2566{'='*w_roi}\u2557"
    )
    mid = (
        f"\u2560{'='*w_dom}\u256c{'='*w_cost}\u256c{'='*w_list}"
        f"\u256c{'='*w_plat}\u256c{'='*w_stat}\u256c{'='*w_roi}\u2563"
    )
    bot = (
        f"\u255a{'='*w_dom}\u2569{'='*w_cost}\u2569{'='*w_list}"
        f"\u2569{'='*w_plat}\u2569{'='*w_stat}\u2569{'='*w_roi}\u255d"
    )

    def row(dom: str, cost: str, lst: str, plat: str, stat: str, roi: str) -> str:
        return (
            f"\u2551 {dom:<{w_dom-2}} "
            f"\u2551 {cost:<{w_cost-2}} "
            f"\u2551 {lst:<{w_list-2}} "
            f"\u2551 {plat:<{w_plat-2}} "
            f"\u2551 {stat:<{w_stat-2}} "
            f"\u2551 {roi:<{w_roi-2}} \u2551"
        )

    print()
    print(top)
    print(row("Domain", "Cost", "Listed At", "Platform", "Status", "ROI"))
    print(mid)

    for i, d in enumerate(domains):
        if i >= _MAX_DOMAINS:
            break
        name = d.get("domain", "?")[:24]
        cost_val = float(d.get("cost", 0))
        cost_str = f"${cost_val:,.2f}"

        listing_price = d.get("listing_price")
        list_str = f"${listing_price:,.0f}" if listing_price else ""

        platform = (d.get("listing_platform") or d.get("sale_platform") or "")
        plat_str = platform.title()[:9]

        status = d.get("status", "OWNED")

        if status == "SOLD":
            sale_price = float(d.get("sale_price", 0))
            roi_val = sale_price - cost_val
        else:
            roi_val = -cost_val
        roi_str = f"${roi_val:+,.0f}"

        print(row(name, cost_str, list_str, plat_str, status, roi_str))

    print(mid)

    # Summary row
    total_cost = f"${summary['total_invested']:,.2f}"
    total_roi = summary["total_roi"]
    owned_str = f"{summary['domains_owned']} owned"
    roi_total = f"${total_roi:+,.0f}"
    print(row("TOTAL", total_cost, "", "", owned_str, roi_total))

    print(bot)
    print()
    return 0


# ── Portfolio Summary (for external callers) ─────────────────────────
def get_portfolio_summary() -> dict:
    """Return portfolio summary dict for use by other scripts."""
    portfolio = _load_portfolio()
    domains = portfolio.get("domains", [])
    summary = _compute_summary(domains)
    assert isinstance(summary, dict), "Summary must be dict"
    assert "total_invested" in summary, "Must have total_invested"
    return summary


# ── CLI ──────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Domain Hunter Portfolio Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subs = parser.add_subparsers(dest="command")

    # add
    p_add = subs.add_parser("add", help="Add a domain to portfolio")
    p_add.add_argument("domain", help="Domain name (e.g. example.com)")
    p_add.add_argument("--cost", required=True, type=float, help="Acquisition cost")
    p_add.add_argument(
        "--method", required=True,
        choices=list(_VALID_METHODS),
        help="Acquisition method",
    )
    p_add.add_argument("--source", help="Pipeline source (e.g. kaggle_reaper, drop_monitor)")
    p_add.add_argument("--score", type=float, help="Domain score from pipeline")
    p_add.add_argument("--sector", help="Domain sector/niche")
    p_add.add_argument(
        "--strategy", choices=list(_VALID_STRATEGIES),
        default="FLIP", help="Strategy (default: FLIP)",
    )

    # list (for sale)
    p_list = subs.add_parser("list", help="Mark domain as listed for sale")
    p_list.add_argument("domain", help="Domain name")
    p_list.add_argument("--price", required=True, type=float, help="Listing price")
    p_list.add_argument(
        "--platform", required=True,
        choices=list(_VALID_PLATFORMS),
        help="Listing platform",
    )

    # sell
    p_sell = subs.add_parser("sell", help="Record a domain sale")
    p_sell.add_argument("domain", help="Domain name")
    p_sell.add_argument("--price", required=True, type=float, help="Sale price")
    p_sell.add_argument("--buyer", help="Buyer name/entity")
    p_sell.add_argument("--platform", help="Platform where sold")

    # stats
    subs.add_parser("stats", help="Show portfolio statistics")

    # show
    subs.add_parser("show", help="Show ASCII table of portfolio")

    assert parser is not None, "Parser creation failed"
    return parser


def main() -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    assert isinstance(args.command, str) or args.command is None, "Parse error"

    if args.command is None:
        # Default: show the ASCII table
        return cmd_show(args)

    dispatch = {
        "add": cmd_add,
        "list": cmd_list_domain,
        "sell": cmd_sell,
        "stats": cmd_stats,
        "show": cmd_show,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())

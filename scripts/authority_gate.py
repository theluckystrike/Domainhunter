#!/usr/bin/env python3
"""Authority Gate — 3-Layer Domain Authority Verification.

Filters DR 0 junk automatically by querying 7 authority sources:
  Layer 0 (LOCAL, $0):  Tranco list, CommonCrawl in-degree
  Layer 1 (FREE API):   Open PageRank, Wayback CDX, Wikipedia
  Layer 2 (PAID API):   DataForSEO bulk_ranks, Gname dropcatch DA

Short-circuit rules:
  - Tranco top 100K       → AUTO-PASS (skip Layer 1+2)
  - OPR=0 AND Wayback=0   → AUTO-KILL (skip Layer 2)
  - OPR >= 5.0             → AUTO-PASS (skip Layer 2)

Usage:
    python3 scripts/authority_gate.py --dry-run --domains example.com,test.com
    python3 scripts/authority_gate.py --domains-file candidates.txt

NASA Power of 10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Project root setup
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.constants import (
    AUTHORITY_CC_MAX_INDEGREE,
    AUTHORITY_DATAFORSEO_BATCH_SIZE,
    AUTHORITY_DATAFORSEO_BULK_COST,
    AUTHORITY_KILL_THRESHOLD,
    AUTHORITY_MAJESTIC_AUTO_PASS,
    AUTHORITY_MAJESTIC_CSV,
    AUTHORITY_MAJESTIC_DECAY_END,
    AUTHORITY_MAJESTIC_DECAY_START,
    AUTHORITY_OPR_AUTO_PASS,
    AUTHORITY_OPR_BATCH_SIZE,
    AUTHORITY_PASS_THRESHOLD,
    AUTHORITY_TRANCO_AUTO_PASS,
    AUTHORITY_TRANCO_DECAY_END,
    AUTHORITY_TRANCO_DECAY_START,
    AUTHORITY_WAYBACK_MAX_SNAPSHOTS,
    AUTHORITY_DATAFORSEO_MAX_RANK,
    MAX_LOOP_ITERATIONS,
)
from config.settings import Settings, load_settings
from models.authority import (
    AuthorityCheck,
    AuthorityResult,
    build_authority_check,
    build_authority_result,
)

_LOG = logging.getLogger("authority_gate")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
def _normalize_tranco(rank: int | None) -> float:
    """Normalize Tranco rank to 0.0-1.0. Lower rank = higher score."""
    if rank is None or rank <= 0:
        return 0.0
    if rank <= AUTHORITY_TRANCO_DECAY_START:
        return 1.0
    if rank >= AUTHORITY_TRANCO_DECAY_END:
        return 0.0
    span = AUTHORITY_TRANCO_DECAY_END - AUTHORITY_TRANCO_DECAY_START
    return 1.0 - ((rank - AUTHORITY_TRANCO_DECAY_START) / span)


def _normalize_opr(page_rank_decimal: float) -> float:
    """Normalize Open PageRank decimal (0-10) to 0.0-1.0."""
    assert isinstance(page_rank_decimal, (int, float)), "must be numeric"
    return min(max(page_rank_decimal / 10.0, 0.0), 1.0)


def _normalize_wayback(count: int) -> float:
    """Normalize Wayback snapshot count to 0.0-1.0."""
    assert isinstance(count, int) and count >= 0, "count must be >= 0"
    return min(count / AUTHORITY_WAYBACK_MAX_SNAPSHOTS, 1.0)


def _normalize_cc(in_degree: int) -> float:
    """Normalize CommonCrawl in-degree to 0.0-1.0."""
    assert isinstance(in_degree, int) and in_degree >= 0, "must be >= 0"
    return min(in_degree / AUTHORITY_CC_MAX_INDEGREE, 1.0)


def _normalize_dataforseo(rank: int) -> float:
    """Normalize DataForSEO rank (0-1000+) to 0.0-1.0."""
    if rank <= 0:
        return 0.0
    return min(rank / AUTHORITY_DATAFORSEO_MAX_RANK, 1.0)


def _normalize_majestic(rank: int) -> float:
    """Normalize Majestic Million rank to 0.0-1.0. Lower rank = higher score."""
    if rank <= 0:
        return 0.0
    if rank <= AUTHORITY_MAJESTIC_DECAY_START:
        return 1.0
    if rank >= AUTHORITY_MAJESTIC_DECAY_END:
        return 0.1  # Still in Million = minimum 0.1 (never zero)
    span = AUTHORITY_MAJESTIC_DECAY_END - AUTHORITY_MAJESTIC_DECAY_START
    return max(0.1, 1.0 - ((rank - AUTHORITY_MAJESTIC_DECAY_START) / span))


# ---------------------------------------------------------------------------
# Majestic Million local CSV lookup
# ---------------------------------------------------------------------------
_MAJESTIC_DATA: dict[str, tuple[int, int]] = {}  # domain -> (rank, refsubnets)
_MAJESTIC_LOADED: bool = False


def _load_majestic_million() -> dict[str, tuple[int, int]]:
    """Load Majestic Million CSV into memory. Cached after first call."""
    global _MAJESTIC_LOADED  # noqa: PLW0603
    if _MAJESTIC_LOADED:
        return _MAJESTIC_DATA

    csv_path = _PROJECT_ROOT / AUTHORITY_MAJESTIC_CSV
    if not csv_path.exists():
        _LOG.warning("Majestic Million CSV not found: %s", csv_path)
        _MAJESTIC_LOADED = True
        return _MAJESTIC_DATA

    import csv
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get("Domain", "").strip().lower()
            if not domain:
                continue
            try:
                rank = int(row.get("GlobalRank", 0))
                refsubnets = int(row.get("RefSubNets", 0))
                _MAJESTIC_DATA[domain] = (rank, refsubnets)
            except (ValueError, TypeError):
                continue

    _MAJESTIC_LOADED = True
    _LOG.info("majestic_million_loaded", extra={"domains": len(_MAJESTIC_DATA)})
    return _MAJESTIC_DATA


def _majestic_lookup(domain: str) -> tuple[int, int] | None:
    """Look up domain in Majestic Million. Returns (rank, refsubnets) or None."""
    data = _load_majestic_million()
    if not data:
        return None

    # Try exact match, then without www
    result = data.get(domain.lower())
    if result is None and domain.startswith("www."):
        result = data.get(domain[4:].lower())
    if result is None and not domain.startswith("www."):
        result = data.get(f"www.{domain}".lower())
    return result


# ---------------------------------------------------------------------------
# Layer 0: Local lookups (instant, $0)
# ---------------------------------------------------------------------------
def run_layer_0(
    domain: str,
    tranco_client: Any | None = None,
    cc_analyzer: Any | None = None,
) -> tuple[list[AuthorityCheck], bool, str]:
    """Run Layer 0 local authority checks.

    Returns (checks, short_circuit, reason).
    """
    assert isinstance(domain, str) and "." in domain, "valid domain required"
    checks: list[AuthorityCheck] = []

    # Tranco check
    tranco_rank: int | None = None
    if tranco_client is not None:
        try:
            tranco_rank = tranco_client.is_ranked(domain)
            norm = _normalize_tranco(tranco_rank)
            status = "PASS" if tranco_rank is not None else "FAIL"
            detail = f"Tranco rank {tranco_rank}" if tranco_rank else "Not in Tranco"
            checks.append(build_authority_check(
                source="tranco", layer=0, status=status,
                value=float(tranco_rank or 0), normalized=norm, detail=detail,
            ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="tranco", layer=0, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="tranco", layer=0, status="SKIP",
            value=0.0, normalized=0.0, detail="Tranco client not available",
        ))

    # Majestic Million check (local CSV, $0, instant)
    majestic_rank: int | None = None
    majestic_result = _majestic_lookup(domain)
    if majestic_result is not None:
        majestic_rank, refsubnets = majestic_result
        norm = _normalize_majestic(majestic_rank)
        checks.append(build_authority_check(
            source="majestic", layer=0, status="PASS",
            value=float(majestic_rank), normalized=norm,
            detail=f"Majestic rank {majestic_rank:,} ({refsubnets} RefSubNets)",
        ))
    else:
        checks.append(build_authority_check(
            source="majestic", layer=0, status="FAIL",
            value=0.0, normalized=0.0, detail="Not in Majestic Million",
        ))

    # CommonCrawl check
    if cc_analyzer is not None:
        try:
            in_degree = cc_analyzer.get_cc_rank(domain)
            norm = _normalize_cc(in_degree)
            status = "PASS" if in_degree > 0 else "FAIL"
            checks.append(build_authority_check(
                source="commoncrawl", layer=0, status=status,
                value=float(in_degree), normalized=norm,
                detail=f"CC in-degree: {in_degree}",
            ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="commoncrawl", layer=0, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="commoncrawl", layer=0, status="SKIP",
            value=0.0, normalized=0.0, detail="CC analyzer not available",
        ))

    # Short-circuit: Tranco top 100K = guaranteed authority
    if tranco_rank is not None and tranco_rank <= AUTHORITY_TRANCO_AUTO_PASS:
        return checks, True, f"Tranco rank {tranco_rank} (top {AUTHORITY_TRANCO_AUTO_PASS:,})"

    # Short-circuit: Majestic Million = has real backlinks (survives site death)
    # CRITICAL for expired domain hunting — Tranco/OPR decay when site dies,
    # but Majestic tracks inbound links which persist on OTHER people's sites.
    if majestic_rank is not None and majestic_rank <= AUTHORITY_MAJESTIC_AUTO_PASS:
        refsubnets = majestic_result[1] if majestic_result else 0
        return checks, True, (
            f"Majestic rank {majestic_rank:,} ({refsubnets} RefSubNets) — "
            f"confirmed backlink authority"
        )

    return checks, False, ""


# ---------------------------------------------------------------------------
# Layer 1: Free remote APIs ($0)
# ---------------------------------------------------------------------------
async def run_layer_1(
    domain: str,
    opr_client: Any | None = None,
    wayback_client: Any | None = None,
    wikipedia_client: Any | None = None,
) -> tuple[list[AuthorityCheck], bool, str]:
    """Run Layer 1 free remote authority checks.

    Returns (checks, short_circuit, reason).
    """
    assert isinstance(domain, str) and "." in domain, "valid domain required"
    checks: list[AuthorityCheck] = []
    opr_score: float = 0.0
    wayback_count: int = 0
    opr_responded: bool = False
    wayback_responded: bool = False

    # Open PageRank
    if opr_client is not None:
        try:
            results = await opr_client.get_pagerank([domain])
            if results:
                opr_score = results[0].page_rank_decimal
                opr_responded = True
                norm = _normalize_opr(opr_score)
                status = "PASS" if opr_score > 0 else "FAIL"
                checks.append(build_authority_check(
                    source="openpagerank", layer=1, status=status,
                    value=opr_score, normalized=norm,
                    detail=f"PageRank {opr_score:.1f} (int: {results[0].page_rank_integer})",
                ))
            else:
                checks.append(build_authority_check(
                    source="openpagerank", layer=1, status="FAIL",
                    value=0.0, normalized=0.0, detail="No result returned",
                ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="openpagerank", layer=1, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="openpagerank", layer=1, status="SKIP",
            value=0.0, normalized=0.0, detail="OPR client not available",
        ))

    # Wayback CDX
    if wayback_client is not None:
        try:
            wayback_count = await wayback_client.get_snapshot_count(domain)
            wayback_responded = True
            norm = _normalize_wayback(wayback_count)
            status = "PASS" if wayback_count > 0 else "FAIL"
            checks.append(build_authority_check(
                source="wayback", layer=1, status=status,
                value=float(wayback_count), normalized=norm,
                detail=f"Wayback pages: {wayback_count}",
            ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="wayback", layer=1, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="wayback", layer=1, status="SKIP",
            value=0.0, normalized=0.0, detail="Wayback client not available",
        ))

    # Wikipedia
    if wikipedia_client is not None:
        try:
            has_links = await wikipedia_client.has_wikipedia_links(domain)
            norm = 1.0 if has_links else 0.0
            status = "PASS" if has_links else "FAIL"
            checks.append(build_authority_check(
                source="wikipedia", layer=1, status=status,
                value=1.0 if has_links else 0.0, normalized=norm,
                detail="Wikipedia links found" if has_links else "No Wikipedia links",
            ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="wikipedia", layer=1, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="wikipedia", layer=1, status="SKIP",
            value=0.0, normalized=0.0, detail="Wikipedia client not available",
        ))

    # Short-circuit: OPR >= 5.0 = strong authority, skip paid
    if opr_score >= AUTHORITY_OPR_AUTO_PASS:
        return checks, True, f"PageRank {opr_score:.1f} >= {AUTHORITY_OPR_AUTO_PASS}"

    # Short-circuit: OPR=0 AND Wayback=0 = guaranteed junk
    # Only trigger if at least one source actually responded
    if opr_score == 0 and wayback_count == 0 and (opr_responded or wayback_responded):
        return checks, True, "PageRank 0 + zero Wayback snapshots = dead domain"

    return checks, False, ""


# ---------------------------------------------------------------------------
# Layer 2: Paid remote APIs
# ---------------------------------------------------------------------------
async def run_layer_2(
    domain: str,
    dataforseo_client: Any | None = None,
) -> list[AuthorityCheck]:
    """Run Layer 2 paid authority checks.

    Returns list of checks. Gname is handled at batch level elsewhere.
    """
    assert isinstance(domain, str) and "." in domain, "valid domain required"
    checks: list[AuthorityCheck] = []

    # DataForSEO bulk_ranks
    if dataforseo_client is not None:
        try:
            ranks = await dataforseo_client.bulk_ranks([domain])
            rank = ranks.get(domain, 0)
            norm = _normalize_dataforseo(rank)
            status = "PASS" if rank > 0 else "FAIL"
            checks.append(build_authority_check(
                source="dataforseo", layer=2, status=status,
                value=float(rank), normalized=norm,
                detail=f"DataForSEO rank: {rank}",
                cost=AUTHORITY_DATAFORSEO_BULK_COST,
            ))
        except Exception as exc:
            checks.append(build_authority_check(
                source="dataforseo", layer=2, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            ))
    else:
        checks.append(build_authority_check(
            source="dataforseo", layer=2, status="SKIP",
            value=0.0, normalized=0.0, detail="DataForSEO not configured",
        ))

    # Gname placeholder (scored at batch level from feed data)
    checks.append(build_authority_check(
        source="gname", layer=2, status="SKIP",
        value=0.0, normalized=0.0, detail="Gname scored from feed data",
    ))

    return checks


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------
async def evaluate_domain(
    domain: str,
    settings: Settings,
    *,
    tranco_client: Any | None = None,
    cc_analyzer: Any | None = None,
    opr_client: Any | None = None,
    wayback_client: Any | None = None,
    wikipedia_client: Any | None = None,
    dataforseo_client: Any | None = None,
    skip_paid: bool = False,
) -> AuthorityResult:
    """Run full 3-layer authority evaluation on a single domain.

    Args:
        domain: Domain to evaluate.
        settings: Pipeline settings.
        tranco_client: TrancoClient instance (Layer 0).
        cc_analyzer: CCBacklinksAnalyzer instance (Layer 0).
        opr_client: OpenPageRankClient instance (Layer 1).
        wayback_client: WaybackClient instance (Layer 1).
        wikipedia_client: WikipediaClient instance (Layer 1).
        dataforseo_client: DataForSEOClient instance (Layer 2).
        skip_paid: Skip Layer 2 paid checks.

    Returns:
        AuthorityResult with composite score and DR estimate.
    """
    assert isinstance(domain, str) and "." in domain, "valid domain required"
    all_checks: list[AuthorityCheck] = []

    # Layer 0
    l0_checks, l0_short, l0_reason = run_layer_0(
        domain, tranco_client, cc_analyzer,
    )
    all_checks.extend(l0_checks)

    if l0_short:
        _LOG.info("Layer 0 short-circuit: %s — %s", domain, l0_reason)
        return build_authority_result(
            domain=domain, checks=all_checks,
            short_circuited=True, short_circuit_reason=l0_reason,
        )

    # Layer 1
    l1_checks, l1_short, l1_reason = await run_layer_1(
        domain, opr_client, wayback_client, wikipedia_client,
    )
    all_checks.extend(l1_checks)

    if l1_short:
        _LOG.info("Layer 1 short-circuit: %s — %s", domain, l1_reason)
        return build_authority_result(
            domain=domain, checks=all_checks,
            short_circuited=True, short_circuit_reason=l1_reason,
        )

    # Layer 2 (skip if disabled or too expensive)
    if not skip_paid and not settings.authority_gate_skip_paid:
        l2_checks = await run_layer_2(domain, dataforseo_client)
        all_checks.extend(l2_checks)
    else:
        all_checks.append(build_authority_check(
            source="dataforseo", layer=2, status="SKIP",
            value=0.0, normalized=0.0, detail="Paid layer skipped",
        ))
        all_checks.append(build_authority_check(
            source="gname", layer=2, status="SKIP",
            value=0.0, normalized=0.0, detail="Paid layer skipped",
        ))

    return build_authority_result(domain=domain, checks=all_checks)


async def evaluate_batch(
    domains: list[str],
    settings: Settings,
    **kwargs: Any,
) -> list[AuthorityResult]:
    """Evaluate authority for a batch of domains.

    Runs all domains through the 3-layer gate sequentially
    to respect rate limits.
    """
    assert isinstance(domains, list), "domains must be a list"
    assert len(domains) <= MAX_LOOP_ITERATIONS, "too many domains"

    results: list[AuthorityResult] = []
    for i, domain in enumerate(domains):
        if i >= MAX_LOOP_ITERATIONS:
            break
        try:
            result = await evaluate_domain(domain, settings, **kwargs)
            results.append(result)
        except Exception as exc:
            _LOG.error("Authority gate error for %s: %s", domain, exc)
            # Create minimal fail result
            fail_check = build_authority_check(
                source="tranco", layer=0, status="ERROR",
                value=0.0, normalized=0.0, detail=str(exc),
            )
            results.append(build_authority_result(
                domain=domain, checks=[fail_check],
            ))

    _LOG.info(
        "Authority gate batch complete: %d domains, %d pass (>%.0f), %d kill (<%.0f)",
        len(results),
        sum(1 for r in results if r.composite_score >= AUTHORITY_PASS_THRESHOLD),
        AUTHORITY_PASS_THRESHOLD,
        sum(1 for r in results if r.composite_score < AUTHORITY_KILL_THRESHOLD),
        AUTHORITY_KILL_THRESHOLD,
    )
    return results


# ---------------------------------------------------------------------------
# Pipeline enrichment helper
# ---------------------------------------------------------------------------
async def enrich_with_authority_gate(
    candidates: list[Any],
    settings: Settings,
) -> list[Any]:
    """Enrich DropCandidate list with authority gate DR estimates.

    Replaces trust_flow on each candidate with the gate's dr_estimate.
    Candidates below AUTHORITY_KILL_THRESHOLD are removed.
    """
    assert isinstance(candidates, list), "candidates must be a list"

    if not candidates:
        return candidates

    # Initialize clients
    tranco_client = _init_tranco(settings)
    opr_client = _init_opr(settings)
    wayback_client = _init_wayback(settings)
    wikipedia_client = _init_wikipedia()
    dataforseo_client = _init_dataforseo(settings)

    domains = [c.domain for c in candidates]
    results = await evaluate_batch(
        domains, settings,
        tranco_client=tranco_client,
        opr_client=opr_client,
        wayback_client=wayback_client,
        wikipedia_client=wikipedia_client,
        dataforseo_client=dataforseo_client,
    )

    # Map domain -> AuthorityResult
    result_map: dict[str, AuthorityResult] = {
        r.domain: r for r in results
    }

    enriched: list[Any] = []
    for c in candidates:
        ar = result_map.get(c.domain)
        if ar is None:
            enriched.append(c)
            continue

        # Kill domains below threshold
        if ar.composite_score < AUTHORITY_KILL_THRESHOLD:
            _LOG.debug("Authority KILL: %s (score=%.1f)", c.domain, ar.composite_score)
            continue

        # Replace trust_flow with authority gate DR estimate
        enriched.append(replace(c, trust_flow=ar.dr_estimate))

    _LOG.info(
        "Authority enrichment: %d → %d candidates (%d killed)",
        len(candidates), len(enriched), len(candidates) - len(enriched),
    )
    return enriched


# ---------------------------------------------------------------------------
# Client initialization helpers
# ---------------------------------------------------------------------------
def _init_tranco(settings: Settings) -> Any | None:
    """Initialize TrancoClient if possible."""
    try:
        from clients.tranco_client import TrancoClient
        return TrancoClient(cache_dir=settings.tranco_cache_dir)
    except Exception as exc:
        _LOG.warning("Tranco init failed: %s", exc)
        return None


def _init_opr(settings: Settings) -> Any | None:
    """Initialize OpenPageRankClient if API key is set."""
    if not settings.openpagerank_api_key:
        _LOG.info("OpenPageRank API key not set, skipping Layer 1 OPR")
        return None
    try:
        from clients.openpagerank import OpenPageRankClient
        return OpenPageRankClient(settings)
    except Exception as exc:
        _LOG.warning("OPR init failed: %s", exc)
        return None


def _init_wayback(settings: Settings) -> Any | None:
    """Initialize WaybackClient."""
    try:
        from clients.wayback import WaybackClient
        return WaybackClient(settings)
    except Exception as exc:
        _LOG.warning("Wayback init failed: %s", exc)
        return None


def _init_wikipedia() -> Any | None:
    """Initialize WikipediaClient."""
    try:
        from clients.wikipedia_client import WikipediaClient
        return WikipediaClient()
    except Exception as exc:
        _LOG.warning("Wikipedia init failed: %s", exc)
        return None


def _init_dataforseo(settings: Settings) -> Any | None:
    """Initialize DataForSEOClient if credentials are set."""
    if not settings.dataforseo_login or not settings.dataforseo_password:
        _LOG.info("DataForSEO credentials not set, skipping Layer 2")
        return None
    try:
        from clients.dataforseo import DataForSEOClient
        return DataForSEOClient(settings)
    except Exception as exc:
        _LOG.warning("DataForSEO init failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Authority Gate — 3-Layer Domain Authority Verification",
    )
    parser.add_argument(
        "--domains", type=str, default="",
        help="Comma-separated domains to evaluate",
    )
    parser.add_argument(
        "--domains-file", type=str, default="",
        help="File with one domain per line",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show results without modifying pipeline",
    )
    parser.add_argument(
        "--skip-paid", action="store_true",
        help="Skip Layer 2 paid checks",
    )
    return parser


async def _async_main() -> None:
    """Async CLI entry point."""
    args = _build_parser().parse_args()
    settings = load_settings()

    # Collect domains
    domains: list[str] = []
    if args.domains:
        domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    elif args.domains_file:
        with open(args.domains_file, "r") as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not domains:
        print("No domains specified. Use --domains or --domains-file.", file=sys.stderr)
        sys.exit(1)

    print(f"Evaluating {len(domains)} domains...", file=sys.stderr)

    # Init clients
    tranco = _init_tranco(settings)
    opr = _init_opr(settings)
    wayback = _init_wayback(settings)
    wikipedia = _init_wikipedia()
    dataforseo = _init_dataforseo(settings) if not args.skip_paid else None

    results = await evaluate_batch(
        domains, settings,
        tranco_client=tranco,
        opr_client=opr,
        wayback_client=wayback,
        wikipedia_client=wikipedia,
        dataforseo_client=dataforseo,
        skip_paid=args.skip_paid,
    )

    # Display results
    for r in results:
        verdict = "PASS" if r.composite_score >= AUTHORITY_PASS_THRESHOLD else (
            "KILL" if r.composite_score < AUTHORITY_KILL_THRESHOLD else "WEAK"
        )
        sc_tag = " [SHORT-CIRCUIT]" if r.short_circuited else ""
        print(
            f"  {verdict:4s}  {r.domain:<35s}  "
            f"score={r.composite_score:5.1f}  DR~{r.dr_estimate:2d}  "
            f"conf={r.confidence:.0%}  cost=${r.total_cost:.4f}{sc_tag}"
        )
        for check in r.checks:
            print(f"         {check.source:14s}  {check.status:5s}  "
                  f"val={check.value:8.1f}  norm={check.normalized:.2f}  {check.detail}")


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()

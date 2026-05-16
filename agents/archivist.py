"""ARCHIVIST History Verification Agent — Pipeline Stage 3.

Verifies domain history via Wayback Machine CDX snapshots and
WHOIS ownership analysis. Detects language changes, content gaps,
and title drift.

Input: list[VettedDomain] from SENTINEL (20-60).
Output: list[VerifiedDomain] (5-15 per day target).
Kill rate: ~75% of input.

NASA Power of 10 rules enforced throughout.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import structlog

from clients.wayback import WaybackClient
from clients.whois_lookup import WhoisLookupClient
from config.constants import (
    MAX_LOOP_ITERATIONS,
    MAX_WAYBACK_SNAPSHOTS,
    WAYBACK_RATE_LIMIT,
)
from config.settings import Settings
from models.verified import VerifiedDomain
from models.vetted import VettedDomain

logger = structlog.get_logger(__name__)

_CJK_RE: re.Pattern[str] = re.compile(
    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)
_TITLE_RE: re.Pattern[str] = re.compile(
    r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL
)


def _calculate_archive_age(snapshots: list[dict[str, str]]) -> float:
    """Calculate years from first snapshot to now.

    Args:
        snapshots: CDX snapshot dicts with 'timestamp' key.

    Returns:
        Age in years. 0.0 if empty or parse error.
    """
    assert isinstance(snapshots, list), "snapshots must be a list"
    assert len(snapshots) <= MAX_WAYBACK_SNAPSHOTS + 1, "too many"

    if len(snapshots) == 0:
        return 0.0

    earliest: str = ""
    for i, s in enumerate(snapshots):
        if i >= MAX_LOOP_ITERATIONS:
            break
        ts = s.get("timestamp", "")
        if ts and (not earliest or ts < earliest):
            earliest = ts

    if not earliest or len(earliest) < 8:
        return 0.0
    try:
        first = datetime(
            int(earliest[:4]), int(earliest[4:6]),
            int(earliest[6:8]), tzinfo=timezone.utc,
        )
        return round(max(0.0, (datetime.now(tz=timezone.utc) - first).days / 365.25), 2)
    except (ValueError, OverflowError):
        return 0.0


def _sample_snapshots(
    snapshots: list[dict[str, str]], count: int = 5,
) -> list[dict[str, str]]:
    """Select evenly-spaced snapshots from the list.

    Args:
        snapshots: Full CDX snapshot dicts.
        count: Number of samples.

    Returns:
        Evenly distributed subset.
    """
    assert isinstance(snapshots, list), "snapshots must be a list"
    assert isinstance(count, int) and count > 0, "count must be positive"

    n = len(snapshots)
    if n <= count:
        return list(snapshots)
    step = (n - 1) / (count - 1)
    indices: list[int] = []
    for i in range(count):
        idx = min(round(i * step), n - 1)
        if idx not in indices:
            indices.append(idx)
    return [snapshots[i] for i in indices]


def _extract_title(html: str) -> str:
    """Extract <title> tag content from HTML.

    Args:
        html: Raw HTML string.

    Returns:
        Title text or empty string.
    """
    assert isinstance(html, str), "html must be a string"
    assert len(html) <= 10_000_000, "html too large"

    match = _TITLE_RE.search(html[:50_000])
    if match:
        return re.sub(r"\s+", " ", match.group(1).strip())
    return ""


def _calculate_title_consistency(titles: list[str]) -> float:
    """Calculate pairwise SequenceMatcher average.

    Args:
        titles: Title strings from different snapshots.

    Returns:
        Average similarity ratio (0.0-1.0).
    """
    assert isinstance(titles, list), "titles must be a list"
    assert len(titles) <= MAX_LOOP_ITERATIONS, "too many"

    valid = [t.lower().strip() for t in titles if t.strip()]
    if len(valid) <= 1:
        return 1.0
    total: float = 0.0
    pairs: int = 0
    for i in range(len(valid)):
        if i >= MAX_LOOP_ITERATIONS:
            break
        for j in range(i + 1, len(valid)):
            if j >= MAX_LOOP_ITERATIONS:
                break
            total += SequenceMatcher(None, valid[i], valid[j]).ratio()
            pairs += 1
    return round(min(1.0, max(0.0, total / pairs)), 4) if pairs > 0 else 1.0


def _detect_language_change(titles: list[str]) -> bool:
    """Detect EN to CJK language change in titles.

    Args:
        titles: Chronologically ordered title strings.

    Returns:
        True if language change detected.
    """
    assert isinstance(titles, list), "titles must be a list"
    assert len(titles) <= MAX_LOOP_ITERATIONS, "too many"

    valid = [t for t in titles if t.strip()]
    if len(valid) < 2:
        return False
    first_half = valid[:len(valid) // 2]
    second_half = valid[len(valid) // 2:]
    return (
        any(_CJK_RE.search(t) for t in second_half)
        and not any(_CJK_RE.search(t) for t in first_half)
    )


def _detect_content_gaps(snapshots: list[dict[str, str]]) -> int:
    """Find maximum gap between snapshots in months.

    Args:
        snapshots: CDX snapshot dicts.

    Returns:
        Maximum gap in months.
    """
    assert isinstance(snapshots, list), "snapshots must be a list"
    assert len(snapshots) <= MAX_WAYBACK_SNAPSHOTS + 1, "too many"

    dates: list[datetime] = []
    for i, s in enumerate(snapshots):
        if i >= MAX_LOOP_ITERATIONS:
            break
        ts = s.get("timestamp", "")
        if ts and len(ts) >= 8:
            try:
                dates.append(datetime(
                    int(ts[:4]), int(ts[4:6]),
                    max(1, min(28, int(ts[6:8]))), tzinfo=timezone.utc,
                ))
            except (ValueError, OverflowError):
                continue
    if len(dates) < 2:
        return 0
    dates.sort()
    max_gap = 0
    for i in range(1, len(dates)):
        if i >= MAX_LOOP_ITERATIONS:
            break
        gap = int((dates[i] - dates[i - 1]).days / 30.44)
        if gap > max_gap:
            max_gap = gap
    return max_gap


def _check_red_flags(
    age: float, consistency: float, lang_change: bool,
    gaps: int, owner_changes: int, settings: Settings,
) -> tuple[bool, list[str]]:
    """Evaluate red flag rules. Any flag kills the domain.

    Args:
        age: Archive age in years.
        consistency: Title consistency ratio (0-1).
        lang_change: Language change detected.
        gaps: Max content gap in months.
        owner_changes: WHOIS ownership transfers.
        settings: Pipeline settings.

    Returns:
        Tuple of (killed, flag_descriptions).
    """
    assert isinstance(age, float), "age must be float"
    assert isinstance(consistency, float), "consistency must be float"

    flags: list[str] = []
    if lang_change:
        flags.append("Language change detected (EN -> CJK)")
    if gaps > 12:
        flags.append(f"Content gap > 12mo ({gaps} months)")
    if owner_changes > 5:
        flags.append(f"Excessive WHOIS transfers: {owner_changes}")
    if age < settings.min_archive_years:
        flags.append(f"Archive age {age:.1f}y < {settings.min_archive_years}y")
    if consistency < 0.6:
        flags.append(f"Title consistency {consistency:.2f} < 0.60")
    return (len(flags) > 0, flags)


def _parse_snapshot_date(
    snapshots: list[dict[str, str]], earliest: bool,
) -> datetime | None:
    """Parse earliest or latest snapshot timestamp.

    Args:
        snapshots: CDX snapshot dicts.
        earliest: True for earliest, False for latest.

    Returns:
        Parsed datetime or None.
    """
    assert isinstance(snapshots, list), "snapshots must be a list"
    assert isinstance(earliest, bool), "earliest must be bool"

    target: str = ""
    for i, s in enumerate(snapshots):
        if i >= MAX_LOOP_ITERATIONS:
            break
        ts = s.get("timestamp", "")
        if not ts or len(ts) < 8:
            continue
        if not target:
            target = ts
        elif earliest and ts < target:
            target = ts
        elif not earliest and ts > target:
            target = ts
    if not target or len(target) < 8:
        return None
    try:
        return datetime(
            int(target[:4]), int(target[4:6]),
            max(1, min(28, int(target[6:8]))), tzinfo=timezone.utc,
        )
    except (ValueError, OverflowError):
        return None


def _build_verified(
    vetted: VettedDomain, age: float, total_snapshots: int,
    first_date: datetime | None, last_date: datetime | None,
    consistency: float, max_gap: int, lang_change: bool,
    owner_changes: int, titles: list[str], red_flags: list[str],
) -> VerifiedDomain:
    """Build immutable VerifiedDomain from analysis.

    Args:
        vetted: Source VettedDomain.
        age: Archive age in years.
        total_snapshots: Wayback snapshot count.
        first_date: Earliest snapshot.
        last_date: Latest snapshot.
        consistency: Title consistency.
        max_gap: Max content gap months.
        lang_change: Language change detected.
        owner_changes: Ownership transfers.
        titles: Sample titles.
        red_flags: Flag descriptions.

    Returns:
        Frozen VerifiedDomain.
    """
    assert isinstance(vetted, VettedDomain), "must be VettedDomain"
    assert isinstance(age, float), "age must be float"

    verified = VerifiedDomain(
        domain=vetted.domain, tld=vetted.tld,
        source=vetted.source, discovered_at=vetted.discovered_at,
        run_id=vetted.run_id,
        domain_authority=vetted.domain_authority,
        page_authority=vetted.page_authority,
        spam_score=vetted.spam_score,
        referring_domains=vetted.referring_domains,
        backlinks_total=vetted.backlinks_total,
        dofollow_ratio=vetted.dofollow_ratio,
        indexed_pages=vetted.indexed_pages,
        archive_age_years=age, total_snapshots=total_snapshots,
        first_snapshot_date=first_date, last_snapshot_date=last_date,
        title_consistency=consistency,
        max_content_gap_months=max_gap,
        language_change_detected=lang_change,
        ownership_changes=owner_changes,
        sample_titles=tuple(titles), red_flags=tuple(red_flags),
        niche_keyword_hits=vetted.niche_keyword_hits,
        niche_relevance_score=vetted.niche_relevance_score,
        flags=vetted.flags,
    )
    assert isinstance(verified, VerifiedDomain), "build failed"
    return verified


async def _fetch_titles(
    domain: str, sampled: list[dict[str, str]],
    wb_client: WaybackClient,
) -> list[str]:
    """Fetch and extract titles from sampled snapshots.

    Args:
        domain: Domain name.
        sampled: CDX snapshot dicts to fetch.
        wb_client: Initialized WaybackClient.

    Returns:
        List of extracted title strings.
    """
    assert isinstance(domain, str), "domain must be a string"
    assert isinstance(sampled, list), "sampled must be a list"

    titles: list[str] = []
    for s_idx, snap in enumerate(sampled):
        if s_idx >= MAX_LOOP_ITERATIONS:
            break
        ts = snap.get("timestamp", "")
        if not ts:
            continue
        wb_url = f"https://web.archive.org/web/{ts}id_/{domain}"
        try:
            html = await wb_client.fetch_snapshot_content(wb_url)
            title = _extract_title(html)
            if title:
                titles.append(title)
        except Exception as exc:
            logger.warning("title_fetch_failed", ts=ts, error=str(exc))
        await asyncio.sleep(WAYBACK_RATE_LIMIT)
    return titles


async def _lookup_whois(
    domain: str,
    whois_client: WhoisLookupClient | None,
    log: Any,
) -> int:
    """Look up WHOIS ownership change count for a domain.

    Args:
        domain: Domain name to query.
        whois_client: WHOIS client or None (returns 0).
        log: Bound structlog logger.

    Returns:
        Number of ownership changes detected.
    """
    assert isinstance(domain, str) and len(domain) >= 4, "invalid domain"
    assert isinstance(whois_client, (WhoisLookupClient, type(None))), "bad whois_client"

    if whois_client is None:
        return 0
    try:
        changes = await whois_client.get_ownership_changes(domain)
        assert isinstance(changes, int), "changes must be int"
        return changes
    except Exception as exc:
        log.warning("whois_failed", domain=domain, error=str(exc))
        return 0


async def _analyze_single(
    dv: VettedDomain, settings: Settings, mock: bool,
    wb_client: WaybackClient | None,
    whois_client: WhoisLookupClient | None,
    log: Any,
) -> VerifiedDomain | None:
    """Run full history analysis on one vetted domain.

    Args:
        dv: The VettedDomain to analyze.
        settings: Pipeline settings.
        mock: Use mock mode.
        wb_client: Wayback client or None.
        whois_client: WHOIS client or None.
        log: Bound structlog logger.

    Returns:
        VerifiedDomain if survived, None if killed.
    """
    assert isinstance(dv, VettedDomain), "must be VettedDomain"
    assert isinstance(settings, Settings), "settings must be Settings"

    domain = dv.domain

    snapshots: list[dict[str, str]] = []
    if wb_client is not None:
        try:
            snapshots = await wb_client.get_snapshot_history(domain)
        except Exception as exc:
            log.error("wayback_failed", domain=domain, error=str(exc))

    age = _calculate_archive_age(snapshots)
    sampled = _sample_snapshots(snapshots, count=5)

    titles: list[str] = []
    if wb_client is not None and sampled:
        titles = await _fetch_titles(domain, sampled, wb_client)

    consistency = _calculate_title_consistency(titles)
    lang_change = _detect_language_change(titles)
    max_gap = _detect_content_gaps(snapshots)

    owner_changes = await _lookup_whois(domain, whois_client, log)

    killed, red_flags = _check_red_flags(
        age, consistency, lang_change, max_gap, owner_changes, settings,
    )
    if killed:
        log.info("killed", domain=domain, red_flags=red_flags)
        return None

    first_date = _parse_snapshot_date(snapshots, earliest=True)
    last_date = _parse_snapshot_date(snapshots, earliest=False)
    return _build_verified(
        dv, age, len(snapshots), first_date, last_date,
        consistency, max_gap, lang_change, owner_changes, titles, [],
    )


async def _close_clients(
    wb: WaybackClient | None, whois: WhoisLookupClient | None,
) -> None:
    """Safely close Wayback and WHOIS clients.

    Args:
        wb: Wayback client or None.
        whois: WHOIS client or None.
    """
    assert isinstance(wb, (WaybackClient, type(None))), "bad wb"
    assert isinstance(whois, (WhoisLookupClient, type(None))), "bad whois"

    if whois is not None:
        try:
            await whois.close()
        except Exception:
            pass


def _finalize_results(
    survivors: list[VerifiedDomain], cap: int,
    input_count: int, killed: int, log: Any,
) -> list[VerifiedDomain]:
    """Sort, cap, and log final results.

    Args:
        survivors: Verified domains that passed.
        cap: Maximum to return.
        input_count: Total input count.
        killed: Number killed.
        log: Bound structlog logger.

    Returns:
        Capped, sorted list.
    """
    assert isinstance(survivors, list), "survivors must be list"
    assert cap > 0, "cap must be positive"

    survivors.sort(key=lambda v: -v.archive_age_years)
    capped = survivors[:cap]
    kill_pct = (
        round((1.0 - len(capped) / input_count) * 100, 1)
        if input_count > 0 else 0.0
    )
    log.info("archivist_complete", input=input_count,
             survivors=len(capped), killed=killed,
             kill_rate_pct=kill_pct)
    assert all(isinstance(v, VerifiedDomain) for v in capped), "bad type"
    return capped


async def run(
    settings: Settings, vetted: list[VettedDomain],
    *, mock: bool = False,
) -> list[VerifiedDomain]:
    """Run ARCHIVIST history verification on vetted domains.

    Args:
        settings: Frozen pipeline settings.
        vetted: VettedDomain list from SENTINEL.
        mock: If True, use mock client data.

    Returns:
        List of VerifiedDomain sorted by archive_age descending.
    """
    assert isinstance(settings, Settings), "settings must be Settings"
    assert isinstance(vetted, list), "vetted must be a list"

    if len(vetted) == 0:
        logger.warning("archivist_empty_input")
        return []

    log = logger.bind(agent="archivist", input_count=len(vetted))
    log.info("archivist_start")

    wb = WaybackClient(settings, mock=mock)
    whois = WhoisLookupClient()
    survivors: list[VerifiedDomain] = []
    killed: int = 0

    try:
        for idx, dv in enumerate(vetted):
            if idx >= MAX_LOOP_ITERATIONS:
                break
            try:
                if idx > 0:
                    await asyncio.sleep(WAYBACK_RATE_LIMIT)
                result = await _analyze_single(
                    dv, settings, mock, wb, whois, log,
                )
                if result is not None:
                    survivors.append(result)
                else:
                    killed += 1
            except Exception as exc:
                log.error("verify_failed", domain=dv.domain, error=str(exc))
    finally:
        await _close_clients(wb, whois)

    return _finalize_results(
        survivors, settings.max_archivist_verified, len(vetted), killed, log,
    )

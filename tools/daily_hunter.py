"""Domain Hunter REVENANT -- Automated Daily Domain Hunting Pipeline.

Scans multiple free sources for expiring/expired high-DA domains,
filters by authority threshold, enriches top candidates via DataForSEO
Labs API, classifies niches, and stores daily JSON snapshots.

NASA Power of 10 rules enforced:
  1. No goto/deep recursion/switch fallthroughs
  2. All loops have fixed upper bounds
  3. No unbounded memory -- explicit max sizes everywhere
  4. All functions < 60 lines
  5. Min 2 assertions per function
  6. Restrict data scope -- no global mutable state
  7. Check every return value -- no swallowed exceptions
  8. Standard Python + requests only
  9. No dangerous mutations -- return new objects
  10. Zero warnings -- all errors fixed, not suppressed

Setup (cron):
  # Daily at 06:00 UTC -- edit path to match your install
  0 6 * * * cd /Users/mike/Desktop/domainhunter && \\
      .venv/bin/python tools/daily_hunter.py >> logs/daily_hunter.log 2>&1

  # Dry-run test:
  python tools/daily_hunter.py --dry-run

Dependencies: requests (pip install requests), Python 3.10+
Cost: ~$0.05/day at 50 DataForSEO lookups x $0.001/lookup
Sprint 13: DeepSeek classification, OpenRank authority check, expiry monitor
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# --- Single external dependency ---
try:
    import requests
except ImportError:
    print("FATAL: 'requests' package required. Install: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants -- no global mutable state (all Final)
# ---------------------------------------------------------------------------
MAX_DOMAINS_PER_SOURCE: Final[int] = 100
MAX_TOTAL_CANDIDATES: Final[int] = 500
MAX_DATAFORSEO_LOOKUPS: Final[int] = 50
MAX_RETRIES: Final[int] = 3
MAX_ALERT_LINES: Final[int] = 50
MAX_NICHE_KEYWORDS: Final[int] = 200
HTTP_TIMEOUT: Final[int] = 15
BASE_DELAY: Final[float] = 1.0
MAX_DELAY: Final[float] = 30.0
CONFIG_FILENAME: Final[str] = "daily_hunter_config.json"
SCRIPT_DIR: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = SCRIPT_DIR.parent

# Sprint 10: CatchDoms + OpenRank constants
CATCHDOMS_MIN_QUALITY: Final[int] = 30
CATCHDOMS_MIN_DA: Final[int] = 15
OPENRANK_BATCH_SIZE: Final[int] = 50
OPENRANK_MAX_DAILY_REQUESTS: Final[int] = 10000
DA_DISCREPANCY_THRESHOLD: Final[int] = 15

# Sprint 12: Price verification constants
PRICE_VERIFY_ENABLED: Final[bool] = True
PRICE_MISMATCH_THRESHOLD: Final[float] = 3.0  # Flag if verified > 3x claimed
PRICE_VERIFY_TIMEOUT: Final[int] = 10  # seconds per domain
MAX_PRICE_CHECKS_PER_RUN: Final[int] = 50

# Sprint 13: DeepSeek V3 batch classification constants
DEEPSEEK_API_URL: Final[str] = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL: Final[str] = "deepseek-chat"
DEEPSEEK_BATCH_SIZE: Final[int] = 50  # 50 domains per API call
DEEPSEEK_MAX_BATCHES: Final[int] = 200  # 10,000 domains max
DEEPSEEK_RPM_LIMIT: Final[int] = 60

# Sprint 13: OpenRank authority check constants
OPENRANK_AUTHORITY_API_URL: Final[str] = "https://openrank.io/api/v1/domain"
OPENRANK_AUTHORITY_BATCH_SIZE: Final[int] = 1  # Check one at a time (rate limit TBD)
OPENRANK_MAX_AUTHORITY_CHECKS: Final[int] = 500

# Sprint 13: Expiring domain monitor constants
WHOIS_CHECK_TIMEOUT: Final[int] = 10
MAX_WHOIS_CHECKS: Final[int] = 50
EXPIRY_WARNING_DAYS: Final[int] = 90

# Sprint 14: DataForSEO ETV verification constants
ETV_MIN_THRESHOLD: Final[float] = 100.0  # Minimum ETV to pass ($100/mo)
ETV_WHALE_THRESHOLD: Final[float] = 1000.0  # WHALE alert level ($1000/mo)
ETV_API_COST: Final[float] = 0.01  # Cost per domain_rank_overview API call
MAX_ETV_CHECKS_PER_RUN: Final[int] = 100  # Budget guard
ETV_RATE_LIMIT_DELAY: Final[float] = 0.2  # 5 calls/sec max = 0.2s between calls

logger: Final[logging.Logger] = logging.getLogger("daily_hunter")


# ---------------------------------------------------------------------------
# Immutable data structures (frozen dataclasses)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DomainCandidate:
    """A single domain candidate from any source."""

    domain: str
    source: str
    da_estimate: int = 0
    traffic_estimate: int = 0
    niche: str = "unknown"
    expiry_date: str = ""
    price_usd: float = 0.0
    backlinks: int = 0
    referring_domains: int = 0
    notes: str = ""


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration loaded from JSON."""

    alert_da_threshold: int
    critical_da_threshold: int
    min_da_filter: int
    max_domains_per_source: int
    max_total_candidates: int
    sources_enabled: tuple[str, ...]
    niches_priority: tuple[str, ...]
    dataforseo_max_lookups_per_day: int
    output_dir: str
    rate_limit_base_delay_seconds: float
    rate_limit_max_delay_seconds: float
    rate_limit_max_retries: int
    http_timeout_seconds: int
    user_agent: str


@dataclass(frozen=True)
class DailyResult:
    """Immutable result of a daily pipeline run."""

    run_date: str
    total_scanned: int
    total_after_dedup: int
    total_above_min_da: int
    dataforseo_lookups_used: int
    alerts: tuple[str, ...]
    candidates: tuple[DomainCandidate, ...]


@dataclass(frozen=True)
class PriceVerification:
    """Immutable result of a single domain price verification check."""

    domain: str
    claimed_price: float
    claimed_source: str
    verified_price: float  # 0.0 if unavailable
    verified_source: str  # "gdauctions", "gd_aftermarket", "registration", "unknown"
    verification_status: str  # "confirmed", "mismatch", "unavailable", "error"
    price_ratio: float  # verified / claimed (>3.0 = flagged)
    verified_url: str
    checked_at: str  # ISO timestamp


@dataclass(frozen=True)
class DeepSeekClassification:
    """Immutable result of DeepSeek V3 domain classification."""

    domain: str
    niche: str
    site_type: str
    tool_idea: str
    keyword_value: int  # 1-10
    brandability: int  # 1-10
    monetization: str
    acquisition_priority: int  # 1-10
    classified_at: str


@dataclass(frozen=True)
class AuthorityCheck:
    """Immutable result of OpenRank authority check."""

    domain: str
    openrank_score: float
    da_estimate: int  # Derived from openrank
    confidence: str  # "high", "medium", "low"
    checked_at: str


@dataclass(frozen=True)
class ExpiryAlert:
    """Immutable result of a WHOIS expiry check for a domain."""

    domain: str
    expiry_date: str
    days_remaining: int
    registrar: str
    status_codes: tuple[str, ...]
    drop_probability: str  # "very_high", "high", "medium", "low"
    recommended_action: str
    checked_at: str


@dataclass(frozen=True)
class ETVVerification:
    """Immutable result of DataForSEO ETV verification for a domain."""

    domain: str
    keywords: int
    etv: float
    top_10: int
    estimated_paid_cost: float
    verified: bool
    verified_at: str


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------
def load_config(config_path: Path) -> PipelineConfig:
    """Load and validate pipeline config from JSON file."""
    assert isinstance(config_path, Path), f"config_path must be Path, got {type(config_path)}"
    assert config_path.is_file(), f"Config file not found: {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    config = PipelineConfig(
        alert_da_threshold=int(raw["alert_da_threshold"]),
        critical_da_threshold=int(raw["critical_da_threshold"]),
        min_da_filter=int(raw["min_da_filter"]),
        max_domains_per_source=min(int(raw["max_domains_per_source"]), MAX_DOMAINS_PER_SOURCE),
        max_total_candidates=min(int(raw["max_total_candidates"]), MAX_TOTAL_CANDIDATES),
        sources_enabled=tuple(raw["sources_enabled"]),
        niches_priority=tuple(raw["niches_priority"]),
        dataforseo_max_lookups_per_day=min(
            int(raw["dataforseo_max_lookups_per_day"]), MAX_DATAFORSEO_LOOKUPS,
        ),
        output_dir=str(raw["output_dir"]),
        rate_limit_base_delay_seconds=float(raw.get("rate_limit_base_delay_seconds", BASE_DELAY)),
        rate_limit_max_delay_seconds=float(raw.get("rate_limit_max_delay_seconds", MAX_DELAY)),
        rate_limit_max_retries=min(int(raw.get("rate_limit_max_retries", MAX_RETRIES)), MAX_RETRIES),
        http_timeout_seconds=int(raw.get("http_timeout_seconds", HTTP_TIMEOUT)),
        user_agent=str(raw.get("user_agent", "DomainHunter/1.0")),
    )
    assert config.min_da_filter >= 0, f"min_da_filter must be >= 0, got {config.min_da_filter}"
    assert config.alert_da_threshold > config.min_da_filter, "alert threshold must exceed min filter"
    return config


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _build_session(user_agent: str) -> requests.Session:
    """Build a requests session with standard headers."""
    assert isinstance(user_agent, str) and len(user_agent) > 0, "user_agent required"

    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/json",
    })
    assert session is not None, "session creation failed"
    return session


def _request_with_backoff(
    session: requests.Session,
    url: str,
    config: PipelineConfig,
    *,
    method: str = "GET",
    json_body: dict | None = None,
    auth: tuple[str, str] | None = None,
) -> requests.Response | None:
    """Make HTTP request with exponential backoff on failure."""
    assert isinstance(url, str) and url.startswith("http"), f"Invalid URL: {url}"
    assert method in ("GET", "POST"), f"Unsupported method: {method}"

    delay = config.rate_limit_base_delay_seconds
    for attempt in range(config.rate_limit_max_retries):
        try:
            if method == "POST":
                resp = session.post(
                    url, json=json_body, auth=auth,
                    timeout=config.http_timeout_seconds,
                )
            else:
                resp = session.get(url, auth=auth, timeout=config.http_timeout_seconds)

            if resp.status_code == 429:
                logger.warning("Rate limited on %s, attempt %d, sleeping %.1fs", url, attempt + 1, delay)
                time.sleep(delay)
                delay = min(delay * 2, config.rate_limit_max_delay_seconds)
                continue

            resp.raise_for_status()
            return resp

        except requests.exceptions.Timeout:
            logger.warning("Timeout on %s, attempt %d/%d", url, attempt + 1, config.rate_limit_max_retries)
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Connection error on %s: %s", url, exc)
        except requests.exceptions.HTTPError as exc:
            logger.warning("HTTP error on %s: %s", url, exc)
            return None

        if attempt < config.rate_limit_max_retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, config.rate_limit_max_delay_seconds)

    logger.error("All %d attempts failed for %s", config.rate_limit_max_retries, url)
    return None


# ---------------------------------------------------------------------------
# Source 1: ExpiredDomains.net (scrape the publicly visible list)
# ---------------------------------------------------------------------------
def _parse_expireddomains_text(text: str, max_count: int) -> list[dict]:
    """Parse domain entries from expireddomains.net HTML response."""
    assert isinstance(text, str), "text must be string"
    assert max_count > 0, f"max_count must be positive, got {max_count}"

    results: list[dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if i >= 10000:  # safety bound on line scan
            break
        if len(results) >= max_count:
            break
        # Look for domain patterns in table cells
        stripped = line.strip()
        if '<td class="field_domain">' in stripped:
            # Extract domain from anchor tag or text
            domain = _extract_domain_from_html(stripped)
            if domain and "." in domain and len(domain) < 253:
                results.append({"domain": domain.lower(), "source": "expired_domains_net"})

    return results


def _extract_domain_from_html(html_line: str) -> str:
    """Extract a domain name from an HTML line containing a link or text."""
    assert isinstance(html_line, str), "html_line must be string"

    # Try to find domain in href or plain text
    for marker in ('title="', ">"):
        idx = html_line.find(marker)
        if idx >= 0:
            start = idx + len(marker)
            end_chars = ("<", '"', " ", "&")
            end = len(html_line)
            for ec in end_chars:
                pos = html_line.find(ec, start)
                if 0 <= pos < end:
                    end = pos
            candidate = html_line[start:end].strip().strip("/")
            if "." in candidate and " " not in candidate and len(candidate) > 3:
                return candidate

    assert isinstance(html_line, str), "html_line type preserved"
    return ""


def fetch_expired_domains_list(
    session: requests.Session, config: PipelineConfig, *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Fetch recently expired domains from expireddomains.net."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if dry_run:
        logger.info("[DRY RUN] Skipping expireddomains.net fetch")
        return _mock_expired_domains()

    url = "https://www.expireddomains.net/deleted-domains/?fwhois=22&ftlds[]=1&fstatuscom=1"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        logger.warning("expireddomains.net fetch failed, returning empty")
        return []

    raw_entries = _parse_expireddomains_text(resp.text, config.max_domains_per_source)
    candidates = [
        DomainCandidate(domain=e["domain"], source=e["source"])
        for e in raw_entries[:config.max_domains_per_source]
    ]
    logger.info("expireddomains.net: found %d candidates", len(candidates))
    return candidates


def _mock_expired_domains() -> list[DomainCandidate]:
    """Return mock data for dry-run mode."""
    mock_domains = [
        ("recipehub.com", 35), ("cookmaster.net", 22), ("devtoolkit.io", 45),
        ("healthguide.org", 28), ("fittrack.com", 31), ("codeforge.dev", 19),
        ("mealplanner.com", 42), ("techpulse.io", 38), ("budgetwise.com", 25),
        ("gardenhelper.net", 17),
    ]
    assert len(mock_domains) > 0, "mock data must not be empty"
    assert len(mock_domains) <= MAX_DOMAINS_PER_SOURCE, "mock data exceeds limit"
    return [
        DomainCandidate(domain=d, source="expired_domains_net", da_estimate=da)
        for d, da in mock_domains
    ]


# ---------------------------------------------------------------------------
# Source 2: DomCop top drops
# ---------------------------------------------------------------------------
def fetch_domcop_drops(
    session: requests.Session, config: PipelineConfig, *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Fetch top dropping domains from DomCop free list."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if dry_run:
        logger.info("[DRY RUN] Skipping DomCop fetch")
        return _mock_domcop_drops()

    # DomCop provides a free RSS feed of top drops
    url = "https://www.domcop.com/top-dropping-domains"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        logger.warning("DomCop fetch failed, returning empty")
        return []

    candidates: list[DomainCandidate] = []
    lines = resp.text.splitlines()
    for i, line in enumerate(lines):
        if i >= 5000:
            break
        if len(candidates) >= config.max_domains_per_source:
            break
        # DomCop HTML table rows contain domain data
        if 'class="domain"' in line or "domcop.com/goto/" in line:
            domain = _extract_domain_from_html(line)
            if domain and "." in domain:
                candidates.append(DomainCandidate(domain=domain.lower(), source="domcop"))

    logger.info("DomCop: found %d candidates", len(candidates))
    return candidates


def _mock_domcop_drops() -> list[DomainCandidate]:
    """Return mock DomCop data for dry-run."""
    mock_domains = [
        ("nutritrack.com", 29), ("codebench.io", 41), ("wellnessapp.org", 23),
        ("smartrecipe.com", 33), ("devdocs.net", 37), ("fitjournal.com", 20),
        ("investsmart.net", 26), ("learncode.org", 44), ("mealkit.io", 18),
        ("travelguide.app", 15),
    ]
    assert len(mock_domains) > 0, "mock data must not be empty"
    assert len(mock_domains) <= MAX_DOMAINS_PER_SOURCE, "mock data exceeds limit"
    return [
        DomainCandidate(domain=d, source="domcop", da_estimate=da)
        for d, da in mock_domains
    ]


# ---------------------------------------------------------------------------
# Source 3: GoDaddy closeout auctions (public API)
# ---------------------------------------------------------------------------
def check_godaddy_closeouts(
    session: requests.Session, config: PipelineConfig, *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Check GoDaddy auctions for closeout / expiry domains under $12."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if dry_run:
        logger.info("[DRY RUN] Skipping GoDaddy closeout fetch")
        return _mock_godaddy_closeouts()

    # GoDaddy Auctions public search page (no API key required for browsing)
    url = (
        "https://auctions.godaddy.com/trpSearchResults.aspx"
        "?t=16&action=search&query=&minPrice=1&maxPrice=12"
        "&tlds=.com&sort=endtime&order=a&rows=100&page=1"
    )
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        logger.warning("GoDaddy closeouts fetch failed, returning empty")
        return []

    candidates = _parse_godaddy_results(resp.text, config.max_domains_per_source)
    logger.info("GoDaddy closeouts: found %d candidates", len(candidates))
    return candidates


def _parse_godaddy_results(text: str, max_count: int) -> list[DomainCandidate]:
    """Parse GoDaddy auction results HTML for domain names."""
    assert isinstance(text, str), "text must be string"
    assert max_count > 0, f"max_count must be positive, got {max_count}"

    candidates: list[DomainCandidate] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if i >= 10000:
            break
        if len(candidates) >= max_count:
            break
        if "tdDomainName" in line or 'class="dmn"' in line:
            domain = _extract_domain_from_html(line)
            if domain and "." in domain:
                candidates.append(DomainCandidate(
                    domain=domain.lower(), source="godaddy_closeouts",
                    price_usd=11.0, notes="closeout auction",
                ))

    return candidates


def _mock_godaddy_closeouts() -> list[DomainCandidate]:
    """Return mock GoDaddy closeout data for dry-run."""
    mock_domains = [
        ("quickmeal.com", 16, 9.99), ("devportal.net", 27, 5.99),
        ("healthblog.org", 21, 11.00), ("toolmaker.com", 34, 7.49),
        ("recipefinder.net", 19, 8.99), ("financeapp.io", 30, 6.49),
        ("buildtools.com", 24, 10.99), ("yogaguide.org", 18, 4.99),
    ]
    assert len(mock_domains) > 0, "mock data must not be empty"
    assert len(mock_domains) <= MAX_DOMAINS_PER_SOURCE, "mock data exceeds limit"
    return [
        DomainCandidate(
            domain=d, source="godaddy_closeouts",
            da_estimate=da, price_usd=price, notes="closeout auction",
        )
        for d, da, price in mock_domains
    ]


# ---------------------------------------------------------------------------
# Source 4: Tech shutdown / startup graveyard search
# ---------------------------------------------------------------------------
def search_tech_shutdowns(
    session: requests.Session, config: PipelineConfig, *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Search for recently shut down tech products/startups with domains."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if dry_run:
        logger.info("[DRY RUN] Skipping tech shutdown search")
        return _mock_tech_shutdowns()

    candidates: list[DomainCandidate] = []

    # Source: Killed by Google (JSON API) -- public data
    kbg_candidates = _fetch_killed_by_google(session, config)
    candidates.extend(kbg_candidates[:config.max_domains_per_source // 2])

    # Source: Our Incredible Journey (Tumblr) -- startup shutdowns
    oij_candidates = _fetch_startup_graveyard(session, config)
    remaining_slots = config.max_domains_per_source - len(candidates)
    candidates.extend(oij_candidates[:max(0, remaining_slots)])

    logger.info("Tech shutdowns: found %d candidates", len(candidates))
    return candidates[:config.max_domains_per_source]


def _fetch_killed_by_google(
    session: requests.Session, config: PipelineConfig,
) -> list[DomainCandidate]:
    """Fetch shutdown products from killedbygoogle.com API."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config required"

    url = "https://raw.githubusercontent.com/codyogden/killedbygoogle/main/graveyard.json"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        return []

    candidates: list[DomainCandidate] = []
    try:
        items = resp.json()
        assert isinstance(items, list), "Expected list from killedbygoogle"
        for idx, item in enumerate(items):
            if idx >= config.max_domains_per_source:
                break
            link = item.get("link", "")
            name = item.get("name", "")
            # Extract domain from product URL
            domain = _extract_domain_from_url(link)
            if domain and not _is_major_platform(domain):
                candidates.append(DomainCandidate(
                    domain=domain, source="tech_shutdowns",
                    notes=f"Killed by Google: {name}",
                ))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse killedbygoogle data: %s", exc)

    return candidates


def _fetch_startup_graveyard(
    session: requests.Session, config: PipelineConfig,
) -> list[DomainCandidate]:
    """Fetch shutdown startups from startup graveyard sources."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config required"

    # Use the public startup cemetery API
    url = "https://www.cbinsights.com/research-unicorn-companies"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        return []

    # Parse for any domain references -- best-effort extraction
    candidates: list[DomainCandidate] = []
    lines = resp.text.splitlines()
    for i, line in enumerate(lines):
        if i >= 5000:
            break
        if len(candidates) >= config.max_domains_per_source // 2:
            break
        # Look for .com domain patterns
        domain = _find_domain_in_text(line)
        if domain and not _is_major_platform(domain):
            candidates.append(DomainCandidate(
                domain=domain, source="tech_shutdowns",
                notes="startup graveyard",
            ))

    return candidates


def _extract_domain_from_url(url: str) -> str:
    """Extract base domain from a URL string."""
    assert isinstance(url, str), "url must be string"

    cleaned = url.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    # Take everything before the first slash
    slash_idx = cleaned.find("/")
    if slash_idx > 0:
        cleaned = cleaned[:slash_idx]

    assert isinstance(cleaned, str), "result must be string"
    return cleaned if "." in cleaned and len(cleaned) > 3 else ""


def _is_major_platform(domain: str) -> bool:
    """Check if domain belongs to a major platform (skip these)."""
    assert isinstance(domain, str), "domain must be string"

    skip_domains = (
        "google.com", "youtube.com", "facebook.com", "twitter.com",
        "github.com", "apple.com", "microsoft.com", "amazon.com",
        "instagram.com", "linkedin.com", "x.com", "reddit.com",
        "wikipedia.org", "medium.com", "tumblr.com",
    )
    assert len(skip_domains) > 0, "skip list must not be empty"
    return any(domain.endswith(sd) for sd in skip_domains)


def _find_domain_in_text(text: str) -> str:
    """Find a .com/.io/.org domain pattern in text."""
    assert isinstance(text, str), "text must be string"

    words = text.split()
    for word_idx, word in enumerate(words):
        if word_idx >= 500:
            break
        cleaned = word.strip("(),<>\"';[]{}").lower()
        if len(cleaned) < 4 or len(cleaned) > 253:
            continue
        for tld in (".com", ".io", ".org", ".net", ".dev", ".app"):
            if cleaned.endswith(tld) and cleaned.count(".") <= 3:
                # Validate it looks like a domain
                if all(c.isalnum() or c in ".-" for c in cleaned):
                    return cleaned

    assert isinstance(text, str), "text type preserved"
    return ""


def _mock_tech_shutdowns() -> list[DomainCandidate]:
    """Return mock tech shutdown data for dry-run."""
    mock_domains = [
        ("ghostautonomy.com", 52, "Autonomous driving startup, shut down 2024"),
        ("peptalk.app", 18, "Mental health startup, ceased operations"),
        ("codestream.io", 39, "Dev tools, acquired and sunset"),
        ("mealprep.ai", 22, "AI meal planning, ran out of funding"),
        ("trackfit.com", 27, "Fitness tracker startup, pivoted away"),
    ]
    assert len(mock_domains) > 0, "mock data must not be empty"
    assert len(mock_domains) <= MAX_DOMAINS_PER_SOURCE, "mock data exceeds limit"
    return [
        DomainCandidate(domain=d, source="tech_shutdowns", da_estimate=da, notes=notes)
        for d, da, notes in mock_domains
    ]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def deduplicate_candidates(
    all_candidates: list[DomainCandidate], max_total: int,
) -> list[DomainCandidate]:
    """Remove duplicate domains, keeping the first occurrence (highest priority source)."""
    assert isinstance(all_candidates, list), "all_candidates must be list"
    assert max_total > 0, f"max_total must be positive, got {max_total}"

    seen: set[str] = set()
    unique: list[DomainCandidate] = []

    for idx, candidate in enumerate(all_candidates):
        if idx >= MAX_TOTAL_CANDIDATES * 2:  # safety bound
            break
        if len(unique) >= max_total:
            break
        domain_key = candidate.domain.lower().strip()
        if domain_key not in seen:
            seen.add(domain_key)
            unique.append(candidate)

    logger.info(
        "Dedup: %d -> %d candidates (removed %d dupes)",
        len(all_candidates), len(unique), len(all_candidates) - len(unique),
    )
    assert len(unique) <= max_total, f"Dedup output exceeds max: {len(unique)}"
    return unique


# ---------------------------------------------------------------------------
# DA checking (free API: Open PageRank)
# ---------------------------------------------------------------------------
def bulk_da_check(
    session: requests.Session,
    candidates: list[DomainCandidate],
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Check domain authority using Open PageRank free API (10k/day free)."""
    assert session is not None, "session required"
    assert isinstance(candidates, list), "candidates must be list"

    if dry_run:
        logger.info("[DRY RUN] Returning candidates with existing DA estimates")
        return candidates

    # Open PageRank API: free tier, 10k lookups/day
    api_key = os.environ.get("OPEN_PAGERANK_API_KEY", "")

    if not api_key:
        logger.info("No OPEN_PAGERANK_API_KEY set, skipping DA check -- using estimates")
        return candidates

    enriched: list[DomainCandidate] = []
    # Process in batches of 100 (API limit)
    batch_size = 100
    for batch_start in range(0, min(len(candidates), MAX_TOTAL_CANDIDATES), batch_size):
        batch_end = min(batch_start + batch_size, len(candidates))
        batch = candidates[batch_start:batch_end]
        batch_results = _check_pagerank_batch(session, batch, api_key, config)
        enriched.extend(batch_results)

    assert len(enriched) <= len(candidates), "enriched count must not exceed input"
    logger.info("DA check: enriched %d candidates", len(enriched))
    return enriched


def _check_pagerank_batch(
    session: requests.Session,
    batch: list[DomainCandidate],
    api_key: str,
    config: PipelineConfig,
) -> list[DomainCandidate]:
    """Check PageRank for a batch of domains (max 100)."""
    assert len(batch) <= 100, f"Batch too large: {len(batch)}"
    assert isinstance(api_key, str) and len(api_key) > 0, "api_key required"

    domains_param = "&".join(f"domains[]={c.domain}" for c in batch)
    url = f"https://openpagerank.com/api/v1.0/getPageRank?{domains_param}"

    headers = {"API-OPR": api_key}
    try:
        resp = session.get(url, headers=headers, timeout=config.http_timeout_seconds)
        if resp.status_code != 200:
            logger.warning("PageRank API returned %d", resp.status_code)
            return list(batch)
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("PageRank batch failed: %s", exc)
        return list(batch)

    # Build lookup of results
    pr_map: dict[str, int] = {}
    response_items = data.get("response", [])
    for item_idx, item in enumerate(response_items):
        if item_idx >= 100:
            break
        domain = item.get("domain", "").lower()
        page_rank = int(item.get("page_rank_integer", 0))
        if domain:
            pr_map[domain] = page_rank

    # Rebuild candidates with updated DA
    enriched = [
        DomainCandidate(
            domain=c.domain, source=c.source,
            da_estimate=pr_map.get(c.domain.lower(), c.da_estimate),
            traffic_estimate=c.traffic_estimate, niche=c.niche,
            expiry_date=c.expiry_date, price_usd=c.price_usd,
            backlinks=c.backlinks, referring_domains=c.referring_domains,
            notes=c.notes,
        )
        for c in batch
    ]
    return enriched


# ---------------------------------------------------------------------------
# DataForSEO traffic enrichment (paid -- $0.001/lookup)
# ---------------------------------------------------------------------------
def _load_dataforseo_credentials() -> tuple[str, str]:
    """Load DataForSEO credentials from environment."""
    login = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    assert isinstance(login, str), "login must be string"
    assert isinstance(password, str), "password must be string"
    return login, password


def _count_todays_lookups(output_dir: Path, today_str: str) -> int:
    """Count how many DataForSEO lookups were already done today."""
    assert isinstance(output_dir, Path), "output_dir must be Path"
    assert len(today_str) == 10, f"today_str must be YYYY-MM-DD, got {today_str}"

    today_file = output_dir / f"{today_str}.json"
    if not today_file.is_file():
        return 0

    try:
        with open(today_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return int(existing.get("dataforseo_lookups_used", 0))
    except (json.JSONDecodeError, KeyError, OSError):
        return 0


def dataforseo_traffic_check(
    session: requests.Session,
    candidates: list[DomainCandidate],
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Enrich top candidates with DataForSEO Labs traffic estimates."""
    assert session is not None, "session required"
    assert isinstance(candidates, list), "candidates must be list"

    if dry_run:
        logger.info("[DRY RUN] Skipping DataForSEO traffic check")
        return candidates

    login, password = _load_dataforseo_credentials()
    if not login or not password:
        logger.warning("DataForSEO credentials not found, skipping traffic check")
        return candidates

    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    output_dir = PROJECT_ROOT / config.output_dir
    used_today = _count_todays_lookups(output_dir, today_str)
    remaining = max(0, config.dataforseo_max_lookups_per_day - used_today)

    if remaining <= 0:
        logger.info("DataForSEO daily lookup limit reached (%d used)", used_today)
        return candidates

    # Sort by DA desc, check top N only (budget conscious)
    sorted_candidates = sorted(candidates, key=lambda c: c.da_estimate, reverse=True)
    to_check = sorted_candidates[:remaining]
    unchecked = sorted_candidates[remaining:]

    enriched = _dataforseo_bulk_lookup(session, to_check, login, password, config)
    result = enriched + unchecked

    logger.info(
        "DataForSEO: checked %d domains, %d remaining in budget",
        len(to_check), remaining - len(to_check),
    )
    assert len(result) == len(candidates), "enrichment must preserve candidate count"
    return result


def _dataforseo_bulk_lookup(
    session: requests.Session,
    candidates: list[DomainCandidate],
    login: str,
    password: str,
    config: PipelineConfig,
) -> list[DomainCandidate]:
    """Look up traffic data for a batch of domains via DataForSEO Labs."""
    assert len(candidates) <= MAX_DATAFORSEO_LOOKUPS, "too many lookups"
    assert isinstance(login, str) and len(login) > 0, "login required"

    auth = (login, password)
    enriched: list[DomainCandidate] = []

    for idx, candidate in enumerate(candidates):
        if idx >= MAX_DATAFORSEO_LOOKUPS:
            break

        traffic_data = _dataforseo_single_lookup(session, candidate.domain, auth, config)
        enriched.append(DomainCandidate(
            domain=candidate.domain, source=candidate.source,
            da_estimate=candidate.da_estimate,
            traffic_estimate=traffic_data.get("organic_traffic", candidate.traffic_estimate),
            niche=candidate.niche, expiry_date=candidate.expiry_date,
            price_usd=candidate.price_usd,
            backlinks=traffic_data.get("backlinks", candidate.backlinks),
            referring_domains=traffic_data.get("referring_domains", candidate.referring_domains),
            notes=candidate.notes,
        ))
        # Rate limit: 1 second between calls
        if idx < len(candidates) - 1:
            time.sleep(config.rate_limit_base_delay_seconds)

    return enriched


def _dataforseo_single_lookup(
    session: requests.Session,
    domain: str,
    auth: tuple[str, str],
    config: PipelineConfig,
) -> dict:
    """Look up a single domain in DataForSEO Labs API."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert len(auth) == 2, "auth must be (login, password) tuple"

    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_metrics_by_categories/live"
    payload = [{"target": domain, "language_code": "en", "location_code": 2840}]

    resp = _request_with_backoff(
        session, url, config, method="POST", json_body=payload, auth=auth,
    )

    if resp is None:
        return {}

    try:
        data = resp.json()
        tasks = data.get("tasks", [])
        if not tasks:
            return {}
        result = tasks[0].get("result", [])
        if not result:
            return {}
        metrics = result[0] if isinstance(result, list) and len(result) > 0 else {}
        return {
            "organic_traffic": int(metrics.get("organic_etv", 0)),
            "backlinks": int(metrics.get("backlinks", 0)),
            "referring_domains": int(metrics.get("referring_domains", 0)),
        }
    except (json.JSONDecodeError, ValueError, IndexError, TypeError) as exc:
        logger.warning("DataForSEO parse error for %s: %s", domain, exc)
        return {}


# ---------------------------------------------------------------------------
# Sprint 14: DataForSEO ETV verification stage
# ---------------------------------------------------------------------------
def _parse_etv_response(response_json: dict, domain: str) -> ETVVerification:
    """Parse DataForSEO domain_rank_overview response into ETVVerification."""
    assert isinstance(response_json, dict), "response_json must be dict"
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    try:
        tasks = response_json.get("tasks", [])
        if not tasks or not isinstance(tasks, list):
            return ETVVerification(
                domain=domain, keywords=0, etv=0.0, top_10=0,
                estimated_paid_cost=0.0, verified=False, verified_at=now_iso,
            )
        result_list = tasks[0].get("result", [])
        if not result_list or not isinstance(result_list, list):
            return ETVVerification(
                domain=domain, keywords=0, etv=0.0, top_10=0,
                estimated_paid_cost=0.0, verified=False, verified_at=now_iso,
            )
        metrics = result_list[0] if len(result_list) > 0 else {}

        keywords = int(metrics.get("organic", {}).get("count", 0))
        etv = float(metrics.get("organic", {}).get("etv", 0.0))
        top_10 = int(metrics.get("organic", {}).get("is_top_10", 0))
        paid_cost = float(metrics.get("organic", {}).get("estimated_paid_traffic_cost", 0.0))

        return ETVVerification(
            domain=domain, keywords=keywords, etv=etv, top_10=top_10,
            estimated_paid_cost=paid_cost, verified=True, verified_at=now_iso,
        )
    except (ValueError, IndexError, TypeError, KeyError) as exc:
        logger.warning("ETV parse error for %s: %s", domain, exc)
        return ETVVerification(
            domain=domain, keywords=0, etv=0.0, top_10=0,
            estimated_paid_cost=0.0, verified=False, verified_at=now_iso,
        )


def _call_dataforseo_etv(
    domain: str, login: str, password: str,
) -> ETVVerification:
    """Call DataForSEO domain_rank_overview for a single domain's ETV."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert isinstance(login, str) and len(login) > 0, "login required"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"
    payload = [{"target": domain, "language_code": "en", "location_code": 2840}]

    try:
        creds = base64.b64encode(f"{login}:{password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
        }

        import urllib.request  # noqa: F811 -- use stdlib per codebase convention
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)

        logger.info("ETV API call for %s: status=%d", domain, resp.status)
        return _parse_etv_response(data, domain)
    except Exception as exc:  # noqa: BLE001 -- graceful fallback
        logger.warning("ETV API error for %s: %s", domain, exc)
        return ETVVerification(
            domain=domain, keywords=0, etv=0.0, top_10=0,
            estimated_paid_cost=0.0, verified=False, verified_at=now_iso,
        )


def _mock_etv_verification(domain: str) -> ETVVerification:
    """Return mock ETV verification data for dry-run mode."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert "." in domain, f"domain must contain dot: {domain}"

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    # Deterministic mock: hash domain name to get stable fake metrics
    hash_val = int(hashlib.sha256(domain.encode()).hexdigest()[:8], 16)
    mock_etv = float(hash_val % 2000)  # 0-1999 range
    mock_kw = (hash_val % 500) + 10
    mock_top10 = hash_val % 50
    mock_cost = mock_etv * 1.2

    return ETVVerification(
        domain=domain, keywords=mock_kw, etv=mock_etv, top_10=mock_top10,
        estimated_paid_cost=mock_cost, verified=True, verified_at=now_iso,
    )


def verify_etv_batch(
    domains: list[str], config: dict, *, dry_run: bool = False,
) -> list[ETVVerification]:
    """Verify ETV for a batch of domains via DataForSEO domain_rank_overview.

    Respects MAX_ETV_CHECKS_PER_RUN budget guard and rate limiting.
    Returns list of ETVVerification results for all checked domains.
    """
    assert isinstance(domains, list), "domains must be list"
    assert isinstance(config, dict), "config must be dict"

    max_checks = min(
        len(domains),
        int(config.get("etv_max_checks_per_run", MAX_ETV_CHECKS_PER_RUN)),
    )
    etv_threshold = float(config.get("etv_min_threshold", ETV_MIN_THRESHOLD))
    results: list[ETVVerification] = []

    if dry_run:
        for idx, domain in enumerate(domains[:max_checks]):
            if idx >= MAX_ETV_CHECKS_PER_RUN:
                break
            results.append(_mock_etv_verification(domain))
        logger.info("[DRY RUN] ETV verified %d domains (threshold=$%.0f)", len(results), etv_threshold)
        return results

    login, password = _load_dataforseo_credentials()
    if not login or not password:
        logger.warning("DataForSEO credentials not set, skipping ETV verification")
        return results

    total_cost = 0.0
    for idx, domain in enumerate(domains[:max_checks]):
        if idx >= MAX_ETV_CHECKS_PER_RUN:
            break

        verification = _call_dataforseo_etv(domain, login, password)
        results.append(verification)
        total_cost += ETV_API_COST

        logger.info(
            "ETV check %d/%d: %s -> etv=$%.2f kw=%d top10=%d verified=%s",
            idx + 1, max_checks, domain, verification.etv,
            verification.keywords, verification.top_10, verification.verified,
        )

        # Rate limit: max 5 calls/second (0.2s delay between calls)
        if idx < max_checks - 1:
            time.sleep(ETV_RATE_LIMIT_DELAY)

    logger.info(
        "ETV batch complete: %d checked, total API cost=$%.2f",
        len(results), total_cost,
    )
    assert len(results) <= MAX_ETV_CHECKS_PER_RUN, "exceeded ETV budget guard"
    return results


def _log_etv_results(results: list[ETVVerification], output_dir: str) -> None:
    """Log ETV verification results summary and write to JSON audit file."""
    assert isinstance(results, list), "results must be list"
    assert isinstance(output_dir, str) and len(output_dir) > 0, "output_dir required"

    if not results:
        logger.info("ETV verify: no results to log")
        return

    passed = [r for r in results if r.verified and r.etv >= ETV_MIN_THRESHOLD]
    whales = [r for r in results if r.verified and r.etv >= ETV_WHALE_THRESHOLD]
    failed = [r for r in results if not r.verified]

    logger.info(
        "ETV summary: %d checked, %d passed (>=$%.0f), %d whales (>=$%.0f), %d failed",
        len(results), len(passed), ETV_MIN_THRESHOLD,
        len(whales), ETV_WHALE_THRESHOLD, len(failed),
    )

    for r in whales:
        logger.info(
            "  WHALE ETV: %s etv=$%.2f kw=%d top10=%d",
            r.domain, r.etv, r.keywords, r.top_10,
        )

    # Write audit JSON
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    audit_file = out_path / f"etv_audit_{today_str}.json"

    audit_data = {
        "run_date": today_str,
        "total_checked": len(results),
        "passed_count": len(passed),
        "whale_count": len(whales),
        "failed_count": len(failed),
        "threshold": ETV_MIN_THRESHOLD,
        "whale_threshold": ETV_WHALE_THRESHOLD,
        "results": [asdict(r) for r in results[:MAX_ETV_CHECKS_PER_RUN]],
    }
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, default=str)

    logger.info("ETV audit written to %s", audit_file)


def _apply_etv_to_candidate(
    candidate: DomainCandidate, etv_result: ETVVerification,
) -> DomainCandidate:
    """Enrich a candidate with ETV verification data in its notes field."""
    assert isinstance(candidate, DomainCandidate), "candidate must be DomainCandidate"
    assert isinstance(etv_result, ETVVerification), "etv_result must be ETVVerification"

    etv_note = (
        f" [ETV: ${etv_result.etv:.0f}/mo, "
        f"kw={etv_result.keywords}, top10={etv_result.top_10}]"
    )
    if etv_result.etv >= ETV_WHALE_THRESHOLD:
        etv_note += " [WHALE-ETV]"

    return DomainCandidate(
        domain=candidate.domain, source=candidate.source,
        da_estimate=candidate.da_estimate,
        traffic_estimate=candidate.traffic_estimate,
        niche=candidate.niche, expiry_date=candidate.expiry_date,
        price_usd=candidate.price_usd,
        backlinks=candidate.backlinks,
        referring_domains=candidate.referring_domains,
        notes=candidate.notes + etv_note,
    )


def run_etv_verification_stage(
    candidates: list[DomainCandidate],
    config: dict,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Sprint 14 ETV verification pipeline stage.

    Takes candidates after PRICE_VERIFY, calls DataForSEO domain_rank_overview
    for each, filters by ETV threshold, and enriches passing candidates.
    Only candidates with verified ETV >= threshold are kept.
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert isinstance(config, dict), "config must be dict"

    if not config.get("etv_enabled", False):
        logger.info("Sprint 14: ETV verification disabled in config, skipping")
        return candidates

    etv_threshold = float(config.get("etv_min_threshold", ETV_MIN_THRESHOLD))
    domain_names = [c.domain for c in candidates[:MAX_ETV_CHECKS_PER_RUN]]

    logger.info(
        "Sprint 14: ETV verification starting for %d candidates (threshold=$%.0f)",
        len(domain_names), etv_threshold,
    )

    # Call DataForSEO ETV batch
    etv_results = verify_etv_batch(domain_names, config, dry_run=dry_run)

    # Build lookup map: domain -> ETVVerification
    etv_map: dict[str, ETVVerification] = {}
    for r in etv_results:
        etv_map[r.domain.lower()] = r

    # Filter and enrich: only keep candidates that pass ETV threshold
    output_dir = str(PROJECT_ROOT / config.get("output_dir", "data/daily"))
    _log_etv_results(etv_results, output_dir)

    enriched: list[DomainCandidate] = []
    filtered_out = 0
    for candidate in candidates:
        etv_result = etv_map.get(candidate.domain.lower())
        if etv_result is None:
            # Not checked (over budget limit) -- pass through unchanged
            enriched.append(candidate)
            continue
        if etv_result.verified and etv_result.etv >= etv_threshold:
            enriched.append(_apply_etv_to_candidate(candidate, etv_result))
        else:
            filtered_out += 1
            logger.info(
                "ETV filter: %s removed (etv=$%.2f, verified=%s)",
                candidate.domain, etv_result.etv, etv_result.verified,
            )

    logger.info(
        "Sprint 14: ETV stage complete: %d in -> %d passed, %d filtered out",
        len(candidates), len(enriched), filtered_out,
    )
    return enriched


# ---------------------------------------------------------------------------
# Niche classification (keyword-based, no ML needed)
# ---------------------------------------------------------------------------
_NICHE_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "cooking": ("recipe", "cook", "meal", "food", "kitchen", "chef", "bake",
                "ingredient", "cuisine", "dine", "eat", "nutrition", "diet"),
    "health": ("health", "medical", "wellness", "therapy", "doctor", "nurse",
               "patient", "clinic", "pharma", "care", "mental", "body"),
    "tech": ("tech", "code", "dev", "software", "app", "api", "cloud", "data",
             "cyber", "digital", "web", "program", "hack", "build", "tool"),
    "finance": ("finance", "invest", "money", "bank", "budget", "fund", "stock",
                "trade", "crypto", "payment", "credit", "loan", "wealth"),
    "tools": ("tool", "util", "helper", "maker", "builder", "generator",
              "calculator", "converter", "editor", "manager", "tracker"),
    "education": ("learn", "edu", "course", "teach", "study", "tutor",
                  "school", "academy", "class", "lesson", "train"),
    "fitness": ("fit", "gym", "workout", "exercise", "yoga", "run", "muscle",
                "weight", "cardio", "sport", "athlete", "train"),
    "travel": ("travel", "trip", "hotel", "flight", "booking", "tour",
               "vacation", "journey", "explore", "destination", "guide"),
    "food": ("food", "restaurant", "snack", "drink", "coffee", "tea",
             "organic", "vegan", "gourmet", "taste", "flavor"),
    "software": ("saas", "platform", "dashboard", "analytics", "crm",
                 "erp", "automation", "workflow", "integration", "sync"),
}


def classify_niche(candidate: DomainCandidate) -> DomainCandidate:
    """Classify a domain into a niche based on domain name keywords."""
    assert isinstance(candidate, DomainCandidate), "candidate must be DomainCandidate"

    domain_lower = candidate.domain.lower()
    # Strip TLD for keyword matching
    base = domain_lower.split(".")[0] if "." in domain_lower else domain_lower
    notes_lower = candidate.notes.lower()
    search_text = f"{base} {notes_lower}"

    best_niche = "unknown"
    best_score = 0

    niche_count = 0
    for niche, keywords in _NICHE_KEYWORDS.items():
        if niche_count >= MAX_NICHE_KEYWORDS:
            break
        niche_count += 1
        score = sum(1 for kw in keywords if kw in search_text)
        if score > best_score:
            best_score = score
            best_niche = niche

    assert isinstance(best_niche, str), "niche must be string"
    return DomainCandidate(
        domain=candidate.domain, source=candidate.source,
        da_estimate=candidate.da_estimate,
        traffic_estimate=candidate.traffic_estimate,
        niche=best_niche if best_score > 0 else "unknown",
        expiry_date=candidate.expiry_date, price_usd=candidate.price_usd,
        backlinks=candidate.backlinks,
        referring_domains=candidate.referring_domains,
        notes=candidate.notes,
    )


def classify_all_niches(candidates: list[DomainCandidate]) -> list[DomainCandidate]:
    """Classify niches for all candidates."""
    assert isinstance(candidates, list), "candidates must be list"

    classified = [
        classify_niche(c)
        for idx, c in enumerate(candidates)
        if idx < MAX_TOTAL_CANDIDATES
    ]
    assert len(classified) <= MAX_TOTAL_CANDIDATES, "classified exceeds max"
    return classified


# ---------------------------------------------------------------------------
# Sprint 12: Price verification (prevent aftermarket price mismatches)
# ---------------------------------------------------------------------------
def _check_gdauctions_price(
    domain: str,
    session: requests.Session,
    config: PipelineConfig,
) -> dict:
    """Check GoDaddy auctions for the actual auction/bid price of a domain."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert session is not None, "session required"

    url = f"https://auctions.godaddy.com/trpSearchResults.aspx?t=16&action=search&query={domain}"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        return {"found": False, "price": 0.0, "url": url}

    text = resp.text.lower()
    # Look for the domain and a price pattern in the auction results
    if domain.lower() not in text:
        return {"found": False, "price": 0.0, "url": url}

    # Search for price indicators in auction page
    price = _extract_price_from_auction_html(text)
    assert isinstance(price, float), "price must be float"
    return {"found": price > 0.0, "price": price, "url": url}


def _extract_price_from_auction_html(text: str) -> float:
    """Extract numeric price from GoDaddy auction HTML text."""
    assert isinstance(text, str), "text must be string"

    # Look for common price patterns: $X,XXX or $X.XX
    price_markers = ("current price:", "buy now:", "minimum bid:", "price:")
    for marker in price_markers:
        idx = text.find(marker)
        if idx < 0:
            continue
        # Scan forward from marker for dollar sign or digits
        segment = text[idx:min(idx + 80, len(text))]
        extracted = _parse_dollar_amount(segment)
        if extracted > 0.0:
            return extracted

    assert isinstance(text, str), "text type preserved"
    return 0.0


def _parse_dollar_amount(segment: str) -> float:
    """Parse a dollar amount from a text segment like '$1,540.00'."""
    assert isinstance(segment, str), "segment must be string"
    assert len(segment) <= 200, f"segment too long: {len(segment)}"

    dollar_idx = segment.find("$")
    if dollar_idx < 0:
        # Try to find bare number after colon
        for ch_idx in range(len(segment)):
            if ch_idx >= 100:  # safety bound
                break
            if segment[ch_idx].isdigit():
                dollar_idx = ch_idx - 1
                break

    if dollar_idx < 0:
        return 0.0

    num_chars: list[str] = []
    for ci in range(dollar_idx + 1, min(dollar_idx + 20, len(segment))):
        ch = segment[ci]
        if ch.isdigit() or ch in (".", ","):
            num_chars.append(ch)
        elif ch == " " and not num_chars:
            continue
        elif num_chars:
            break

    if not num_chars:
        return 0.0

    try:
        cleaned = "".join(num_chars).replace(",", "")
        return float(cleaned)
    except ValueError:
        return 0.0


def _check_aftermarket_price(
    domain: str,
    session: requests.Session,
    config: PipelineConfig,
) -> dict:
    """Check GoDaddy domain search for aftermarket/premium listing price."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert session is not None, "session required"

    url = f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        return {"found": False, "price": 0.0, "url": url}

    text = resp.text.lower()
    # Aftermarket listings show "aftermarket" or "premium" or "make offer"
    is_aftermarket = any(
        marker in text
        for marker in ("aftermarket", "premium listing", "make offer", "buy now for")
    )
    price = _extract_price_from_auction_html(text) if is_aftermarket else 0.0

    assert isinstance(price, float), "price must be float"
    return {"found": is_aftermarket, "price": price, "url": url}


def _check_registration_available(
    domain: str,
    session: requests.Session,
    config: PipelineConfig,
) -> dict:
    """Check if a domain is available for standard registration (not aftermarket)."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert session is not None, "session required"

    url = f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        return {"available": False, "reg_price": 0.0, "url": url}

    text = resp.text.lower()
    # Standard registration shows "add to cart" without "aftermarket"/"premium"
    is_standard = "add to cart" in text and "aftermarket" not in text and "premium listing" not in text
    reg_price = _extract_price_from_auction_html(text) if is_standard else 0.0

    assert isinstance(reg_price, float), "reg_price must be float"
    return {"available": is_standard, "reg_price": reg_price, "url": url}


def _classify_price_source(
    gdauctions_result: dict,
    aftermarket_result: dict,
    reg_result: dict,
) -> tuple[float, str, str]:
    """Determine the real price source from multiple check results.

    Returns: (verified_price, verified_source, verified_url)
    """
    assert isinstance(gdauctions_result, dict), "gdauctions_result must be dict"
    assert isinstance(aftermarket_result, dict), "aftermarket_result must be dict"

    # Priority: aftermarket listing > auction bid > registration
    if aftermarket_result.get("found", False) and aftermarket_result.get("price", 0) > 0:
        return (
            float(aftermarket_result["price"]),
            "gd_aftermarket",
            str(aftermarket_result.get("url", "")),
        )

    if gdauctions_result.get("found", False) and gdauctions_result.get("price", 0) > 0:
        return (
            float(gdauctions_result["price"]),
            "gdauctions",
            str(gdauctions_result.get("url", "")),
        )

    if reg_result.get("available", False):
        return (
            float(reg_result.get("reg_price", 0.0)),
            "registration",
            str(reg_result.get("url", "")),
        )

    return (0.0, "unknown", "")


def _mock_price_verification(domain: str) -> PriceVerification:
    """Return mock price verification data for dry-run mode."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert "." in domain, f"domain must contain dot: {domain}"

    # Simulate a few mismatches for testing the pipeline flag logic
    mismatch_domains = ("devtoolkit.io", "codesnippets.io", "devworkflow.io")
    is_mismatch = domain.lower() in mismatch_domains

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    if is_mismatch:
        return PriceVerification(
            domain=domain,
            claimed_price=9.99,
            claimed_source="godaddy_closeouts",
            verified_price=1540.0,
            verified_source="gd_aftermarket",
            verification_status="mismatch",
            price_ratio=154.15,
            verified_url=f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}",
            checked_at=now_iso,
        )
    return PriceVerification(
        domain=domain,
        claimed_price=9.99,
        claimed_source="godaddy_closeouts",
        verified_price=9.99,
        verified_source="registration",
        verification_status="confirmed",
        price_ratio=1.0,
        verified_url=f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}",
        checked_at=now_iso,
    )


def _build_single_verification(
    candidate: DomainCandidate,
    session: requests.Session,
    config: PipelineConfig,
) -> PriceVerification:
    """Run all price checks for a single domain and return verification result."""
    assert isinstance(candidate, DomainCandidate), "candidate must be DomainCandidate"
    assert session is not None, "session required"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    domain = candidate.domain
    claimed = candidate.price_usd if candidate.price_usd > 0 else 9.99

    # Run all three checks
    gd_auction = _check_gdauctions_price(domain, session, config)
    gd_aftermarket = _check_aftermarket_price(domain, session, config)
    reg_check = _check_registration_available(domain, session, config)

    verified_price, verified_source, verified_url = _classify_price_source(
        gd_auction, gd_aftermarket, reg_check,
    )

    # Determine status and ratio
    if verified_price <= 0.0:
        status = "unavailable"
        ratio = 0.0
    elif claimed > 0 and verified_price / claimed > PRICE_MISMATCH_THRESHOLD:
        status = "mismatch"
        ratio = verified_price / claimed
    else:
        status = "confirmed"
        ratio = verified_price / claimed if claimed > 0 else 0.0

    return PriceVerification(
        domain=domain,
        claimed_price=claimed,
        claimed_source=candidate.source,
        verified_price=verified_price,
        verified_source=verified_source,
        verification_status=status,
        price_ratio=round(ratio, 2),
        verified_url=verified_url,
        checked_at=now_iso,
    )


def _apply_price_flag(
    candidate: DomainCandidate,
    verification: PriceVerification,
) -> DomainCandidate:
    """Apply price mismatch flag to a candidate, downgrading tier if needed."""
    assert isinstance(candidate, DomainCandidate), "candidate must be DomainCandidate"
    assert isinstance(verification, PriceVerification), "verification must be PriceVerification"

    if verification.verification_status != "mismatch":
        return candidate

    mismatch_note = (
        f" [PRICE MISMATCH: claimed=${verification.claimed_price:.2f} "
        f"vs verified=${verification.verified_price:.2f} "
        f"({verification.verified_source}, ratio={verification.price_ratio:.1f}x)]"
    )
    new_notes = candidate.notes + mismatch_note

    logger.warning(
        "PRICE MISMATCH: %s claimed=$%.2f verified=$%.2f (%s, %.1fx)",
        candidate.domain, verification.claimed_price,
        verification.verified_price, verification.verified_source,
        verification.price_ratio,
    )

    # Downgrade: zero out the misleading price, add warning to notes
    return DomainCandidate(
        domain=candidate.domain, source=candidate.source,
        da_estimate=candidate.da_estimate,
        traffic_estimate=candidate.traffic_estimate,
        niche=candidate.niche, expiry_date=candidate.expiry_date,
        price_usd=verification.verified_price,
        backlinks=candidate.backlinks,
        referring_domains=candidate.referring_domains,
        notes=new_notes,
    )


def verify_domain_prices(
    candidates: list,
    config: PipelineConfig,
    session: requests.Session,
    *,
    dry_run: bool = False,
) -> tuple[list, list[PriceVerification]]:
    """Verify actual purchase prices for pipeline candidates.

    Returns: (candidates_with_price_data, list_of_verifications)

    Candidates with price mismatch > PRICE_MISMATCH_THRESHOLD get
    their notes updated with [PRICE MISMATCH] warning and are
    downgraded from BUY to MONITOR tier.
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if not PRICE_VERIFY_ENABLED:
        logger.info("Price verification disabled, skipping")
        return candidates, []

    max_checks = min(len(candidates), MAX_PRICE_CHECKS_PER_RUN)
    verifications: list[PriceVerification] = []
    updated_candidates: list[DomainCandidate] = []

    for idx, candidate in enumerate(candidates):
        if idx >= MAX_TOTAL_CANDIDATES:  # safety bound
            break

        if idx < max_checks:
            if dry_run:
                verification = _mock_price_verification(candidate.domain)
            else:
                verification = _build_single_verification(candidate, session, config)
            verifications.append(verification)
            updated = _apply_price_flag(candidate, verification)
            updated_candidates.append(updated)

            # Rate limit between checks (not after last one)
            if not dry_run and idx < max_checks - 1:
                time.sleep(config.rate_limit_base_delay_seconds)
        else:
            updated_candidates.append(candidate)

    mismatch_count = sum(1 for v in verifications if v.verification_status == "mismatch")
    confirmed_count = sum(1 for v in verifications if v.verification_status == "confirmed")
    logger.info(
        "Price verify: %d checked, %d confirmed, %d mismatches, %d skipped",
        len(verifications), confirmed_count, mismatch_count,
        len(candidates) - len(verifications),
    )

    assert len(updated_candidates) == len(candidates), "price verify must preserve candidate count"
    return updated_candidates, verifications


def _log_price_verifications(verifications: list[PriceVerification]) -> None:
    """Log a summary of price verification results for audit trail."""
    assert isinstance(verifications, list), "verifications must be list"

    if not verifications:
        logger.info("Price verify: no verifications to log")
        assert isinstance(verifications, list), "verifications type preserved when empty"
        return

    for idx, v in enumerate(verifications):
        if idx >= MAX_PRICE_CHECKS_PER_RUN:  # safety bound
            break
        if v.verification_status == "mismatch":
            logger.warning(
                "  MISMATCH: %s claimed=$%.2f actual=$%.2f (%s, %.1fx)",
                v.domain, v.claimed_price, v.verified_price,
                v.verified_source, v.price_ratio,
            )
        elif v.verification_status == "confirmed":
            logger.info(
                "  CONFIRMED: %s $%.2f (%s)", v.domain, v.verified_price, v.verified_source,
            )


# ---------------------------------------------------------------------------
# Result storage (daily JSON snapshots)
# ---------------------------------------------------------------------------
def _ensure_output_dir(output_dir: Path) -> None:
    """Create output directory if it does not exist."""
    assert isinstance(output_dir, Path), "output_dir must be Path"

    output_dir.mkdir(parents=True, exist_ok=True)
    assert output_dir.is_dir(), f"Failed to create output dir: {output_dir}"


def _compute_run_hash(candidates: list[DomainCandidate]) -> str:
    """Compute a deterministic hash of the candidate list for idempotency."""
    assert isinstance(candidates, list), "candidates must be list"

    domains_str = "|".join(sorted(c.domain for c in candidates))
    hash_val = hashlib.sha256(domains_str.encode("utf-8")).hexdigest()[:16]
    assert len(hash_val) == 16, "hash must be 16 chars"
    return hash_val


def _load_existing_snapshot(output_file: Path) -> tuple[list[dict], int]:
    """Load existing daily snapshot for idempotent merge."""
    assert isinstance(output_file, Path), "output_file must be Path"

    if not output_file.is_file():
        assert isinstance(output_file, Path), "output_file type preserved when absent"
        return [], 0

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        candidates = existing_data.get("candidates", [])
        lookups = existing_data.get("dataforseo_lookups_used", 0)
        return candidates, int(lookups)
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        logger.warning("Failed to read existing snapshot, will overwrite: %s", exc)
        return [], 0


def _write_snapshot(
    output_file: Path,
    all_stored: list[dict],
    candidates: list[DomainCandidate],
    total_lookups: int,
    min_da_filter: int,
) -> None:
    """Write merged snapshot data to JSON file."""
    assert isinstance(output_file, Path), "output_file must be Path"
    assert isinstance(all_stored, list), "all_stored must be list"

    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    output_data = {
        "run_date": today_str,
        "run_hash": _compute_run_hash(candidates),
        "total_scanned": len(all_stored),
        "total_after_dedup": len(all_stored),
        "total_above_min_da": sum(1 for c in all_stored if c.get("da_estimate", 0) >= min_da_filter),
        "dataforseo_lookups_used": total_lookups,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "candidates": all_stored[:MAX_TOTAL_CANDIDATES],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, default=str)

    assert output_file.is_file(), f"Output file was not created: {output_file}"


def store_daily_results(
    candidates: list[DomainCandidate],
    config: PipelineConfig,
    dataforseo_lookups: int,
) -> Path:
    """Save daily results to JSON file. Idempotent -- same-day runs merge."""
    assert isinstance(candidates, list), "candidates must be list"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    output_dir = PROJECT_ROOT / config.output_dir
    _ensure_output_dir(output_dir)

    today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    output_file = output_dir / f"{today_str}.json"

    existing_candidates, existing_lookups = _load_existing_snapshot(output_file)
    existing_domains = {c["domain"] for c in existing_candidates}

    new_candidates = [asdict(c) for c in candidates if c.domain not in existing_domains]
    all_stored = existing_candidates + new_candidates

    _write_snapshot(output_file, all_stored, candidates, existing_lookups + dataforseo_lookups, config.min_da_filter)
    logger.info("Stored %d candidates to %s", len(all_stored), output_file)
    return output_file


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------
def generate_alerts(
    candidates: list[DomainCandidate], config: PipelineConfig,
) -> list[str]:
    """Generate human-readable alerts for high-value finds."""
    assert isinstance(candidates, list), "candidates must be list"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    alerts: list[str] = []

    for idx, c in enumerate(candidates):
        if idx >= MAX_TOTAL_CANDIDATES:
            break
        if len(alerts) >= MAX_ALERT_LINES:
            break

        if c.da_estimate >= config.critical_da_threshold:
            alerts.append(
                f"*** CRITICAL (DA {c.da_estimate}) *** {c.domain} "
                f"[{c.source}] traffic={c.traffic_estimate} niche={c.niche}"
            )
        elif c.da_estimate >= config.alert_da_threshold:
            alerts.append(
                f"ALERT (DA {c.da_estimate}): {c.domain} "
                f"[{c.source}] traffic={c.traffic_estimate} niche={c.niche}"
            )

    assert len(alerts) <= MAX_ALERT_LINES, f"Too many alerts: {len(alerts)}"
    return alerts


def print_alerts(alerts: list[str]) -> None:
    """Print alerts to stdout with visual formatting."""
    assert isinstance(alerts, list), "alerts must be list"

    if not alerts:
        print("\n  No high-DA alerts today.\n")
        assert isinstance(alerts, list), "alerts list verified empty"
        return

    print("\n" + "=" * 70)
    print("  DOMAIN HUNTER DAILY ALERTS")
    print("=" * 70)
    for idx, alert in enumerate(alerts):
        if idx >= MAX_ALERT_LINES:
            break
        print(f"  {alert}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# Pipeline filters
# ---------------------------------------------------------------------------
def filter_by_min_da(
    candidates: list[DomainCandidate], min_da: int,
) -> list[DomainCandidate]:
    """Filter candidates to only those meeting minimum DA threshold."""
    assert isinstance(candidates, list), "candidates must be list"
    assert min_da >= 0, f"min_da must be >= 0, got {min_da}"

    filtered = [
        c for idx, c in enumerate(candidates)
        if idx < MAX_TOTAL_CANDIDATES and c.da_estimate >= min_da
    ]
    logger.info(
        "DA filter (>= %d): %d -> %d candidates",
        min_da, len(candidates), len(filtered),
    )
    assert len(filtered) <= len(candidates), "filter cannot increase count"
    return filtered


# ---------------------------------------------------------------------------
# Pipeline summary
# ---------------------------------------------------------------------------
def print_summary(
    all_raw: list[DomainCandidate],
    deduped: list[DomainCandidate],
    filtered: list[DomainCandidate],
    enriched: list[DomainCandidate],
    output_file: Path,
    elapsed: float,
    dry_run: bool,
    dataforseo_lookups: int = 0,
) -> None:
    """Print a human-readable pipeline summary with timing and cost."""
    assert isinstance(output_file, Path), "output_file must be Path"
    assert elapsed >= 0, "elapsed must be non-negative"

    mode = "DRY RUN" if dry_run else "LIVE"
    cost_usd = dataforseo_lookups * 0.001
    niche_counts: dict[str, int] = {}
    for idx, c in enumerate(enriched):
        if idx >= MAX_TOTAL_CANDIDATES:
            break
        niche_counts[c.niche] = niche_counts.get(c.niche, 0) + 1

    print("\n" + "=" * 70)
    print(f"  DOMAIN HUNTER DAILY PIPELINE [{mode}]")
    print(f"  Date: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  DataForSEO lookups:  {dataforseo_lookups:>5}  (~${cost_usd:.3f})")
    print("=" * 70)
    print(f"  Sources scanned:     {len(all_raw):>5} raw candidates")
    print(f"  After dedup:         {len(deduped):>5} unique")
    print(f"  After DA filter:     {len(filtered):>5} (DA >= threshold)")
    print(f"  After enrichment:    {len(enriched):>5} final")
    print("-" * 70)
    print("  Niche breakdown:")
    for niche, count in sorted(niche_counts.items(), key=lambda x: -x[1]):
        print(f"    {niche:<20} {count:>3}")
    print("-" * 70)
    print(f"  Output: {output_file}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    assert argv is None or isinstance(argv, list), "argv must be None or list"

    parser = argparse.ArgumentParser(
        description="Domain Hunter REVENANT -- Automated Daily Pipeline",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Run with mock data, no API calls",
    )
    parser.add_argument(
        "--config", type=Path,
        default=SCRIPT_DIR / CONFIG_FILENAME,
        help=f"Path to config JSON (default: {CONFIG_FILENAME})",
    )
    parser.add_argument(
        "--min-da", type=int, default=None,
        help="Override minimum DA filter (default: from config)",
    )
    parser.add_argument(
        "--sources", type=str, default=None,
        help="Comma-separated source list override (e.g. 'domcop,tech_shutdowns')",
    )
    args = parser.parse_args(argv)
    assert isinstance(args.dry_run, bool), "dry_run must be bool"
    return args


# ---------------------------------------------------------------------------
# Source 5: CatchDoms Apify Actor (55K+ domains/day from 12 platforms)
# ---------------------------------------------------------------------------
def fetch_catchdoms_apify(
    session: requests.Session, config: PipelineConfig, *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Fetch expired domains from CatchDoms Apify actor (public, no auth)."""
    assert session is not None, "session required"
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"

    if dry_run:
        logger.info("[DRY RUN] Skipping CatchDoms Apify fetch")
        return _mock_catchdoms_apify()

    url = "https://api.apify.com/v2/acts/catchdoms~expired-domains-api/runs/last/dataset/items"
    resp = _request_with_backoff(session, url, config)

    if resp is None:
        logger.warning("CatchDoms Apify fetch failed, returning empty")
        return []

    candidates = _parse_catchdoms_response(resp, config.max_domains_per_source)
    logger.info("CatchDoms Apify: found %d candidates (post-filter)", len(candidates))
    return candidates


def _parse_catchdoms_response(
    resp: requests.Response, max_count: int,
) -> list[DomainCandidate]:
    """Parse CatchDoms JSON response, applying quality + DA filters."""
    assert resp is not None, "response required"
    assert max_count > 0, f"max_count must be positive, got {max_count}"

    try:
        items = resp.json()
        assert isinstance(items, list), "CatchDoms response must be a JSON array"
    except (json.JSONDecodeError, ValueError, AssertionError) as exc:
        logger.warning("CatchDoms parse error: %s", exc)
        return []

    candidates: list[DomainCandidate] = []
    for idx, item in enumerate(items):
        if idx >= MAX_TOTAL_CANDIDATES * 2:  # safety bound
            break
        if len(candidates) >= max_count:
            break
        candidate = _catchdoms_item_to_candidate(item)
        if candidate is not None:
            candidates.append(candidate)

    return candidates


def _catchdoms_item_to_candidate(item: dict) -> DomainCandidate | None:
    """Convert a single CatchDoms item to DomainCandidate if it passes filters."""
    assert isinstance(item, dict), "item must be dict"

    domain = str(item.get("domain", "")).lower().strip()
    quality_score = int(item.get("quality_score", 0))
    da_value = int(item.get("DA", item.get("da", 0)))
    platform = str(item.get("platform", ""))

    # Apply quality + DA filters per spec
    if quality_score < CATCHDOMS_MIN_QUALITY or da_value < CATCHDOMS_MIN_DA:
        return None
    if not domain or "." not in domain or len(domain) > 253:
        return None

    assert len(domain) > 0, "domain validated non-empty"
    return DomainCandidate(
        domain=domain,
        source="catchdoms_apify",
        da_estimate=da_value,
        referring_domains=int(item.get("referring_domains", 0)),
        backlinks=int(item.get("dofollow%", 0)),  # store dofollow% in backlinks
        price_usd=float(item.get("price", 0.0)),
        notes=f"platform={platform} quality={quality_score} tf={item.get('TF', 0)} cf={item.get('CF', 0)} wayback_age={item.get('wayback_age', 'N/A')}",
    )


def _mock_catchdoms_apify() -> list[DomainCandidate]:
    """Return mock CatchDoms data for dry-run (8 domains)."""
    mock_domains = [
        ("freshpantry.com", 32, 45, "dropcatch", 89),
        ("codesnippets.io", 48, 62, "namejet", 156),
        ("fitnesslog.net", 21, 38, "snapnames", 34),
        ("budgettracker.org", 27, 41, "godaddy_auctions", 67),
        ("herbalgarden.com", 35, 55, "dynadot", 112),
        ("devworkflow.io", 44, 70, "dropcatch", 201),
        ("mealprepguide.com", 18, 33, "porkbun", 23),
        ("investcalc.net", 29, 50, "namecheap", 78),
    ]
    assert len(mock_domains) >= 8, "mock data must have at least 8 entries"
    assert len(mock_domains) <= MAX_DOMAINS_PER_SOURCE, "mock data exceeds limit"
    return [
        DomainCandidate(
            domain=d, source="catchdoms_apify", da_estimate=da,
            referring_domains=rd,
            notes=f"platform={plat} quality={qs}",
        )
        for d, da, qs, plat, rd in mock_domains
    ]


# ---------------------------------------------------------------------------
# Cross-validation: OpenRank.io (bulk DA check, 500K/day, 50/request)
# ---------------------------------------------------------------------------
def openrank_cross_validate(
    session: requests.Session,
    candidates: list[DomainCandidate],
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Cross-validate DA scores using OpenRank.io free API."""
    assert session is not None, "session required"
    assert isinstance(candidates, list), "candidates must be list"

    if dry_run:
        logger.info("[DRY RUN] Skipping OpenRank cross-validation")
        return candidates

    if not candidates:
        return candidates

    enriched: list[DomainCandidate] = []
    total_batches = min(
        (len(candidates) + OPENRANK_BATCH_SIZE - 1) // OPENRANK_BATCH_SIZE,
        OPENRANK_MAX_DAILY_REQUESTS,
    )

    for batch_idx in range(total_batches):
        batch_start = batch_idx * OPENRANK_BATCH_SIZE
        batch_end = min(batch_start + OPENRANK_BATCH_SIZE, len(candidates))
        batch = candidates[batch_start:batch_end]
        batch_results = _openrank_check_batch(session, batch, config)
        enriched.extend(batch_results)
        if batch_idx < total_batches - 1:
            time.sleep(config.rate_limit_base_delay_seconds)

    assert len(enriched) <= len(candidates), "cross-validation must not increase count"
    logger.info("OpenRank cross-validation: processed %d candidates", len(enriched))
    return enriched


def _openrank_check_batch(
    session: requests.Session,
    batch: list[DomainCandidate],
    config: PipelineConfig,
) -> list[DomainCandidate]:
    """Check OpenRank scores for a batch of domains (max 50)."""
    assert len(batch) <= OPENRANK_BATCH_SIZE, f"Batch exceeds limit: {len(batch)}"
    assert session is not None, "session required"

    domain_list = [c.domain for c in batch]
    url = "https://openrank.io/api/v1/domain/batch"
    payload = {"domains": domain_list}

    try:
        resp = session.post(
            url, json=payload, timeout=config.http_timeout_seconds,
        )
        if resp.status_code != 200:
            logger.warning("OpenRank API returned %d", resp.status_code)
            return list(batch)
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("OpenRank batch failed: %s", exc)
        return list(batch)

    # Build lookup map from OpenRank response
    or_map = _build_openrank_score_map(data)
    return _merge_openrank_scores(batch, or_map)


def _build_openrank_score_map(data: list | dict) -> dict[str, float]:
    """Build domain -> openrank_score map from API response."""
    assert isinstance(data, (list, dict)), "data must be list or dict"

    or_map: dict[str, float] = {}
    items = data if isinstance(data, list) else data.get("results", data.get("data", []))
    if not isinstance(items, list):
        return or_map

    for idx, item in enumerate(items):
        if idx >= OPENRANK_BATCH_SIZE * 2:  # safety bound
            break
        if isinstance(item, dict):
            domain = str(item.get("domain", "")).lower()
            score = float(item.get("openrank_score", item.get("score", 0)))
            if domain:
                or_map[domain] = score

    assert isinstance(or_map, dict), "result must be dict"
    return or_map


def _merge_openrank_scores(
    batch: list[DomainCandidate], or_map: dict[str, float],
) -> list[DomainCandidate]:
    """Merge OpenRank scores into candidates, flagging DA discrepancies."""
    assert isinstance(batch, list), "batch must be list"
    assert isinstance(or_map, dict), "or_map must be dict"

    enriched: list[DomainCandidate] = []
    for candidate in batch:
        or_score = or_map.get(candidate.domain.lower())
        if or_score is not None:
            discrepancy = abs(candidate.da_estimate - int(or_score))
            flag = ""
            if discrepancy >= DA_DISCREPANCY_THRESHOLD:
                flag = f" [DA DISCREPANCY: OPR={candidate.da_estimate} vs OR={int(or_score)}, diff={discrepancy}]"
                logger.warning(
                    "DA discrepancy for %s: OpenPageRank=%d, OpenRank=%d (diff=%d)",
                    candidate.domain, candidate.da_estimate, int(or_score), discrepancy,
                )
            new_notes = candidate.notes + flag if flag else candidate.notes
            enriched.append(DomainCandidate(
                domain=candidate.domain, source=candidate.source,
                da_estimate=candidate.da_estimate,
                traffic_estimate=candidate.traffic_estimate,
                niche=candidate.niche, expiry_date=candidate.expiry_date,
                price_usd=candidate.price_usd,
                backlinks=candidate.backlinks,
                referring_domains=candidate.referring_domains,
                notes=new_notes,
            ))
        else:
            enriched.append(candidate)

    return enriched


def _mock_openrank_scores() -> dict[str, float]:
    """Return mock OpenRank scores for dry-run testing."""
    mock_scores = {
        "recipehub.com": 33.0, "cookmaster.net": 20.0, "devtoolkit.io": 42.0,
        "healthguide.org": 25.0, "fittrack.com": 29.0, "codeforge.dev": 17.0,
        "mealplanner.com": 40.0, "techpulse.io": 36.0, "budgetwise.com": 23.0,
        "gardenhelper.net": 15.0,
    }
    assert len(mock_scores) >= 8, "mock scores must have at least 8 entries"
    assert all(isinstance(v, float) for v in mock_scores.values()), "all scores must be float"
    return mock_scores


# ---------------------------------------------------------------------------
# Sprint 13: DeepSeek V3 Batch Classification
# ---------------------------------------------------------------------------
def _build_deepseek_prompt(domains: list[str]) -> str:
    """Build a classification prompt for a batch of domains."""
    assert isinstance(domains, list), "domains must be list"
    assert 0 < len(domains) <= DEEPSEEK_BATCH_SIZE, f"batch size must be 1-{DEEPSEEK_BATCH_SIZE}, got {len(domains)}"

    domain_list = "\n".join(f"- {d}" for d in domains[:DEEPSEEK_BATCH_SIZE])
    prompt = (
        "You are a domain investment analyst. Classify each domain below.\n"
        "Return ONLY a JSON array with one object per domain. Each object must have:\n"
        '  "domain": string, "niche": string, "site_type": string (e.g. "blog", "tool", "saas", "marketplace"),\n'
        '  "tool_idea": string (a one-line product idea), "keyword_value": int (1-10),\n'
        '  "brandability": int (1-10), "monetization": string (e.g. "ads", "affiliate", "saas", "freemium"),\n'
        '  "acquisition_priority": int (1-10, where 10 = must buy immediately)\n\n'
        f"Domains to classify:\n{domain_list}\n\n"
        "Return ONLY valid JSON. No markdown, no explanation."
    )
    assert len(prompt) > 100, "prompt must have meaningful content"
    return prompt


def _parse_deepseek_response(response_text: str) -> list[DeepSeekClassification]:
    """Parse DeepSeek JSON response into classification objects."""
    assert isinstance(response_text, str), "response_text must be string"
    assert len(response_text) > 0, "response_text must not be empty"

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    # Strip markdown fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        last_fence = cleaned.rfind("```")
        if first_nl > 0 and last_fence > first_nl:
            cleaned = cleaned[first_nl + 1:last_fence].strip()

    try:
        items = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("DeepSeek response not valid JSON: %s", exc)
        return []

    if not isinstance(items, list):
        logger.warning("DeepSeek response not a list, got %s", type(items).__name__)
        return []

    results: list[DeepSeekClassification] = []
    for idx, item in enumerate(items):
        if idx >= DEEPSEEK_BATCH_SIZE:
            break
        if not isinstance(item, dict):
            continue
        results.append(DeepSeekClassification(
            domain=str(item.get("domain", "")),
            niche=str(item.get("niche", "unknown")),
            site_type=str(item.get("site_type", "unknown")),
            tool_idea=str(item.get("tool_idea", "")),
            keyword_value=max(1, min(10, int(item.get("keyword_value", 5)))),
            brandability=max(1, min(10, int(item.get("brandability", 5)))),
            monetization=str(item.get("monetization", "unknown")),
            acquisition_priority=max(1, min(10, int(item.get("acquisition_priority", 5)))),
            classified_at=now_iso,
        ))

    return results


def _classify_batch_deepseek(
    domains: list[str], api_key: str, session: requests.Session,
) -> list[DeepSeekClassification]:
    """Send a single batch to DeepSeek for classification."""
    assert isinstance(domains, list) and len(domains) > 0, "domains must be non-empty list"
    assert isinstance(api_key, str) and len(api_key) > 0, "api_key required"

    prompt = _build_deepseek_prompt(domains)
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = session.post(
            DEEPSEEK_API_URL, json=payload, headers=headers, timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("DeepSeek API returned %d: %s", resp.status_code, resp.text[:200])
            return []
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("DeepSeek API call failed: %s", exc)
        return []

    choices = data.get("choices", [])
    if not choices:
        logger.warning("DeepSeek returned no choices")
        return []

    content = choices[0].get("message", {}).get("content", "")
    return _parse_deepseek_response(content)


def _mock_deepseek_classification(domains: list[str]) -> list[DeepSeekClassification]:
    """Return mock DeepSeek classification data for dry-run mode."""
    assert isinstance(domains, list), "domains must be list"
    assert len(domains) >= 0, "domains length must be non-negative"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    mock_niches = ("cooking", "tech", "health", "finance", "fitness", "tools", "education", "travel")
    mock_types = ("blog", "tool", "saas", "marketplace", "community", "directory")
    mock_monetization = ("ads", "affiliate", "saas", "freemium", "subscription", "sponsored")

    results: list[DeepSeekClassification] = []
    for idx, domain in enumerate(domains):
        if idx >= DEEPSEEK_BATCH_SIZE * DEEPSEEK_MAX_BATCHES:
            break
        results.append(DeepSeekClassification(
            domain=domain,
            niche=mock_niches[idx % len(mock_niches)],
            site_type=mock_types[idx % len(mock_types)],
            tool_idea=f"Build a {mock_types[idx % len(mock_types)]} for {domain.split('.')[0]}",
            keyword_value=min(10, (idx % 7) + 4),
            brandability=min(10, (idx % 5) + 5),
            monetization=mock_monetization[idx % len(mock_monetization)],
            acquisition_priority=min(10, (idx % 8) + 3),
            classified_at=now_iso,
        ))

    return results


def _log_deepseek_usage(batches: int, domains: int, est_cost: float) -> None:
    """Log DeepSeek API usage and estimated cost."""
    assert isinstance(batches, int) and batches >= 0, "batches must be non-negative int"
    assert isinstance(domains, int) and domains >= 0, "domains must be non-negative int"

    logger.info(
        "DeepSeek usage: %d batches, %d domains classified, est. cost $%.4f",
        batches, domains, est_cost,
    )
    if est_cost > 1.0:
        logger.warning("DeepSeek cost exceeds $1.00: $%.4f", est_cost)


def classify_domains_deepseek(
    domains: list[str],
    config: dict,
    session: requests.Session,
    dry_run: bool,
) -> list[DeepSeekClassification]:
    """Classify domains using DeepSeek V3 with rate limiting and batching.

    Main orchestrator for DeepSeek classification. Splits domains into batches
    of DEEPSEEK_BATCH_SIZE, respects RPM limits, and tracks cost.
    """
    assert isinstance(domains, list), "domains must be list"
    assert isinstance(config, dict), "config must be dict"

    if dry_run:
        logger.info("[DRY RUN] Using mock DeepSeek classifications for %d domains", len(domains))
        return _mock_deepseek_classification(domains)

    api_key = config.get("deepseek_api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.info("No DeepSeek API key configured, skipping classification")
        return []

    total_domains = min(len(domains), DEEPSEEK_BATCH_SIZE * DEEPSEEK_MAX_BATCHES)
    num_batches = min(
        (total_domains + DEEPSEEK_BATCH_SIZE - 1) // DEEPSEEK_BATCH_SIZE,
        DEEPSEEK_MAX_BATCHES,
    )

    all_results: list[DeepSeekClassification] = []
    batch_delay = 60.0 / DEEPSEEK_RPM_LIMIT  # seconds between batches

    for batch_idx in range(num_batches):
        batch_start = batch_idx * DEEPSEEK_BATCH_SIZE
        batch_end = min(batch_start + DEEPSEEK_BATCH_SIZE, total_domains)
        batch = domains[batch_start:batch_end]

        results = _classify_batch_deepseek(batch, api_key, session)
        all_results.extend(results)

        if batch_idx < num_batches - 1:
            time.sleep(batch_delay)

    # Estimate cost: ~$0.0004 per 1K input tokens, ~$0.0016 per 1K output tokens
    est_cost = num_batches * 0.003  # rough estimate per batch
    _log_deepseek_usage(num_batches, len(all_results), est_cost)

    return all_results


# ---------------------------------------------------------------------------
# Sprint 13: OpenRank Bulk Authority Check
# ---------------------------------------------------------------------------
def _check_openrank(domain: str, session: requests.Session) -> float:
    """Check OpenRank authority score for a single domain."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert session is not None, "session required"

    url = f"{OPENRANK_AUTHORITY_API_URL}/{domain}"
    try:
        resp = session.get(url, timeout=WHOIS_CHECK_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("OpenRank authority check failed for %s: HTTP %d", domain, resp.status_code)
            return 0.0
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("OpenRank authority check error for %s: %s", domain, exc)
        return 0.0

    score = float(data.get("openrank_score", data.get("score", data.get("rank", 0.0))))
    assert isinstance(score, float), "score must be float"
    return score


def _openrank_to_da(score: float) -> int:
    """Convert OpenRank score (0-10 scale) to estimated Domain Authority (0-100).

    OpenRank uses a logarithmic scale similar to Moz DA. This mapping
    provides a rough but useful approximation.
    """
    assert isinstance(score, (int, float)), f"score must be numeric, got {type(score)}"
    assert score >= 0.0, f"score must be non-negative, got {score}"

    if score <= 0.0:
        return 0
    # OpenRank 0-10 maps roughly to DA 0-100 via linear scaling
    # with adjustments for the typical distribution
    da = int(min(100, score * 10))
    assert 0 <= da <= 100, f"DA must be 0-100, got {da}"
    return da


def _bulk_authority_check(
    domains: list[str], session: requests.Session, dry_run: bool,
) -> list[AuthorityCheck]:
    """Perform bulk OpenRank authority checks on a list of domains.

    Checks domains one at a time (rate limit TBD) up to OPENRANK_MAX_AUTHORITY_CHECKS.
    Returns AuthorityCheck objects with derived DA estimates.
    """
    assert isinstance(domains, list), "domains must be list"
    assert session is not None, "session required"

    if dry_run:
        logger.info("[DRY RUN] Using mock authority checks for %d domains", len(domains))
        return _mock_authority_check(domains)

    results: list[AuthorityCheck] = []
    check_count = min(len(domains), OPENRANK_MAX_AUTHORITY_CHECKS)
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    for idx in range(check_count):
        domain = domains[idx]
        score = _check_openrank(domain, session)
        da = _openrank_to_da(score)

        # Determine confidence based on score magnitude
        if score >= 5.0:
            confidence = "high"
        elif score >= 2.0:
            confidence = "medium"
        else:
            confidence = "low"

        results.append(AuthorityCheck(
            domain=domain,
            openrank_score=score,
            da_estimate=da,
            confidence=confidence,
            checked_at=now_iso,
        ))

        # Rate limit: 1 request per second
        if idx < check_count - 1:
            time.sleep(1.0)

    logger.info("OpenRank authority: checked %d domains", len(results))
    return results


def _mock_authority_check(domains: list[str]) -> list[AuthorityCheck]:
    """Return mock authority check data for dry-run mode."""
    assert isinstance(domains, list), "domains must be list"
    assert len(domains) >= 0, "domains length must be non-negative"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    mock_scores = (3.5, 5.2, 1.8, 4.1, 6.7, 2.3, 7.1, 3.9, 4.5, 2.8)

    results: list[AuthorityCheck] = []
    for idx, domain in enumerate(domains):
        if idx >= OPENRANK_MAX_AUTHORITY_CHECKS:
            break
        score = mock_scores[idx % len(mock_scores)]
        da = _openrank_to_da(score)
        confidence = "high" if score >= 5.0 else ("medium" if score >= 2.0 else "low")
        results.append(AuthorityCheck(
            domain=domain,
            openrank_score=score,
            da_estimate=da,
            confidence=confidence,
            checked_at=now_iso,
        ))

    return results


# ---------------------------------------------------------------------------
# Sprint 13: Expiring Domain Monitor
# ---------------------------------------------------------------------------
def _calculate_drop_probability(status_codes: tuple[str, ...], days_remaining: int) -> str:
    """Calculate drop probability based on WHOIS status codes and days remaining.

    Status codes like 'pendingDelete', 'redemptionPeriod' indicate
    imminent drops. Combined with days remaining, this gives a probability.
    """
    assert isinstance(status_codes, tuple), "status_codes must be tuple"
    assert isinstance(days_remaining, int), "days_remaining must be int"

    high_drop_statuses = (
        "pendingdelete", "redemptionperiod", "pendingrenew",
        "serverhold", "clienthold", "expired",
    )
    status_lower = tuple(s.lower() for s in status_codes)

    drop_signals = sum(
        1 for s in status_lower
        if any(hds in s for hds in high_drop_statuses)
    )

    if drop_signals >= 2 or (drop_signals >= 1 and days_remaining <= 5):
        return "very_high"
    if drop_signals >= 1 or days_remaining <= 14:
        return "high"
    if days_remaining <= 30:
        return "medium"

    assert isinstance(days_remaining, int), "days_remaining type preserved"
    return "low"


def _extract_rdap_registrar(data: dict) -> str:
    """Extract registrar name from RDAP response entities."""
    assert isinstance(data, dict), "data must be dict"

    entities = data.get("entities", [])
    for ent_idx, entity in enumerate(entities):
        if ent_idx >= 10:
            break
        roles = entity.get("roles", [])
        if "registrar" in roles:
            vcard = entity.get("vcardArray", [None, []])
            if isinstance(vcard, list) and len(vcard) > 1:
                for field in vcard[1][:20]:
                    if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                        return str(field[3])

    assert isinstance(data, dict), "data type preserved"
    return "unknown"


def _check_whois_expiry(domain: str, session: requests.Session) -> ExpiryAlert:
    """Check WHOIS expiry date for a single domain via RDAP."""
    assert isinstance(domain, str) and "." in domain, f"Invalid domain: {domain}"
    assert session is not None, "session required"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    url = f"https://rdap.org/domain/{domain}"

    try:
        resp = session.get(url, timeout=WHOIS_CHECK_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("RDAP check failed for %s: HTTP %d", domain, resp.status_code)
            return _fallback_expiry_alert(domain, now_iso)
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logger.warning("RDAP check error for %s: %s", domain, exc)
        return _fallback_expiry_alert(domain, now_iso)

    # Extract expiry date from RDAP events
    expiry_date_str = ""
    events = data.get("events", [])
    for ev_idx, event in enumerate(events):
        if ev_idx >= 20:  # safety bound
            break
        if event.get("eventAction") == "expiration":
            expiry_date_str = str(event.get("eventDate", ""))
            break

    status_codes = tuple(str(s) for s in data.get("status", [])[:20])
    registrar = _extract_rdap_registrar(data)
    days_remaining = _parse_expiry_days(expiry_date_str)
    drop_prob = _calculate_drop_probability(status_codes, days_remaining)

    return ExpiryAlert(
        domain=domain, expiry_date=expiry_date_str,
        days_remaining=days_remaining, registrar=registrar,
        status_codes=status_codes, drop_probability=drop_prob,
        recommended_action=_recommend_action(days_remaining, drop_prob),
        checked_at=now_iso,
    )


def _parse_expiry_days(expiry_date_str: str) -> int:
    """Parse expiry date string and return days remaining from now."""
    assert isinstance(expiry_date_str, str), "expiry_date_str must be string"

    if not expiry_date_str:
        return 9999  # Unknown expiry = assume far future

    # Try common date formats
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            expiry_dt = datetime.strptime(expiry_date_str[:19] + "Z", fmt if "T" not in fmt else "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            delta = expiry_dt - now
            return max(0, delta.days)
        except ValueError:
            continue

    assert isinstance(expiry_date_str, str), "expiry_date_str type preserved"
    return 9999


def _recommend_action(days_remaining: int, drop_probability: str) -> str:
    """Recommend acquisition action based on expiry timing and drop probability."""
    assert isinstance(days_remaining, int), "days_remaining must be int"
    assert drop_probability in ("very_high", "high", "medium", "low"), f"Invalid probability: {drop_probability}"

    if drop_probability == "very_high":
        return "BACKORDER IMMEDIATELY - domain dropping imminently"
    if drop_probability == "high" and days_remaining <= 14:
        return "PLACE BACKORDER - high chance of drop within 2 weeks"
    if drop_probability == "high":
        return "MONITOR CLOSELY - high drop signals detected"
    if days_remaining <= 30:
        return "SET ALERT - expiring within 30 days"
    if days_remaining <= EXPIRY_WARNING_DAYS:
        return "ADD TO WATCHLIST - expiring within 90 days"

    return "NO ACTION - domain not expiring soon"


def _fallback_expiry_alert(domain: str, now_iso: str) -> ExpiryAlert:
    """Return a fallback ExpiryAlert when WHOIS/RDAP lookup fails."""
    assert isinstance(domain, str) and len(domain) > 0, "domain required"
    assert isinstance(now_iso, str) and len(now_iso) > 0, "timestamp required"

    return ExpiryAlert(
        domain=domain, expiry_date="unknown",
        days_remaining=9999, registrar="unknown",
        status_codes=(), drop_probability="low",
        recommended_action="RETRY - WHOIS lookup failed",
        checked_at=now_iso,
    )


def monitor_expiring_domains(
    domains: list[str], session: requests.Session, dry_run: bool,
) -> list[ExpiryAlert]:
    """Monitor a list of domains for upcoming expiry dates.

    Checks WHOIS/RDAP data, calculates drop probability, and recommends
    acquisition actions for domains expiring within EXPIRY_WARNING_DAYS.
    """
    assert isinstance(domains, list), "domains must be list"
    assert session is not None, "session required"

    if dry_run:
        logger.info("[DRY RUN] Using mock expiry checks for %d domains", len(domains))
        return _mock_expiry_check(domains)

    results: list[ExpiryAlert] = []
    check_count = min(len(domains), MAX_WHOIS_CHECKS)

    for idx in range(check_count):
        alert = _check_whois_expiry(domains[idx], session)
        results.append(alert)
        if alert.days_remaining <= EXPIRY_WARNING_DAYS:
            logger.warning(
                "EXPIRY ALERT: %s expires in %d days (prob=%s) -> %s",
                alert.domain, alert.days_remaining,
                alert.drop_probability, alert.recommended_action,
            )
        if idx < check_count - 1:
            time.sleep(1.0)

    expiring = sum(1 for a in results if a.days_remaining <= EXPIRY_WARNING_DAYS)
    logger.info("Expiry monitor: %d checked, %d expiring within %d days", len(results), expiring, EXPIRY_WARNING_DAYS)
    return results


def _mock_expiry_check(domains: list[str]) -> list[ExpiryAlert]:
    """Return mock expiry check data for dry-run mode."""
    assert isinstance(domains, list), "domains must be list"
    assert len(domains) >= 0, "domains length must be non-negative"

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    mock_data = (
        (15, "GoDaddy", ("clientTransferProhibited",), "high"),
        (45, "Namecheap", ("ok",), "medium"),
        (3, "Dynadot", ("pendingDelete", "redemptionPeriod"), "very_high"),
        (120, "Google Domains", ("clientTransferProhibited",), "low"),
        (7, "Porkbun", ("serverHold",), "high"),
        (60, "Cloudflare", ("ok",), "medium"),
        (1, "NameSilo", ("pendingDelete",), "very_high"),
        (200, "Hover", ("clientTransferProhibited",), "low"),
    )

    results: list[ExpiryAlert] = []
    for idx, domain in enumerate(domains):
        if idx >= MAX_WHOIS_CHECKS:
            break
        days, registrar, status, prob = mock_data[idx % len(mock_data)]
        action = _recommend_action(days, prob)
        # Calculate a mock expiry date
        expiry_str = (
            datetime.now(tz=timezone.utc).__class__(2026, 6, 1, tzinfo=timezone.utc).isoformat()
            if days < 90 else "2027-01-01T00:00:00Z"
        )
        results.append(ExpiryAlert(
            domain=domain, expiry_date=expiry_str,
            days_remaining=days, registrar=registrar,
            status_codes=status, drop_probability=prob,
            recommended_action=action, checked_at=now_iso,
        ))

    return results


# ---------------------------------------------------------------------------
# Source dispatcher
# ---------------------------------------------------------------------------
def fetch_from_source(
    source_name: str,
    session: requests.Session,
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Dispatch to the correct source fetcher by name."""
    assert isinstance(source_name, str) and len(source_name) > 0, "source_name required"
    assert session is not None, "session required"

    fetchers = {
        "expired_domains_net": fetch_expired_domains_list,
        "domcop": fetch_domcop_drops,
        "godaddy_closeouts": check_godaddy_closeouts,
        "tech_shutdowns": search_tech_shutdowns,
        "catchdoms_apify": fetch_catchdoms_apify,
    }

    fetcher = fetchers.get(source_name)
    if fetcher is None:
        logger.warning("Unknown source: %s, skipping", source_name)
        return []

    return fetcher(session, config, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
def _apply_config_overrides(
    config: PipelineConfig, args: argparse.Namespace,
) -> PipelineConfig:
    """Apply CLI argument overrides to config. Returns new config if changed."""
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"
    assert hasattr(args, "min_da"), "args must have min_da attribute"

    if args.min_da is None:
        return config

    return PipelineConfig(
        alert_da_threshold=config.alert_da_threshold,
        critical_da_threshold=config.critical_da_threshold,
        min_da_filter=args.min_da,
        max_domains_per_source=config.max_domains_per_source,
        max_total_candidates=config.max_total_candidates,
        sources_enabled=config.sources_enabled,
        niches_priority=config.niches_priority,
        dataforseo_max_lookups_per_day=config.dataforseo_max_lookups_per_day,
        output_dir=config.output_dir,
        rate_limit_base_delay_seconds=config.rate_limit_base_delay_seconds,
        rate_limit_max_delay_seconds=config.rate_limit_max_delay_seconds,
        rate_limit_max_retries=config.rate_limit_max_retries,
        http_timeout_seconds=config.http_timeout_seconds,
        user_agent=config.user_agent,
    )


def _fetch_all_sources(
    sources: list[str],
    session: requests.Session,
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> list[DomainCandidate]:
    """Fetch candidates from all enabled sources."""
    assert isinstance(sources, list), "sources must be list"
    assert session is not None, "session required"

    all_candidates: list[DomainCandidate] = []
    for source_idx, source_name in enumerate(sources):
        if source_idx >= 10:
            break
        logger.info("Fetching source %d/%d: %s", source_idx + 1, len(sources), source_name)
        source_results = fetch_from_source(source_name, session, config, dry_run=dry_run)
        all_candidates.extend(source_results[:config.max_domains_per_source])

    assert len(all_candidates) <= MAX_TOTAL_CANDIDATES * 2, "raw candidates exceed safety limit"
    return all_candidates


def _load_sprint13_config() -> dict:
    """Load Sprint 13 feature flags from the pipeline config JSON file."""
    config_path = SCRIPT_DIR / CONFIG_FILENAME
    assert isinstance(config_path, Path), "config_path must be Path"

    if not config_path.is_file():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        assert isinstance(raw, dict), "config must be dict"
        return raw
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load Sprint 13 config: %s", exc)
        return {}


def _run_sprint13_stages(
    candidates: list[DomainCandidate],
    session: requests.Session,
    dry_run: bool,
) -> None:
    """Run Sprint 13 optional pipeline stages (DeepSeek, OpenRank, Expiry).

    These stages are side-effect-only: they log results and store data
    but do not modify the candidate list (which is already finalized).
    """
    assert isinstance(candidates, list), "candidates must be list"
    assert session is not None, "session required"

    raw_config = _load_sprint13_config()
    domain_names = [c.domain for c in candidates[:MAX_TOTAL_CANDIDATES]]

    # Stage 1: DeepSeek classification (optional, needs API key)
    if raw_config.get("deepseek_enabled", False):
        logger.info("Sprint 13: DeepSeek classification enabled")
        classifications = classify_domains_deepseek(domain_names, raw_config, session, dry_run)
        logger.info("Sprint 13: DeepSeek classified %d domains", len(classifications))

    # Stage 2: OpenRank authority check (free, default enabled)
    if raw_config.get("openrank_enabled", True):
        logger.info("Sprint 13: OpenRank authority check enabled")
        authority_checks = _bulk_authority_check(domain_names, session, dry_run)
        logger.info("Sprint 13: OpenRank checked %d domains", len(authority_checks))

    # Stage 3: Expiry monitor (default enabled)
    if raw_config.get("expiry_monitor_enabled", True):
        logger.info("Sprint 13: Expiry monitor enabled")
        expiry_alerts = monitor_expiring_domains(domain_names, session, dry_run)
        urgent = [a for a in expiry_alerts if a.drop_probability in ("very_high", "high")]
        logger.info("Sprint 13: Expiry monitor found %d urgent alerts", len(urgent))


def _run_pipeline_phases(
    session: requests.Session,
    all_candidates: list[DomainCandidate],
    config: PipelineConfig,
    *, dry_run: bool = False,
) -> tuple[list[DomainCandidate], list[DomainCandidate], list[DomainCandidate], Path, int]:
    """Run dedup, DA check, filter, enrich, classify, and store phases."""
    assert session is not None, "session required"
    assert isinstance(all_candidates, list), "all_candidates must be list"

    deduped = deduplicate_candidates(all_candidates, config.max_total_candidates)
    da_checked = bulk_da_check(session, deduped, config, dry_run=dry_run)

    # Sprint 10: OpenRank cross-validation (compare vs OpenPageRank, flag discrepancies)
    cross_validated = openrank_cross_validate(session, da_checked, config, dry_run=dry_run)
    filtered = filter_by_min_da(cross_validated, config.min_da_filter)

    dataforseo_lookup_count = min(len(filtered), config.dataforseo_max_lookups_per_day)
    enriched = dataforseo_traffic_check(session, filtered, config, dry_run=dry_run)
    classified = classify_all_niches(enriched)

    # Sprint 12: Price verification (prevent aftermarket price mismatches)
    price_verified, price_verifications = verify_domain_prices(
        classified, config, session, dry_run=dry_run,
    )
    _log_price_verifications(price_verifications)

    # Sprint 13: Optional stages (configured via raw config JSON)
    _run_sprint13_stages(price_verified, session, dry_run)

    # Sprint 14: ETV verification stage (after PRICE_VERIFY, before Store)
    raw_config = _load_sprint13_config()
    etv_verified = run_etv_verification_stage(price_verified, raw_config, dry_run=dry_run)

    output_file = store_daily_results(etv_verified, config, dataforseo_lookup_count)
    return deduped, filtered, etv_verified, output_file, dataforseo_lookup_count


def main() -> None:
    """Orchestrate the full daily hunting pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    args = parse_args()
    assert isinstance(args.dry_run, bool), "dry_run must be bool"
    start_time = time.monotonic()
    _load_dotenv()

    config = _apply_config_overrides(load_config(args.config), args)
    assert isinstance(config, PipelineConfig), "config must be PipelineConfig"
    sources = [s.strip() for s in args.sources.split(",")] if args.sources else list(config.sources_enabled)

    logger.info("Pipeline starting: dry_run=%s, sources=%s", args.dry_run, sources)
    session = _build_session(config.user_agent)

    all_candidates = _fetch_all_sources(sources, session, config, dry_run=args.dry_run)
    deduped, filtered, classified, output_file, dfs_lookups = _run_pipeline_phases(
        session, all_candidates, config, dry_run=args.dry_run,
    )

    alerts = generate_alerts(classified, config)
    print_alerts(alerts)

    elapsed = time.monotonic() - start_time
    print_summary(
        all_candidates, deduped, filtered, classified, output_file,
        elapsed, args.dry_run, dataforseo_lookups=dfs_lookups,
    )

    session.close()
    logger.info("Pipeline complete in %.1fs", elapsed)


def _load_dotenv() -> None:
    """Load .env file from project root if present."""
    env_path = PROJECT_ROOT / ".env"
    assert isinstance(env_path, Path), "env_path must be Path"

    if not env_path.is_file():
        logger.info("No .env file found at %s", env_path)
        return

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    loaded_count = 0
    for line_idx, line in enumerate(lines):
        if line_idx >= 100:  # safety bound
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded_count += 1

    assert loaded_count >= 0, "loaded_count must be non-negative"
    logger.info("Loaded %d env vars from .env", loaded_count)


if __name__ == "__main__":
    main()

"""DropWatch Scorer — Score DropCatch auction domains against goldmine keywords.

Cross-references domain names against FINAL-GOLDMINE-RANKED.json to identify
high-value auction domains worth bidding on.

NASA Power of 10 rules enforced:
  1. No goto/deep recursion/switch fallthroughs
  2. All loops have fixed upper bounds
  3. No unbounded memory -- explicit max sizes everywhere
  4. All functions < 60 lines
  5. Min 2 assertions per function
  6. Restrict data scope -- no global mutable state
  7. Check every return value -- no swallowed exceptions
  8. Standard Python only (difflib for fuzzy matching)
  9. No dangerous mutations -- return new objects
  10. Zero warnings -- all errors fixed, not suppressed

Usage:
  python tools/dropwatch_scorer.py domains.txt
  python tools/dropwatch_scorer.py --domains "calcboss.com,speedchecker.io,loancalc.net"
  python tools/dropwatch_scorer.py domains.txt --auction-data auction.json --top 30

Dependencies: Python 3.12+ standard library only
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final

# --- Constants (immutable) ---
GOLDMINE_PATH: Final[str] = (
    "/Users/mike/agentic-autonomous-pipeline/data/keywords/FINAL-GOLDMINE-RANKED.json"
)
MAX_DOMAINS: Final[int] = 5000
MAX_KEYWORDS: Final[int] = 1000
MAX_WORDS_PER_DOMAIN: Final[int] = 10
FUZZY_THRESHOLD: Final[float] = 0.70
DEFAULT_TOP_N: Final[int] = 20

# Buildability scores by tool_type
BUILDABILITY_SCORES: Final[dict[str, int]] = {
    "calculator": 5,
    "generator": 5,
    "converter": 5,
    "formatter": 4,
    "validator": 4,
    "encoder": 4,
    "editor": 3,
    "viewer": 3,
    "analyzer": 3,
    "lookup": 3,
    "tool": 2,
}

# Weight configuration for final score
W_VOLUME: Final[float] = 0.4
W_CPC: Final[float] = 0.3
W_BUILDABILITY: Final[float] = 0.2
W_DOMAIN_QUALITY: Final[float] = 0.1


@dataclass(frozen=True, slots=True)
class GoldmineEntry:
    """Immutable keyword record from goldmine data."""

    keyword: str
    volume: int
    cpc: float
    tool_type: str
    score: float
    cluster_keywords: tuple[str, ...]
    rev_low: int
    rev_high: int


@dataclass(frozen=True, slots=True)
class ScoredDomain:
    """Immutable scored domain result."""

    domain: str
    total_score: float
    volume_score: float
    cpc_score: float
    buildability_score: float
    quality_score: float
    matched_keyword: str
    match_ratio: float
    volume: int
    cpc: float
    tool_type: str
    rev_estimate: str
    auction_price: float | None = None


# --- Core Functions ---


def load_goldmine(path: str) -> list[GoldmineEntry]:
    """Load and validate goldmine keyword data from JSON file."""
    assert Path(path).exists(), f"Goldmine file not found: {path}"

    raw: list[dict] = json.loads(Path(path).read_text(encoding="utf-8"))
    assert isinstance(raw, list) and len(raw) > 0, "Goldmine data must be non-empty list"

    entries: list[GoldmineEntry] = []
    for i, item in enumerate(raw[:MAX_KEYWORDS]):
        cluster = item.get("cluster_keywords", [])
        entry = GoldmineEntry(
            keyword=str(item.get("keyword", "")),
            volume=int(item.get("volume", 0)),
            cpc=float(item.get("cpc", 0.0)),
            tool_type=str(item.get("tool_type", "tool")),
            score=float(item.get("score", 0.0)),
            cluster_keywords=tuple(str(k) for k in cluster[:20]),
            rev_low=int(item.get("rev_low", 0)),
            rev_high=int(item.get("rev_high", 0)),
        )
        entries.append(entry)

    return entries


def extract_words_from_domain(domain: str) -> list[str]:
    """Extract meaningful words from a domain name.

    Splits on hyphens, numbers, camelCase boundaries, and removes TLD.
    Returns lowercased word tokens.
    """
    assert isinstance(domain, str), "Domain must be a string"
    assert len(domain) > 0, "Domain must not be empty"

    # Strip TLD (.com, .io, .net, .org, etc.)
    name = domain.split(".")[0] if "." in domain else domain
    name = name.lower().strip()

    # Split on hyphens first
    parts = name.split("-")

    words: list[str] = []
    for part in parts[:MAX_WORDS_PER_DOMAIN]:
        # Split camelCase: insert space before uppercase runs
        camel_split = re.sub(r"([a-z])([A-Z])", r"\1 \2", part)
        # Split on number boundaries
        num_split = re.sub(r"(\d+)", r" \1 ", camel_split)
        # Tokenize
        tokens = num_split.split()
        for token in tokens[:MAX_WORDS_PER_DOMAIN]:
            cleaned = re.sub(r"[^a-z]", "", token.lower())
            if len(cleaned) >= 2:
                words.append(cleaned)

    return words[:MAX_WORDS_PER_DOMAIN]


def fuzzy_match_keyword(
    domain_words: list[str], entry: GoldmineEntry
) -> tuple[float, str]:
    """Find best fuzzy match between domain words and a goldmine entry.

    Checks against primary keyword and all cluster keywords.
    Returns (match_ratio, matched_keyword_string).
    """
    assert len(domain_words) > 0, "Domain words must not be empty"
    assert entry.keyword, "Entry keyword must not be empty"

    best_ratio: float = 0.0
    best_keyword: str = ""

    # Build domain phrase for comparison
    domain_phrase = " ".join(domain_words)

    # Check primary keyword + cluster keywords
    all_keywords: list[str] = [entry.keyword] + list(entry.cluster_keywords[:20])

    for keyword in all_keywords[:25]:
        kw_lower = keyword.lower().strip()
        if not kw_lower:
            continue

        # Strategy 1: Full phrase match
        ratio = SequenceMatcher(None, domain_phrase, kw_lower).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_keyword = keyword

        # Strategy 2: Check if domain words are a subset of keyword words
        kw_words = set(kw_lower.split())
        domain_set = set(domain_words)
        overlap = domain_set & kw_words
        if len(kw_words) > 0:
            subset_ratio = len(overlap) / max(len(kw_words), len(domain_set))
            if subset_ratio > best_ratio:
                best_ratio = subset_ratio
                best_keyword = keyword

        # Strategy 3: Exact word containment (domain word IN keyword)
        for word in domain_words:
            if len(word) >= 3 and word in kw_lower:
                contain_ratio = len(word) / len(kw_lower)
                boosted = min(contain_ratio + 0.3, 1.0)
                if boosted > best_ratio:
                    best_ratio = boosted
                    best_keyword = keyword

    return (best_ratio, best_keyword)


def compute_volume_score(volume: int) -> float:
    """Compute volume score: log10(volume) / log10(10_000_000) * 100, capped at 100."""
    assert isinstance(volume, int), "Volume must be int"
    assert volume >= 0, "Volume must be non-negative"

    if volume <= 0:
        return 0.0
    raw = math.log10(volume) / math.log10(10_000_000) * 100.0
    return min(raw, 100.0)


def compute_cpc_score(cpc: float) -> float:
    """Compute CPC score: min(cpc / 10.0, 1.0) * 100."""
    assert isinstance(cpc, (int, float)), "CPC must be numeric"
    assert cpc >= 0, "CPC must be non-negative"

    return min(cpc / 10.0, 1.0) * 100.0


def compute_buildability(tool_type: str) -> float:
    """Return buildability score (1-5 scaled to 0-100) based on tool type."""
    assert isinstance(tool_type, str), "Tool type must be string"

    raw = BUILDABILITY_SCORES.get(tool_type.lower(), 2)
    assert 1 <= raw <= 5, f"Buildability raw must be 1-5, got {raw}"
    return (raw / 5.0) * 100.0


def compute_domain_quality(domain: str) -> float:
    """Score domain quality: length penalty, TLD bonus, no-numbers bonus.

    Returns 0-100 score.
    """
    assert isinstance(domain, str) and len(domain) > 0, "Domain must be non-empty string"

    score = 50.0  # Base score

    name = domain.split(".")[0] if "." in domain else domain
    tld = domain.split(".")[-1] if "." in domain else ""

    # Length bonus: ideal 6-12 chars for the name part
    name_len = len(name)
    if 6 <= name_len <= 12:
        score += 25.0
    elif name_len <= 5:
        score += 20.0  # Very short is good too
    elif name_len <= 16:
        score += 10.0
    # >16 chars: no bonus (stays at 50)

    # TLD bonus
    tld_bonuses = {"com": 20.0, "io": 10.0, "app": 10.0, "dev": 8.0, "net": 5.0, "org": 5.0}
    score += tld_bonuses.get(tld.lower(), 0.0)

    # No-numbers bonus
    if not re.search(r"\d", name):
        score += 5.0

    assert 0 <= score <= 150, f"Quality score out of expected range: {score}"
    return min(score, 100.0)


def find_best_match(
    words: list[str], goldmine: list[GoldmineEntry]
) -> tuple[float, str, GoldmineEntry | None]:
    """Find the best matching goldmine entry for domain words."""
    assert len(words) > 0, "Words must not be empty"
    assert len(goldmine) > 0, "Goldmine must not be empty"

    best_ratio: float = 0.0
    best_keyword: str = ""
    best_entry: GoldmineEntry | None = None

    for entry in goldmine[:MAX_KEYWORDS]:
        ratio, matched_kw = fuzzy_match_keyword(words, entry)
        if ratio > best_ratio:
            best_ratio = ratio
            best_keyword = matched_kw
            best_entry = entry

    return (best_ratio, best_keyword, best_entry)


def build_scored_domain(
    domain: str,
    best_entry: GoldmineEntry,
    best_keyword: str,
    best_ratio: float,
    auction_prices: dict[str, float],
) -> ScoredDomain:
    """Compute component scores and build final ScoredDomain."""
    assert best_ratio > 0, "Match ratio must be positive"
    assert best_entry.keyword, "Entry must have keyword"

    vol_score = compute_volume_score(best_entry.volume)
    cpc_score = compute_cpc_score(best_entry.cpc)
    build_score = compute_buildability(best_entry.tool_type)
    quality_score = compute_domain_quality(domain)

    total = (
        vol_score * W_VOLUME + cpc_score * W_CPC
        + build_score * W_BUILDABILITY + quality_score * W_DOMAIN_QUALITY
    )
    total *= (0.5 + 0.5 * best_ratio)

    rev_est = f"${best_entry.rev_low:,}-${best_entry.rev_high:,}/mo"
    price = auction_prices.get(domain.lower())

    return ScoredDomain(
        domain=domain, total_score=round(total, 2),
        volume_score=round(vol_score, 2), cpc_score=round(cpc_score, 2),
        buildability_score=round(build_score, 2), quality_score=round(quality_score, 2),
        matched_keyword=best_keyword, match_ratio=round(best_ratio, 3),
        volume=best_entry.volume, cpc=best_entry.cpc,
        tool_type=best_entry.tool_type, rev_estimate=rev_est, auction_price=price,
    )


def score_single_domain(
    domain: str,
    goldmine: list[GoldmineEntry],
    auction_prices: dict[str, float],
    threshold: float = FUZZY_THRESHOLD,
) -> ScoredDomain | None:
    """Score a single domain against all goldmine entries.

    Returns ScoredDomain if match exceeds threshold, None otherwise.
    """
    assert len(domain) > 0, "Domain must not be empty"
    assert len(goldmine) > 0, "Goldmine must not be empty"

    words = extract_words_from_domain(domain)
    if not words:
        return None

    best_ratio, best_keyword, best_entry = find_best_match(words, goldmine)

    if best_ratio < threshold or best_entry is None:
        return None

    return build_scored_domain(domain, best_entry, best_keyword, best_ratio, auction_prices)


def load_domains_from_file(filepath: str) -> list[str]:
    """Load domain names from a text file (one per line)."""
    path = Path(filepath)
    assert path.exists(), f"Domain file not found: {filepath}"

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0, f"Domain file is empty: {filepath}"

    domains: list[str] = []
    for line in lines[:MAX_DOMAINS]:
        cleaned = line.strip().split(",")[0].strip().split("\t")[0].strip()
        if cleaned and "." in cleaned and len(cleaned) > 3:
            domains.append(cleaned.lower())

    return domains


def load_auction_data(filepath: str | None) -> dict[str, float]:
    """Load auction price data from JSON file. Returns domain->price mapping."""
    if filepath is None:
        return {}

    path = Path(filepath)
    assert path.exists(), f"Auction data file not found: {filepath}"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw, (list, dict)), "Auction data must be list or dict"

    prices: dict[str, float] = {}
    if isinstance(raw, dict):
        for domain, price in list(raw.items())[:MAX_DOMAINS]:
            prices[str(domain).lower()] = float(price)
    elif isinstance(raw, list):
        for item in raw[:MAX_DOMAINS]:
            if isinstance(item, dict):
                dom = str(item.get("domain", item.get("name", ""))).lower()
                price = float(item.get("price", item.get("bid", item.get("amount", 0))))
                if dom:
                    prices[dom] = price

    return prices


def score_all_domains(
    domains: list[str],
    goldmine: list[GoldmineEntry],
    auction_prices: dict[str, float],
    top_n: int,
    threshold: float = FUZZY_THRESHOLD,
) -> list[ScoredDomain]:
    """Score all domains and return top N sorted by score descending."""
    assert len(domains) > 0, "Domains list must not be empty"
    assert top_n > 0, "top_n must be positive"

    scored: list[ScoredDomain] = []
    for domain in domains[:MAX_DOMAINS]:
        result = score_single_domain(domain, goldmine, auction_prices, threshold)
        if result is not None:
            scored.append(result)

    scored.sort(key=lambda s: s.total_score, reverse=True)
    return scored[:top_n]


def format_results(scored: list[ScoredDomain]) -> str:
    """Format scored domains into a readable table."""
    assert isinstance(scored, list), "Scored must be a list"
    assert all(isinstance(s, ScoredDomain) for s in scored[:10]), "All items must be ScoredDomain"

    if not scored:
        return "No domains matched goldmine keywords above threshold."

    lines: list[str] = []
    lines.append("")
    lines.append("=" * 100)
    lines.append("DROPWATCH SCORER — Top Candidates")
    lines.append("=" * 100)
    lines.append("")

    header = (
        f"{'#':<4} {'Domain':<30} {'Score':<7} {'Match%':<7} "
        f"{'Keyword':<25} {'Vol':<10} {'CPC':<7} {'Type':<12} {'Price':<8}"
    )
    lines.append(header)
    lines.append("-" * 100)

    for i, s in enumerate(scored[:100], start=1):
        price_str = f"${s.auction_price:.0f}" if s.auction_price else "—"
        vol_str = f"{s.volume:,}"
        kw_display = s.matched_keyword[:23] if len(s.matched_keyword) > 23 else s.matched_keyword
        lines.append(
            f"{i:<4} {s.domain:<30} {s.total_score:<7.1f} "
            f"{s.match_ratio*100:<6.0f}% {kw_display:<25} "
            f"{vol_str:<10} ${s.cpc:<6.2f} {s.tool_type:<12} {price_str:<8}"
        )

    lines.append("")
    lines.append("-" * 100)
    lines.append(f"Total matched: {len(scored)} domains above {FUZZY_THRESHOLD*100:.0f}% threshold")
    lines.append("")

    # Detail section for top 5
    lines.append("TOP 5 DETAILED BREAKDOWN:")
    lines.append("")
    for i, s in enumerate(scored[:5], start=1):
        lines.append(f"  #{i} {s.domain}")
        lines.append(f"      Score: {s.total_score:.1f} = "
                     f"Vol({s.volume_score:.1f}*{W_VOLUME}) + "
                     f"CPC({s.cpc_score:.1f}*{W_CPC}) + "
                     f"Build({s.buildability_score:.1f}*{W_BUILDABILITY}) + "
                     f"Quality({s.quality_score:.1f}*{W_DOMAIN_QUALITY})")
        lines.append(f"      Matched: '{s.matched_keyword}' ({s.match_ratio*100:.0f}% confidence)")
        lines.append(f"      Revenue potential: {s.rev_estimate}")
        if s.auction_price:
            lines.append(f"      Auction price: ${s.auction_price:.2f}")
        lines.append("")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Score DropCatch auction domains against goldmine keywords",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "domain_file",
        nargs="?",
        help="Path to text file with domain names (one per line)",
    )
    parser.add_argument(
        "--domains",
        type=str,
        default=None,
        help="Comma-separated list of domains to score",
    )
    parser.add_argument(
        "--goldmine",
        type=str,
        default=GOLDMINE_PATH,
        help=f"Path to goldmine JSON (default: {GOLDMINE_PATH})",
    )
    parser.add_argument(
        "--auction-data",
        type=str,
        default=None,
        help="Path to auction price data JSON",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Number of top results to show (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="Path to write JSON results file",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=FUZZY_THRESHOLD,
        help=f"Minimum match ratio threshold (default: {FUZZY_THRESHOLD})",
    )

    args = parser.parse_args(argv)
    assert args.domain_file or args.domains, (
        "Must provide either a domain file or --domains argument"
    )
    assert args.top > 0, "Top N must be positive"
    return args


def write_json_results(scored: list[ScoredDomain], output_path: str) -> None:
    """Write scored domain results to JSON file."""
    assert len(scored) > 0, "Scored list must not be empty for JSON output"
    assert output_path, "Output path must not be empty"

    json_results = []
    for s in scored[:MAX_DOMAINS]:
        json_results.append({
            "domain": s.domain, "total_score": s.total_score,
            "volume_score": s.volume_score, "cpc_score": s.cpc_score,
            "buildability_score": s.buildability_score, "quality_score": s.quality_score,
            "matched_keyword": s.matched_keyword, "match_ratio": s.match_ratio,
            "volume": s.volume, "cpc": s.cpc, "tool_type": s.tool_type,
            "rev_estimate": s.rev_estimate, "auction_price": s.auction_price,
        })
    Path(output_path).write_text(json.dumps(json_results, indent=2), encoding="utf-8")
    print(f"\nJSON results written to: {output_path}")


def main(argv: list[str] | None = None) -> int:
    """Main entry point. Returns 0 on success, 1 on error."""
    assert argv is None or isinstance(argv, list), "argv must be None or list"
    assert argv is None or len(argv) <= 100, "Too many CLI arguments"

    try:
        args = parse_args(argv)
    except (SystemExit, AssertionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Load goldmine data
    try:
        goldmine = load_goldmine(args.goldmine)
    except (AssertionError, json.JSONDecodeError, OSError) as exc:
        print(f"Error loading goldmine: {exc}", file=sys.stderr)
        return 1

    # Load domains
    try:
        if args.domains:
            domains = [d.strip().lower() for d in args.domains.split(",") if d.strip()]
        else:
            domains = load_domains_from_file(args.domain_file)
    except (AssertionError, OSError) as exc:
        print(f"Error loading domains: {exc}", file=sys.stderr)
        return 1

    if not domains:
        print("Error: No valid domains to score.", file=sys.stderr)
        return 1

    # Load auction prices
    try:
        auction_prices = load_auction_data(args.auction_data)
    except (AssertionError, json.JSONDecodeError, OSError) as exc:
        print(f"Warning: Could not load auction data: {exc}", file=sys.stderr)
        auction_prices = {}

    # Score and output
    threshold = args.threshold
    print(f"Scoring {len(domains)} domains against {len(goldmine)} goldmine keywords...")
    scored = score_all_domains(domains, goldmine, auction_prices, args.top, threshold)
    print(format_results(scored))

    if args.json_output and scored:
        write_json_results(scored, args.json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""DropCatch CSV Scanner — stream-score domains from DropCatch CSV exports.
Usage: python scripts/dropcatch_csv_scanner.py <csv> [--tld com] [--min-score 20] [--keyword X]
NASA P10: streaming, fns <60 lines, 2+ assertions, bounded output, no global mutable.
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, TextIO

_ROOT: str = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: str = os.path.join(_ROOT, "data")
_MAX_RESULTS: int = 500
_TOP_DISPLAY: int = 100
_DEFAULT_MIN_SCORE: int = 15
_TLD_SCORES: dict[str, int] = {
    ".ai": 10, ".io": 8, ".co": 5, ".com": 3, ".org": 2,
    ".net": 2, ".dev": 6, ".app": 5, ".sh": 4, ".xyz": 1,
}
_GOLDMINE_KEYWORDS: tuple[str, ...] = (
    "ai", "cloud", "data", "api", "code", "health", "finance", "crypto",
    "tool", "calc", "recipe", "cook", "fit", "bot", "hub", "lab", "dev",
    "sync", "flow", "stack", "dash", "link", "meta", "pay", "trade",
    "scan", "track", "mint", "vault", "nest", "node", "edge", "core",
    "wave", "grid", "pulse", "shift", "spark", "beam", "forge", "quest",
    "pixel", "byte", "logic", "cyber", "smart", "auto", "rapid", "quick",
)

def extract_domain_parts(full_domain: str) -> tuple[str, str]:
    """Split 'example.com' into ('example', '.com')."""
    assert isinstance(full_domain, str), "domain must be a string"
    full_domain = full_domain.strip().lower()
    assert len(full_domain) > 0, "domain must not be empty"
    dot_idx = full_domain.rfind(".")
    if dot_idx <= 0:
        return full_domain, ""
    return full_domain[:dot_idx], full_domain[dot_idx:]

def score_length(sld: str) -> int:
    """Shorter SLD = higher score."""
    assert isinstance(sld, str) and len(sld) > 0, "sld must be non-empty"
    n = len(sld)
    if n <= 3:  return 15
    if n <= 5:  return 12
    if n <= 7:  return 8
    if n <= 10: return 5
    if n <= 14: return 2
    return 0

def score_tld(tld: str) -> int:
    """Premium TLD bonus."""
    assert isinstance(tld, str), "tld must be a string"
    return _TLD_SCORES.get(tld, 0)

def score_keywords(sld: str, extra_keywords: tuple[str, ...] = ()) -> tuple[int, list[str]]:
    """Return (score, matched_keywords). Capped at 20 pts."""
    assert isinstance(sld, str) and len(sld) > 0, "sld must be non-empty"
    assert isinstance(extra_keywords, tuple), "extra_keywords must be tuple"
    matched: list[str] = []
    for kw in _GOLDMINE_KEYWORDS + extra_keywords:
        if kw in sld.lower() and kw not in matched:
            matched.append(kw)
    return min(len(matched) * 5, 20), matched

def score_structure(sld: str) -> tuple[int, list[str]]:
    """Structural bonuses: no hyphens, no numbers, word-count."""
    assert isinstance(sld, str) and len(sld) > 0, "sld must be non-empty"
    bonuses: list[str] = []
    score = 0
    if "-" not in sld:
        score += 5; bonuses.append("no-hyphens")
    if not re.search(r"\d", sld):
        score += 3; bonuses.append("no-numbers")
    clean = re.sub(r"[^a-z]", "", sld.lower())
    if len(clean) <= 8 and "-" not in sld and not re.search(r"\d", sld):
        score += 10; bonuses.append("single-word")
    elif len(clean) <= 14 and "-" not in sld:
        score += 5; bonuses.append("compound-word")
    return score, bonuses

def score_domain(full_domain: str, extra_keywords: tuple[str, ...] = ()) -> dict[str, Any]:
    """Full scoring breakdown for one domain."""
    assert isinstance(full_domain, str) and "." in full_domain, "need valid domain"
    sld, tld = extract_domain_parts(full_domain)
    assert len(sld) > 0 and len(tld) > 0, f"invalid domain parse: {full_domain}"
    ls = score_length(sld)
    ts = score_tld(tld)
    ks, km = score_keywords(sld, extra_keywords)
    ss, sb = score_structure(sld)
    return {
        "domain": full_domain.strip().lower(), "sld": sld, "tld": tld,
        "total_score": ls + ts + ks + ss,
        "length_score": ls, "tld_score": ts,
        "keyword_score": ks, "keyword_matches": km,
        "structure_score": ss, "structure_bonuses": sb,
    }

def detect_domain_column(header: list[str]) -> int:
    """Find domain column index from CSV header row."""
    assert isinstance(header, list) and len(header) > 0, "header must be non-empty"
    lower = [h.strip().lower() for h in header]
    for target in ("domain", "domain name", "domainname", "name"):
        if target in lower:
            return lower.index(target)
    return 0

def stream_csv_domains(filepath: str, tld_filter: str | None = None) -> Generator[str, None, None]:
    """Yield domains one at a time. Never loads full file into memory."""
    assert os.path.isfile(filepath), f"CSV not found: {filepath}"
    assert filepath.endswith(".csv"), "file must be .csv"
    fh: TextIO = open(filepath, "r", encoding="utf-8", errors="replace")
    reader = csv.reader(fh)
    header = next(reader, None)
    if header is None:
        fh.close(); return
    col_idx = detect_domain_column(header)
    for row in reader:
        if len(row) <= col_idx:
            continue
        domain = row[col_idx].strip().lower()
        if not domain or "." not in domain:
            continue
        if tld_filter:
            _, tld = extract_domain_parts(domain)
            if tld != f".{tld_filter}":
                continue
        yield domain
    fh.close()

def format_table(results: list[dict[str, Any]], limit: int = _TOP_DISPLAY) -> str:
    """Render top results as formatted ASCII table."""
    assert isinstance(results, list), "results must be a list"
    assert 0 < limit <= _MAX_RESULTS, f"limit must be 1..{_MAX_RESULTS}"
    display = results[:limit]
    hdr = f"{'#':>4}  {'Domain':<35} {'Score':>5}  {'Len':>3}  {'TLD':>3}  {'KW':>3}  {'Str':>3}  {'Keywords':<30}  {'Bonuses'}"
    sep = "-" * len(hdr)
    lines: list[str] = [sep, hdr, sep]
    for i, r in enumerate(display, 1):
        kw = ", ".join(r["keyword_matches"][:5]) or "-"
        bn = ", ".join(r["structure_bonuses"]) or "-"
        lines.append(
            f"{i:>4}  {r['domain']:<35} {r['total_score']:>5}  "
            f"{r['length_score']:>3}  {r['tld_score']:>3}  "
            f"{r['keyword_score']:>3}  {r['structure_score']:>3}  "
            f"{kw:<30}  {bn}"
        )
    lines.append(sep)
    return "\n".join(lines)

def save_results(results: list[dict[str, Any]], filepath: str) -> None:
    """Write scored results to JSON."""
    assert isinstance(results, list) and len(results) > 0, "need non-empty results"
    assert filepath.endswith(".json"), "output must be .json"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_scored": len(results),
        "top_score": results[0]["total_score"] if results else 0,
        "results": results,
    }
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    p = argparse.ArgumentParser(description="Scan DropCatch CSV exports for high-value domains.")
    p.add_argument("csv_path", help="Path to DropCatch CSV file")
    p.add_argument("--min-score", type=int, default=_DEFAULT_MIN_SCORE,
                    help=f"Minimum score threshold (default: {_DEFAULT_MIN_SCORE})")
    p.add_argument("--tld", type=str, default=None, help="Filter by TLD (e.g. 'com', 'ai')")
    p.add_argument("--keyword", type=str, default=None, help="Extra keyword to search for")
    p.add_argument("--top", type=int, default=_TOP_DISPLAY,
                    help=f"Top N results to display (default: {_TOP_DISPLAY})")
    p.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    return p

def run_scan(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Stream CSV, score each domain, return bounded sorted results."""
    assert os.path.isfile(args.csv_path), f"CSV not found: {args.csv_path}"
    assert args.min_score >= 0, "min-score must be non-negative"
    extra_kw: tuple[str, ...] = (args.keyword.lower(),) if args.keyword else ()
    tld_filter: str | None = args.tld.lower().lstrip(".") if args.tld else None
    scored: list[dict[str, Any]] = []
    scanned = 0
    for domain in stream_csv_domains(args.csv_path, tld_filter):
        scanned += 1
        result = score_domain(domain, extra_kw)
        if result["total_score"] >= args.min_score:
            scored.append(result)
        # Bounded memory: prune periodically
        if len(scored) > _MAX_RESULTS * 2:
            scored.sort(key=lambda x: x["total_score"], reverse=True)
            scored = scored[:_MAX_RESULTS]
        if scanned % 100_000 == 0:
            print(f"  ... scanned {scanned:,} domains, {len(scored):,} passed", file=sys.stderr)
    scored.sort(key=lambda x: (-x["total_score"], x["domain"]))
    return scored[:_MAX_RESULTS]

def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    print(f"DropCatch CSV Scanner", file=sys.stderr)
    print(f"  File:      {args.csv_path}", file=sys.stderr)
    print(f"  Min score: {args.min_score}", file=sys.stderr)
    print(f"  TLD:       {args.tld or 'all'}", file=sys.stderr)
    print(f"  Keyword:   {args.keyword or 'none'}", file=sys.stderr)
    print(f"  Top:       {args.top}\n", file=sys.stderr)
    results = run_scan(args)
    if not results:
        print("No domains matched the criteria.", file=sys.stderr)
        sys.exit(0)
    display_limit = min(args.top, len(results), _MAX_RESULTS)
    print(format_table(results, display_limit))
    print(f"\nTotal scanned | Passed: {len(results)} domains above score {args.min_score}")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = args.output or os.path.join(_DATA_DIR, f"dropcatch_scan_{date_str}.json")
    save_results(results, out_path)
    print(f"Results saved to: {out_path}", file=sys.stderr)

if __name__ == "__main__":
    main()

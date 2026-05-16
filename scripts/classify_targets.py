#!/usr/bin/env python3
"""DeepSeek Target Classifier — niche, brandability, quality, bid, priority, risk.

Usage: python scripts/classify_targets.py [--domain X] [--dry-run] [--output F]
NASA P10: <60-line fns, 2+ assertions/fn, no global mutable, bounded loops.
"""
from __future__ import annotations
import argparse, asyncio, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT: str = str(Path(__file__).resolve().parent.parent)
_MONITORED: str = os.path.join(_ROOT, "scripts", "monitored_domains.json")
_DEFAULT_OUT: str = os.path.join(_ROOT, "data", "domain_classifications.json")
_MAX_BATCH: int = 50
_MAX_BATCHES: int = 5
_FALLBACK: tuple[str, ...] = (
    "ghostautonomy.com", "guerrameats.com", "sunnyray.org", "globalgeopark.org",
    "goodglammgroup.com", "sendy.co", "readingfoundation.org", "imageeditor.net",
    "codeparrot.ai", "bestdevtools.com", "taskplanner.com", "codehelper.com",
)

def load_domains_from_json(path: str) -> list[dict[str, Any]]:
    """Parse monitored_domains.json into flat domain-entry list."""
    assert isinstance(path, str) and len(path) > 0, "path must be non-empty string"
    assert os.path.isfile(path), f"file not found: {path}"
    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)
    assert isinstance(raw, dict) and "domains" in raw, "JSON must have 'domains' dict"
    entries: list[dict[str, Any]] = []
    for tier_list in raw["domains"].values():
        assert isinstance(tier_list, list), "each tier must be a list"
        for item in tier_list:
            if len(entries) >= _MAX_BATCH * _MAX_BATCHES:
                break
            assert "domain" in item, f"entry missing 'domain': {item}"
            entries.append(item)
    return entries

def load_domains(single: str | None) -> list[dict[str, Any]]:
    """Load from single arg, JSON file, or hardcoded fallback."""
    assert single is None or isinstance(single, str), "single must be str or None"
    assert _MAX_BATCH > 0, "MAX_BATCH must be positive"
    if single:
        return [{"domain": single, "notes": "manual lookup"}]
    if os.path.isfile(_MONITORED):
        entries = load_domains_from_json(_MONITORED)
        if entries:
            return entries[:_MAX_BATCH * _MAX_BATCHES]
    return [{"domain": d, "notes": "fallback"} for d in _FALLBACK]

def build_prompt(entries: list[dict[str, Any]]) -> str:
    """Build acquisition-classification prompt for DeepSeek."""
    assert isinstance(entries, list) and 1 <= len(entries) <= _MAX_BATCH, "bad batch size"
    assert all("domain" in e for e in entries), "all entries need 'domain'"
    lines = [
        f"{i+1}. {e['domain']} (ETV=${e.get('etv',0)}, bid=${e.get('max_bid',0)}) — {e.get('notes','')}"
        for i, e in enumerate(entries)
    ]
    return (
        "You are a domain acquisition analyst. Classify each domain below.\n\n"
        f"Domains:\n" + "\n".join(lines) + "\n\n"
        "For EACH domain return JSON with these fields:\n"
        '- "domain": the domain name\n'
        '- "niche": (tech, cooking, finance, health, education, gaming, automotive, '
        'tools, productivity, design, ai, nonprofit, other)\n'
        '- "brandability": 1-10\n- "quality": 1-10 (length, TLD, memorability, keyword)\n'
        '- "max_bid": recommended max bid USD\n'
        '- "priority": critical | high | medium | low | skip\n'
        '- "monetization": content_site | redirect | flip | hold | develop\n'
        '- "risk": brief trademark/legal assessment\n'
        '- "reasoning": 1-sentence justification\n\n'
        'Wrap in {"classifications": [...]}. ONLY valid JSON, no markdown.'
    )

def _mock(entry: dict[str, Any]) -> dict[str, Any]:
    """Dry-run placeholder result."""
    assert isinstance(entry, dict) and "domain" in entry, "entry needs domain"
    assert isinstance(entry["domain"], str), "domain must be string"
    return {"domain": entry["domain"], "niche": "unknown", "brandability": 5,
            "quality": 5, "max_bid": entry.get("max_bid", 50), "priority": "medium",
            "monetization": "content_site", "risk": "not assessed", "reasoning": "dry run"}

def _validate(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single classification from LLM response."""
    assert isinstance(item, dict) and "domain" in item, "item needs 'domain'"
    assert isinstance(item["domain"], str), "domain must be string"
    return {"domain": str(item["domain"]), "niche": str(item.get("niche", "other")),
            "brandability": max(1, min(10, int(item.get("brandability", 5)))),
            "quality": max(1, min(10, int(item.get("quality", 5)))),
            "max_bid": max(0, int(item.get("max_bid", 50))),
            "priority": str(item.get("priority", "medium")),
            "monetization": str(item.get("monetization", "content_site")),
            "risk": str(item.get("risk", "unknown")),
            "reasoning": str(item.get("reasoning", ""))}

async def classify_batch(entries: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    """Send one batch to DeepSeek; returns validated classifications."""
    assert isinstance(entries, list) and 1 <= len(entries) <= _MAX_BATCH, "bad batch"
    assert isinstance(dry_run, bool), "dry_run must be bool"
    prompt: str = build_prompt(entries)
    if dry_run:
        print("=== DRY RUN PROMPT ===\n" + prompt + "\n======================")
        return [_mock(e) for e in entries]
    sys.path.insert(0, _ROOT)
    from config.settings import load_settings
    from clients.deepseek import DeepSeekClient  # noqa: F811
    settings = load_settings()
    if not settings.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not set. Add to .env (https://platform.deepseek.com)")
        sys.exit(1)
    client = DeepSeekClient(settings)
    import httpx
    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
               "max_tokens": 4096, "temperature": 0.3, "response_format": {"type": "json_object"}}
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.post("https://api.deepseek.com/v1/chat/completions",
                                   headers=client._build_headers(), json=payload)
    except httpx.TimeoutException:
        print("ERROR: DeepSeek timed out (60s)"); return [_mock(e) for e in entries]
    if resp.status_code != 200:
        print(f"ERROR: DeepSeek {resp.status_code}: {resp.text[:200]}"); return [_mock(e) for e in entries]
    parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
    results: list = parsed if isinstance(parsed, list) else []
    if isinstance(parsed, dict):
        for k in ("classifications", "results", "data", "domains"):
            if k in parsed and isinstance(parsed[k], list):
                results = parsed[k]; break
    assert isinstance(results, list), "parsed must be list"
    return [_validate(r) for r in results[:_MAX_BATCH]]

def print_table(results: list[dict[str, Any]]) -> None:
    """Print formatted classification table to stdout."""
    assert isinstance(results, list), "results must be list"
    assert all(isinstance(r, dict) for r in results[:_MAX_BATCH]), "items must be dicts"
    print("\n" + "=" * 120)
    print(f"{'Domain':<28} {'Niche':<14} {'Brand':>5} {'Qual':>4} {'Bid':>6} {'Priority':<10} {'Strategy':<14} {'Risk'}")
    print("-" * 120)
    for r in results[:_MAX_BATCH * _MAX_BATCHES]:
        print(f"{r['domain']:<28} {r['niche']:<14} {r['brandability']:>5} {r['quality']:>4} "
              f"${r['max_bid']:>5} {r['priority']:<10} {r['monetization']:<14} {r['risk'][:38]}")
    print("=" * 120)

def save_results(results: list[dict[str, Any]], path: str) -> None:
    """Write classifications to JSON file."""
    assert isinstance(results, list) and isinstance(path, str), "bad args"
    assert len(path) > 0, "output path empty"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out = {"generated": datetime.now(timezone.utc).isoformat(), "count": len(results),
           "classifications": results}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"Saved {len(results)} classifications -> {path}")

async def run(args: argparse.Namespace) -> None:
    """Orchestrate batched classification."""
    assert isinstance(args, argparse.Namespace) and hasattr(args, "dry_run"), "bad args"
    assert hasattr(args, "domain"), "args needs domain attr"
    entries = load_domains(args.domain)
    print(f"Classifying {len(entries)} domain(s)...")
    all_results: list[dict[str, Any]] = []
    for batch_idx in range(_MAX_BATCHES):
        batch = entries[batch_idx * _MAX_BATCH:(batch_idx + 1) * _MAX_BATCH]
        if not batch:
            break
        print(f"  Batch {batch_idx + 1}: {len(batch)} domains")
        all_results.extend(await classify_batch(batch, args.dry_run))
    print_table(all_results)
    save_results(all_results, args.output or _DEFAULT_OUT)

def main() -> None:
    """CLI entrypoint: parse args, run async."""
    p = argparse.ArgumentParser(description="Classify monitored domains via DeepSeek")
    p.add_argument("--domain", type=str, default=None, help="Single domain to classify")
    p.add_argument("--dry-run", action="store_true", help="Show prompt, skip API")
    p.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = p.parse_args()
    assert isinstance(args, argparse.Namespace), "parse failed"
    assert args.domain is None or len(args.domain) > 2, "domain too short"
    asyncio.run(run(args))

if __name__ == "__main__":
    main()

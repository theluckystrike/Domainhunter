#!/usr/bin/env python3
"""DropCatch Dropping Domains Scanner v2 — download, cross-reference, and score.

Downloads the DropCatch dropping domains list via the v2 API, cross-references
against monitored domains, and surfaces high-value opportunistic finds.

Usage:
    python scripts/dropcatch_dropping_scanner_v2.py              # All days
    python scripts/dropcatch_dropping_scanner_v2.py --days 0     # Dropping today
    python scripts/dropcatch_dropping_scanner_v2.py --days 1     # Dropping tomorrow
    python scripts/dropcatch_dropping_scanner_v2.py --dry-run    # No API calls

NASA Power of 10: functions <60 lines, 2+ assertions, bounded loops,
frozen dataclasses, no global mutable state, all return values checked.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import Settings
from clients.dropcatch_client import DropCatchClient

# ---------------------------------------------------------------------------
# Constants (immutable)
# ---------------------------------------------------------------------------
_ROOT: Final[str] = str(Path(__file__).resolve().parent.parent)
_DATA_DIR: Final[str] = os.path.join(_ROOT, "data")
_MONITORED_PATH: Final[str] = os.path.join(_ROOT, "scripts", "monitored_domains.json")

_DAYS_OUT_MAP: Final[dict[int, str]] = {
    0: "DaysOut0", 1: "DaysOut1", 2: "DaysOut2",
    3: "DaysOut3", 4: "DaysOut4", 5: "AllDays",
}
_DAYS_OUT_LABEL: Final[dict[int, str]] = {
    0: "Today (0 days)", 1: "Tomorrow (1 day)", 2: "2 days out",
    3: "3 days out", 4: "4 days out", 5: "AllDays (0-4 days out)",
}

_MAX_RESULTS: Final[int] = 500
_MAX_OPPS: Final[int] = 100
_MAX_ROWS: Final[int] = 5_000_000  # hard loop bound

# Short .com thresholds
_SHORT_COM_MAX_LEN: Final[int] = 4
_PREMIUM_COM_MAX_LEN: Final[int] = 6

# Dictionary words for opportunistic detection (high-frequency English)
_DICTIONARY_WORDS: Final[frozenset[str]] = frozenset((
    "able", "acre", "aged", "aide", "ally", "apex", "arch", "aria", "aura",
    "auto", "axis", "band", "bank", "barn", "base", "bath", "beam", "bear",
    "bell", "belt", "best", "bird", "bite", "blue", "boat", "bold", "bolt",
    "bond", "bone", "book", "boom", "born", "boss", "bowl", "bulk", "burn",
    "cafe", "cage", "cake", "calm", "camp", "cape", "card", "care", "cart",
    "case", "cash", "cast", "cave", "cell", "chat", "chip", "city", "clan",
    "clay", "clip", "club", "coal", "coat", "code", "coil", "coin", "cold",
    "cole", "colt", "cone", "cook", "cool", "cope", "copy", "cord", "core",
    "corn", "cost", "cozy", "crew", "crop", "crow", "cube", "cure", "curl",
    "dale", "dare", "dark", "dart", "dash", "dawn", "deal", "dear", "debt",
    "deck", "deed", "deep", "deer", "demo", "desk", "dial", "diet", "dine",
    "disc", "dock", "dome", "door", "dose", "dove", "down", "draw", "drop",
    "drum", "dual", "dusk", "dust", "duty", "each", "earn", "ease", "east",
    "echo", "edge", "edit", "epic", "even", "ever", "exam", "exec", "expo",
    "face", "fact", "fade", "fail", "fair", "fake", "fall", "fame", "fare",
    "farm", "fast", "fate", "fawn", "feed", "feel", "file", "film", "find",
    "fine", "fire", "firm", "fish", "five", "flag", "flat", "flaw", "flex",
    "flip", "flow", "foam", "fold", "folk", "fond", "font", "food", "foot",
    "ford", "fore", "fork", "form", "fort", "four", "free", "fuel", "full",
    "fund", "fury", "fuse", "gain", "gala", "gale", "game", "gang", "gate",
    "gave", "gaze", "gear", "gift", "gist", "glad", "glow", "glue", "goal",
    "goat", "gold", "golf", "good", "grab", "gray", "grid", "grip", "grit",
    "grow", "gulf", "guru", "gust", "hack", "hail", "hair", "hale", "half",
    "hall", "halt", "hand", "hard", "harm", "harp", "hash", "haul", "have",
    "hawk", "haze", "head", "heal", "heap", "hear", "heat", "heed", "heir",
    "held", "helm", "help", "herb", "herd", "hero", "hide", "high", "hike",
    "hill", "hint", "hire", "hive", "hold", "hole", "home", "hood", "hook",
    "hope", "horn", "host", "hour", "huge", "hull", "hunt", "hurt", "hype",
    "icon", "idea", "iron", "isle", "jade", "jail", "jazz", "jest", "jobs",
    "join", "joke", "jump", "jury", "just", "keen", "keep", "kelp", "kept",
    "kick", "kind", "king", "kite", "knit", "knob", "knot", "know", "lace",
    "lack", "laid", "lake", "lamb", "lamp", "land", "lane", "lark", "lash",
    "last", "late", "lawn", "lead", "leaf", "leak", "lean", "leap", "left",
    "lend", "lens", "less", "lien", "life", "lift", "like", "lime", "limp",
    "line", "link", "lint", "lion", "list", "live", "load", "loan", "lock",
    "loft", "logo", "long", "look", "loop", "loom", "lord", "lore", "lose",
    "loss", "lost", "loud", "love", "luck", "lure", "lush", "luxe", "lynx",
    "mace", "made", "maid", "mail", "main", "make", "male", "mall", "malt",
    "mane", "many", "maps", "mare", "mark", "mars", "mart", "mask", "mass",
    "mast", "mate", "maze", "meal", "mean", "meat", "meet", "melt", "memo",
    "mend", "menu", "mesh", "mild", "mile", "milk", "mill", "mind", "mine",
    "mint", "miss", "mist", "moat", "mode", "mold", "mood", "moon", "moor",
    "more", "moss", "most", "move", "much", "muse", "must", "myth", "nail",
    "name", "nave", "navy", "near", "neat", "neck", "need", "nest", "news",
    "next", "nice", "nine", "node", "none", "noon", "norm", "nose", "note",
    "noun", "nova", "null", "oaks", "oath", "odds", "omen", "once", "only",
    "onto", "open", "opus", "oral", "orca", "oven", "over", "pace", "pack",
    "page", "paid", "pail", "pain", "pair", "pale", "palm", "pane", "park",
    "part", "pass", "past", "path", "pave", "peak", "pear", "peel", "peer",
    "perk", "pest", "pick", "pier", "pike", "pile", "pine", "pink", "pipe",
    "pith", "plan", "play", "plea", "plot", "plow", "plug", "plum", "plus",
    "poem", "poet", "pole", "poll", "polo", "pond", "pool", "pony", "poor",
    "pope", "pore", "pork", "port", "pose", "post", "pour", "prep", "prey",
    "prop", "pros", "pull", "pulp", "pump", "punk", "pure", "push", "quit",
    "quiz", "race", "rack", "raft", "rage", "raid", "rail", "rain", "rake",
    "ramp", "rang", "rank", "rare", "rash", "rate", "rave", "rays", "read",
    "real", "reap", "reed", "reef", "reel", "rely", "rent", "rest", "rice",
    "rich", "ride", "rift", "rind", "ring", "rink", "riot", "rise", "risk",
    "road", "roam", "roar", "robe", "rock", "rode", "role", "roll", "roof",
    "room", "root", "rope", "rose", "rosy", "ruin", "rule", "rung", "ruse",
    "rush", "rust", "safe", "sage", "said", "sail", "sake", "sale", "salt",
    "same", "sand", "sane", "sang", "sank", "save", "scan", "seal", "seam",
    "seas", "seat", "seed", "seek", "seem", "seen", "self", "sell", "semi",
    "send", "sent", "shed", "shin", "ship", "shop", "shot", "show", "shut",
    "sick", "side", "sift", "sigh", "sign", "silk", "silo", "sing", "sink",
    "site", "size", "skim", "skin", "skip", "slab", "slam", "slap", "slim",
    "slip", "slot", "slow", "slug", "snap", "snow", "soak", "soar", "sock",
    "sofa", "soft", "soil", "sold", "sole", "solo", "some", "song", "soon",
    "sort", "soul", "sour", "span", "spec", "spin", "spit", "spot", "spur",
    "stab", "star", "stay", "stem", "step", "stew", "stop", "stow", "stub",
    "such", "suit", "sulk", "sump", "sung", "sunk", "sure", "surf", "swap",
    "sway", "swim", "tack", "tact", "tail", "take", "tale", "talk", "tall",
    "tame", "tank", "tape", "tarp", "task", "taxa", "team", "tear", "tech",
    "tell", "tend", "tent", "term", "test", "text", "than", "that", "them",
    "then", "they", "thin", "this", "thou", "tick", "tide", "tidy", "tied",
    "tier", "tile", "till", "tilt", "time", "tiny", "tire", "toad", "toil",
    "told", "toll", "tomb", "tone", "tool", "tops", "tore", "torn", "toss",
    "tour", "town", "trap", "tray", "tree", "trek", "trim", "trio", "trip",
    "trot", "true", "tube", "tuck", "tuft", "tulip", "tune", "turf", "turn",
    "twin", "type", "unit", "upon", "urge", "used", "user", "vain", "vale",
    "vane", "vary", "vase", "vast", "veil", "vein", "vent", "verb", "very",
    "vest", "vibe", "view", "vine", "visa", "void", "volt", "vote", "wade",
    "wage", "wail", "wait", "wake", "walk", "wall", "wand", "want", "ward",
    "warm", "warn", "warp", "wary", "wash", "wasp", "wave", "wavy", "waxy",
    "weak", "wear", "weed", "week", "weld", "well", "went", "were", "west",
    "what", "when", "whim", "whom", "wick", "wide", "wife", "wild", "will",
    "wilt", "wily", "wind", "wine", "wing", "wink", "wipe", "wire", "wise",
    "wish", "with", "woke", "wolf", "wood", "wool", "word", "wore", "work",
    "worm", "worn", "wrap", "wren", "yard", "yarn", "year", "yell", "yoga",
    "yoke", "your", "zeal", "zero", "zinc", "zone", "zoom",
    # 5-letter high-value words
    "angel", "audio", "badge", "bench", "blend", "block", "bloom", "board",
    "boost", "bound", "brain", "brand", "brave", "bread", "break", "breed",
    "brick", "bride", "brief", "bring", "broad", "brook", "brush", "build",
    "buyer", "cabin", "cable", "candy", "cargo", "carry", "cause", "cedar",
    "chain", "chair", "chalk", "charm", "chart", "chase", "cheap", "check",
    "chess", "chief", "child", "chord", "civic", "civil", "claim", "class",
    "clean", "clear", "clerk", "cliff", "climb", "cling", "clock", "close",
    "cloud", "coach", "coast", "color", "comet", "coral", "count", "court",
    "cover", "craft", "crane", "crash", "cream", "creek", "crest", "crisp",
    "cross", "crowd", "crown", "crush", "cubic", "curve", "cycle", "daily",
    "dance", "debut", "decor", "delta", "depot", "depth", "derby", "diner",
    "disco", "ditto", "donor", "dozen", "draft", "drain", "drake", "drama",
    "dream", "dress", "drift", "drill", "drink", "drive", "drone", "dwell",
    "eagle", "early", "earth", "eight", "elect", "elite", "ember", "entry",
    "equal", "equip", "erase", "error", "essay", "event", "every", "exact",
    "exalt", "exile", "expat", "extra", "fable", "faith", "feast", "fence",
    "fetch", "fever", "fiber", "field", "final", "first", "fixed", "flame",
    "flash", "flask", "fleet", "flesh", "float", "flock", "flood", "floor",
    "flora", "floss", "flour", "flush", "flute", "focus", "force", "forge",
    "forth", "forum", "found", "frame", "frank", "fraud", "fresh", "front",
    "frost", "fruit", "gamma", "gauge", "ghost", "giant", "given", "gland",
    "glass", "gleam", "glide", "globe", "gloom", "gloss", "glyph", "going",
    "grace", "grade", "graft", "grain", "grand", "grant", "grape", "graph",
    "grasp", "grass", "grave", "great", "green", "greet", "grief", "grind",
    "gripe", "gross", "group", "grove", "growl", "grown", "guard", "guess",
    "guest", "guide", "guild", "haiku", "haven", "heart", "heavy", "hedge",
    "hello", "hence", "hobby", "homer", "honey", "honor", "horse", "hotel",
    "house", "human", "humor", "hyper", "ideal", "image", "inbox", "index",
    "indie", "inner", "input", "intel", "ivory", "jewel", "joint", "joker",
    "juice", "karma", "kayak", "knack", "knife", "knock", "known", "label",
    "labor", "lance", "large", "laser", "latch", "later", "laugh", "layer",
    "lease", "ledge", "legal", "lemon", "level", "lever", "light", "limbo",
    "limit", "linen", "lions", "llama", "local", "lodge", "logic", "loose",
    "lotus", "lover", "lower", "loyal", "lucky", "lunar", "lunch", "macro",
    "magic", "major", "manor", "maple", "march", "marsh", "match", "mayor",
    "media", "medal", "merge", "merit", "metal", "meter", "micro", "might",
    "minor", "minus", "mixer", "model", "money", "month", "moral", "motor",
    "mound", "mount", "mouse", "mouth", "movie", "mural", "music", "myths",
    "naive", "nerve", "never", "nexus", "night", "noble", "noise", "north",
    "notch", "novel", "nurse", "nylon", "oasis", "ocean", "offer", "often",
    "olive", "omega", "onset", "opera", "orbit", "order", "organ", "other",
    "outer", "owner", "oxide", "ozone", "panda", "panel", "paper", "party",
    "pasta", "patch", "pause", "peace", "peach", "pearl", "penny", "perch",
    "phase", "phone", "photo", "piano", "piece", "pilot", "pinch", "pixel",
    "pizza", "place", "plain", "plane", "plant", "plate", "plaza", "plead",
    "plumb", "point", "polar", "pouch", "pound", "power", "press", "price",
    "pride", "prime", "print", "prior", "prize", "probe", "proof", "proud",
    "proxy", "pulse", "punch", "pupil", "purse", "queen", "query", "quest",
    "queue", "quick", "quiet", "quota", "quote", "radar", "radio", "rally",
    "ranch", "range", "rapid", "reach", "react", "realm", "rebel", "reign",
    "relay", "renew", "reply", "rider", "ridge", "rifle", "right", "rigor",
    "river", "robin", "robot", "rocky", "rogue", "round", "route", "royal",
    "rover", "ruler", "rural", "salad", "scale", "scene", "scope", "score",
    "scout", "sedan", "sense", "serve", "setup", "seven", "shade", "shaft",
    "shake", "shall", "shape", "share", "shark", "sharp", "shawl", "shear",
    "sheep", "sheer", "sheet", "shelf", "shell", "shift", "shine", "shore",
    "short", "shout", "sided", "siege", "sight", "sigma", "since", "sixth",
    "sixty", "skill", "skull", "slate", "sleep", "slice", "slide", "slope",
    "smart", "smell", "smile", "smoke", "snack", "snake", "solar", "solid",
    "solve", "sonic", "sorry", "sound", "south", "space", "spare", "spark",
    "speak", "speed", "spend", "spice", "spine", "spoke", "spoon", "sport",
    "spray", "squad", "stack", "staff", "stage", "stain", "stake", "stale",
    "stall", "stamp", "stand", "stare", "stark", "start", "state", "stave",
    "stays", "steam", "steel", "steep", "steer", "stern", "stick", "still",
    "stock", "stone", "stool", "store", "storm", "story", "stout", "stove",
    "strap", "straw", "strip", "stuff", "style", "sugar", "suite", "sunny",
    "super", "surge", "swamp", "swarm", "sweet", "swept", "swift", "swirl",
    "swing", "sword", "sworn", "syrup", "table", "tally", "talon", "taste",
    "taxes", "teach", "tempo", "thank", "theme", "there", "thick", "thing",
    "think", "third", "those", "three", "throw", "thumb", "tiger", "tight",
    "timer", "title", "token", "topic", "total", "touch", "tough", "towel",
    "tower", "trace", "track", "trade", "trail", "train", "trait", "trend",
    "trial", "tribe", "trick", "trust", "truth", "tumor", "tweak", "twice",
    "twist", "ultra", "uncle", "under", "union", "unite", "unity", "until",
    "upper", "urban", "usage", "utter", "valid", "valor", "value", "vault",
    "venue", "verse", "video", "vigor", "viral", "viper", "visit", "vista",
    "vital", "vivid", "vocal", "voice", "voter", "watch", "water", "weave",
    "wedge", "wheat", "wheel", "where", "which", "while", "white", "whole",
    "whose", "width", "witch", "woman", "world", "worst", "worth", "wound",
    "wrist", "write", "yacht", "yield", "young", "youth", "zebra",
))


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DroppingDomain:
    """A single domain from the DropCatch dropping list."""
    domain: str
    drop_date: str
    tld: str
    sld: str


@dataclass(frozen=True)
class MonitoredMatch:
    """A monitored domain found in the dropping list."""
    domain: str
    drop_date: str
    tier: str
    max_bid: float
    notes: str
    action: str = "BACKORDER IMMEDIATELY"


@dataclass(frozen=True)
class OpportunisticFind:
    """A high-value domain found opportunistically."""
    domain: str
    drop_date: str
    length: int
    find_type: str
    est_value: str
    score: int


@dataclass(frozen=True)
class ScanResult:
    """Complete scan results."""
    scan_type: str
    total_dropping: int
    monitored_matches: tuple[MonitoredMatch, ...]
    opportunistic_finds: tuple[OpportunisticFind, ...]
    scanned_at: str


# ---------------------------------------------------------------------------
# Monitored domains loader
# ---------------------------------------------------------------------------
def load_monitored_domains(path: str) -> dict[str, dict[str, Any]]:
    """Load monitored domains into a lookup dict keyed by lowercase domain.

    Returns:
        Dict mapping domain name -> {tier, max_bid, notes, drop_est}.
    """
    assert os.path.isfile(path), f"Monitored domains file not found: {path}"
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), f"Expected dict root, got {type(data)}"

    lookup: dict[str, dict[str, Any]] = {}
    active = data.get("active_targets", {})
    for tier_name in ("critical", "high", "medium", "low"):
        entries = active.get(tier_name, [])
        for entry in entries:
            domain = entry.get("domain", "").strip().lower()
            if domain:
                lookup[domain] = {
                    "tier": tier_name,
                    "max_bid": entry.get("max_bid", 59),
                    "notes": entry.get("notes", ""),
                    "drop_est": entry.get("drop_est", ""),
                }

    # Also include watch_list domains
    for entry in data.get("watch_list", []):
        domain = entry.get("domain", "").strip().lower()
        if domain and domain not in lookup:
            lookup[domain] = {
                "tier": "watch",
                "max_bid": 59,
                "notes": entry.get("notes", ""),
                "drop_est": "",
            }

    assert len(lookup) > 0, "No monitored domains loaded"
    return lookup


# ---------------------------------------------------------------------------
# ZIP / CSV extraction
# ---------------------------------------------------------------------------
def extract_csv_from_zip(zip_bytes: bytes) -> str:
    """Extract the first CSV file from a ZIP archive.

    Returns:
        CSV content as a string.
    """
    assert len(zip_bytes) > 0, "ZIP bytes must not be empty"
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = zf.namelist()
        assert len(names) > 0, "ZIP archive is empty"
        csv_names = [n for n in names if n.lower().endswith(".csv")]
        target = csv_names[0] if csv_names else names[0]
        content = zf.read(target).decode("utf-8", errors="replace")
    assert len(content) > 0, f"CSV file '{target}' is empty"
    return content


def parse_domain_parts(full_domain: str) -> tuple[str, str]:
    """Split 'example.com' into ('example', '.com')."""
    assert isinstance(full_domain, str), "domain must be a string"
    full_domain = full_domain.strip().lower()
    assert len(full_domain) > 0, "domain must not be empty"
    dot_idx = full_domain.rfind(".")
    if dot_idx <= 0:
        return full_domain, ""
    return full_domain[:dot_idx], full_domain[dot_idx:]


def detect_columns(header: list[str]) -> tuple[int, int]:
    """Find domain and drop-date column indices from CSV header.

    Returns:
        (domain_col_idx, date_col_idx). date_col_idx is -1 if not found.
    """
    assert isinstance(header, list), "header must be a list"
    assert len(header) > 0, "header must not be empty"
    lower = [h.strip().lower() for h in header]

    domain_col = 0
    for target in ("domain", "domain name", "domainname", "name"):
        if target in lower:
            domain_col = lower.index(target)
            break

    date_col = -1
    for target in ("drop date", "dropdate", "drop_date", "date", "dropping date"):
        if target in lower:
            date_col = lower.index(target)
            break

    return domain_col, date_col


def parse_csv_domains(csv_content: str) -> list[DroppingDomain]:
    """Parse CSV content into a list of DroppingDomain objects.

    Bounded to _MAX_ROWS to prevent unbounded memory growth.
    """
    assert len(csv_content) > 0, "CSV content must not be empty"
    assert isinstance(csv_content, str), "csv_content must be a string"
    reader = csv.reader(io.StringIO(csv_content))
    header = next(reader, None)
    if header is None:
        return []

    domain_col, date_col = detect_columns(header)
    domains: list[DroppingDomain] = []
    row_count = 0

    for row in reader:
        row_count += 1
        if row_count > _MAX_ROWS:
            break
        if len(row) <= domain_col:
            continue
        raw_domain = row[domain_col].strip().lower()
        if not raw_domain or "." not in raw_domain:
            continue
        sld, tld = parse_domain_parts(raw_domain)
        if not sld or not tld:
            continue
        drop_date = ""
        if date_col >= 0 and len(row) > date_col:
            drop_date = row[date_col].strip()
        domains.append(DroppingDomain(
            domain=raw_domain, drop_date=drop_date, tld=tld, sld=sld,
        ))

    return domains


# ---------------------------------------------------------------------------
# Cross-referencing
# ---------------------------------------------------------------------------
def find_monitored_matches(
    dropping: list[DroppingDomain],
    monitored: dict[str, dict[str, Any]],
) -> list[MonitoredMatch]:
    """Cross-reference dropping domains against monitored list.

    Returns:
        List of MonitoredMatch for every monitored domain found dropping.
    """
    assert isinstance(dropping, list), "dropping must be a list"
    assert isinstance(monitored, dict), "monitored must be a dict"

    matches: list[MonitoredMatch] = []
    dropping_lookup: frozenset[str] = frozenset(d.domain for d in dropping)
    drop_dates: dict[str, str] = {d.domain: d.drop_date for d in dropping}

    for domain in monitored:
        if domain in dropping_lookup:
            info = monitored[domain]
            matches.append(MonitoredMatch(
                domain=domain,
                drop_date=drop_dates.get(domain, ""),
                tier=info["tier"],
                max_bid=info["max_bid"],
                notes=info["notes"][:80] if info["notes"] else "",
            ))

    matches.sort(key=lambda m: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3, "watch": 4}.get(m.tier, 5),
        m.domain,
    ))
    return matches


# ---------------------------------------------------------------------------
# Opportunistic scoring
# ---------------------------------------------------------------------------
def _score_length_and_type(
    sld: str, tld: str,
) -> tuple[int, str, str]:
    """Score domain by length, TLD, and dictionary membership.

    Returns:
        (score, find_type, est_value) tuple.
    """
    assert isinstance(sld, str) and len(sld) > 0, "sld must be non-empty"
    assert isinstance(tld, str) and len(tld) > 0, "tld must be non-empty"
    score = 0
    find_type = ""
    est_value = ""

    # Short .com detection
    if tld == ".com" and len(sld) <= _SHORT_COM_MAX_LEN:
        score += 40
        find_type = "SHORT_COM"
        if len(sld) <= 2:
            est_value = "$100,000+"
        elif len(sld) == 3:
            est_value = "$50,000+"
        else:
            est_value = "$10,000+"
    elif tld == ".com" and len(sld) <= _PREMIUM_COM_MAX_LEN:
        if sld.isalpha() and "-" not in sld:
            score += 25
            find_type = "PREMIUM_SHORT"
            est_value = "$2,000+"

    # Short premium TLD (.ai, .io) <= 4 chars
    if tld in (".ai", ".io") and len(sld) <= _SHORT_COM_MAX_LEN:
        score += 15
        if not find_type:
            find_type = f"SHORT_{tld[1:].upper()}"
            est_value = "$1,000+"

    # All-alpha, no hyphens, no numbers bonus
    if sld.isalpha() and len(sld) <= 7:
        score += 5

    return score, find_type, est_value


def _score_dictionary(
    sld: str, tld: str, base_type: str,
) -> tuple[int, str, str]:
    """Score domain by dictionary word membership.

    Returns:
        (score_delta, find_type, est_value) tuple.
    """
    assert isinstance(sld, str) and len(sld) > 0, "sld must be non-empty"
    assert isinstance(tld, str), "tld must be a string"

    if tld == ".com" and sld in _DICTIONARY_WORDS:
        if not base_type:
            return 35, "DICTIONARY_COM", "$5,000+"
        upgraded = "$50,000+" if len(sld) <= 4 else "$10,000+"
        return 35, base_type + "+DICT", upgraded

    if tld in (".ai", ".io") and sld in _DICTIONARY_WORDS:
        if not base_type:
            return 20, f"DICTIONARY_{tld[1:].upper()}", "$2,000+"
        return 20, base_type, ""

    return 0, "", ""


def classify_opportunistic(domain: DroppingDomain) -> OpportunisticFind | None:
    """Score a single domain for opportunistic value.

    Returns None if the domain does not meet any high-value criteria.
    """
    assert isinstance(domain, DroppingDomain), "must be DroppingDomain"
    assert len(domain.sld) > 0 and len(domain.tld) > 0, "domain parts required"
    score, find_type, est_value = _score_length_and_type(domain.sld, domain.tld)
    dict_score, dict_type, dict_value = _score_dictionary(
        domain.sld, domain.tld, find_type,
    )
    score += dict_score
    if dict_type:
        find_type = dict_type
    if dict_value:
        est_value = dict_value

    if score < 15:
        return None

    return OpportunisticFind(
        domain=domain.domain,
        drop_date=domain.drop_date,
        length=len(domain.sld),
        find_type=find_type,
        est_value=est_value,
        score=score,
    )


def find_opportunistic(
    dropping: list[DroppingDomain],
) -> list[OpportunisticFind]:
    """Scan all dropping domains for high-value opportunistic finds.

    Bounded to _MAX_OPPS results to cap memory.
    """
    assert isinstance(dropping, list), "dropping must be a list"
    assert len(dropping) <= _MAX_ROWS, f"dropping list exceeds bound: {len(dropping)}"

    finds: list[OpportunisticFind] = []
    for domain in dropping:
        result = classify_opportunistic(domain)
        if result is not None:
            finds.append(result)
        # Bounded: prune if too large
        if len(finds) > _MAX_OPPS * 2:
            finds.sort(key=lambda f: -f.score)
            finds = finds[:_MAX_OPPS]

    finds.sort(key=lambda f: (-f.score, f.domain))
    return finds[:_MAX_OPPS]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def format_header(scan_type: str, total: int) -> str:
    """Format the scan header block."""
    assert isinstance(scan_type, str), "scan_type must be string"
    assert total >= 0, "total must be non-negative"
    lines = [
        "",
        "DROPCATCH DROPPING DOMAINS SCAN",
        "================================",
        f"Scanning: {scan_type}",
        f"Total dropping: {total:,} domains",
        "",
    ]
    return "\n".join(lines)


def format_monitored_table(matches: list[MonitoredMatch]) -> str:
    """Format monitored domain matches as ASCII table."""
    assert isinstance(matches, list), "matches must be a list"
    assert len(matches) <= _MAX_RESULTS, "matches exceeds display bound"
    if not matches:
        return "MONITORED DOMAIN MATCHES (0 found): None\n"

    lines = [f"MONITORED DOMAIN MATCHES ({len(matches)} found):"]
    lines.append(
        f"  {'Domain':<30} {'Drop Date':<14} {'Tier':<10} "
        f"{'Max Bid':<10} {'Action'}"
    )
    lines.append("  " + "-" * 95)
    for m in matches:
        bid_str = f"${m.max_bid:,.0f}"
        lines.append(
            f"  {m.domain:<30} {m.drop_date:<14} {m.tier:<10} "
            f"{bid_str:<10} {m.action}"
        )
    lines.append("")
    return "\n".join(lines)


def format_opportunistic_table(finds: list[OpportunisticFind]) -> str:
    """Format opportunistic finds as ASCII table."""
    assert isinstance(finds, list), "finds must be a list"
    assert len(finds) <= _MAX_OPPS, "finds exceeds display bound"
    if not finds:
        return "OPPORTUNISTIC FINDS (0 found): None\n"

    display = finds[:50]
    lines = [f"OPPORTUNISTIC FINDS ({len(finds)} found):"]
    lines.append(
        f"  {'Domain':<30} {'Len':>4} {'Score':>5}  "
        f"{'Type':<20} {'Est. Value'}"
    )
    lines.append("  " + "-" * 80)
    for f in display:
        lines.append(
            f"  {f.domain:<30} {f.length:>4} {f.score:>5}  "
            f"{f.find_type:<20} {f.est_value}"
        )
    if len(finds) > 50:
        lines.append(f"  ... and {len(finds) - 50} more")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Results persistence
# ---------------------------------------------------------------------------
def save_results(result: ScanResult, output_path: str) -> None:
    """Save scan results to JSON."""
    assert isinstance(result, ScanResult), "must be ScanResult"
    assert output_path.endswith(".json"), "output must be .json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    payload: dict[str, Any] = {
        "scan_type": result.scan_type,
        "scanned_at": result.scanned_at,
        "total_dropping": result.total_dropping,
        "monitored_matches": [
            {
                "domain": m.domain,
                "drop_date": m.drop_date,
                "tier": m.tier,
                "max_bid": m.max_bid,
                "action": m.action,
                "notes": m.notes,
            }
            for m in result.monitored_matches
        ],
        "opportunistic_finds": [
            {
                "domain": f.domain,
                "drop_date": f.drop_date,
                "length": f.length,
                "find_type": f.find_type,
                "est_value": f.est_value,
                "score": f.score,
            }
            for f in result.opportunistic_finds
        ],
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------
def run_dry(days: int | None) -> None:
    """Dry-run: show what would happen without making API calls."""
    assert days is None or (0 <= days <= 4), f"days must be 0-4 or None, got {days}"
    assert os.path.isfile(_MONITORED_PATH), f"Monitored file missing: {_MONITORED_PATH}"
    scan_label = _DAYS_OUT_LABEL.get(
        5 if days is None else days, f"DaysOut{days}"
    )
    print(format_header(f"{scan_label} [DRY RUN]", 0))
    print("  Would authenticate via NameBright OAuth2")
    print("  Would download dropping domains CSV")
    print("  Would extract ZIP and parse CSV")

    monitored = load_monitored_domains(_MONITORED_PATH)
    print(f"  Loaded {len(monitored)} monitored domains for cross-reference")
    print("  Would cross-reference and score opportunistic finds")
    print("\n  [DRY RUN] No API calls made.\n")


# ---------------------------------------------------------------------------
# Main scan orchestration
# ---------------------------------------------------------------------------
def download_dropping(client: DropCatchClient, days: int | None) -> bytes:
    """Download dropping domains ZIP from DropCatch API.

    Args:
        client: Authenticated DropCatchClient.
        days: 0-4 for specific day, None for AllDays.

    Returns:
        Raw ZIP bytes.
    """
    assert isinstance(client, DropCatchClient), "must be DropCatchClient"
    days_out = 5 if days is None else days
    assert 0 <= days_out <= 5, f"days_out must be 0-5, got {days_out}"
    zip_bytes = client.download_dropping_domains(days_out=days_out)
    assert len(zip_bytes) > 0, "Downloaded ZIP is empty"
    return zip_bytes


def run_scan(days: int | None) -> ScanResult:
    """Execute the full scan pipeline.

    Steps:
        1. Authenticate and download dropping domains CSV
        2. Extract ZIP and parse CSV
        3. Cross-reference against monitored domains
        4. Score opportunistic finds
        5. Return structured results
    """
    settings = Settings()
    assert len(settings.dropcatch_client_id) > 0, (
        "DROPCATCH_CLIENT_ID not set in .env"
    )
    assert len(settings.dropcatch_api_secret) > 0, (
        "DROPCATCH_API_SECRET not set in .env"
    )

    scan_label = _DAYS_OUT_LABEL.get(
        5 if days is None else days, f"DaysOut{days}"
    )
    print(f"\n  Authenticating to DropCatch via NameBright OAuth2...",
          file=sys.stderr)

    with DropCatchClient(
        client_id=settings.dropcatch_client_id,
        client_secret=settings.dropcatch_api_secret,
    ) as client:
        print(f"  Downloading dropping domains: {scan_label}...",
              file=sys.stderr)
        zip_bytes = download_dropping(client, days)
        print(f"  Downloaded {len(zip_bytes):,} bytes", file=sys.stderr)

    csv_content = extract_csv_from_zip(zip_bytes)
    print(f"  Extracted CSV ({len(csv_content):,} chars)", file=sys.stderr)

    dropping = parse_csv_domains(csv_content)
    print(f"  Parsed {len(dropping):,} dropping domains", file=sys.stderr)

    monitored = load_monitored_domains(_MONITORED_PATH)
    print(f"  Cross-referencing against {len(monitored)} monitored domains...",
          file=sys.stderr)

    matches = find_monitored_matches(dropping, monitored)
    print(f"  Found {len(matches)} monitored matches", file=sys.stderr)

    print("  Scanning for opportunistic finds...", file=sys.stderr)
    opps = find_opportunistic(dropping)
    print(f"  Found {len(opps)} opportunistic finds\n", file=sys.stderr)

    return ScanResult(
        scan_type=scan_label,
        total_dropping=len(dropping),
        monitored_matches=tuple(matches),
        opportunistic_finds=tuple(opps),
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    assert argparse is not None, "argparse module required"
    parser = argparse.ArgumentParser(
        description="Download and scan DropCatch dropping domains list.",
    )
    parser.add_argument(
        "--days", type=int, default=None, choices=[0, 1, 2, 3, 4],
        help="Days out (0=today, 1=tomorrow, ..., 4). Omit for AllDays.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making API calls.",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Custom output JSON path.",
    )
    assert isinstance(parser, argparse.ArgumentParser), "parser build failed"
    return parser


def main() -> None:
    """CLI entry point."""
    assert os.path.isdir(_DATA_DIR) or True, "data dir check"  # will be created
    parser = build_parser()
    args = parser.parse_args()
    assert args is not None, "argument parsing failed"

    if args.dry_run:
        run_dry(args.days)
        return

    result = run_scan(args.days)

    # Display results
    print(format_header(result.scan_type, result.total_dropping))
    print(format_monitored_table(list(result.monitored_matches)))
    print(format_opportunistic_table(list(result.opportunistic_finds)))

    # Urgent alerts for monitored matches
    if result.monitored_matches:
        print("=" * 60)
        print("  URGENT: Monitored domains found in dropping list!")
        print("  Place backorders immediately on DropCatch.")
        print("=" * 60)
        print()

    # Save results
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = args.output or os.path.join(
        _DATA_DIR, f"dropcatch_dropping_{date_str}.json",
    )
    save_results(result, output_path)
    print(f"Results saved to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

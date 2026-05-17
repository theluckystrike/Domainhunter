#!/usr/bin/env python3
"""Domain Hunter -- GoDaddy Auction Inventory Monitor.

Downloads GoDaddy's free daily inventory files (no auth required) and checks
for target domains in auctions, closeouts, and expiring listings.

Inventory files updated daily 7-8am PST at:
  https://inventory.auctions.godaddy.com/

Supports:
  - all_biddable_auctions.json.zip — currently in auction
  - closeout_listings.json.zip — closeout Buy Now (Dutch auction $9→$5)
  - all_expiring_auctions.json.zip — expiring soon
  - auctions_ending_today.json.zip — ending today
  - recent_listings.json.zip — newly listed

Run:   python scripts/godaddy_monitor.py
Cron:  0 8 * * * cd ~/Desktop/domainhunter && python scripts/godaddy_monitor.py
Test:  python scripts/godaddy_monitor.py --dry-run
Check: python scripts/godaddy_monitor.py --domain cytheris.com

NASA Power of 10: functions <60 lines, min 2 assertions,
fixed loop bounds, no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# -- Resolve project root --
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import structlog

# ── Constants ─────────────────────────────────────────────────────────
INVENTORY_BASE_URL: Final[str] = "https://inventory.auctions.godaddy.com/"
MAX_DOWNLOAD_SIZE: Final[int] = 100 * 1024 * 1024  # 100MB safety limit
REQUEST_TIMEOUT: Final[int] = 60
DATA_DIR: Final[Path] = _PROJECT_ROOT / "data"
RESULTS_DIR: Final[Path] = DATA_DIR / "godaddy_inventory"
CONFIG_PATH: Final[Path] = Path(__file__).parent / "monitored_domains.json"

# Retry constants
MAX_RETRIES: Final[int] = 3
RETRY_BASE_DELAY: Final[int] = 30  # seconds, exponential backoff

# Frequency escalation date thresholds
ELEVATED_START: Final[str] = "2026-06-25"
CRITICAL_START: Final[str] = "2026-06-28"

INVENTORY_FILES: Final[dict[str, str]] = {
    "biddable": "all_biddable_auctions.json.zip",
    "closeout": "closeout_listings.json.zip",
    "expiring": "all_expiring_auctions.json.zip",
    "ending_today": "auctions_ending_today.json.zip",
    "ending_tomorrow": "auctions_ending_tomorrow.json.zip",
    "recent": "recent_listings.json.zip",
}

# Target domains to watch (loaded from config or defaults)
DEFAULT_TARGETS: Final[tuple[str, ...]] = (
    "cytheris.com",
    "ghostautonomy.com",
    "bside.com",
    "guerrameats.com",
    "infarm.com",
    "canoo.com",
    "northvolt.com",
)

# ── Opportunistic scanning: ~500 common English dictionary words ──────
DICTIONARY_WORDS: Final[frozenset[str]] = frozenset((
    "able", "about", "above", "accept", "acid", "across", "act", "add",
    "admit", "adult", "after", "again", "age", "agent", "agree", "ahead",
    "aim", "air", "alarm", "album", "alert", "alive", "allow", "alone",
    "alpha", "alter", "among", "amount", "angel", "anger", "angle", "animal",
    "annual", "answer", "apart", "apple", "apply", "arch", "area", "arena",
    "argue", "arise", "army", "array", "arrow", "art", "asset", "atom",
    "audit", "auto", "avoid", "award", "aware", "axis", "baby", "back",
    "badge", "bag", "balance", "ball", "band", "bank", "bar", "base",
    "basic", "basket", "batch", "bath", "battle", "beach", "beam", "bear",
    "beast", "beat", "beauty", "bed", "beef", "begin", "being", "belt",
    "bench", "best", "beta", "bike", "bind", "bird", "birth", "bit",
    "black", "blade", "blame", "blank", "blast", "blaze", "blend", "blind",
    "block", "blood", "bloom", "blow", "blue", "board", "boat", "body",
    "bolt", "bomb", "bond", "bone", "bonus", "book", "boost", "boot",
    "border", "boss", "bottom", "bounce", "bowl", "box", "brain", "brand",
    "brave", "bread", "break", "brick", "bridge", "brief", "bright",
    "bring", "broad", "bronze", "brush", "bubble", "bucket", "buddy",
    "budget", "build", "bulk", "bullet", "bunch", "bundle", "burn", "burst",
    "bus", "butter", "buyer", "cabin", "cable", "cage", "cake", "call",
    "calm", "camera", "camp", "cancel", "candy", "canvas", "cap", "carbon",
    "card", "cargo", "carpet", "carry", "cart", "case", "cash", "cast",
    "castle", "cat", "catch", "cause", "cave", "cell", "center", "chain",
    "chair", "chalk", "chance", "change", "charge", "charm", "chart",
    "chase", "cheap", "check", "chest", "chief", "child", "chip", "choice",
    "chunk", "circle", "citizen", "city", "civil", "claim", "class",
    "clean", "clear", "clever", "click", "client", "cliff", "climb",
    "clip", "clock", "clone", "close", "cloth", "cloud", "club", "clue",
    "coach", "coast", "code", "coffee", "coin", "cold", "collar", "color",
    "column", "combat", "come", "comfort", "common", "company", "concert",
    "confirm", "connect", "console", "control", "convert", "cook", "cool",
    "copy", "coral", "core", "corn", "corner", "cost", "cotton", "couch",
    "count", "country", "couple", "course", "cover", "crack", "craft",
    "crash", "crazy", "cream", "credit", "crew", "cross", "crowd", "crush",
    "crystal", "cube", "cup", "curve", "custom", "cycle", "dad", "damage",
    "dance", "danger", "dare", "dark", "dash", "data", "dawn", "day",
    "deal", "debate", "decade", "deck", "deep", "deer", "degree", "delay",
    "demand", "demo", "denial", "depth", "deputy", "desert", "design",
    "desk", "detail", "device", "dial", "diet", "digital", "dinner",
    "direct", "dirt", "dish", "display", "divide", "dock", "doctor", "dog",
    "domain", "door", "dose", "double", "draft", "dragon", "drama", "draw",
    "dream", "dress", "drift", "drill", "drink", "drive", "drop", "drum",
    "dry", "duck", "dune", "dust", "duty", "eagle", "earth", "east", "easy",
    "echo", "edge", "edit", "effort", "eight", "elder", "elite", "email",
    "emerge", "emotion", "empire", "empty", "end", "enemy", "energy",
    "engine", "entry", "equal", "era", "error", "escape", "essay", "estate",
    "event", "exact", "exam", "excess", "exile", "expand", "expert",
    "export", "extra", "eye", "fabric", "face", "fact", "fade", "fail",
    "faith", "fall", "fame", "family", "fan", "fancy", "farm", "fast",
    "fat", "fatal", "fault", "favor", "fear", "feast", "feed", "feel",
    "fence", "fever", "fiber", "field", "figure", "file", "film", "filter",
    "final", "find", "fine", "finger", "fire", "firm", "first", "fish",
    "fit", "fix", "flag", "flame", "flash", "flat", "fleet", "flight",
    "flip", "float", "flock", "floor", "flow", "flower", "fluid", "flush",
    "fly", "foam", "focus", "fold", "follow", "food", "foot", "force",
    "forest", "forget", "fork", "form", "fort", "forum", "fossil", "found",
    "fox", "frame", "free", "freeze", "fresh", "friend", "front", "frost",
    "fruit", "fuel", "fun", "fund", "fury", "future", "gain", "galaxy",
    "game", "gap", "garden", "gas", "gate", "gauge", "gear", "gem",
    "gentle", "ghost", "giant", "gift", "girl", "give", "glad",
    "glass", "globe", "gloom", "glory", "glove", "glow", "glue", "goat",
    "gold", "good", "grace", "grain", "grant", "grape", "grass",
    "great", "green", "grid", "grief", "grit", "group", "grow",
    "guard", "guess", "guide", "guilt", "guitar", "gun", "habit", "hair",
    "half", "hammer", "hand", "happy", "harbor", "hard", "harvest", "hat",
    "hawk", "head", "health", "heart", "heat", "heavy", "hedge", "hello",
    "help", "hero", "hidden", "high", "hill", "hint", "hold", "hole",
    "home", "honey", "hood", "hope", "horn", "horse", "host",
    "hotel", "hour", "house", "hub", "huge", "human", "humor", "hunt",
    "ice", "icon", "idea", "idle", "image", "impact", "import",
    "income", "index", "indoor", "info", "inner", "input",
    "insect", "inside", "intact", "into", "invest", "iron",
    "island", "issue", "item", "ivory", "jacket", "jazz", "jewel", "job",
    "join", "joke", "joy", "judge", "juice", "jump", "jungle", "just",
    "keen", "keep", "kernel", "key", "kick", "kid", "kind", "king", "kit",
    "knee", "knife", "knock", "know", "label", "labor", "lake", "lamp",
    "land", "large", "laser", "latin", "laugh", "lawn", "layer", "lazy",
    "lead", "leaf", "learn", "leave", "legal", "lemon", "length", "lens",
    "level", "lift", "light", "limit", "line", "link", "lion", "list",
    "live", "load", "loan", "local", "lock", "logic", "long", "loop",
    "loud", "love", "lucky", "lunch", "luxury", "magic", "mail", "major",
    "maker", "mall", "mango", "manor", "maple", "march", "mark", "market",
    "mask", "master", "match", "matter", "media", "melody", "melon",
    "member", "memory", "menu", "mercy", "merge", "merit", "mesh", "metal",
    "method", "micro", "milk", "mind", "mine", "minor", "mint", "mirror",
    "model", "money", "month", "moon", "moral", "motor", "mouse", "mouth",
    "movie", "much", "music", "myth", "name", "nature", "near", "nerve",
    "nest", "net", "never", "news", "next", "night", "noble", "node",
    "noise", "north", "note", "novel", "nurse", "ocean", "offer", "olive",
    "once", "open", "opera", "orbit", "order", "organ", "other", "outer",
    "over", "owner", "oxygen", "pack", "page", "pair", "palace", "palm",
    "panel", "paper", "park", "party", "patch", "path", "pause", "peace",
    "peak", "pen", "people", "pepper", "phone", "photo", "piano", "piece",
    "pilot", "pine", "pink", "pipe", "pitch", "pizza", "place", "plan",
    "planet", "plant", "plate", "play", "plaza", "poem", "point", "polar",
    "pond", "pool", "poor", "port", "post", "power", "price", "pride",
    "print", "prize", "proof", "proud", "pulse", "pump", "punch", "pupil",
    "push", "puzzle", "queen", "quest", "quick", "quiet", "quote", "race",
    "radio", "rail", "rain", "raise", "range", "rank", "rapid", "rare",
    "rate", "razor", "reach", "ready", "real", "rebel", "recipe", "record",
    "reform", "region", "relief", "rent", "repair", "report", "rescue",
    "resist", "result", "return", "reveal", "review", "reward", "rich",
    "ride", "rifle", "right", "ring", "riot", "ripple", "risk", "river",
    "road", "robot", "rock", "rocket", "role", "roof", "room", "rope",
    "rose", "rough", "round", "route", "royal", "rule", "rural", "rush",
    "sad", "safe", "sail", "salad", "salt", "same", "sand", "sauce",
    "save", "scale", "scene", "school", "score", "scout", "screen",
    "script", "search", "season", "secret", "seed", "sense", "series",
    "serve", "seven", "shadow", "shaft", "shame", "shape", "share",
    "sharp", "shell", "shift", "shine", "ship", "shock", "shoot", "shop",
    "short", "shout", "show", "shut", "sick", "side", "sight", "sign",
    "silk", "silly", "silver", "simple", "since", "size", "skill", "skin",
    "skull", "slap", "sleep", "slice", "slide", "slim", "slow", "small",
    "smart", "smile", "smoke", "smooth", "snake", "snow", "social", "sock",
    "soft", "solar", "solid", "solve", "song", "soon", "sort", "soul",
    "sound", "south", "space", "spare", "spark", "speak", "speed", "spend",
    "sphere", "spider", "spike", "spirit", "split", "sport", "spray",
    "spread", "spring", "square", "stable", "staff", "stage", "stamp",
    "stand", "start", "state", "stay", "steak", "steel", "stem", "step",
    "stick", "still", "stock", "stone", "stop", "store", "storm", "story",
    "stove", "street", "strike", "string", "strong", "stuff", "style",
    "sugar", "summer", "sun", "super", "supply", "surge", "sweet", "swift",
    "swim", "sword", "symbol", "system", "table", "tail", "talent", "talk",
    "tank", "tape", "target", "task", "taste", "team", "tell", "ten",
    "tent", "term", "test", "text", "theme", "then", "thing", "think",
    "three", "throw", "thumb", "tide", "tiger", "time", "tiny", "tip",
    "title", "toast", "today", "token", "tool", "top", "topic", "torch",
    "total", "touch", "tour", "tower", "town", "toy", "trace", "track",
    "trade", "train", "trap", "travel", "treat", "tree", "trend", "trial",
    "tribe", "trick", "trim", "trip", "truck", "true", "trust", "truth",
    "tube", "tuna", "turn", "tutor", "twin", "twist", "type", "ultra",
    "uncle", "under", "unfair", "unhappy", "unique", "unit", "until",
    "upper", "urban", "usage", "used", "useful", "usual", "vacuum",
    "valid", "valley", "value", "valve", "vapor", "vast", "vault", "verb",
    "verify", "verse", "very", "video", "view", "village", "violin",
    "virus", "visa", "visit", "vital", "vivid", "voice", "volume", "vote",
    "wage", "wagon", "wait", "walk", "wall", "wander", "want", "warm",
    "warn", "wash", "waste", "watch", "water", "wave", "wealth", "weapon",
    "wear", "web", "wedding", "weird", "west", "wheat", "wheel", "where",
    "while", "whisper", "wide", "wife", "wild", "will", "win", "wind",
    "window", "wine", "wing", "winner", "winter", "wire", "wisdom", "wise",
    "wish", "witness", "wolf", "woman", "wonder", "wood", "wool", "word",
    "work", "world", "worry", "worth", "wrap", "write", "wrong", "yard",
    "year", "yellow", "young", "youth", "zebra", "zero", "zone",
))

logger = structlog.get_logger()


# ── Data Models ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class AuctionListing:
    """A domain found in GoDaddy inventory."""

    domain: str
    source: str  # biddable, closeout, expiring, ending_today, recent
    price: float = 0.0
    bid_count: int = 0
    end_time: str = ""
    traffic: int = 0
    domain_age: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert self.domain, "domain must not be empty"
        assert self.source in INVENTORY_FILES, f"unknown source: {self.source}"


@dataclass(frozen=True)
class OpportunisticFind:
    """A domain found via opportunistic scanning (not on watchlist)."""

    domain: str
    price: float
    source: str
    reason: str  # SHORT_COM or DICTIONARY_COM

    def __post_init__(self) -> None:
        assert self.domain, "domain must not be empty"
        assert self.reason in ("SHORT_COM", "DICTIONARY_COM")


@dataclass(frozen=True)
class MonitorResult:
    """Results from a single monitoring run."""

    timestamp: str
    targets_checked: int
    matches_found: int
    listings: list[dict[str, Any]]
    errors: list[str]
    opportunistic_finds: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert self.targets_checked >= 0
        assert self.matches_found >= 0


# ── Core Functions ────────────────────────────────────────────────────
def load_targets(config_path: Path) -> set[str]:
    """Load target domains from monitored_domains.json + defaults."""
    targets: set[str] = set(d.lower() for d in DEFAULT_TARGETS)

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            assert "active_targets" in config
            for tier_domains in config["active_targets"].values():
                for entry in tier_domains[:200]:  # bounded
                    if isinstance(entry, dict) and "domain" in entry:
                        targets.add(entry["domain"].lower())
                    elif isinstance(entry, str):
                        targets.add(entry.lower())
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("config_load_error", error=str(e))

    logger.info("targets_loaded", count=len(targets))
    return targets


def _parse_inventory_json(raw: Any, filename: str) -> list[dict[str, Any]]:
    """Parse raw JSON with format detection. Graceful degradation on unknown formats."""
    assert filename, "filename must not be empty"
    # Expected: {"meta": {...}, "data": [...]} or bare list
    if isinstance(raw, dict) and "data" in raw:
        data = raw["data"]
    elif isinstance(raw, list):
        data = raw
    else:
        # FORMAT CHANGED — graceful degradation instead of crashing
        logger.warning(
            "FORMAT_CHANGE_ALERT",
            file=filename,
            received_type=type(raw).__name__,
            keys=list(raw.keys())[:10] if isinstance(raw, dict) else None,
            msg="JSON structure changed! Not dict-with-data or list. Skipping file.",
        )
        return []

    assert isinstance(data, list), "expected data to be a list"
    logger.info("inventory_loaded", file=filename, count=len(data))
    return data[:500_000]  # safety bound


def _download_once(file_key: str) -> list[dict[str, Any]]:
    """Single download attempt for a GoDaddy inventory ZIP file."""
    import urllib.request

    assert file_key in INVENTORY_FILES, f"unknown file_key: {file_key}"
    filename = INVENTORY_FILES[file_key]
    url = INVENTORY_BASE_URL + filename

    logger.info("downloading", file=filename)
    req = urllib.request.Request(url, headers={"User-Agent": "DomainHunter/5.2"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        content = resp.read(MAX_DOWNLOAD_SIZE)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for name in zf.namelist()[:5]:  # bounded
            if name.endswith(".json"):
                with zf.open(name) as jf:
                    raw = json.loads(jf.read())
                    return _parse_inventory_json(raw, filename)
    logger.warning("no_json_in_zip", file=filename)
    return []


def download_inventory(file_key: str, dry_run: bool = False) -> list[dict[str, Any]]:
    """Download inventory with retry (3x, 30s exponential backoff)."""
    assert file_key in INVENTORY_FILES, f"unknown file_key: {file_key}"

    if dry_run:
        logger.info("dry_run_skip", file=INVENTORY_FILES[file_key])
        return []

    last_error: str = ""
    for attempt in range(MAX_RETRIES):  # bounded: 0, 1, 2
        try:
            return _download_once(file_key)
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)  # 30s, 60s
                logger.warning(
                    "download_retry",
                    file=INVENTORY_FILES[file_key],
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                    delay_seconds=delay,
                    error=last_error,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "download_failed_all_retries",
                    file=INVENTORY_FILES[file_key],
                    attempts=MAX_RETRIES,
                    error=last_error,
                )
    return []


def _parse_price(raw_val: Any) -> float:
    """Parse price from GoDaddy data — handles '$5', '$12.99', and numeric values."""
    if isinstance(raw_val, (int, float)):
        return float(raw_val)
    s = str(raw_val).strip().lstrip("$").replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def search_inventory(
    data: list[dict[str, Any]], targets: set[str], source: str
) -> list[AuctionListing]:
    """Search inventory data for target domains."""
    assert source in INVENTORY_FILES
    matches: list[AuctionListing] = []

    # GoDaddy JSON uses "domainName" (confirmed from actual inventory files)
    domain_keys = ("domainName", "DomainName", "domain", "Domain", "name")

    for item in data[:500_000]:  # bounded
        domain_val = ""
        for key in domain_keys:
            if key in item:
                domain_val = str(item[key]).lower().strip()
                break

        if domain_val in targets:
            price = _parse_price(item.get("Price", item.get("price", item.get("MinBid", 0))))
            bid_count = int(item.get("Bids", item.get("bids", item.get("BidCount", 0))))
            end_time = str(item.get("EndTime", item.get("endTime", item.get("AuctionEndTime", ""))))
            traffic = int(item.get("Traffic", item.get("traffic", 0)))
            age = int(item.get("DomainAge", item.get("domainAge", 0)))

            listing = AuctionListing(
                domain=domain_val,
                source=source,
                price=price,
                bid_count=bid_count,
                end_time=end_time,
                traffic=traffic,
                domain_age=age,
                raw=item,
            )
            matches.append(listing)
            logger.info(
                "MATCH_FOUND",
                domain=domain_val,
                source=source,
                price=price,
                bids=bid_count,
                end_time=end_time,
            )

    return matches


def scan_opportunistic(
    data: list[dict[str, Any]], source: str
) -> list[OpportunisticFind]:
    """Scan listings for short .com domains and dictionary .com domains."""
    assert source in INVENTORY_FILES
    finds: list[OpportunisticFind] = []
    domain_keys = ("domainName", "DomainName", "domain", "Domain", "name")

    for item in data[:500_000]:  # bounded
        domain_val = ""
        for key in domain_keys:
            if key in item:
                domain_val = str(item[key]).lower().strip()
                break

        if not domain_val or not domain_val.endswith(".com"):
            continue

        name_part = domain_val[:-4]  # strip ".com"
        if not name_part:
            continue

        price = _parse_price(item.get("Price", item.get("price", item.get("MinBid", 0))))

        # SHORT_COM: 5 or fewer alphanumeric characters
        if len(name_part) <= 5 and name_part.isalnum():
            finds.append(OpportunisticFind(
                domain=domain_val, price=price, source=source, reason="SHORT_COM",
            ))
            logger.info(
                "OPPORTUNISTIC_FIND", domain=domain_val,
                price=price, source=source, reason="SHORT_COM",
            )

        # DICTIONARY_COM: single common English word
        if name_part.isalpha() and name_part in DICTIONARY_WORDS:
            finds.append(OpportunisticFind(
                domain=domain_val, price=price, source=source, reason="DICTIONARY_COM",
            ))
            logger.info(
                "OPPORTUNISTIC_FIND", domain=domain_val,
                price=price, source=source, reason="DICTIONARY_COM",
            )

    return finds


def determine_frequency() -> str:
    """Auto-detect frequency based on current date vs escalation thresholds."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert isinstance(today, str) and len(today) == 10

    if today >= CRITICAL_START:
        logger.info(
            "frequency_escalated", level="critical",
            schedule="run at 08:00, 12:00, 18:00",
        )
        return "critical"
    elif today >= ELEVATED_START:
        logger.info(
            "frequency_escalated", level="elevated",
            schedule="run at 08:00 + 14:00",
        )
        return "elevated"
    else:
        logger.info("frequency_normal", schedule="once daily")
        return "normal"


def run_monitor(
    targets: set[str],
    sources: tuple[str, ...] | None = None,
    dry_run: bool = False,
) -> MonitorResult:
    """Run the full monitoring sweep across all inventory files."""
    assert len(targets) > 0, "no targets to monitor"

    sources_to_check = sources or tuple(INVENTORY_FILES.keys())
    all_matches: list[AuctionListing] = []
    all_opportunistic: list[OpportunisticFind] = []
    errors: list[str] = []

    for source_key in sources_to_check:
        data = download_inventory(source_key, dry_run=dry_run)
        if data:
            matches = search_inventory(data, targets, source_key)
            all_matches.extend(matches)
            # Opportunistic scanning on closeout data
            if source_key == "closeout":
                opp_finds = scan_opportunistic(data, source_key)
                all_opportunistic.extend(opp_finds)
        elif not dry_run:
            errors.append(f"No data from {source_key}")

    # Serialize matches
    listings_data = [
        {
            "domain": m.domain,
            "source": m.source,
            "price": m.price,
            "bid_count": m.bid_count,
            "end_time": m.end_time,
            "traffic": m.traffic,
            "domain_age": m.domain_age,
        }
        for m in all_matches
    ]

    opp_data = [
        {"domain": f.domain, "price": f.price, "source": f.source, "reason": f.reason}
        for f in all_opportunistic
    ]

    result = MonitorResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        targets_checked=len(targets),
        matches_found=len(all_matches),
        listings=listings_data,
        errors=errors,
        opportunistic_finds=opp_data,
    )
    return result


def save_results(result: MonitorResult) -> Path:
    """Save monitoring results to data/godaddy_inventory/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = RESULTS_DIR / f"gd_monitor_{date_str}.json"

    with open(out_path, "w") as f:
        json.dump(
            {
                "timestamp": result.timestamp,
                "targets_checked": result.targets_checked,
                "matches_found": result.matches_found,
                "listings": result.listings,
                "errors": result.errors,
                "opportunistic_finds": result.opportunistic_finds,
            },
            f,
            indent=2,
        )
    logger.info("results_saved", path=str(out_path))
    return out_path


def format_report(result: MonitorResult) -> str:
    """Format a human-readable report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  GODADDY INVENTORY MONITOR — RESULTS")
    lines.append(f"  {result.timestamp}")
    lines.append("=" * 60)
    lines.append(f"\n  Targets checked: {result.targets_checked}")
    lines.append(f"  Matches found:   {result.matches_found}")

    if result.matches_found > 0:
        lines.append("\n  *** DOMAINS FOUND IN GODADDY INVENTORY ***\n")
        lines.append(f"  {'Domain':<25} {'Source':<15} {'Price':>8} {'Bids':>5} {'Ends':<20}")
        lines.append("  " + "-" * 75)
        for listing in result.listings:
            lines.append(
                f"  {listing['domain']:<25} "
                f"{listing['source']:<15} "
                f"${listing['price']:>7.2f} "
                f"{listing['bid_count']:>5} "
                f"{listing['end_time'][:19]:<20}"
            )
        lines.append("\n  ACTION: Buy at closeout or place bid at auctions.godaddy.com")
        lines.append("  MEMBERSHIP: $4.99/year required to bid/buy")
    else:
        lines.append("\n  No target domains found in current inventory.")
        lines.append("  (Domains appear ~26 days after expiry)")

    if result.opportunistic_finds:
        lines.append(f"\n  OPPORTUNISTIC FINDS ({len(result.opportunistic_finds)}):")
        for opp in result.opportunistic_finds[:20]:  # bounded display
            lines.append(
                f"    [{opp['reason']}] {opp['domain']} — ${opp['price']:.2f} ({opp['source']})"
            )

    if result.errors:
        lines.append(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors[:10]:
            lines.append(f"    - {err}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def send_alert(result: MonitorResult) -> None:
    """Send alert if matches found via travel-proof notification system."""
    if result.matches_found == 0:
        return

    from scripts.notify import send_alert as dispatch_alert, format_domain_alert

    # Send individual alert per match (max 10 to avoid spam)
    for listing in result.listings[:10]:
        domain = listing["domain"]
        source = listing["source"]
        price = listing.get("price", 0.0)
        action_url = (
            f"https://auctions.godaddy.com/trpItemListing.aspx"
            f"?miession=searchitem&searchterm={domain}"
        )

        subject, body = format_domain_alert(
            domain=domain,
            event=f"Found in GoDaddy {source}",
            price=price,
            action_url=action_url,
            extra=f"Bids: {listing.get('bid_count', 0)}, Ends: {listing.get('end_time', 'N/A')}",
        )
        priority = "critical"
        dispatch_alert(subject, body, priority=priority)

    # Legacy Slack webhook (kept for backward compatibility)
    webhook_url = os.environ.get("DOMAIN_HUNTER_SLACK_WEBHOOK")
    if not webhook_url:
        return

    import urllib.request

    payload = json.dumps({
        "text": f"GoDaddy Monitor: {result.matches_found} target(s) found!\n"
        + "\n".join(
            f"- {l['domain']} -- {l['source']} -- ${l['price']}"
            for l in result.listings[:5]
        )
    }).encode()

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("slack_alert_failed", error=str(e))


# ── CLI ───────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor GoDaddy inventory files for target domains"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip downloads, validate config only"
    )
    parser.add_argument(
        "--domain", type=str, help="Check a single domain (overrides config)"
    )
    parser.add_argument(
        "--source",
        choices=list(INVENTORY_FILES.keys()),
        help="Check only one inventory file",
    )
    parser.add_argument(
        "--closeout-only",
        action="store_true",
        help="Only check closeout listings (fastest)",
    )
    parser.add_argument(
        "--frequency",
        choices=["normal", "elevated", "critical", "auto"],
        default="auto",
        help="Run frequency: normal (daily), elevated (2x), critical (3x), auto (date-based)",
    )
    parser.add_argument(
        "--save", action="store_true", default=True, help="Save results to JSON"
    )
    parser.add_argument(
        "--no-alert", action="store_true", help="Suppress alerts"
    )
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()

    # Determine and log frequency
    if args.frequency == "auto":
        freq = determine_frequency()
    else:
        freq = args.frequency
        if freq == "elevated":
            logger.info("frequency_override", level="elevated", schedule="run at 08:00 + 14:00")
        elif freq == "critical":
            logger.info("frequency_override", level="critical", schedule="run at 08:00, 12:00, 18:00")

    # Load targets
    if args.domain:
        targets = {args.domain.lower()}
    else:
        targets = load_targets(CONFIG_PATH)

    # Determine sources
    sources: tuple[str, ...] | None = None
    if args.source:
        sources = (args.source,)
    elif args.closeout_only:
        sources = ("closeout",)

    # Run monitor
    result = run_monitor(targets, sources=sources, dry_run=args.dry_run)

    # Output
    report = format_report(result)
    print(report)

    # Save
    if args.save and not args.dry_run:
        save_results(result)

    # Alert
    if not args.no_alert:
        send_alert(result)

    return 0 if not result.errors or result.matches_found > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

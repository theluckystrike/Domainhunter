"""Immutable constants for the Domain Hunter pipeline.

All collections use tuples (immutable) instead of lists.
All dicts are wrapped in MappingProxyType (frozen).
NASA Rule 2: No global mutable state.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final

# ---------------------------------------------------------------------------
# TLD filters
# ---------------------------------------------------------------------------
ALLOWED_TLDS: Final[tuple[str, ...]] = (
    ".com", ".io", ".dev", ".ai", ".app", ".tools", ".tech", ".cloud",
    ".sh", ".run", ".build", ".code", ".software", ".engineering",
)

SPAM_TLDS: Final[tuple[str, ...]] = (
    ".xyz", ".top", ".buzz", ".click", ".link", ".info", ".biz",
    ".win", ".loan", ".racing", ".review", ".stream", ".gdn",
    ".men", ".party", ".science", ".work", ".date", ".download",
)

# ---------------------------------------------------------------------------
# Niche keywords — 4 tiers with weights (higher = more relevant)
# ---------------------------------------------------------------------------
NICHE_KEYWORDS_TIER1: Final[tuple[str, ...]] = (
    "ai", "llm", "gpt", "claude", "openai", "anthropic", "copilot",
    "chatbot", "langchain", "vector", "embedding", "transformer",
    "prompt", "rag", "agent", "multimodal",
)
NICHE_KEYWORDS_TIER2: Final[tuple[str, ...]] = (
    "devtools", "developer", "api", "sdk", "cli", "framework",
    "saas", "platform", "automation", "workflow", "pipeline",
    "observability", "monitoring", "analytics", "dashboard",
)
NICHE_KEYWORDS_TIER3: Final[tuple[str, ...]] = (
    "code", "coding", "programming", "software", "deploy",
    "kubernetes", "docker", "cloud", "serverless", "microservice",
    "database", "backend", "frontend", "fullstack", "devops",
)
NICHE_KEYWORDS_TIER4: Final[tuple[str, ...]] = (
    "startup", "tech", "digital", "data", "machine", "learning",
    "neural", "deep", "model", "inference", "training", "fine-tune",
)

NICHE_KEYWORD_WEIGHTS: Final[MappingProxyType[str, float]] = MappingProxyType({
    **{kw: 1.0 for kw in NICHE_KEYWORDS_TIER1},
    **{kw: 0.7 for kw in NICHE_KEYWORDS_TIER2},
    **{kw: 0.4 for kw in NICHE_KEYWORDS_TIER3},
    **{kw: 0.2 for kw in NICHE_KEYWORDS_TIER4},
})

# ---------------------------------------------------------------------------
# SPECTRE scoring weights (social signal analysis)
# ---------------------------------------------------------------------------
SPECTRE_WEIGHTS: Final[MappingProxyType[str, float]] = MappingProxyType({
    "github_stars": 0.20,
    "github_forks": 0.10,
    "github_mentions": 0.15,
    "reddit_mentions": 0.15,
    "reddit_sentiment": 0.10,
    "hn_mentions": 0.10,
    "brand_searchability": 0.10,
    "social_recency": 0.10,
})

# ---------------------------------------------------------------------------
# ORACLE scoring weights (final verdict)
# ---------------------------------------------------------------------------
ORACLE_WEIGHTS: Final[MappingProxyType[str, float]] = MappingProxyType({
    "domain_authority": 0.15,
    "backlink_quality": 0.15,
    "niche_relevance": 0.20,
    "archive_integrity": 0.15,
    "social_signal": 0.10,
    "brand_value": 0.10,
    "spam_safety": 0.10,
    "registration_feasibility": 0.05,
})

# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------
VERDICT_BUY_NOW_THRESHOLD: Final[float] = 80.0
VERDICT_WATCH_THRESHOLD: Final[float] = 60.0
VERDICT_SKIP_THRESHOLD: Final[float] = 0.0  # anything below WATCH

# ---------------------------------------------------------------------------
# Target subreddits for SPECTRE social analysis
# ---------------------------------------------------------------------------
TARGET_SUBREDDITS: Final[tuple[str, ...]] = (
    "artificial", "MachineLearning", "LocalLLaMA", "ChatGPT",
    "OpenAI", "ClaudeAI", "LangChain", "programming",
    "webdev", "devops", "SaaS", "startups", "sideproject",
    "selfhosted", "datascience", "learnmachinelearning",
)

# ---------------------------------------------------------------------------
# Domain quality filters (SENTINEL thresholds)
# ---------------------------------------------------------------------------
MIN_DA_THRESHOLD: Final[int] = 25
MAX_SPAM_SCORE: Final[float] = 20.0
MIN_REFERRING_DOMAINS: Final[int] = 100
MIN_BRANDED_ANCHOR_PCT: Final[float] = 40.0

# SCOUT domain quality filters
MAX_DOMAIN_LENGTH: Final[int] = 63
MAX_NUMBERS_IN_DOMAIN: Final[int] = 2
MAX_HYPHENS_IN_DOMAIN: Final[int] = 1

# Unified niche keyword tuple (all tiers combined for simple membership checks)
NICHE_KEYWORDS: Final[tuple[str, ...]] = (
    NICHE_KEYWORDS_TIER1 + NICHE_KEYWORDS_TIER2
    + NICHE_KEYWORDS_TIER3 + NICHE_KEYWORDS_TIER4
)

# ARCHIVIST thresholds
MIN_ARCHIVE_YEARS: Final[float] = 3.0
MIN_ARCHIVE_SNAPSHOTS: Final[int] = 50
MAX_CONTENT_DRIFT_SCORE: Final[float] = 0.6
MAX_WAYBACK_SNAPSHOTS: Final[int] = 500
WAYBACK_RATE_LIMIT: Final[float] = 1.0

# ---------------------------------------------------------------------------
# Rate limits (requests per second)
# ---------------------------------------------------------------------------
RATE_LIMIT_WHOISFREAKS: Final[float] = 2.0
RATE_LIMIT_DATAFORSEO: Final[float] = 5.0
RATE_LIMIT_WAYBACK: Final[float] = 1.0
RATE_LIMIT_GITHUB: Final[float] = 10.0
RATE_LIMIT_REDDIT: Final[float] = 1.0
RATE_LIMIT_GOOGLE_CSE: Final[float] = 5.0

# ---------------------------------------------------------------------------
# Pipeline hard limits (NASA Rule 3: all loops bounded)
# ---------------------------------------------------------------------------
MAX_LOOP_ITERATIONS: Final[int] = 10_000
MAX_API_RETRIES: Final[int] = 3
MAX_CONCURRENT_REQUESTS: Final[int] = 20
MAX_DB_BATCH_SIZE: Final[int] = 500
MAX_PIPELINE_RUNTIME_SECONDS: Final[int] = 3600
MAX_CANDIDATES_PER_SOURCE: Final[int] = 200

# Pipeline stage hard caps
MAX_SCOUT_CANDIDATES: Final[int] = 500
MAX_SENTINEL_SURVIVORS: Final[int] = 60
MAX_ARCHIVIST_VERIFIED: Final[int] = 15
MAX_SPECTRE_SCORED: Final[int] = 5

# ---------------------------------------------------------------------------
# HTTP defaults
# ---------------------------------------------------------------------------
HTTP_TIMEOUT_SECONDS: Final[int] = 30
HTTP_USER_AGENT: Final[str] = "DomainHunter/1.0 (+https://github.com/domain-hunter)"

# ---------------------------------------------------------------------------
# Sprint 3: Tool-potential niches
# ---------------------------------------------------------------------------
TOOL_NICHES: Final[dict[str, tuple[str, ...]]] = {
    "finance": ("mortgage", "loan", "invest", "budget", "tax", "savings", "compound", "interest"),
    "health": ("calorie", "macro", "bmi", "workout", "exercise", "nutrition", "diet", "fitness"),
    "cooking": ("recipe", "ingredient", "cooking", "meal", "kitchen", "baking", "food"),
    "real_estate": ("property", "rent", "housing", "mortgage", "home", "realtor"),
    "education": ("learn", "course", "study", "tutor", "quiz", "exam", "flashcard"),
    "photography": ("photo", "image", "camera", "editing", "color", "resize"),
    "marketing": ("seo", "analytics", "conversion", "email", "campaign", "funnel"),
    "productivity": ("todo", "task", "project", "calendar", "schedule", "timer"),
    "travel": ("flight", "hotel", "itinerary", "packing", "visa", "currency"),
    "design": ("color", "font", "palette", "wireframe", "mockup", "ui", "ux"),
    "crypto": ("bitcoin", "ethereum", "defi", "wallet", "gas", "staking"),
}

# ---------------------------------------------------------------------------
# Sprint 3: Revised ORACLE weights (backlinks-first)
# ---------------------------------------------------------------------------
SPRINT3_WEIGHTS: Final[dict[str, float]] = {
    "backlink_quality": 0.35,
    "referring_domains": 0.20,
    "archive_history": 0.15,
    "tool_opportunity": 0.15,
    "domain_rating": 0.10,
    "price": 0.05,
}

# ---------------------------------------------------------------------------
# Tier 1 authority domains (DR 70+)
# ---------------------------------------------------------------------------
TIER1_AUTHORITY_DOMAINS: Final[tuple[str, ...]] = (
    "nytimes.com", "bbc.com", "wikipedia.org", "forbes.com", "techcrunch.com",
    "theguardian.com", "nature.com", "github.com", "reddit.com", "medium.com",
    "wsj.com", "bloomberg.com", "reuters.com", "cnn.com", "wired.com",
    "arstechnica.com", "theverge.com", "mashable.com", "entrepreneur.com",
    "inc.com", "fastcompany.com", "businessinsider.com",
)

# ---------------------------------------------------------------------------
# DeepSeek rate limits
# ---------------------------------------------------------------------------
RATE_LIMIT_DEEPSEEK: Final[float] = 5.0
DEEPSEEK_MAX_BATCH_SIZE: Final[int] = 50

# ---------------------------------------------------------------------------
# Sprint 19 — Drop Monitor Constants
# ---------------------------------------------------------------------------
RDAP_SERVERS: Final[MappingProxyType] = MappingProxyType({
    "com": "https://rdap.verisign.com/com/v1/domain/",
    "net": "https://rdap.verisign.com/net/v1/domain/",
    "org": "https://rdap.publicinterestregistry.org/rdap/domain/",
    "io": "https://rdap.nic.io/domain/",
    "ai": "https://rdap.nic.ai/domain/",
    "co": "https://rdap.nic.co/domain/",
    "dev": "https://rdap.nic.google/domain/",
})

RDAP_RATE_LIMIT_DELAY: Final[float] = 3.0  # seconds between requests per TLD
RDAP_MAX_CONCURRENT: Final[int] = 20
RDAP_TIMEOUT_SECONDS: Final[int] = 15
RDAP_MAX_RETRIES: Final[int] = 3

DYNADOT_API_BASE: Final[str] = "https://api.dynadot.com/api3.json"
DYNADOT_RATE_LIMIT_RPM: Final[int] = 10
DYNADOT_BACKORDER_COST: Final[float] = 10.99
DYNADOT_TIMEOUT_SECONDS: Final[int] = 30

DROP_MONITOR_MAX_DOMAINS: Final[int] = 100
DROP_MONITOR_DB_PATH: Final[str] = "data/domain_monitoring.db"

# EPP status codes indicating domain is dropping
EPP_DROP_SIGNALS: Final[tuple] = (
    "pendingDelete",
    "redemptionPeriod",
)

EPP_WATCH_SIGNALS: Final[tuple] = (
    "clientRenewProhibited",
    "clientHold",
    "autoRenewPeriod",
    "serverHold",
)

# Registrar grace period estimates (days from expiry to drop)
REGISTRAR_GRACE_PERIODS: Final[MappingProxyType] = MappingProxyType({
    "GoDaddy": 80,
    "Wild West Domains": 80,
    "Squarespace": 75,
    "Tucows": 80,
    "Cloudflare": 75,
    "Namecheap": 62,
    "default": 75,
})

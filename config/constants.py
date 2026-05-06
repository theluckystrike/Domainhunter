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

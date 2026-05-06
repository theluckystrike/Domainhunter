"""API client exports for Domain Hunter pipeline.

All 9 clients follow the same pattern:
- Class-based with Settings injected via constructor
- async methods using aiohttp
- Input validation at entry (assert)
- Output validation before return (assert)
- Hard retry limit with exponential backoff (max 3 retries)
- Timeout on every request
- Returns typed data or raises typed exception
- mock parameter for testing with fixture data
"""
from __future__ import annotations

from clients.anthropic_client import AnthropicClient, AnthropicClientError
from clients.catchdoms import CatchDomsClient, CatchDomsError
from clients.dataforseo import DataForSEOClient, DataForSEOError
from clients.github_search import GitHubSearchClient, GitHubSearchError
from clients.google_cse import (
    GoogleCSEClient,
    GoogleCSEError,
    GoogleCSEQuotaExhausted,
)
from clients.moz_apify import MozApifyClient, MozApifyError
from clients.reddit_search import RedditSearchClient, RedditSearchError
from clients.wayback import WaybackClient, WaybackError
from clients.whoisfreaks import WhoisFreaksClient, WhoisFreaksError

__all__: list[str] = [
    # Clients
    "WhoisFreaksClient",
    "CatchDomsClient",
    "DataForSEOClient",
    "GoogleCSEClient",
    "MozApifyClient",
    "WaybackClient",
    "GitHubSearchClient",
    "RedditSearchClient",
    "AnthropicClient",
    # Errors
    "WhoisFreaksError",
    "CatchDomsError",
    "DataForSEOError",
    "GoogleCSEError",
    "GoogleCSEQuotaExhausted",
    "MozApifyError",
    "WaybackError",
    "GitHubSearchError",
    "RedditSearchError",
    "AnthropicClientError",
]

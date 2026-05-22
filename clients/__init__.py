"""API client exports for Domain Hunter pipeline.

All 10 clients follow the same pattern:
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
from clients.deepseek import (
    DeepSeekClient,
    DeepSeekError,
    DeepSeekRateLimitError,
    DeepSeekTimeoutError,
)
from clients.github_search import GitHubSearchClient, GitHubSearchError
from clients.google_cse import (
    GoogleCSEClient,
    GoogleCSEError,
    GoogleCSEQuotaExhausted,
)
from clients.moz_apify import MozApifyClient, MozApifyError
from clients.reddit_search import RedditSearchClient, RedditSearchError
from clients.wayback import WaybackClient, WaybackError
from clients.gname_client import (
    GnameClient,
    GnameError,
    GnameAuthError,
    GnameBackorderError,
)
from clients.namebright_client import (
    NameBrightClient,
    NameBrightError,
    NameBrightAuthError,
    NameBrightRateLimitError,
    NameBrightNotFoundError,
)
from clients.ntfy_client import send_alert as ntfy_send_alert, send_domain_alert as ntfy_send_domain_alert
from clients.openpagerank import OpenPageRankClient, OpenPageRankError
from clients.tranco_client import TrancoClient, TrancoError
from clients.wikipedia_client import WikipediaClient, WikipediaError
from clients.whoisfreaks import WhoisFreaksClient, WhoisFreaksError

__all__: list[str] = [
    # ntfy push notifications
    "ntfy_send_alert",
    "ntfy_send_domain_alert",
    # Clients
    "WhoisFreaksClient",
    "CatchDomsClient",
    "DataForSEOClient",
    "DeepSeekClient",
    "GoogleCSEClient",
    "MozApifyClient",
    "WaybackClient",
    "GitHubSearchClient",
    "RedditSearchClient",
    "AnthropicClient",
    "NameBrightClient",
    "GnameClient",
    # Errors
    "WhoisFreaksError",
    "CatchDomsError",
    "DataForSEOError",
    "DeepSeekError",
    "DeepSeekRateLimitError",
    "DeepSeekTimeoutError",
    "GoogleCSEError",
    "GoogleCSEQuotaExhausted",
    "MozApifyError",
    "WaybackError",
    "GitHubSearchError",
    "RedditSearchError",
    "AnthropicClientError",
    "NameBrightError",
    "NameBrightAuthError",
    "NameBrightRateLimitError",
    "NameBrightNotFoundError",
    "GnameError",
    "GnameAuthError",
    "GnameBackorderError",
    # Authority Gate clients
    "OpenPageRankClient",
    "OpenPageRankError",
    "TrancoClient",
    "TrancoError",
    "WikipediaClient",
    "WikipediaError",
]

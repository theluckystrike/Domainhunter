"""Reddit search client for domain social signal analysis.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.

PRAW is synchronous. All calls are wrapped in asyncio.to_thread().
"""
from __future__ import annotations

import asyncio
from typing import Any

import praw
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TARGET_SUBREDDITS: tuple[str, ...] = (
    "webdev", "programming", "devtools", "MachineLearning",
    "LocalLLaMA", "ChatGPT", "artificial", "learnprogramming",
    "coding", "softwareengineering", "vscode", "neovim",
)
_SEARCH_LIMIT: int = 10
_TIMEOUT_PER_SUBREDDIT: float = 10.0
_MAX_SUBREDDITS: int = 50


class RedditSearchError(Exception):
    """Raised when Reddit search fails."""


class RedditSearchClient:
    """Client for Reddit domain mention search via PRAW."""

    def __init__(
        self, settings: Settings, *, mock: bool = False
    ) -> None:
        assert isinstance(settings, Settings), (
            "settings must be a Settings instance"
        )
        assert isinstance(mock, bool), "mock must be a boolean"
        self._mock: bool = mock
        self._client_id: str = settings.reddit_client_id
        self._client_secret: str = settings.reddit_client_secret
        self._user_agent: str = settings.reddit_user_agent

    def _create_reddit(self) -> praw.Reddit:
        """Create a PRAW Reddit instance (read-only)."""
        reddit: praw.Reddit = praw.Reddit(
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_agent=self._user_agent,
        )
        reddit.read_only = True
        assert reddit.read_only is True, (
            "reddit must be in read-only mode"
        )
        assert reddit is not None, "reddit instance must be created"
        return reddit

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def search_domain_mentions(
        self, domain: str
    ) -> dict[str, int]:
        """Search for domain mentions across target subreddits.

        Args:
            domain: Target domain name to search.

        Returns:
            Dict mapping subreddit name to mention count.
        """
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return {}

        return await self._search_all_subreddits(domain)

    async def _search_all_subreddits(
        self, domain: str
    ) -> dict[str, int]:
        """Search each target subreddit for domain mentions."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4, "domain must be at least 4 chars"

        results: dict[str, int] = {}

        for i, subreddit_name in enumerate(_TARGET_SUBREDDITS):
            if i >= _MAX_SUBREDDITS:
                break
            try:
                count: int = await asyncio.wait_for(
                    self._search_single_subreddit(
                        domain, subreddit_name
                    ),
                    timeout=_TIMEOUT_PER_SUBREDDIT,
                )
                if count > 0:
                    results[subreddit_name] = count
            except asyncio.TimeoutError:
                logger.warning(
                    "reddit_subreddit_timeout",
                    subreddit=subreddit_name, domain=domain,
                )
            except Exception as exc:
                logger.warning(
                    "reddit_subreddit_error",
                    subreddit=subreddit_name, error=str(exc),
                )

        assert isinstance(results, dict), "results must be a dict"
        logger.info(
            "reddit_search_complete",
            domain=domain,
            subreddits_with_mentions=len(results),
        )
        return results

    async def _search_single_subreddit(
        self, domain: str, subreddit_name: str
    ) -> int:
        """Search a single subreddit via PRAW in a thread."""
        assert isinstance(domain, str), "domain must be a string"
        assert isinstance(subreddit_name, str), (
            "subreddit must be a string"
        )

        def _sync_search() -> int:
            assert isinstance(domain, str), "domain must be a string"
            assert isinstance(subreddit_name, str), "subreddit_name must be a string"
            reddit: praw.Reddit = self._create_reddit()
            subreddit: Any = reddit.subreddit(subreddit_name)
            count: int = 0
            for j, _submission in enumerate(
                subreddit.search(domain, limit=_SEARCH_LIMIT)
            ):
                if j >= _SEARCH_LIMIT:
                    break
                count += 1
            return count

        result: int = await asyncio.to_thread(_sync_search)
        assert isinstance(result, int), "search count must be an int"
        assert result >= 0, "count must be non-negative"
        return result

    @staticmethod
    def _total_mentions(results: dict[str, int]) -> int:
        """Sum all mention counts across subreddits.

        Args:
            results: Dict mapping subreddit -> count.

        Returns:
            Total mention count.
        """
        assert isinstance(results, dict), "results must be a dict"
        assert all(isinstance(v, int) for v in results.values()), (
            "all values must be ints"
        )

        total: int = sum(results.values())
        assert isinstance(total, int), "total must be an int"
        assert total >= 0, "total must be non-negative"
        return total

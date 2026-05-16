"""DeepSeek API client — OpenAI-compatible format.
100x cheaper than Claude for mass classification tasks.
$0.27/M input tokens vs $3/M for Claude Sonnet.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_BASE_URL: str = "https://api.deepseek.com/v1/chat/completions"
_MODEL: str = "deepseek-chat"
_TIMEOUT_SECONDS: int = 60
_MAX_BATCH_SIZE: int = 50
_MAX_RETRIES: int = 3
_MAX_TOKENS: int = 4096
_RATE_LIMIT_MAX_DOMAINS: int = 200


class DeepSeekError(Exception):
    """Raised when DeepSeek API returns an error."""


class DeepSeekRateLimitError(DeepSeekError):
    """Raised when DeepSeek API returns 429 rate limit."""


class DeepSeekTimeoutError(DeepSeekError):
    """Raised when DeepSeek API request times out."""


class DeepSeekClient:
    """Client for DeepSeek chat completions API (OpenAI-compatible)."""

    def __init__(self, settings: Settings, *, mock: bool = False) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert isinstance(mock, bool), "mock must be a boolean"
        self._api_key: str = settings.deepseek_api_key
        self._mock: bool = mock
        self._timeout: float = float(_TIMEOUT_SECONDS)

    def _build_headers(self) -> dict[str, str]:
        """Build authorization headers for DeepSeek API."""
        assert isinstance(self._api_key, str), "api_key must be a string"
        assert len(self._api_key) > 0, "api_key must not be empty"
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_classification_prompt(
        self, domains: list[str],
    ) -> str:
        """Build the batch classification prompt for domains.

        Args:
            domains: List of domain names to classify.

        Returns:
            Formatted prompt string for the LLM.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert 1 <= len(domains) <= _MAX_BATCH_SIZE, (
            f"batch size must be 1-{_MAX_BATCH_SIZE}, got {len(domains)}"
        )

        domain_list: str = "\n".join(
            f"{i + 1}. {d}" for i, d in enumerate(domains)
        )

        return (
            "You are a domain classification expert. Analyze each domain name below "
            "and classify it for tool-building potential.\n\n"
            f"Domains:\n{domain_list}\n\n"
            "For EACH domain, respond with a JSON array. Each element must have:\n"
            '- "domain": the domain name\n'
            '- "niche": one of [finance, health, cooking, real_estate, education, '
            'photography, marketing, productivity, travel, design, crypto, tech, other]\n'
            '- "site_type": one of [tool, blog, saas, marketplace, community, directory, other]\n'
            '- "tool_idea": brief description of a tool that could be built on this domain\n'
            '- "quality_signal": one of [strong, moderate, weak]\n'
            '- "score": integer 1-100 rating the domain\'s tool-building potential\n\n'
            "Respond with ONLY a valid JSON array, no markdown fences."
        )

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )
    async def classify_domains_batch(
        self, domains: list[str],
    ) -> list[dict[str, Any]]:
        """Classify a batch of domains using DeepSeek chat.

        Args:
            domains: List of domain name strings (max 50).

        Returns:
            List of classification dicts with domain, niche, site_type,
            tool_idea, quality_signal, score.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert 1 <= len(domains) <= _MAX_BATCH_SIZE, (
            f"batch must be 1-{_MAX_BATCH_SIZE} domains, got {len(domains)}"
        )

        if self._mock:
            return self._mock_classify(domains)

        return await self._classify_live(domains)

    async def _classify_live(
        self, domains: list[str],
    ) -> list[dict[str, Any]]:
        """Execute live classification via DeepSeek API.

        Args:
            domains: Validated list of domain strings.

        Returns:
            Parsed classification results.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert len(domains) >= 1, "domains must not be empty"

        prompt: str = self._build_classification_prompt(domains)
        payload: dict[str, Any] = {
            "model": _MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _MAX_TOKENS,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        headers: dict[str, str] = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response: httpx.Response = await client.post(
                    _BASE_URL, headers=headers, json=payload,
                )
        except httpx.TimeoutException as exc:
            logger.error("deepseek_timeout", domains_count=len(domains))
            raise DeepSeekTimeoutError(
                f"DeepSeek API timed out after {_TIMEOUT_SECONDS}s"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("deepseek_http_error", error=str(exc))
            raise DeepSeekError(f"DeepSeek HTTP error: {exc}") from exc

        return self._handle_response(response, domains)

    def _handle_response(
        self, response: httpx.Response, domains: list[str],
    ) -> list[dict[str, Any]]:
        """Handle and parse the DeepSeek API response.

        Args:
            response: httpx Response object.
            domains: Original domain list for fallback.

        Returns:
            Parsed list of classification dicts.
        """
        assert response is not None, "response must not be None"
        assert isinstance(domains, list), "domains must be a list"

        status: int = response.status_code

        if status == 429:
            logger.warning("deepseek_rate_limited")
            raise DeepSeekRateLimitError("DeepSeek API rate limited (429)")

        if status != 200:
            body_text: str = response.text[:500]
            logger.error(
                "deepseek_api_error", status=status, body=body_text,
            )
            raise DeepSeekError(
                f"DeepSeek API returned {status}: {body_text[:200]}"
            )

        raw_data: dict[str, Any] = response.json()
        result: list[dict[str, Any]] = self._extract_classifications(
            raw_data, domains,
        )
        logger.info(
            "deepseek_classified",
            domains_count=len(domains), results_count=len(result),
        )
        return result

    def _extract_classifications(
        self, raw_data: dict[str, Any], domains: list[str],
    ) -> list[dict[str, Any]]:
        """Extract classification results from API response.

        Args:
            raw_data: Raw JSON response from DeepSeek.
            domains: Original domain list for validation.

        Returns:
            Validated list of classification dicts.
        """
        assert isinstance(raw_data, dict), "raw_data must be a dict"
        assert "choices" in raw_data, "response must contain 'choices'"

        choices: list[dict[str, Any]] = raw_data["choices"]
        assert len(choices) > 0, "choices list must not be empty"

        message: dict[str, Any] = choices[0].get("message", {})
        content: str = message.get("content", "")
        assert len(content) > 0, "response content must not be empty"

        parsed: Any = self._parse_json_content(content)
        results: list[dict[str, Any]] = self._normalize_parsed(parsed)

        validated: list[dict[str, Any]] = []
        for idx, item in enumerate(results):
            if idx >= _MAX_BATCH_SIZE:
                break
            validated.append(self._validate_classification(item))

        assert isinstance(validated, list), "result must be a list"
        return validated

    @staticmethod
    def _parse_json_content(content: str) -> Any:
        """Parse JSON from the LLM response content.

        Args:
            content: Raw text content from the LLM.

        Returns:
            Parsed JSON (list or dict).
        """
        assert isinstance(content, str), "content must be a string"
        assert len(content) > 0, "content must not be empty"

        text: str = content.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines: list[str] = text.split("\n")
            inner: list[str] = [
                ln for ln in lines if not ln.strip().startswith("```")
            ]
            text = "\n".join(inner).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeepSeekError(
                f"Failed to parse DeepSeek JSON: {exc}"
            ) from exc

    @staticmethod
    def _normalize_parsed(parsed: Any) -> list[dict[str, Any]]:
        """Normalize parsed JSON into a list of dicts.

        Args:
            parsed: Raw parsed JSON (may be list or dict).

        Returns:
            List of classification dicts.
        """
        assert parsed is not None, "parsed data must not be None"

        if isinstance(parsed, list):
            assert all(isinstance(d, dict) for d in parsed[:_MAX_BATCH_SIZE]), (
                "all list items must be dicts"
            )
            return parsed

        if isinstance(parsed, dict):
            # Handle {"results": [...]} or {"classifications": [...]} wrappers
            for key in ("results", "classifications", "domains", "data"):
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
            # Single result dict
            return [parsed]

        raise DeepSeekError(f"Unexpected response format: {type(parsed)}")

    @staticmethod
    def _validate_classification(
        item: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and normalize a single classification result.

        Args:
            item: Raw classification dict from LLM.

        Returns:
            Validated classification dict with required fields.
        """
        assert isinstance(item, dict), "classification item must be a dict"
        assert "domain" in item, "classification must include 'domain'"

        valid_signals: tuple[str, ...] = ("strong", "moderate", "weak")
        quality: str = str(item.get("quality_signal", "moderate")).lower()
        if quality not in valid_signals:
            quality = "moderate"

        score: int = int(item.get("score", 50))
        score = max(1, min(100, score))

        return {
            "domain": str(item.get("domain", "")),
            "niche": str(item.get("niche", "other")),
            "site_type": str(item.get("site_type", "other")),
            "tool_idea": str(item.get("tool_idea", "Generic tool")),
            "quality_signal": quality,
            "score": score,
        }

    @staticmethod
    def _mock_classify(domains: list[str]) -> list[dict[str, Any]]:
        """Generate mock classification results for dry-run mode.

        Args:
            domains: List of domain names.

        Returns:
            List of mock classification dicts.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert len(domains) >= 1, "domains must not be empty"

        results: list[dict[str, Any]] = []
        for idx, domain in enumerate(domains):
            if idx >= _MAX_BATCH_SIZE:
                break
            results.append({
                "domain": domain,
                "niche": "tech",
                "site_type": "tool",
                "tool_idea": f"AI-powered analysis tool for {domain}",
                "quality_signal": "moderate",
                "score": 65,
            })
        assert len(results) == len(domains[:_MAX_BATCH_SIZE]), (
            "mock must return same count as input"
        )
        return results

    async def classify_domains_all(
        self, domains: list[str],
    ) -> list[dict[str, Any]]:
        """Classify a large list of domains in batches.

        Splits input into batches of _MAX_BATCH_SIZE and classifies each.

        Args:
            domains: Full list of domain strings (any size).

        Returns:
            Aggregated classification results.
        """
        assert isinstance(domains, list), "domains must be a list"
        assert len(domains) >= 1, "domains must not be empty"

        all_results: list[dict[str, Any]] = []
        capped_domains: list[str] = domains[:_RATE_LIMIT_MAX_DOMAINS]

        for batch_start in range(0, len(capped_domains), _MAX_BATCH_SIZE):
            if batch_start >= _RATE_LIMIT_MAX_DOMAINS:
                break
            batch: list[str] = capped_domains[
                batch_start:batch_start + _MAX_BATCH_SIZE
            ]
            try:
                batch_results: list[dict[str, Any]] = (
                    await self.classify_domains_batch(batch)
                )
                all_results.extend(batch_results)
            except DeepSeekError as exc:
                logger.error(
                    "deepseek_batch_failed",
                    batch_start=batch_start, error=str(exc),
                )

        assert isinstance(all_results, list), "result must be a list"
        logger.info(
            "deepseek_all_classified",
            total_input=len(capped_domains),
            total_results=len(all_results),
        )
        return all_results

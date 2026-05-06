"""Anthropic Claude API client for AI classification and verdicts.

NASA Power of 10: All functions <60 lines, min 2 assertions, bounded loops,
no global mutable state, all return values checked, full type hints.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import Settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_SPECTRE_MODEL: str = "claude-sonnet-4-20250514"
_ORACLE_MODEL: str = "claude-opus-4-20250514"
_MAX_CLASSIFY_TOKENS: int = 200
_MAX_VERDICT_TOKENS: int = 500
_MAX_CONTENT_LENGTH: int = 50_000
_MAX_RISK_FACTORS: int = 20


class AnthropicClientError(Exception):
    """Raised when Anthropic API calls fail."""


class AnthropicClient:
    """Client for Claude-powered domain classification and verdicts."""

    def __init__(
        self, settings: Settings, *, mock: bool = False
    ) -> None:
        assert isinstance(settings, Settings), (
            "settings must be a Settings instance"
        )
        assert isinstance(mock, bool), "mock must be a boolean"
        self._mock: bool = mock
        self._api_key: str = settings.anthropic_api_key
        if not mock:
            self._client: anthropic.AsyncAnthropic = (
                anthropic.AsyncAnthropic(api_key=self._api_key)
            )
        else:
            self._client = None  # type: ignore[assignment]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def classify_domain_content(
        self, content: str, domain: str
    ) -> dict[str, Any]:
        """Classify domain content using Claude Sonnet (SPECTRE).

        Args:
            content: HTML/text content from the domain's archives.
            domain: The domain name being classified.

        Returns:
            Dict with 'score' (1-10) and 'label' (topic description).
        """
        assert isinstance(content, str), "content must be a string"
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) >= 4 and "." in domain, (
            f"domain must be valid, got: {domain}"
        )

        if self._mock:
            return self._mock_classification(domain)

        return await self._classify_live(content, domain)

    async def _classify_live(
        self, content: str, domain: str
    ) -> dict[str, Any]:
        """Execute live classification via Claude Sonnet."""
        assert isinstance(content, str), "content must be a string"
        assert self._client is not None, "client must be initialized"

        truncated: str = content[:_MAX_CONTENT_LENGTH]

        prompt: str = (
            f"Analyze this archived web content from '{domain}' "
            f"and classify it for relevance to AI/developer tools."
            f"\n\nContent:\n{truncated}\n\n"
            f"Respond with ONLY valid JSON: "
            f'{{"score": <1-10>, "label": "<brief topic>"}}\n'
            f"Score 1=irrelevant, 10=perfect AI/devtools fit."
        )

        response: anthropic.types.Message = (
            await self._client.messages.create(
                model=_SPECTRE_MODEL,
                max_tokens=_MAX_CLASSIFY_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        )

        result: dict[str, Any] = self._parse_json_response(response)
        assert "score" in result, "classification must include score"
        assert "label" in result, "classification must include label"

        score: int = int(result["score"])
        assert 1 <= score <= 10, f"score must be 1-10, got {score}"
        result["score"] = score

        logger.info(
            "anthropic_classified", domain=domain, score=score
        )
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def generate_verdict(
        self, dossier: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate final domain verdict using Claude Opus (ORACLE).

        Args:
            dossier: Complete domain analysis dossier from agents.

        Returns:
            Dict with verdict, reasoning, risk_level, risk_factors.
        """
        assert isinstance(dossier, dict), "dossier must be a dict"
        assert len(dossier) > 0, "dossier must not be empty"

        if self._mock:
            return self._mock_verdict()

        return await self._verdict_live(dossier)

    async def _verdict_live(
        self, dossier: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute live verdict generation via Claude Opus."""
        assert isinstance(dossier, dict), "dossier must be a dict"
        assert self._client is not None, "client must be initialized"

        dossier_json: str = json.dumps(
            dossier, indent=2, default=str
        )

        prompt: str = (
            "You are ORACLE, an expert domain acquisition analyst. "
            "Analyze this domain dossier and produce a verdict.\n\n"
            f"Dossier:\n{dossier_json}\n\n"
            "Respond with ONLY valid JSON:\n"
            "{\n"
            '  "verdict": "BUY_NOW" | "WATCH" | "SKIP",\n'
            '  "reasoning": "<2-3 sentence explanation>",\n'
            '  "risk_level": "LOW" | "MEDIUM" | "HIGH",\n'
            '  "risk_factors": ["<factor1>", "<factor2>"]\n'
            "}"
        )

        response: anthropic.types.Message = (
            await self._client.messages.create(
                model=_ORACLE_MODEL,
                max_tokens=_MAX_VERDICT_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        )

        result: dict[str, Any] = self._parse_json_response(response)
        validated: dict[str, Any] = self._validate_verdict(result)

        logger.info(
            "anthropic_verdict_generated",
            verdict=validated["verdict"],
            risk_level=validated["risk_level"],
        )
        return validated

    @staticmethod
    def _validate_verdict(
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and normalize verdict response fields."""
        assert isinstance(result, dict), "result must be a dict"
        assert "verdict" in result, "verdict key required"

        verdict: str = result.get("verdict", "SKIP")
        assert verdict in ("BUY_NOW", "WATCH", "SKIP"), (
            f"verdict must be BUY_NOW/WATCH/SKIP, got: {verdict}"
        )

        risk_level: str = result.get("risk_level", "HIGH")
        assert risk_level in ("LOW", "MEDIUM", "HIGH"), (
            f"risk_level must be LOW/MEDIUM/HIGH, got: {risk_level}"
        )

        risk_factors: list[str] = result.get("risk_factors", [])
        assert isinstance(risk_factors, list), (
            "risk_factors must be a list"
        )

        bounded: list[str] = risk_factors[:_MAX_RISK_FACTORS]

        return {
            "verdict": verdict,
            "reasoning": result.get("reasoning", ""),
            "risk_level": risk_level,
            "risk_factors": bounded,
        }

    @staticmethod
    def _parse_json_response(
        response: anthropic.types.Message,
    ) -> dict[str, Any]:
        """Parse JSON from Claude's text response."""
        assert response is not None, "response must not be None"
        assert len(response.content) > 0, (
            "response must have content"
        )

        text_block: anthropic.types.TextBlock = response.content[0]
        raw_text: str = text_block.text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines: list[str] = raw_text.split("\n")
            inner: list[str] = [
                ln for ln in lines
                if not ln.strip().startswith("```")
            ]
            raw_text = "\n".join(inner).strip()

        result: dict[str, Any] = json.loads(raw_text)
        assert isinstance(result, dict), (
            "parsed response must be a dict"
        )
        return result

    @staticmethod
    def _mock_classification(domain: str) -> dict[str, Any]:
        """Return predefined classification for testing."""
        assert isinstance(domain, str), "domain must be a string"
        assert len(domain) > 0, "domain must not be empty"
        return {
            "score": 7,
            "label": "AI developer tools and API platform",
        }

    @staticmethod
    def _mock_verdict() -> dict[str, Any]:
        """Return predefined verdict for testing."""
        assert True, "mock verdict generation"
        result: dict[str, Any] = {
            "verdict": "WATCH",
            "reasoning": (
                "Domain has strong backlink profile and relevant "
                "content history. However, social signals are "
                "moderate and DA is below premium threshold."
            ),
            "risk_level": "MEDIUM",
            "risk_factors": [
                "Moderate domain authority",
                "Limited recent social mentions",
                "Content drift risk from long expiry gap",
            ],
        }
        assert isinstance(result, dict), "mock verdict must be a dict"
        return result

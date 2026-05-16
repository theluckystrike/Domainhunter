"""Tests for DeepSeek API client — batch domain classification.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.deepseek import (
    DeepSeekClient,
    DeepSeekError,
    DeepSeekRateLimitError,
    DeepSeekTimeoutError,
    _MAX_BATCH_SIZE,
)
from config.settings import Settings

_MOCK_DOMAINS: list[str] = [
    "calculatorhub.com",
    "recipebuddy.io",
    "fitnesstracker.dev",
    "budgetwise.app",
    "studypal.tools",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> Settings:
    """Build a Settings instance with test-only DeepSeek key."""
    return Settings(
        deepseek_api_key="sk-test-deepseek-key-000",
        database_url="sqlite:///test_domainhunter.db",
        max_scout_candidates=100,
        max_sentinel_survivors=20,
        max_archivist_verified=10,
        max_spectre_scored=5,
    )


def _make_mock_api_response(domains: list[str]) -> dict[str, Any]:
    """Build a mock DeepSeek API response payload."""
    classifications: list[dict[str, Any]] = []
    for domain in domains:
        classifications.append({
            "domain": domain,
            "niche": "tech",
            "site_type": "tool",
            "tool_idea": f"Smart tool for {domain}",
            "quality_signal": "strong",
            "score": 75,
        })
    return {
        "choices": [{
            "message": {
                "content": json.dumps(classifications),
            },
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200},
    }


def _make_mock_httpx_response(
    status_code: int, json_data: dict[str, Any] | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data or {})
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = json.JSONDecodeError("", "", 0)
    return resp


# ---------------------------------------------------------------------------
# Test: Mock/dry-run mode
# ---------------------------------------------------------------------------

def test_mock_classify_returns_correct_count() -> None:
    """Mock mode must return one result per input domain."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    results = client._mock_classify(_MOCK_DOMAINS)
    assert len(results) == len(_MOCK_DOMAINS)
    for r in results:
        assert isinstance(r, dict)


def test_mock_classify_has_required_fields() -> None:
    """Each mock result must have all 6 required fields."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    results = client._mock_classify(_MOCK_DOMAINS)
    required: set[str] = {"domain", "niche", "site_type", "tool_idea", "quality_signal", "score"}
    for r in results:
        assert required.issubset(set(r.keys()))
        assert isinstance(r["score"], int)
        assert 1 <= r["score"] <= 100


def test_mock_classify_preserves_domains() -> None:
    """Mock results must contain the exact input domain names."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    results = client._mock_classify(_MOCK_DOMAINS)
    returned_domains = [r["domain"] for r in results]
    assert returned_domains == _MOCK_DOMAINS


@pytest.mark.asyncio
async def test_classify_batch_mock_mode() -> None:
    """classify_domains_batch in mock mode returns expected results."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    results = await client.classify_domains_batch(_MOCK_DOMAINS)
    assert len(results) == 5
    assert all(r["quality_signal"] == "moderate" for r in results)


# ---------------------------------------------------------------------------
# Test: Batch size validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_size_assertion_too_large() -> None:
    """Batch exceeding MAX_BATCH_SIZE must raise AssertionError."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    oversized: list[str] = [f"domain{i}.com" for i in range(51)]
    with pytest.raises(AssertionError, match="batch must be 1-50"):
        await client.classify_domains_batch(oversized)


@pytest.mark.asyncio
async def test_batch_size_assertion_empty() -> None:
    """Empty batch must raise AssertionError."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    with pytest.raises(AssertionError, match="batch must be 1-50"):
        await client.classify_domains_batch([])


# ---------------------------------------------------------------------------
# Test: JSON parsing
# ---------------------------------------------------------------------------

def test_parse_json_content_valid_array() -> None:
    """Valid JSON array should parse correctly."""
    data: list[dict[str, Any]] = [
        {"domain": "test.com", "niche": "tech", "score": 80}
    ]
    result = DeepSeekClient._parse_json_content(json.dumps(data))
    assert isinstance(result, list)
    assert len(result) == 1


def test_parse_json_content_with_markdown_fences() -> None:
    """JSON wrapped in markdown code fences should still parse."""
    data: list[dict[str, Any]] = [
        {"domain": "test.com", "niche": "tech", "score": 80}
    ]
    content = f"```json\n{json.dumps(data)}\n```"
    result = DeepSeekClient._parse_json_content(content)
    assert isinstance(result, list)
    assert len(result) == 1


def test_parse_json_content_invalid_raises() -> None:
    """Invalid JSON content must raise DeepSeekError."""
    with pytest.raises(DeepSeekError, match="Failed to parse"):
        DeepSeekClient._parse_json_content("this is not json at all")


# ---------------------------------------------------------------------------
# Test: Response normalization
# ---------------------------------------------------------------------------

def test_normalize_parsed_list() -> None:
    """A list of dicts should pass through directly."""
    data: list[dict[str, Any]] = [
        {"domain": "a.com"}, {"domain": "b.com"}
    ]
    result = DeepSeekClient._normalize_parsed(data)
    assert len(result) == 2


def test_normalize_parsed_wrapped_dict() -> None:
    """A dict with 'results' key should unwrap to list."""
    data: dict[str, Any] = {
        "results": [{"domain": "a.com"}, {"domain": "b.com"}]
    }
    result = DeepSeekClient._normalize_parsed(data)
    assert len(result) == 2


def test_normalize_parsed_single_dict() -> None:
    """A single dict result should become a one-element list."""
    data: dict[str, Any] = {"domain": "a.com", "score": 80}
    result = DeepSeekClient._normalize_parsed(data)
    assert len(result) == 1
    assert result[0]["domain"] == "a.com"


# ---------------------------------------------------------------------------
# Test: Classification validation
# ---------------------------------------------------------------------------

def test_validate_classification_clamps_score() -> None:
    """Score outside 1-100 range must be clamped."""
    item: dict[str, Any] = {"domain": "test.com", "score": 150}
    result = DeepSeekClient._validate_classification(item)
    assert result["score"] == 100

    item2: dict[str, Any] = {"domain": "test.com", "score": -5}
    result2 = DeepSeekClient._validate_classification(item2)
    assert result2["score"] == 1


def test_validate_classification_normalizes_quality() -> None:
    """Invalid quality_signal must be normalized to 'moderate'."""
    item: dict[str, Any] = {
        "domain": "test.com", "quality_signal": "INVALID", "score": 50,
    }
    result = DeepSeekClient._validate_classification(item)
    assert result["quality_signal"] == "moderate"


def test_validate_classification_missing_domain_raises() -> None:
    """Missing 'domain' key must raise AssertionError."""
    with pytest.raises(AssertionError, match="must include 'domain'"):
        DeepSeekClient._validate_classification({"score": 50})


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------

def test_handle_response_rate_limit() -> None:
    """429 status must raise DeepSeekRateLimitError."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=False)
    mock_response = _make_mock_httpx_response(429, text="rate limited")
    with pytest.raises(DeepSeekRateLimitError):
        client._handle_response(mock_response, _MOCK_DOMAINS)


def test_handle_response_server_error() -> None:
    """500 status must raise DeepSeekError."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=False)
    mock_response = _make_mock_httpx_response(500, text="internal error")
    with pytest.raises(DeepSeekError, match="DeepSeek API returned 500"):
        client._handle_response(mock_response, _MOCK_DOMAINS)


def test_handle_response_success() -> None:
    """200 status with valid JSON must return classification results."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=False)
    api_data = _make_mock_api_response(_MOCK_DOMAINS)
    mock_response = _make_mock_httpx_response(200, json_data=api_data)
    results = client._handle_response(mock_response, _MOCK_DOMAINS)
    assert len(results) == 5
    assert all(isinstance(r, dict) for r in results)


# ---------------------------------------------------------------------------
# Test: classify_domains_all batching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_all_batches_correctly() -> None:
    """classify_domains_all must batch large lists correctly."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    large_list: list[str] = [f"domain{i}.com" for i in range(75)]
    results = await client.classify_domains_all(large_list)
    assert len(results) == 75
    assert all(r["domain"].startswith("domain") for r in results)


# ---------------------------------------------------------------------------
# Test: Settings integration
# ---------------------------------------------------------------------------

def test_client_initialization() -> None:
    """Client must initialize with correct settings."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=False)
    assert client._api_key == "sk-test-deepseek-key-000"
    assert client._mock is False


def test_client_headers() -> None:
    """Headers must include Bearer authorization."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=False)
    headers = client._build_headers()
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["Content-Type"] == "application/json"


def test_prompt_building() -> None:
    """Classification prompt must include all domain names."""
    settings = _make_settings()
    client = DeepSeekClient(settings, mock=True)
    prompt = client._build_classification_prompt(_MOCK_DOMAINS)
    for domain in _MOCK_DOMAINS:
        assert domain in prompt
    assert "JSON array" in prompt

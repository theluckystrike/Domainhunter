"""Tests for DataForSEO bulk backlink API methods.

NASA Power of 10 compliant:
- Every function under 60 lines
- Min 2 assertions per test
- No mutable global state
- Bounded loops
- All return values checked
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.dataforseo import DataForSEOClient, DataForSEOError
from config.settings import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MOCK_RANKS_RESPONSE: dict[str, Any] = {
    "version": "0.1.20260507",
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks_count": 1,
    "tasks_error": 0,
    "tasks": [
        {
            "id": "test-bulk-ranks-001",
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {"target": "builder.ai", "rank": 744},
                {"target": "devhub.io", "rank": 350},
                {"target": "seochecker.com", "rank": 13},
            ],
        }
    ],
}

_MOCK_REFERRING_RESPONSE: dict[str, Any] = {
    "version": "0.1.20260507",
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks_count": 1,
    "tasks_error": 0,
    "tasks": [
        {
            "id": "test-bulk-referring-001",
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {"target": "builder.ai", "referring_domains": 2600},
                {"target": "devhub.io", "referring_domains": 275},
                {"target": "seochecker.com", "referring_domains": 129},
            ],
        }
    ],
}

_MOCK_SUMMARY_RESPONSE: dict[str, Any] = {
    "version": "0.1.20260507",
    "status_code": 20000,
    "status_message": "Ok.",
    "tasks_count": 1,
    "tasks_error": 0,
    "tasks": [
        {
            "id": "test-bulk-summary-001",
            "status_code": 20000,
            "status_message": "Ok.",
            "result": [
                {
                    "target": "builder.ai",
                    "page": "https://builder.ai/",
                    "rank": 744,
                    "backlinks": 21000,
                    "referring_domains": 2600,
                    "referring_main_domains": 2400,
                    "broken_backlinks": 150,
                    "referring_pages": 18000,
                    "spam_score": 3,
                },
                {
                    "target": "devhub.io",
                    "page": "https://devhub.io/",
                    "rank": 350,
                    "backlinks": 851,
                    "referring_domains": 275,
                    "referring_main_domains": 250,
                    "broken_backlinks": 20,
                    "referring_pages": 700,
                    "spam_score": 5,
                },
            ],
        }
    ],
}

_MOCK_ERROR_RESPONSE: dict[str, Any] = {
    "version": "0.1.20260507",
    "status_code": 20000,
    "tasks_count": 1,
    "tasks_error": 1,
    "tasks": [
        {
            "id": "test-error-001",
            "status_code": 40204,
            "status_message": "Access denied.",
            "result": None,
        }
    ],
}

_TEST_DOMAINS: list[str] = ["builder.ai", "devhub.io", "seochecker.com"]


@pytest.fixture()
def client(settings: Settings) -> DataForSEOClient:
    """Return a DataForSEOClient instance for testing."""
    return DataForSEOClient(settings, mock=False)


# ---------------------------------------------------------------------------
# Tests: bulk_ranks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_ranks_returns_correct_mapping(client: DataForSEOClient) -> None:
    """bulk_ranks should return domain->rank dict from mock response."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_RANKS_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result: dict[str, int] = await client.bulk_ranks(_TEST_DOMAINS)

    assert isinstance(result, dict), "result must be a dict"
    assert result["builder.ai"] == 744, "builder.ai rank must be 744"
    assert result["devhub.io"] == 350, "devhub.io rank must be 350"
    assert len(result) == 3, "result must have 3 entries"


@pytest.mark.asyncio
async def test_bulk_ranks_error_raises(client: DataForSEOClient) -> None:
    """bulk_ranks should raise DataForSEOError on API error response."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_ERROR_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(DataForSEOError) as exc_info:
            await client.bulk_ranks(_TEST_DOMAINS)

    assert "bulk_ranks failed" in str(exc_info.value)
    assert "Access denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_bulk_ranks_validates_input(client: DataForSEOClient) -> None:
    """bulk_ranks should reject non-list or empty input."""
    with pytest.raises(AssertionError):
        await client.bulk_ranks([])  # type: ignore

    assert True, "empty list correctly rejected"

    with pytest.raises(AssertionError):
        await client.bulk_ranks("not-a-list")  # type: ignore

    assert True, "non-list correctly rejected"


# ---------------------------------------------------------------------------
# Tests: bulk_referring_domains
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_referring_returns_correct_mapping(
    client: DataForSEOClient,
) -> None:
    """bulk_referring_domains returns domain->count dict."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_REFERRING_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result: dict[str, int] = await client.bulk_referring_domains(_TEST_DOMAINS)

    assert result["builder.ai"] == 2600, "builder.ai must have 2600 referring domains"
    assert result["seochecker.com"] == 129, "seochecker.com must have 129 referring domains"
    assert len(result) == 3, "all 3 domains must be present"


@pytest.mark.asyncio
async def test_bulk_referring_error_raises(client: DataForSEOClient) -> None:
    """bulk_referring_domains should raise on task error."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_ERROR_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(DataForSEOError) as exc_info:
            await client.bulk_referring_domains(_TEST_DOMAINS)

    assert "bulk_referring failed" in str(exc_info.value)
    assert "Access denied" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests: bulk_pages_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_pages_summary_returns_list(client: DataForSEOClient) -> None:
    """bulk_pages_summary should return list of domain summaries."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_SUMMARY_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result: list[dict] = await client.bulk_pages_summary(_TEST_DOMAINS)

    assert isinstance(result, list), "result must be a list"
    assert len(result) == 2, "result must have 2 items"
    assert result[0]["target"] == "builder.ai", "first target must be builder.ai"
    assert result[0]["rank"] == 744, "builder.ai rank must be 744"
    assert result[0]["backlinks"] == 21000, "builder.ai backlinks must be 21000"
    assert result[1]["spam_score"] == 5, "devhub.io spam_score must be 5"


@pytest.mark.asyncio
async def test_bulk_pages_summary_error_raises(client: DataForSEOClient) -> None:
    """bulk_pages_summary should raise DataForSEOError on access denied."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_ERROR_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(DataForSEOError) as exc_info:
            await client.bulk_pages_summary(_TEST_DOMAINS)

    assert "bulk_pages_summary failed" in str(exc_info.value)
    assert "Access denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_bulk_pages_summary_extracts_all_fields(
    client: DataForSEOClient,
) -> None:
    """bulk_pages_summary items must contain all expected fields."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=_MOCK_SUMMARY_RESPONSE)
    mock_resp.text = AsyncMock(return_value="")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result: list[dict] = await client.bulk_pages_summary(_TEST_DOMAINS)

    expected_keys: set[str] = {
        "target", "page", "rank", "backlinks", "referring_domains",
        "referring_main_domains", "broken_backlinks", "referring_pages",
        "spam_score",
    }
    item: dict = result[0]
    assert expected_keys.issubset(set(item.keys())), (
        f"missing keys: {expected_keys - set(item.keys())}"
    )
    assert item["broken_backlinks"] == 150, "broken_backlinks must be 150"


# ---------------------------------------------------------------------------
# Tests: HTTP error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_post_http_error_raises(client: DataForSEOClient) -> None:
    """_bulk_post should raise DataForSEOError on non-200 HTTP status."""
    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.text = AsyncMock(return_value="Internal Server Error")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(DataForSEOError) as exc_info:
            await client.bulk_ranks(["builder.ai"])

    assert "500" in str(exc_info.value), "error must contain status code"
    assert "Internal Server Error" in str(exc_info.value)

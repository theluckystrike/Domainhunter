"""Tests for Dynadot API client — backorder, search, and domain info.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No mutable global state.
NASA Rule 6: All assertions explicit — min 2 per test.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import httpx
import pytest
import respx

from clients.dynadot_client import (
    BackorderResult,
    DomainInfoResult,
    DomainSearchResult,
    DynadotAuthError,
    DynadotClient,
    DynadotError,
    DynadotRateLimitError,
)
from config.settings import Settings

_BASE_URL: str = "https://api.dynadot.com/api3.json"


# ---------------------------------------------------------------------------
# Fixture: Settings with a Dynadot API key
# ---------------------------------------------------------------------------
@pytest.fixture()
def dynadot_settings() -> Settings:
    """Return a Settings instance with a test Dynadot API key."""
    return Settings(
        _env_file=None,
        dynadot_api_key="test-dynadot-key-999",
        database_url="sqlite:///test_domainhunter.db",
    )


@pytest.fixture()
def client(dynadot_settings: Settings) -> DynadotClient:
    """Return a DynadotClient in normal (non-dry-run) mode."""
    return DynadotClient(dynadot_settings)


@pytest.fixture()
def dry_client(dynadot_settings: Settings) -> DynadotClient:
    """Return a DynadotClient in dry_run mode."""
    return DynadotClient(dynadot_settings, dry_run=True)


# ---------------------------------------------------------------------------
# 1. Backorder success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_backorder_success(client: DynadotClient) -> None:
    """Successful backorder returns BackorderResult with success=True."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "StatusHeader": {"Status": "success", "Message": "Backorder placed"},
    }))
    result: BackorderResult = await client.backorder("ghostautonomy.com")
    assert result.success is True
    assert result.domain == "ghostautonomy.com"
    assert "Backorder placed" in result.message


# ---------------------------------------------------------------------------
# 2. Backorder dry_run — no API call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_backorder_dry_run(dry_client: DynadotClient) -> None:
    """In dry_run mode, backorder returns mock result without API call."""
    result: BackorderResult = await dry_client.backorder("ghostautonomy.com")
    assert result.success is True
    assert "DRY RUN" in result.message
    assert result.domain == "ghostautonomy.com"


# ---------------------------------------------------------------------------
# 3. Backorder already exists
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_backorder_already_exists(client: DynadotClient) -> None:
    """Domain already backordered returns success=False with message."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "StatusHeader": {"Status": "error", "Message": "Backorder already exists"},
    }))
    result: BackorderResult = await client.backorder("guerrameats.com")
    assert result.success is False
    assert "already exists" in result.message


# ---------------------------------------------------------------------------
# 4. Delete backorder success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_delete_backorder_success(client: DynadotClient) -> None:
    """Successful delete_backorder returns BackorderResult with success=True."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "StatusHeader": {"Status": "success", "Message": "Backorder deleted"},
    }))
    result: BackorderResult = await client.delete_backorder("guerrameats.com")
    assert result.success is True
    assert result.domain == "guerrameats.com"
    assert "deleted" in result.message.lower()


# ---------------------------------------------------------------------------
# 5. List backorders — 3 active
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_list_backorders(client: DynadotClient) -> None:
    """Listing 3 active backorders returns correct domain list."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "BackorderList": [
            {"Domain": "guerrameats.com"},
            {"Domain": "sunnyray.org"},
            {"Domain": "globalgeopark.org"},
        ],
    }))
    domains: list[str] = await client.list_backorder()
    assert len(domains) == 3
    assert "guerrameats.com" in domains
    assert "sunnyray.org" in domains


# ---------------------------------------------------------------------------
# 6. List backorders — empty
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_list_backorders_empty(client: DynadotClient) -> None:
    """Empty backorder list returns empty list, not None."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "BackorderList": [],
    }))
    domains: list[str] = await client.list_backorder()
    assert isinstance(domains, list)
    assert len(domains) == 0


# ---------------------------------------------------------------------------
# 7. Search — domain available
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_search_available(client: DynadotClient) -> None:
    """Available domain returns available=True with a price."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "SearchResponse": {"SearchResults": [
            {"DomainName": "freshstartup.dev", "Available": "yes", "Price": 12.99},
        ]},
    }))
    result: DomainSearchResult = await client.search("freshstartup.dev")
    assert result.available is True
    assert result.price_usd == pytest.approx(12.99)
    assert result.domain == "freshstartup.dev"


# ---------------------------------------------------------------------------
# 8. Search — domain taken
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_search_taken(client: DynadotClient) -> None:
    """Taken domain returns available=False."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "SearchResponse": {"SearchResults": [
            {"DomainName": "ghostautonomy.com", "Available": "no"},
        ]},
    }))
    result: DomainSearchResult = await client.search("ghostautonomy.com")
    assert result.available is False
    assert result.domain == "ghostautonomy.com"


# ---------------------------------------------------------------------------
# 9. Domain info
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_domain_info(client: DynadotClient) -> None:
    """domain_info returns expiration, nameservers, and status."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(200, json={
        "DomainInfoResponse": {
            "Expiration": "2027-06-15",
            "NameServers": ["ns1.dynadot.com", "ns2.dynadot.com"],
            "Status": "active",
        },
    }))
    result: DomainInfoResult = await client.domain_info("guerrameats.com")
    assert result.domain == "guerrameats.com"
    assert result.expiration == "2027-06-15"
    assert len(result.name_servers) == 2
    assert result.status == "active"


# ---------------------------------------------------------------------------
# 10. Auth error — invalid API key
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@respx.mock
async def test_auth_error(client: DynadotClient) -> None:
    """401 response raises DynadotAuthError."""
    respx.get(_BASE_URL).mock(return_value=httpx.Response(401, text="Unauthorized"))
    with pytest.raises(DynadotAuthError) as exc_info:
        await client.search("anything.com")
    assert "auth" in str(exc_info.value).lower()
    assert isinstance(exc_info.value, DynadotError)


# ---------------------------------------------------------------------------
# 11. Rate limit — exceed RPM
# ---------------------------------------------------------------------------
def test_rate_limit(dynadot_settings: Settings) -> None:
    """Exceeding rate limit raises DynadotRateLimitError."""
    from clients.dynadot_client import _RateLimiter
    limiter = _RateLimiter(max_calls=2, window_seconds=60.0)
    limiter.acquire()
    limiter.acquire()
    with pytest.raises(DynadotRateLimitError) as exc_info:
        limiter.acquire()
    assert "Rate limit" in str(exc_info.value)
    assert isinstance(exc_info.value, DynadotError)


# ---------------------------------------------------------------------------
# 12. Result dataclasses are frozen
# ---------------------------------------------------------------------------
def test_result_frozen() -> None:
    """All result dataclasses must be frozen (immutable)."""
    bo = BackorderResult(domain="x.com", success=True, message="ok")
    sr = DomainSearchResult(domain="x.com", available=True, price_usd=9.99)
    di = DomainInfoResult(domain="x.com", expiration="2027-01-01",
                          name_servers=("ns1.x.com",), status="active")
    for obj in (bo, sr, di):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.domain = "hacked.com"  # must raise — frozen dataclass

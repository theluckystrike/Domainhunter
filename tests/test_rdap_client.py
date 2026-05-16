"""Tests for RDAP client — async domain registration data lookups.

NASA Rule 1: Every function under 60 lines.
NASA Rule 6: All assertions explicit (min 2 per test).
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clients.rdap_client import (
    RDAP_SERVERS,
    RDAPClient,
    RDAPError,
    RDAPNotFoundError,
    RDAPRateLimitError,
    RDAPResult,
)

# ---------------------------------------------------------------------------
# Constants (immutable — NASA Rule 2)
# ---------------------------------------------------------------------------
_SAMPLE_DOMAIN: str = "example.com"
_SAMPLE_TLD: str = ".com"

_RDAP_RESPONSE: dict[str, Any] = {
    "objectClassName": "domain",
    "handle": "EXAMPLE.COM",
    "ldhName": "example.com",
    "status": ["client renew prohibited", "client transfer prohibited"],
    "events": [
        {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"},
        {"eventAction": "expiration", "eventDate": "2026-06-07T00:00:00Z"},
        {"eventAction": "last changed", "eventDate": "2026-05-01T00:00:00Z"},
    ],
    "entities": [
        {
            "roles": ["registrar"],
            "vcardArray": [
                "vcard",
                [["fn", {}, "text", "Wild West Domains"]],
            ],
        }
    ],
    "nameservers": [
        {"ldhName": "ns1.cloudflare.com"},
        {"ldhName": "ns2.cloudflare.com"},
    ],
}

_PENDING_DELETE_RESPONSE: dict[str, Any] = {
    "objectClassName": "domain",
    "ldhName": "expired-site.com",
    "status": ["pendingDelete", "redemptionPeriod"],
    "events": [
        {"eventAction": "registration", "eventDate": "2018-03-15T00:00:00Z"},
        {"eventAction": "expiration", "eventDate": "2026-01-01T00:00:00Z"},
    ],
    "entities": [],
    "nameservers": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(
    status_code: int,
    json_data: dict[str, Any] | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx.Response with the given status and body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data or {})
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = json.JSONDecodeError("", "", 0)
    return resp


# ---------------------------------------------------------------------------
# Server routing tests
# ---------------------------------------------------------------------------

def test_rdap_server_routing_com() -> None:
    """Dot-com domains must route to rdap.verisign.com."""
    client = RDAPClient()
    tld: str = client._extract_tld("techstack.com")
    url: str = client._resolve_rdap_url("techstack.com", tld)
    assert tld == ".com"
    assert "rdap.verisign.com/com" in url
    assert url.endswith("techstack.com")


def test_rdap_server_routing_org() -> None:
    """Dot-org domains must route to publicinterestregistry."""
    client = RDAPClient()
    tld: str = client._extract_tld("opentools.org")
    url: str = client._resolve_rdap_url("opentools.org", tld)
    assert tld == ".org"
    assert "publicinterestregistry" in url


def test_rdap_server_routing_unknown_tld() -> None:
    """Unknown TLD must raise AssertionError from _resolve_rdap_url."""
    client = RDAPClient()
    tld: str = client._extract_tld("oddsite.pizza")
    assert tld == ".pizza"
    with pytest.raises(AssertionError, match="unsupported TLD"):
        client._resolve_rdap_url("oddsite.pizza", tld)


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

def test_rdap_parse_response() -> None:
    """Full RDAP JSON must parse into correct RDAPResult fields."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(_SAMPLE_DOMAIN, _RDAP_RESPONSE)
    assert result.domain == "example.com"
    assert result.registrar_name == "Wild West Domains"
    assert result.creation_date == "2020-01-01T00:00:00Z"


def test_rdap_parse_epp_status() -> None:
    """All EPP status codes from the response must be extracted."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(_SAMPLE_DOMAIN, _RDAP_RESPONSE)
    assert len(result.status_codes) == 2
    assert "client renew prohibited" in result.status_codes
    assert "client transfer prohibited" in result.status_codes


def test_rdap_parse_dates() -> None:
    """ISO 8601 dates must be extracted from events array."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(_SAMPLE_DOMAIN, _RDAP_RESPONSE)
    assert result.creation_date == "2020-01-01T00:00:00Z"
    assert result.registry_expiry == "2026-06-07T00:00:00Z"
    assert result.last_updated == "2026-05-01T00:00:00Z"


def test_rdap_parse_nameservers() -> None:
    """Nameserver hostnames must be extracted and lowercased."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(_SAMPLE_DOMAIN, _RDAP_RESPONSE)
    assert len(result.nameservers) == 2
    assert "ns1.cloudflare.com" in result.nameservers
    assert "ns2.cloudflare.com" in result.nameservers


# ---------------------------------------------------------------------------
# HTTP error handling tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rdap_not_found() -> None:
    """404 response must raise RDAPNotFoundError."""
    client = RDAPClient()
    mock_resp = _make_mock_response(404, text="not found")

    with pytest.raises(RDAPNotFoundError, match="not found"):
        client._handle_response(mock_resp, _SAMPLE_DOMAIN)

    assert issubclass(RDAPNotFoundError, RDAPError)


@pytest.mark.asyncio
async def test_rdap_rate_limited() -> None:
    """429 response must raise RDAPRateLimitError."""
    client = RDAPClient()
    mock_resp = _make_mock_response(429, text="too many requests")

    with pytest.raises(RDAPRateLimitError, match="rate limited"):
        client._handle_response(mock_resp, _SAMPLE_DOMAIN)

    assert issubclass(RDAPRateLimitError, RDAPError)


# ---------------------------------------------------------------------------
# Dataclass immutability test
# ---------------------------------------------------------------------------

def test_rdap_result_frozen() -> None:
    """RDAPResult dataclass must reject attribute mutation."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(_SAMPLE_DOMAIN, _RDAP_RESPONSE)
    assert dataclasses.is_dataclass(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.domain = "hacked.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Batch lookup test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rdap_batch_lookup() -> None:
    """Batch lookup must return one result per domain with rate limiting."""
    client = RDAPClient()
    domains: list[str] = ["alpha.com", "beta.org", "gamma.dev"]

    mock_results: list[RDAPResult] = [
        RDAPResult(
            domain=d, status_codes=("active",), registry_expiry="2027-01-01T00:00:00Z",
            registrar_expiry="", registrar_name="TestReg", nameservers=("ns1.test.com",),
            creation_date="2020-01-01T00:00:00Z", last_updated="2026-01-01T00:00:00Z",
        )
        for d in domains
    ]

    async def _fake_lookup(domain: str) -> RDAPResult:
        idx: int = domains.index(domain)
        return mock_results[idx]

    with patch.object(client, "lookup", side_effect=_fake_lookup):
        results = await client.lookup_batch(domains)

    assert len(results) == 3
    assert all(isinstance(r, RDAPResult) for r in results)
    assert results[0].domain == "alpha.com"
    assert results[2].domain == "gamma.dev"


# ---------------------------------------------------------------------------
# Pending-delete detection test
# ---------------------------------------------------------------------------

def test_rdap_detect_pending_delete() -> None:
    """pendingDelete EPP status must be detectable in status_codes."""
    client = RDAPClient()
    result: RDAPResult = client._build_result(
        "expired-site.com", _PENDING_DELETE_RESPONSE,
    )
    assert "pendingDelete" in result.status_codes
    assert "redemptionPeriod" in result.status_codes
    assert len(result.nameservers) == 0

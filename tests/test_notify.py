"""Tests for scripts/notify.py -- travel-proof notification dispatcher.

Verifies:
  - Payload format for ntfy.sh channel
  - Payload format for Resend email channel
  - Priority routing (critical = all channels, normal = email + stdout)
  - Alert formatting

NASA Power of 10: functions <60 lines, min 2 assertions.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest

# Ensure project root importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.notify import (
    NotifyConfig,
    NotifyResult,
    _send_ntfy,
    _send_email,
    _send_stdout,
    format_domain_alert,
    load_config,
    send_alert,
    NTFY_BASE_URL,
    RESEND_API_URL,
)


# ── Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def full_config() -> NotifyConfig:
    """Config with all channels enabled."""
    return NotifyConfig(
        email_to="user@example.com",
        resend_api_key="re_test_key_123",
        ntfy_topic="domainhunter-test",
    )


@pytest.fixture
def ntfy_only_config() -> NotifyConfig:
    """Config with only ntfy enabled."""
    return NotifyConfig(
        email_to="",
        resend_api_key="",
        ntfy_topic="domainhunter-test",
    )


@pytest.fixture
def email_only_config() -> NotifyConfig:
    """Config with only email enabled."""
    return NotifyConfig(
        email_to="user@example.com",
        resend_api_key="re_test_key_123",
        ntfy_topic="",
    )


# ── Test: NotifyConfig ────────────────────────────────────────────────
def test_config_has_email(full_config: NotifyConfig) -> None:
    """Config reports email availability correctly."""
    assert full_config.has_email is True
    assert full_config.has_ntfy is True


def test_config_missing_email(ntfy_only_config: NotifyConfig) -> None:
    """Config without email reports correctly."""
    assert ntfy_only_config.has_email is False
    assert ntfy_only_config.has_ntfy is True


def test_config_missing_ntfy(email_only_config: NotifyConfig) -> None:
    """Config without ntfy reports correctly."""
    assert email_only_config.has_email is True
    assert email_only_config.has_ntfy is False


# ── Test: load_config from env ────────────────────────────────────────
def test_load_config_from_env() -> None:
    """load_config reads environment variables."""
    env = {
        "NOTIFY_EMAIL_TO": "test@test.com",
        "RESEND_API_KEY": "re_key",
        "NOTIFY_NTFY_TOPIC": "my-topic",
    }
    with patch.dict(os.environ, env, clear=False):
        config = load_config()
        assert config.email_to == "test@test.com"
        assert config.ntfy_topic == "my-topic"


def test_load_config_empty_env() -> None:
    """load_config handles missing env vars gracefully."""
    env = {
        "NOTIFY_EMAIL_TO": "",
        "RESEND_API_KEY": "",
        "NOTIFY_NTFY_TOPIC": "",
    }
    with patch.dict(os.environ, env, clear=False):
        config = load_config()
        assert config.has_email is False
        assert config.has_ntfy is False


# ── Test: format_domain_alert ─────────────────────────────────────────
def test_format_domain_alert_basic() -> None:
    """format_domain_alert produces correct subject and body."""
    subject, body = format_domain_alert(
        domain="example.com",
        event="pendingDelete",
        price=99.50,
        action_url="https://dropcatch.com/snap/listing/example.com",
    )
    assert subject == "DOMAIN ALERT: example.com - pendingDelete"
    assert "example.com" in body
    assert "$99.50" in body
    assert "dropcatch.com" in body


def test_format_domain_alert_no_price() -> None:
    """format_domain_alert works without price."""
    subject, body = format_domain_alert(
        domain="test.org",
        event="entered auction",
    )
    assert "test.org" in subject
    assert "Price" not in body
    assert "entered auction" in body


# ── Test: _send_stdout ────────────────────────────────────────────────
def test_send_stdout_always_succeeds(capsys) -> None:
    """stdout channel always returns success."""
    result = _send_stdout("Test Subject", "Test body content")
    assert result.success is True
    assert result.channel == "stdout"
    captured = capsys.readouterr()
    assert "Test Subject" in captured.out


# ── Test: _send_ntfy payload format ──────────────────────────────────
@patch("scripts.notify.urllib.request.urlopen")
def test_send_ntfy_payload(mock_urlopen, full_config: NotifyConfig) -> None:
    """ntfy channel sends correct HTTP POST with headers."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    result = _send_ntfy("Alert Title", "Alert body", "critical", full_config)

    assert result.success is True
    assert result.channel == "ntfy"

    # Verify the request was made
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert req.full_url == f"{NTFY_BASE_URL}domainhunter-test"
    assert req.get_header("Title") == "Alert Title"
    assert req.get_header("Priority") == "urgent"
    assert req.data == b"Alert body"


@patch("scripts.notify.urllib.request.urlopen")
def test_send_ntfy_high_priority(mock_urlopen, full_config: NotifyConfig) -> None:
    """ntfy maps 'high' priority correctly."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    _send_ntfy("Title", "Body", "high", full_config)

    req = mock_urlopen.call_args[0][0]
    assert req.get_header("Priority") == "high"
    assert req.get_header("Tags") == "loudspeaker"


# ── Test: _send_email payload format ─────────────────────────────────
@patch("scripts.notify.urllib.request.urlopen")
def test_send_email_payload(mock_urlopen, full_config: NotifyConfig) -> None:
    """Email channel sends correct Resend API payload."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"id": "test-123"}'
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    result = _send_email("Email Subject", "Email body text", full_config)

    assert result.success is True
    assert result.channel == "email"

    # Verify request
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == RESEND_API_URL
    assert req.get_header("Authorization") == "Bearer re_test_key_123"
    assert req.get_header("Content-type") == "application/json"

    # Verify payload structure
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["to"] == ["user@example.com"]
    assert payload["subject"] == "Email Subject"
    assert payload["text"] == "Email body text"
    assert "DomainHunter" in payload["from"]


# ── Test: Priority Routing ────────────────────────────────────────────
@patch("scripts.notify.load_config")
@patch("scripts.notify._send_email")
@patch("scripts.notify._send_ntfy")
@patch("scripts.notify._send_stdout")
def test_critical_routes_all_channels(
    mock_stdout, mock_ntfy, mock_email, mock_config,
    full_config: NotifyConfig,
) -> None:
    """Critical priority sends to all configured channels."""
    mock_config.return_value = full_config
    mock_stdout.return_value = NotifyResult("stdout", True, "ok")
    mock_ntfy.return_value = NotifyResult("ntfy", True, "ok")
    mock_email.return_value = NotifyResult("email", True, "ok")

    results = send_alert("Subject", "Body", priority="critical")

    assert len(results) == 3
    mock_stdout.assert_called_once()
    mock_ntfy.assert_called_once()
    mock_email.assert_called_once()


@patch("scripts.notify.load_config")
@patch("scripts.notify._send_email")
@patch("scripts.notify._send_ntfy")
@patch("scripts.notify._send_stdout")
def test_normal_routes_email_and_stdout(
    mock_stdout, mock_ntfy, mock_email, mock_config,
    full_config: NotifyConfig,
) -> None:
    """Normal priority sends to email + stdout + ntfy (all channels)."""
    mock_config.return_value = full_config
    mock_stdout.return_value = NotifyResult("stdout", True, "ok")
    mock_ntfy.return_value = NotifyResult("ntfy", True, "ok")
    mock_email.return_value = NotifyResult("email", True, "ok")

    results = send_alert("Subject", "Body", priority="normal")

    assert len(results) == 3
    mock_stdout.assert_called_once()
    mock_ntfy.assert_called_once()
    mock_email.assert_called_once()


@patch("scripts.notify.load_config")
@patch("scripts.notify._send_email")
@patch("scripts.notify._send_ntfy")
@patch("scripts.notify._send_stdout")
def test_high_routes_ntfy_and_email(
    mock_stdout, mock_ntfy, mock_email, mock_config,
    full_config: NotifyConfig,
) -> None:
    """High priority sends to ntfy + email + stdout."""
    mock_config.return_value = full_config
    mock_stdout.return_value = NotifyResult("stdout", True, "ok")
    mock_ntfy.return_value = NotifyResult("ntfy", True, "ok")
    mock_email.return_value = NotifyResult("email", True, "ok")

    results = send_alert("Subject", "Body", priority="high")

    assert len(results) == 3
    mock_ntfy.assert_called_once()
    mock_email.assert_called_once()


@patch("scripts.notify.load_config")
@patch("scripts.notify._send_stdout")
def test_no_channels_configured(mock_stdout, mock_config) -> None:
    """With no channels configured, only stdout fires."""
    mock_config.return_value = NotifyConfig(
        email_to="", resend_api_key="", ntfy_topic="",
    )
    mock_stdout.return_value = NotifyResult("stdout", True, "ok")

    results = send_alert("Subject", "Body", priority="critical")

    assert len(results) == 1
    assert results[0].channel == "stdout"


# ── Test: Error Handling ──────────────────────────────────────────────
@patch("scripts.notify.urllib.request.urlopen")
def test_ntfy_network_error(mock_urlopen, full_config: NotifyConfig) -> None:
    """ntfy gracefully handles network errors."""
    import urllib.error
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    result = _send_ntfy("Title", "Body", "critical", full_config)

    assert result.success is False
    assert "error" in result.detail.lower()


@patch("scripts.notify.urllib.request.urlopen")
def test_email_network_error(mock_urlopen, full_config: NotifyConfig) -> None:
    """Email channel gracefully handles network errors."""
    import urllib.error
    mock_urlopen.side_effect = urllib.error.URLError("Timeout")

    result = _send_email("Subject", "Body", full_config)

    assert result.success is False
    assert "error" in result.detail.lower()


# ── Test: Invalid Input ───────────────────────────────────────────────
def test_send_alert_invalid_priority() -> None:
    """send_alert rejects invalid priority levels."""
    with pytest.raises(AssertionError, match="Invalid priority"):
        send_alert("Subject", "Body", priority="extreme")


def test_format_alert_invalid_domain() -> None:
    """format_domain_alert rejects invalid domains."""
    with pytest.raises(AssertionError, match="Invalid domain"):
        format_domain_alert(domain="nodot", event="test")

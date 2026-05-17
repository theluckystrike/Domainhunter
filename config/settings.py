"""Pipeline settings loaded from environment variables via Pydantic.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state — settings are frozen after creation.
"""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Immutable pipeline configuration loaded from .env file."""

    model_config = {"frozen": True, "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # SCOUT API keys
    whoisfreaks_api_key: str = ""
    catchdoms_api_key: str = ""
    apify_api_token: str = ""

    # SENTINEL API keys
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    google_cse_api_key: str = ""
    google_cse_cx: str = ""

    # SPECTRE API keys
    github_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "DomainHunter/1.0"

    # ORACLE + SPECTRE
    anthropic_api_key: str = ""

    # CLASSIFIER (Sprint 3 — DeepSeek)
    deepseek_api_key: str = ""

    # REGISTRAR (Dynadot backorders)
    dynadot_api_key: str = ""

    # REGISTRAR (DropCatch backorders + NameBright domain management)
    # Both share the same NameBright OAuth2 credentials
    # Format: client_id = "accountname:appname"
    # Setup: https://www.namebright.com/Settings#Api
    dropcatch_client_id: str = ""
    dropcatch_client_secret: str = ""

    # POST-CATCH DNS (used by post_catch_executor.py)
    post_catch_nameservers: str = "ns1.cloudflare.com,ns2.cloudflare.com"
    post_catch_landing_ip: str = ""

    # Sprint 19 — Drop Monitor
    drop_monitor_db_path: str = "data/domain_monitoring.db"
    monitored_domains_path: str = "scripts/monitored_domains.json"
    rdap_rate_limit: float = 3.0

    # Infrastructure
    database_url: str = "sqlite:///domainhunter.db"
    slack_webhook_url: str = ""
    alert_email: str = ""

    # Pipeline caps
    max_scout_candidates: int = Field(default=500, ge=1, le=10000)
    max_sentinel_survivors: int = Field(default=60, ge=1, le=1000)
    max_archivist_verified: int = Field(default=15, ge=1, le=500)
    max_spectre_scored: int = Field(default=5, ge=1, le=100)

    # Quality thresholds
    min_da_threshold: int = Field(default=25, ge=0, le=100)
    max_spam_score: float = Field(default=20.0, ge=0.0, le=100.0)
    min_archive_years: float = Field(default=3.0, ge=0.0, le=30.0)
    min_referring_domains: int = Field(default=100, ge=0, le=100000)
    min_branded_anchor_pct: float = Field(default=40.0, ge=0.0, le=100.0)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        assert isinstance(v, str), "database_url must be a string"
        assert len(v) > 0, "database_url must not be empty"
        return v


def load_settings() -> Settings:
    """Load and validate pipeline settings from environment.

    Returns:
        Frozen Settings instance with all configuration.
    """
    settings = Settings()
    assert isinstance(settings, Settings), "Settings failed to instantiate"
    assert settings.max_scout_candidates >= settings.max_sentinel_survivors, (
        f"Scout cap ({settings.max_scout_candidates}) must >= Sentinel cap "
        f"({settings.max_sentinel_survivors})"
    )
    return settings

import json
import logging
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


class Settings(BaseSettings):
    """Authoritative backend configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///backend/app/paper_trading.db"
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_pool_timeout: int = Field(default=30, ge=1, le=120)
    database_pool_recycle: int = Field(default=1800, ge=60)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    scanner_max_workers: int = Field(default=8, ge=1, le=16)
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"

    outlook_sec_enabled: bool = True
    outlook_sec_documents_enabled: bool = True
    outlook_sec_max_document_filings: int = Field(default=2, ge=1, le=3)
    outlook_fred_enabled: bool = True
    outlook_market_enabled: bool = True
    outlook_industry_enabled: bool = True
    outlook_fomc_enabled: bool = True
    outlook_fomc_cache_ttl: int = Field(default=1800, ge=60)
    outlook_macro_enabled: bool = True
    outlook_macro_cache_ttl: int = Field(default=3600, ge=300, le=21600)
    outlook_earnings_events_enabled: bool = True
    outlook_earnings_calendar_cache_ttl: int = Field(default=21600, ge=300, le=86400)
    outlook_geopolitical_enabled: bool = True
    outlook_geopolitical_cache_ttl: int = Field(default=21600, ge=300)
    outlook_industry_cache_ttl: int = Field(default=1800, ge=60)
    outlook_classification_cache_ttl: int = Field(default=604800, ge=3600)
    outlook_sec_user_agent: str = ""
    fred_api_key: SecretStr = SecretStr("")
    outlook_sec_cache_ttl: int = Field(default=3600, ge=60)
    outlook_cik_cache_ttl: int = Field(default=86400, ge=3600)
    outlook_sec_history_enabled: bool = False
    outlook_historical_revenue_enabled: bool = False
    outlook_historical_revenue_q4_derivation_enabled: bool = False
    outlook_sec_history_cache_ttl: int = Field(default=21600, ge=300, le=86400)
    outlook_sec_history_request_budget: int = Field(default=3, ge=2, le=3)
    outlook_sec_history_max_source_facts: int = Field(default=256, ge=32, le=1024)
    outlook_sec_history_max_quarters: int = Field(default=8, ge=1, le=8)
    outlook_sec_history_max_annual_periods: int = Field(default=5, ge=0, le=5)
    outlook_sec_q4_enabled: bool = False
    outlook_sec_q4_cache_ttl: int = Field(default=21600, ge=300, le=86400)
    outlook_sec_q4_request_budget: int = Field(default=4, ge=1, le=6)
    outlook_sec_q4_max_candidate_filings: int = Field(default=2, ge=1, le=4)
    outlook_sec_q4_documents_per_filing: int = Field(default=2, ge=1, le=2)
    outlook_sec_q4_document_max_bytes: int = Field(default=1048576, ge=65536, le=4194304)
    outlook_sec_q4_max_concurrency: int = Field(default=1, ge=1, le=2)
    outlook_economic_cache_ttl: int = Field(default=21600, ge=300)
    outlook_market_cache_ttl: int = Field(default=900, ge=60)
    outlook_failure_cache_ttl: int = Field(default=60, ge=10)
    outlook_http_timeout: float = Field(default=5, ge=1, le=15)
    outlook_http_attempts: int = Field(default=1, ge=1, le=2)
    outlook_sec_request_interval: float = Field(default=1, ge=1, le=60)
    outlook_llm_enabled: bool = False
    outlook_llm_provider: Literal["openai"] = "openai"
    outlook_llm_model: str = "gpt-5.4-mini"
    outlook_llm_timeout: float = Field(default=30, ge=5, le=120)
    outlook_llm_cache_ttl: int = Field(default=3600, ge=60, le=86400)
    openai_api_key: SecretStr = SecretStr("")

    supabase_auth_issuer: str | None = None
    supabase_auth_audience: str | None = None
    supabase_jwks_url: str | None = None

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "CORS_ORIGINS must be a comma-separated list or JSON array"
                    ) from exc
            else:
                value = raw.split(",")

        if not isinstance(value, (list, tuple)):
            raise ValueError("CORS_ORIGINS must be a comma-separated list or JSON array")

        origins = [str(origin).strip().rstrip("/") for origin in value]
        if any(not origin for origin in origins):
            raise ValueError("CORS_ORIGINS cannot contain empty origins")
        if any(origin == "*" for origin in origins):
            raise ValueError("CORS_ORIGINS must contain explicit origins, not '*'")
        return origins

    @model_validator(mode="after")
    def require_production_auth_configuration(self):
        if self.environment == "production" and not self.auth_configured:
            raise ValueError(
                "Production requires SUPABASE_AUTH_ISSUER, "
                "SUPABASE_AUTH_AUDIENCE, and SUPABASE_JWKS_URL"
            )
        return self

    @property
    def auth_configured(self) -> bool:
        return all(
            value and value.strip()
            for value in (
                self.supabase_auth_issuer,
                self.supabase_auth_audience,
                self.supabase_jwks_url,
            )
        )

    @property
    def log_level_value(self) -> int:
        return getattr(logging, self.log_level)


settings = Settings()

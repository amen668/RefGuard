"""RefGuard application configuration (Pydantic Settings)."""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="RefGuard", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Runtime environment"
    )

    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    cache_enabled: bool = Field(default=True, description="Enable cache")
    cache_ttl: int = Field(default=3600, description="Cache TTL seconds")
    cache_max_size: int = Field(default=1000, description="Max cache size")

    request_timeout: int = Field(default=30, description="Request timeout seconds")
    max_workers: int = Field(default=4, description="Max concurrent workers")

    # Per-source delays (seconds) - conservative defaults
    arxiv_rate_limit_delay: float = Field(default=3.0, description="arXiv: 1 req/3s")
    crossref_rate_limit_delay: float = Field(default=1.0, description="Crossref polite")
    semantic_scholar_rate_limit_delay: float = Field(default=1.0, description="S2")
    dblp_rate_limit_delay: float = Field(default=1.5, description="DBLP 1-2s")
    openalex_rate_limit_delay: float = Field(default=0.5, description="OpenAlex")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )
    log_format: Literal["json", "text"] = Field(default="text", description="Log format")
    log_file: str = Field(default="logs/refguard.log", description="Log file")

    semantic_scholar_api_key: str | None = Field(default=None, description="S2 API key")
    openalex_api_key: str | None = Field(default=None, description="OpenAlex API key, optional")
    crossref_mailto: str = Field(default="", description="Crossref polite pool email")

    # Optional LLM relevance checks. These are never used for identity decisions.
    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    refguard_telemetry: bool = Field(default=False, alias="REFGUARD_TELEMETRY")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()

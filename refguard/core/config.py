"""RefGuard 应用配置。"""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量和 .env 文件读取配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="RefGuard", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="运行环境"
    )

    api_host: str = Field(default="0.0.0.0", description="接口监听地址")
    api_port: int = Field(default=8000, description="接口端口")

    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=3600, description="缓存过期秒数")
    cache_max_size: int = Field(default=1000, description="缓存最大条目数")

    request_timeout: int = Field(default=30, description="请求超时秒数")
    max_workers: int = Field(default=4, description="最大并发任务数")

    # 各公开元数据源的保守请求间隔。
    arxiv_rate_limit_delay: float = Field(default=3.0, description="arXiv 请求间隔")
    crossref_rate_limit_delay: float = Field(default=1.0, description="Crossref 请求间隔")
    semantic_scholar_rate_limit_delay: float = Field(default=1.0, description="Semantic Scholar 请求间隔")
    dblp_rate_limit_delay: float = Field(default=1.5, description="DBLP 请求间隔")
    openalex_rate_limit_delay: float = Field(default=0.5, description="OpenAlex 请求间隔")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="日志级别"
    )
    log_format: Literal["json", "text"] = Field(default="text", description="日志格式")
    log_file: str = Field(default="logs/refguard.log", description="日志文件")

    semantic_scholar_api_key: str | None = Field(default=None, description="Semantic Scholar 可选访问密钥")
    openalex_api_key: str | None = Field(default=None, description="OpenAlex 可选访问密钥")
    crossref_mailto: str = Field(default="", description="Crossref 礼貌池邮箱")

    refguard_telemetry: bool = Field(default=False, alias="REFGUARD_TELEMETRY")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()

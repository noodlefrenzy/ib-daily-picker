"""
Configuration management using pydantic-settings.

PURPOSE: Centralized configuration from environment, TOML files, and CLI
DEPENDENCIES: pydantic-settings, toml

ARCHITECTURE NOTES:
Configuration hierarchy (highest to lowest priority):
1. CLI arguments (handled by Typer)
2. Environment variables
3. Config file (~/.ib-picker/config.toml or project .env)
4. Defaults
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import toml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_config_dir() -> Path:
    """Return the default configuration directory."""
    return Path.home() / ".ib-picker"


def get_default_data_dir() -> Path:
    """Return the default data directory."""
    return Path.home() / ".ib-picker" / "data"


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="IB_PICKER_DB_")

    # DuckDB for analytics (OHLCV, flow data)
    duckdb_path: Path = Field(
        default_factory=lambda: get_default_data_dir() / "analytics.duckdb",
        description="Path to DuckDB database for analytics data",
    )

    # SQLite for state (sync tracking, configuration)
    sqlite_path: Path = Field(
        default_factory=lambda: get_default_data_dir() / "state.sqlite",
        description="Path to SQLite database for application state",
    )

    @field_validator("duckdb_path", "sqlite_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand user home directory in paths."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v.expanduser()


class APISettings(BaseSettings):
    """External API settings."""

    model_config = SettingsConfigDict(env_prefix="IB_PICKER_")

    # Finnhub (fallback stock data)
    finnhub_api_key: str | None = Field(
        default=None,
        description="Finnhub API key for stock data fallback",
    )

    # Unusual Whales
    unusual_whales_api_key: str | None = Field(
        default=None,
        description="Unusual Whales API key for flow data",
    )

    # LLM settings
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL for local LLM",
    )
    llm_provider: str = Field(
        default="anthropic",
        description="LLM provider to use: 'anthropic' or 'ollama'",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="LLM model to use",
    )


class CacheSettings(BaseSettings):
    """Cache settings for API responses."""

    model_config = SettingsConfigDict(env_prefix="IB_PICKER_CACHE_")

    flow_cache_ttl_minutes: int = Field(
        default=15,
        description="Flow alert cache TTL in minutes",
    )
    stock_cache_ttl_hours: int = Field(
        default=24,
        description="Stock data cache TTL in hours",
    )


class RiskProfile(BaseSettings):
    """Risk profile for position sizing."""

    model_config = SettingsConfigDict(env_prefix="IB_PICKER_RISK_")

    name: str = Field(default="moderate", description="Risk profile name")
    risk_per_trade: Decimal = Field(
        default=Decimal("0.01"),
        description="Risk per trade as decimal (0.01 = 1%)",
    )
    min_risk_reward: Decimal = Field(
        default=Decimal("2.0"),
        description="Minimum risk/reward ratio",
    )
    max_positions: int = Field(
        default=8,
        description="Maximum concurrent positions",
    )
    max_sector_exposure: Decimal = Field(
        default=Decimal("0.30"),
        description="Maximum exposure to single sector (0.30 = 30%)",
    )


# Sector ETF mappings for comparison charts
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial": "XLF",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}

# Market benchmark for comparisons
MARKET_BENCHMARK = "SPY"


class BasketSettings(BaseSettings):
    """Stock basket configuration."""

    model_config = SettingsConfigDict(env_prefix="IB_PICKER_BASKET_")

    # Default tickers to track
    default_tickers: list[str] = Field(
        default_factory=lambda: [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "META",
            "TSLA",
            "JPM",
            "V",
            "UNH",
        ],
        description="Default stock tickers to track",
    )

    # Sector-based selection
    include_sectors: list[str] = Field(
        default_factory=list,
        description="Sectors to include (empty = all)",
    )
    exclude_sectors: list[str] = Field(
        default_factory=list,
        description="Sectors to exclude",
    )


class DiscordSettings(BaseSettings):
    """Discord bot configuration."""

    model_config = SettingsConfigDict(env_prefix="DISCORD_")

    token: str | None = Field(
        default=None,
        description="Discord bot token",
    )
    guild_id: int | None = Field(
        default=None,
        description="Discord guild ID for faster slash command sync (dev mode)",
    )
    daily_channel_id: int | None = Field(
        default=None,
        description="Channel ID for daily analysis posts",
    )
    daily_time: str = Field(
        default="09:30",
        description="Time for daily analysis (HH:MM in ET)",
    )
    daily_strategy: str = Field(
        default="example_rsi_flow",
        description="Strategy to use for daily analysis",
    )
    daily_enabled: bool = Field(
        default=True,
        description="Enable/disable daily scheduled analysis",
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="IB_PICKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    risk: RiskProfile = Field(default_factory=RiskProfile)
    basket: BasketSettings = Field(default_factory=BasketSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)

    # General settings
    config_dir: Path = Field(
        default_factory=get_default_config_dir,
        description="Configuration directory",
    )
    strategies_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "strategies",
        description="Directory containing strategy YAML files",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_api_calls: bool = Field(
        default=True,
        description="Log all external API calls with timing",
    )

    @classmethod
    def from_toml(cls, config_path: Path | None = None) -> Settings:
        """Load settings from TOML file, merging with defaults and env vars."""
        if config_path is None:
            config_path = get_default_config_dir() / "config.toml"

        toml_config: dict[str, Any] = {}
        if config_path.exists():
            toml_config = toml.load(config_path)

        return cls(**toml_config)

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.database.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        self.database.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.strategies_dir.mkdir(parents=True, exist_ok=True)

    def save_toml(self, config_path: Path | None = None) -> None:
        """Save current settings to TOML file."""
        if config_path is None:
            config_path = self.config_dir / "config.toml"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, handling nested models
        config_dict = self.model_dump(mode="json", exclude_none=True)

        # Convert Path objects to strings for TOML
        def path_to_str(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: path_to_str(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [path_to_str(v) for v in obj]
            if isinstance(obj, Path):
                return str(obj)
            return obj

        config_dict = path_to_str(config_dict)

        with open(config_path, "w") as f:
            toml.dump(config_dict, f)


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_toml()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None

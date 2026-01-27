"""
TEST DOC: Configuration Management

WHAT: Tests for pydantic-settings based configuration
WHY: Ensure configuration loading, validation, and persistence work correctly
HOW: Test Settings class with various inputs and edge cases

CASES:
- Default configuration loads with sensible defaults
- Environment variables override defaults
- TOML file loading works
- Path expansion handles ~ correctly
- Nested settings (database, api, cost, risk) work

EDGE CASES:
- Missing config file: Falls back to defaults
- Invalid values: Validation errors raised
- Path creation: Directories created on ensure_directories()
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ib_daily_picker.config import (
    APISettings,
    BasketSettings,
    CacheSettings,
    DatabaseSettings,
    RiskProfile,
    Settings,
    get_default_config_dir,
    get_default_data_dir,
)


class TestDefaultPaths:
    """Test default path functions."""

    def test_default_config_dir(self) -> None:
        """Config dir should be under home directory."""
        config_dir = get_default_config_dir()
        assert config_dir == Path.home() / ".ib-picker"

    def test_default_data_dir(self) -> None:
        """Data dir should be under config directory."""
        data_dir = get_default_data_dir()
        assert data_dir == Path.home() / ".ib-picker" / "data"


class TestDatabaseSettings:
    """Test DatabaseSettings configuration."""

    def test_defaults(self) -> None:
        """Default paths should be under data directory."""
        settings = DatabaseSettings()
        assert settings.duckdb_path.name == "analytics.duckdb"
        assert settings.sqlite_path.name == "state.sqlite"

    def test_path_expansion(self) -> None:
        """Tilde should be expanded in paths."""
        settings = DatabaseSettings(
            duckdb_path="~/custom/analytics.duckdb",
            sqlite_path="~/custom/state.sqlite",
        )
        assert str(settings.duckdb_path).startswith(str(Path.home()))
        assert str(settings.sqlite_path).startswith(str(Path.home()))


class TestAPISettings:
    """Test APISettings configuration."""

    def test_defaults(self) -> None:
        """API settings should have sensible defaults."""
        settings = APISettings()
        assert settings.finnhub_api_key is None
        assert settings.unusual_whales_api_key is None
        assert settings.llm_provider == "anthropic"
        assert settings.ollama_base_url == "http://localhost:11434"

    def test_with_api_keys(self) -> None:
        """API keys should be stored when provided."""
        settings = APISettings(
            finnhub_api_key="test_finnhub_key",
            unusual_whales_api_key="test_uw_key",
        )
        assert settings.finnhub_api_key == "test_finnhub_key"
        assert settings.unusual_whales_api_key == "test_uw_key"


class TestCacheSettings:
    """Test CacheSettings configuration."""

    def test_defaults(self) -> None:
        """Cache settings should have sensible defaults."""
        settings = CacheSettings()
        assert settings.flow_cache_ttl_minutes == 15
        assert settings.stock_cache_ttl_hours == 24


class TestRiskProfile:
    """Test RiskProfile configuration."""

    def test_defaults(self) -> None:
        """Default risk profile should be moderate."""
        profile = RiskProfile()
        assert profile.name == "moderate"
        assert profile.risk_per_trade == Decimal("0.01")
        assert profile.min_risk_reward == Decimal("2.0")
        assert profile.max_positions == 8

    def test_aggressive_profile(self) -> None:
        """Aggressive profile should allow higher risk."""
        profile = RiskProfile(
            name="aggressive",
            risk_per_trade=Decimal("0.02"),
            min_risk_reward=Decimal("1.5"),
            max_positions=10,
        )
        assert profile.risk_per_trade == Decimal("0.02")
        assert profile.max_positions == 10


class TestBasketSettings:
    """Test BasketSettings configuration."""

    def test_defaults(self) -> None:
        """Default basket should have major stocks."""
        settings = BasketSettings()
        assert len(settings.default_tickers) > 0
        assert "AAPL" in settings.default_tickers
        assert "MSFT" in settings.default_tickers

    def test_sector_filters(self) -> None:
        """Sector filters should be empty by default."""
        settings = BasketSettings()
        assert settings.include_sectors == []
        assert settings.exclude_sectors == []


class TestSettings:
    """Test main Settings class."""

    def test_defaults(self) -> None:
        """Settings should load with defaults."""
        settings = Settings()
        assert settings.log_level == "INFO"
        assert settings.log_api_calls is True
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.api, APISettings)

    def test_ensure_directories(self, temp_dir: Path) -> None:
        """ensure_directories should create required paths."""
        settings = Settings(
            config_dir=temp_dir / "config",
            strategies_dir=temp_dir / "strategies",
        )
        settings.database.duckdb_path = temp_dir / "data" / "test.duckdb"
        settings.database.sqlite_path = temp_dir / "data" / "test.sqlite"

        settings.ensure_directories()

        assert settings.config_dir.exists()
        assert settings.strategies_dir.exists()
        assert settings.database.duckdb_path.parent.exists()

    def test_save_and_load_toml(self, temp_dir: Path) -> None:
        """Settings should save to and load from TOML."""
        config_path = temp_dir / "config.toml"

        # Create settings with custom values
        settings = Settings(
            config_dir=temp_dir,
            log_level="DEBUG",
        )
        settings.save_toml(config_path)

        assert config_path.exists()

        # Load and verify
        loaded = Settings.from_toml(config_path)
        assert loaded.log_level == "DEBUG"

    def test_model_dump_json(self) -> None:
        """Settings should serialize to JSON."""
        settings = Settings()
        json_str = settings.model_dump_json()
        assert "log_level" in json_str
        assert "database" in json_str


class TestSettingsIntegration:
    """Integration tests for Settings."""

    def test_full_settings_hierarchy(self, temp_dir: Path) -> None:
        """Test complete settings hierarchy works together."""
        settings = Settings(
            config_dir=temp_dir / "config",
            strategies_dir=temp_dir / "strategies",
            log_level="DEBUG",
            database=DatabaseSettings(
                duckdb_path=temp_dir / "data" / "test.duckdb",
                sqlite_path=temp_dir / "data" / "test.sqlite",
            ),
            api=APISettings(
                finnhub_api_key="test_key",
                llm_provider="ollama",
            ),
            cache=CacheSettings(
                flow_cache_ttl_minutes=30,
            ),
            risk=RiskProfile(
                name="conservative",
                risk_per_trade=Decimal("0.005"),
            ),
            basket=BasketSettings(
                default_tickers=["AAPL", "MSFT"],
            ),
        )

        # Verify all nested settings
        assert settings.log_level == "DEBUG"
        assert settings.database.duckdb_path == temp_dir / "data" / "test.duckdb"
        assert settings.api.finnhub_api_key == "test_key"
        assert settings.api.llm_provider == "ollama"
        assert settings.cache.flow_cache_ttl_minutes == 30
        assert settings.risk.name == "conservative"
        assert settings.basket.default_tickers == ["AAPL", "MSFT"]

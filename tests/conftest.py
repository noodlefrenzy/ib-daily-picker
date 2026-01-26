"""
Shared test fixtures for IB Daily Picker.

PURPOSE: Provide common fixtures for database, config, and mocks
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from ib_daily_picker.config import Settings, reset_settings
from ib_daily_picker.store.database import DatabaseManager, reset_db_manager


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Generator[Settings, None, None]:
    """Create test settings with temporary directories."""
    reset_settings()

    settings = Settings(
        config_dir=temp_dir / "config",
        strategies_dir=temp_dir / "strategies",
        database=Settings.model_fields["database"].default_factory(),
        api=Settings.model_fields["api"].default_factory(),
        cost=Settings.model_fields["cost"].default_factory(),
        risk=Settings.model_fields["risk"].default_factory(),
        basket=Settings.model_fields["basket"].default_factory(),
    )

    # Override database paths
    settings.database.duckdb_path = temp_dir / "data" / "test.duckdb"
    settings.database.sqlite_path = temp_dir / "data" / "test.sqlite"

    settings.ensure_directories()

    yield settings

    reset_settings()


@pytest.fixture
def test_db(test_settings: Settings) -> Generator[DatabaseManager, None, None]:
    """Create test database manager with temporary databases."""
    reset_db_manager()

    db = DatabaseManager(test_settings)
    db.initialize()

    yield db

    reset_db_manager()


@pytest.fixture
def sample_tickers() -> list[str]:
    """Return sample ticker list for testing."""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]


@pytest.fixture
def sample_ohlcv_data() -> list[dict]:
    """Return sample OHLCV data for testing."""
    from decimal import Decimal

    return [
        {
            "symbol": "AAPL",
            "trade_date": "2024-01-02",
            "open_price": Decimal("185.50"),
            "high_price": Decimal("186.75"),
            "low_price": Decimal("184.25"),
            "close_price": Decimal("186.00"),
            "volume": 50000000,
            "adjusted_close": Decimal("186.00"),
        },
        {
            "symbol": "AAPL",
            "trade_date": "2024-01-03",
            "open_price": Decimal("186.00"),
            "high_price": Decimal("187.50"),
            "low_price": Decimal("185.00"),
            "close_price": Decimal("185.50"),
            "volume": 45000000,
            "adjusted_close": Decimal("185.50"),
        },
        {
            "symbol": "MSFT",
            "trade_date": "2024-01-02",
            "open_price": Decimal("375.00"),
            "high_price": Decimal("378.50"),
            "low_price": Decimal("374.00"),
            "close_price": Decimal("377.50"),
            "volume": 25000000,
            "adjusted_close": Decimal("377.50"),
        },
    ]


@pytest.fixture
def sample_flow_alert() -> dict:
    """Return sample flow alert data for testing."""
    from decimal import Decimal

    return {
        "id": "alert_001",
        "symbol": "AAPL",
        "alert_time": "2024-01-03T14:30:00Z",
        "alert_type": "unusual_volume",
        "direction": "bullish",
        "premium": Decimal("500000.00"),
        "volume": 1000,
        "open_interest": 5000,
        "strike": Decimal("190.00"),
        "expiration": "2024-02-16",
        "option_type": "call",
        "sentiment": "bullish",
    }

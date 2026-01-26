"""
TEST DOC: Stock Domain Models

WHAT: Tests for OHLCV and StockMetadata models
WHY: Ensure price data is correctly validated and calculated
HOW: Test construction, validation, and computed properties

CASES:
- Valid OHLCV data is accepted
- Invalid OHLCV relationships are rejected
- Decimal precision is maintained
- Computed properties work correctly

EDGE CASES:
- Zero volume handled
- Negative prices rejected
- Symbol normalization to uppercase
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ib_daily_picker.models.stock import OHLCV, OHLCVBatch, StockMetadata


class TestOHLCV:
    """Tests for OHLCV model."""

    def test_valid_ohlcv(self) -> None:
        """Valid OHLCV data should be accepted."""
        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.50"),
            high_price=Decimal("186.75"),
            low_price=Decimal("184.25"),
            close_price=Decimal("186.00"),
            volume=50000000,
        )

        assert ohlcv.symbol == "AAPL"
        assert ohlcv.open_price == Decimal("185.50")
        assert ohlcv.volume == 50000000

    def test_symbol_uppercase(self) -> None:
        """Symbol should be normalized to uppercase."""
        ohlcv = OHLCV(
            symbol="aapl",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.50"),
            high_price=Decimal("186.75"),
            low_price=Decimal("184.25"),
            close_price=Decimal("186.00"),
            volume=50000000,
        )

        assert ohlcv.symbol == "AAPL"

    def test_float_to_decimal_conversion(self) -> None:
        """Float values should be converted to Decimal."""
        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=185.50,
            high_price=186.75,
            low_price=184.25,
            close_price=186.00,
            volume=50000000,
        )

        assert isinstance(ohlcv.open_price, Decimal)
        assert ohlcv.open_price == Decimal("185.5")

    def test_low_greater_than_high_rejected(self) -> None:
        """Low cannot be greater than high."""
        with pytest.raises(ValueError, match="Low .* cannot be greater than high"):
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 2),
                open_price=Decimal("185.50"),
                high_price=Decimal("184.00"),  # High lower than low
                low_price=Decimal("186.00"),
                close_price=Decimal("185.00"),
                volume=50000000,
            )

    def test_open_outside_range_rejected(self) -> None:
        """Open must be between low and high."""
        with pytest.raises(ValueError, match="Open .* must be between"):
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 2),
                open_price=Decimal("190.00"),  # Outside range
                high_price=Decimal("186.00"),
                low_price=Decimal("184.00"),
                close_price=Decimal("185.00"),
                volume=50000000,
            )

    def test_change_property(self) -> None:
        """Change should be close - open."""
        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.00"),
            high_price=Decimal("187.00"),
            low_price=Decimal("184.00"),
            close_price=Decimal("186.50"),
            volume=50000000,
        )

        assert ohlcv.change == Decimal("1.50")

    def test_change_percent_property(self) -> None:
        """Change percent should be calculated correctly."""
        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=50000000,
        )

        assert ohlcv.change_percent == Decimal("5.0")

    def test_is_bullish_property(self) -> None:
        """is_bullish should be True when close > open."""
        bullish = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("100.00"),
            high_price=Decimal("105.00"),
            low_price=Decimal("99.00"),
            close_price=Decimal("104.00"),
            volume=50000000,
        )

        bearish = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("100.00"),
            high_price=Decimal("101.00"),
            low_price=Decimal("96.00"),
            close_price=Decimal("97.00"),
            volume=50000000,
        )

        assert bullish.is_bullish is True
        assert bearish.is_bullish is False

    def test_price_range_property(self) -> None:
        """Range should be high - low."""
        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            close_price=Decimal("105.00"),
            volume=50000000,
        )

        assert ohlcv.price_range == Decimal("15.00")


class TestOHLCVBatch:
    """Tests for OHLCVBatch model."""

    def test_empty_batch(self) -> None:
        """Empty batch should have None date range."""
        batch = OHLCVBatch(symbol="AAPL", data=[])
        assert batch.date_range is None
        assert batch.count == 0

    def test_batch_with_data(self) -> None:
        """Batch should track date range and count."""
        data = [
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 2),
                open_price=Decimal("185.00"),
                high_price=Decimal("186.00"),
                low_price=Decimal("184.00"),
                close_price=Decimal("185.50"),
                volume=50000000,
            ),
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 3),
                open_price=Decimal("185.50"),
                high_price=Decimal("187.00"),
                low_price=Decimal("185.00"),
                close_price=Decimal("186.50"),
                volume=45000000,
            ),
        ]

        batch = OHLCVBatch(symbol="AAPL", data=data)
        assert batch.count == 2
        assert batch.date_range == (date(2024, 1, 2), date(2024, 1, 3))


class TestStockMetadata:
    """Tests for StockMetadata model."""

    def test_minimal_metadata(self) -> None:
        """Metadata with just symbol should work."""
        meta = StockMetadata(symbol="AAPL")
        assert meta.symbol == "AAPL"
        assert meta.name is None
        assert meta.currency == "USD"

    def test_full_metadata(self) -> None:
        """Metadata with all fields should work."""
        meta = StockMetadata(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            market_cap=3000000000000,
            exchange="NASDAQ",
        )

        assert meta.name == "Apple Inc."
        assert meta.sector == "Technology"
        assert meta.market_cap == 3000000000000

    def test_symbol_uppercase(self) -> None:
        """Symbol should be normalized to uppercase."""
        meta = StockMetadata(symbol="aapl")
        assert meta.symbol == "AAPL"

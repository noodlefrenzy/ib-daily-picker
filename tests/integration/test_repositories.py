"""
TEST DOC: Repository Integration Tests

WHAT: Tests for database round-trips through repositories
WHY: Ensure data is correctly persisted and retrieved
HOW: Use test database fixtures, write and read data

CASES:
- OHLCV data round-trips correctly
- Flow alerts preserve all fields
- Recommendations maintain status
- Trades calculate metrics on close

EDGE CASES:
- Duplicate inserts (upsert behavior)
- Empty result sets
- Decimal precision preserved
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from ib_daily_picker.models import (
    OHLCV,
    AlertType,
    FlowAlert,
    FlowDirection,
    OptionType,
    Recommendation,
    RecommendationStatus,
    Sentiment,
    SignalType,
    Trade,
    TradeDirection,
    TradeStatus,
)
from ib_daily_picker.store import (
    FlowRepository,
    RecommendationRepository,
    StockRepository,
    TradeRepository,
    generate_id,
)
from ib_daily_picker.store.database import DatabaseManager


class TestStockRepository:
    """Tests for StockRepository."""

    def test_save_and_get_ohlcv(self, test_db: DatabaseManager) -> None:
        """OHLCV data should round-trip correctly."""
        repo = StockRepository(test_db)

        ohlcv = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.50"),
            high_price=Decimal("186.75"),
            low_price=Decimal("184.25"),
            close_price=Decimal("186.00"),
            volume=50000000,
            adjusted_close=Decimal("186.00"),
        )

        repo.save_ohlcv(ohlcv)
        result = repo.get_ohlcv("AAPL")

        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].open_price == Decimal("185.5")
        assert result[0].close_price == Decimal("186.0")
        assert result[0].volume == 50000000

    def test_save_batch(self, test_db: DatabaseManager) -> None:
        """Batch save should persist multiple records."""
        repo = StockRepository(test_db)

        records = [
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

        count = repo.save_ohlcv_batch(records)
        assert count == 2

        result = repo.get_ohlcv("AAPL")
        assert len(result) == 2

    def test_upsert_behavior(self, test_db: DatabaseManager) -> None:
        """Saving same date twice should update, not duplicate."""
        repo = StockRepository(test_db)

        ohlcv1 = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.00"),
            high_price=Decimal("186.00"),
            low_price=Decimal("184.00"),
            close_price=Decimal("185.50"),
            volume=50000000,
        )

        ohlcv2 = OHLCV(
            symbol="AAPL",
            trade_date=date(2024, 1, 2),
            open_price=Decimal("185.00"),
            high_price=Decimal("186.00"),
            low_price=Decimal("184.00"),
            close_price=Decimal("186.00"),  # Updated close
            volume=50000000,
        )

        repo.save_ohlcv(ohlcv1)
        repo.save_ohlcv(ohlcv2)

        result = repo.get_ohlcv("AAPL")
        assert len(result) == 1
        assert result[0].close_price == Decimal("186.0")

    def test_date_filtering(self, test_db: DatabaseManager) -> None:
        """Date filters should work correctly."""
        repo = StockRepository(test_db)

        records = [
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 1),
                open_price=Decimal("184.00"),
                high_price=Decimal("185.00"),
                low_price=Decimal("183.00"),
                close_price=Decimal("184.50"),
                volume=40000000,
            ),
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
        repo.save_ohlcv_batch(records)

        result = repo.get_ohlcv("AAPL", start_date=date(2024, 1, 2))
        assert len(result) == 2

        result = repo.get_ohlcv(
            "AAPL", start_date=date(2024, 1, 2), end_date=date(2024, 1, 2)
        )
        assert len(result) == 1

    def test_get_latest_date(self, test_db: DatabaseManager) -> None:
        """get_latest_date should return most recent date."""
        repo = StockRepository(test_db)

        records = [
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 1),
                open_price=Decimal("184.00"),
                high_price=Decimal("185.00"),
                low_price=Decimal("183.00"),
                close_price=Decimal("184.50"),
                volume=40000000,
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
        repo.save_ohlcv_batch(records)

        latest = repo.get_latest_date("AAPL")
        assert latest == date(2024, 1, 3)

    def test_get_symbols(self, test_db: DatabaseManager) -> None:
        """get_symbols should return all unique symbols."""
        repo = StockRepository(test_db)

        records = [
            OHLCV(
                symbol="AAPL",
                trade_date=date(2024, 1, 1),
                open_price=Decimal("184.00"),
                high_price=Decimal("185.00"),
                low_price=Decimal("183.00"),
                close_price=Decimal("184.50"),
                volume=40000000,
            ),
            OHLCV(
                symbol="MSFT",
                trade_date=date(2024, 1, 1),
                open_price=Decimal("375.00"),
                high_price=Decimal("378.00"),
                low_price=Decimal("374.00"),
                close_price=Decimal("377.00"),
                volume=25000000,
            ),
        ]
        repo.save_ohlcv_batch(records)

        symbols = repo.get_symbols()
        assert set(symbols) == {"AAPL", "MSFT"}


class TestFlowRepository:
    """Tests for FlowRepository."""

    def test_save_and_get_alert(self, test_db: DatabaseManager) -> None:
        """Flow alert should round-trip correctly."""
        repo = FlowRepository(test_db)

        alert = FlowAlert(
            id="alert_001",
            symbol="AAPL",
            alert_time=datetime(2024, 1, 3, 14, 30, 0),
            alert_type=AlertType.UNUSUAL_VOLUME,
            direction=FlowDirection.BULLISH,
            premium=Decimal("500000.00"),
            volume=1000,
            open_interest=5000,
            strike=Decimal("190.00"),
            expiration=date(2024, 2, 16),
            option_type=OptionType.CALL,
            sentiment=Sentiment.BULLISH,
        )

        repo.save(alert)
        result = repo.get_by_symbol("AAPL")

        assert len(result) == 1
        assert result[0].id == "alert_001"
        assert result[0].premium == Decimal("500000.0")
        assert result[0].direction == FlowDirection.BULLISH

    def test_batch_save(self, test_db: DatabaseManager) -> None:
        """Batch save should persist multiple alerts."""
        repo = FlowRepository(test_db)

        alerts = [
            FlowAlert(
                id="alert_001",
                symbol="AAPL",
                alert_time=datetime(2024, 1, 3, 14, 30, 0),
                alert_type=AlertType.UNUSUAL_VOLUME,
                direction=FlowDirection.BULLISH,
                premium=Decimal("500000.00"),
            ),
            FlowAlert(
                id="alert_002",
                symbol="AAPL",
                alert_time=datetime(2024, 1, 3, 15, 0, 0),
                alert_type=AlertType.GOLDEN_SWEEP,
                direction=FlowDirection.BULLISH,
                premium=Decimal("1000000.00"),
            ),
        ]

        count = repo.save_batch(alerts)
        assert count == 2

        result = repo.get_by_symbol("AAPL")
        assert len(result) == 2

    def test_get_recent_with_premium_filter(self, test_db: DatabaseManager) -> None:
        """get_recent should filter by minimum premium."""
        repo = FlowRepository(test_db)

        alerts = [
            FlowAlert(
                id="alert_001",
                symbol="AAPL",
                alert_time=datetime(2024, 1, 3, 14, 30, 0),
                alert_type=AlertType.UNUSUAL_VOLUME,
                premium=Decimal("100000.00"),
            ),
            FlowAlert(
                id="alert_002",
                symbol="MSFT",
                alert_time=datetime(2024, 1, 3, 15, 0, 0),
                alert_type=AlertType.GOLDEN_SWEEP,
                premium=Decimal("500000.00"),
            ),
        ]
        repo.save_batch(alerts)

        result = repo.get_recent(min_premium=Decimal("200000"))
        assert len(result) == 1
        assert result[0].id == "alert_002"


class TestRecommendationRepository:
    """Tests for RecommendationRepository."""

    def test_save_and_get(self, test_db: DatabaseManager) -> None:
        """Recommendation should round-trip correctly."""
        repo = RecommendationRepository(test_db)

        rec = Recommendation(
            id=generate_id(),
            symbol="AAPL",
            strategy_name="RSI_Flow",
            signal_type=SignalType.BUY,
            entry_price=Decimal("185.00"),
            stop_loss=Decimal("180.00"),
            take_profit=Decimal("195.00"),
            confidence=Decimal("0.75"),
            reasoning="RSI oversold with bullish flow",
        )

        rec_id = repo.save(rec)
        result = repo.get_by_id(rec_id)

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.confidence == Decimal("0.75")
        assert result.status == RecommendationStatus.PENDING

    def test_get_pending(self, test_db: DatabaseManager) -> None:
        """get_pending should return only pending recommendations."""
        repo = RecommendationRepository(test_db)

        rec1 = Recommendation(
            id=generate_id(),
            symbol="AAPL",
            strategy_name="RSI_Flow",
            signal_type=SignalType.BUY,
            status=RecommendationStatus.PENDING,
        )
        rec2 = Recommendation(
            id=generate_id(),
            symbol="MSFT",
            strategy_name="RSI_Flow",
            signal_type=SignalType.BUY,
            status=RecommendationStatus.EXECUTED,
        )

        repo.save(rec1)
        repo.save(rec2)

        result = repo.get_pending()
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_update_status(self, test_db: DatabaseManager) -> None:
        """update_status should change recommendation status."""
        repo = RecommendationRepository(test_db)

        rec = Recommendation(
            id=generate_id(),
            symbol="AAPL",
            strategy_name="RSI_Flow",
            signal_type=SignalType.BUY,
        )
        rec_id = repo.save(rec)

        repo.update_status(rec_id, RecommendationStatus.EXECUTED)

        result = repo.get_by_id(rec_id)
        assert result is not None
        assert result.status == RecommendationStatus.EXECUTED


class TestTradeRepository:
    """Tests for TradeRepository."""

    def test_save_and_get(self, test_db: DatabaseManager) -> None:
        """Trade should round-trip correctly."""
        repo = TradeRepository(test_db)

        trade = Trade(
            id=generate_id(),
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("185.00"),
            entry_time=datetime(2024, 1, 3, 10, 30, 0),
            position_size=Decimal("100"),
            stop_loss=Decimal("180.00"),
            take_profit=Decimal("195.00"),
        )

        trade_id = repo.save(trade)
        result = repo.get_by_id(trade_id)

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.entry_price == Decimal("185.0")
        assert result.status == TradeStatus.OPEN

    def test_get_open_trades(self, test_db: DatabaseManager) -> None:
        """get_open should return only open trades."""
        repo = TradeRepository(test_db)

        open_trade = Trade(
            id=generate_id(),
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("185.00"),
            entry_time=datetime(2024, 1, 3, 10, 30, 0),
            position_size=Decimal("100"),
            status=TradeStatus.OPEN,
        )

        closed_trade = Trade(
            id=generate_id(),
            symbol="MSFT",
            direction=TradeDirection.LONG,
            entry_price=Decimal("375.00"),
            entry_time=datetime(2024, 1, 2, 10, 30, 0),
            exit_price=Decimal("380.00"),
            exit_time=datetime(2024, 1, 3, 14, 0, 0),
            position_size=Decimal("50"),
            status=TradeStatus.CLOSED,
        )

        repo.save(open_trade)
        repo.save(closed_trade)

        result = repo.get_open()
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_get_closed_with_date_filter(self, test_db: DatabaseManager) -> None:
        """get_closed should filter by date range."""
        repo = TradeRepository(test_db)

        trades = [
            Trade(
                id=generate_id(),
                symbol="AAPL",
                direction=TradeDirection.LONG,
                entry_price=Decimal("185.00"),
                entry_time=datetime(2024, 1, 1, 10, 30, 0),
                exit_price=Decimal("190.00"),
                exit_time=datetime(2024, 1, 1, 14, 0, 0),
                position_size=Decimal("100"),
                status=TradeStatus.CLOSED,
            ),
            Trade(
                id=generate_id(),
                symbol="MSFT",
                direction=TradeDirection.LONG,
                entry_price=Decimal("375.00"),
                entry_time=datetime(2024, 1, 5, 10, 30, 0),
                exit_price=Decimal("380.00"),
                exit_time=datetime(2024, 1, 5, 14, 0, 0),
                position_size=Decimal("50"),
                status=TradeStatus.CLOSED,
            ),
        ]

        for trade in trades:
            repo.save(trade)

        result = repo.get_closed(start_date=date(2024, 1, 3))
        assert len(result) == 1
        assert result[0].symbol == "MSFT"

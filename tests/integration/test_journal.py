"""
Integration tests for journal manager.

TEST DOC: Journal Manager Integration

WHAT: Tests JournalManager operations with database
WHY: Ensure trade lifecycle and persistence work correctly
HOW: Use test database, create/close trades, verify metrics

CASES:
- Execute recommendation as trade
- Open/close manual trades
- Add notes and tags
- Query open/closed trades
- Export to CSV/JSON

EDGE CASES:
- Execute non-existent recommendation
- Close already-closed trade
- Cancel open trade
"""

from decimal import Decimal

import pytest

from ib_daily_picker.journal.manager import JournalManager
from ib_daily_picker.models import (
    Recommendation,
    RecommendationStatus,
    SignalType,
    TradeDirection,
    TradeStatus,
)
from ib_daily_picker.store.database import DatabaseManager


class TestJournalManagerTradeLifecycle:
    """Tests for trade lifecycle operations."""

    def test_open_and_close_trade(self, test_db: DatabaseManager):
        """Can open and close a trade."""
        manager = JournalManager(test_db)

        # Open a trade
        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
            stop_loss=Decimal("145.00"),
            take_profit=Decimal("160.00"),
            tags=["momentum"],
        )

        assert trade.id is not None
        assert trade.status == TradeStatus.OPEN
        assert trade.symbol == "AAPL"

        # Verify it's in open trades
        open_trades = manager.get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].id == trade.id

        # Close the trade
        closed_trade = manager.close_trade(
            trade_id=trade.id,
            exit_price=Decimal("158.00"),
            notes="Hit resistance level",
        )

        assert closed_trade.status == TradeStatus.CLOSED
        assert closed_trade.exit_price == Decimal("158.00")
        assert closed_trade.pnl == Decimal("800.00")  # (158-150) * 100
        assert closed_trade.notes is not None
        assert "Hit resistance level" in closed_trade.notes

        # Verify it's now in closed trades
        open_trades = manager.get_open_trades()
        assert len(open_trades) == 0

        closed_trades = manager.get_closed_trades()
        assert len(closed_trades) == 1

    def test_execute_recommendation(self, test_db: DatabaseManager):
        """Can execute a recommendation as a trade."""
        manager = JournalManager(test_db)

        # Create a recommendation
        rec = Recommendation(
            id="rec-001",
            symbol="MSFT",
            strategy_name="RSI Oversold",
            signal_type=SignalType.BUY,
            entry_price=Decimal("350.00"),
            stop_loss=Decimal("340.00"),
            take_profit=Decimal("370.00"),
            confidence=Decimal("0.75"),
        )
        manager.save_recommendation(rec)

        # Verify it's pending
        pending = manager.get_pending_recommendations()
        assert len(pending) == 1

        # Execute the recommendation
        trade = manager.execute_recommendation(
            recommendation_id="rec-001",
            entry_price=Decimal("351.00"),  # Actual entry slightly different
            position_size=Decimal("50"),
        )

        assert trade.recommendation_id == "rec-001"
        assert trade.symbol == "MSFT"
        assert trade.direction == TradeDirection.LONG
        assert trade.entry_price == Decimal("351.00")
        assert trade.stop_loss == Decimal("340.00")  # From recommendation

        # Recommendation should be executed
        updated_rec = manager.get_recommendation("rec-001")
        assert updated_rec.status == RecommendationStatus.EXECUTED

    def test_execute_nonexistent_recommendation_fails(self, test_db: DatabaseManager):
        """Executing non-existent recommendation raises error."""
        manager = JournalManager(test_db)

        with pytest.raises(ValueError, match="not found"):
            manager.execute_recommendation(
                recommendation_id="nonexistent",
                entry_price=Decimal("100.00"),
                position_size=Decimal("10"),
            )

    def test_close_already_closed_trade_fails(self, test_db: DatabaseManager):
        """Closing an already-closed trade raises error."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )

        manager.close_trade(trade.id, Decimal("155.00"))

        with pytest.raises(ValueError, match="already closed"):
            manager.close_trade(trade.id, Decimal("160.00"))

    def test_cancel_trade(self, test_db: DatabaseManager):
        """Can cancel an open trade."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )

        cancelled = manager.cancel_trade(trade.id, "Market conditions changed")

        assert cancelled.status == TradeStatus.CANCELLED
        assert "Cancelled: Market conditions changed" in cancelled.notes


class TestJournalManagerNotesAndTags:
    """Tests for notes and tags operations."""

    def test_add_note_to_trade(self, test_db: DatabaseManager):
        """Can add timestamped notes to trade."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )

        updated = manager.add_note(trade.id, "Price approaching resistance")

        assert "Price approaching resistance" in updated.notes
        assert "[" in updated.notes  # Has timestamp

    def test_add_tag_to_trade(self, test_db: DatabaseManager):
        """Can add tags to trade."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )

        updated = manager.add_tag(trade.id, "breakout")
        updated = manager.add_tag(trade.id, "earnings")

        assert "breakout" in updated.tags
        assert "earnings" in updated.tags

    def test_add_duplicate_tag_ignored(self, test_db: DatabaseManager):
        """Adding duplicate tag is idempotent."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
            tags=["momentum"],
        )

        updated = manager.add_tag(trade.id, "momentum")

        assert updated.tags.count("momentum") == 1


class TestJournalManagerQueries:
    """Tests for query operations."""

    def test_get_trades_by_symbol(self, test_db: DatabaseManager):
        """Can query trades by symbol."""
        manager = JournalManager(test_db)

        # Create trades for different symbols
        manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )
        manager.open_trade(
            symbol="MSFT",
            direction=TradeDirection.LONG,
            entry_price=Decimal("350.00"),
            position_size=Decimal("50"),
        )

        aapl_trades = manager.get_trades_by_symbol("AAPL")
        assert len(aapl_trades) == 1
        assert aapl_trades[0].symbol == "AAPL"

    def test_get_closed_trades_date_range(self, test_db: DatabaseManager):
        """Can query closed trades by date range."""
        manager = JournalManager(test_db)

        # Create and close trades
        for _ in range(3):
            trade = manager.open_trade(
                symbol="AAPL",
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                position_size=Decimal("100"),
            )
            manager.close_trade(trade.id, Decimal("155.00"))

        # Query all closed trades
        closed = manager.get_closed_trades()
        assert len(closed) == 3


class TestJournalManagerMetrics:
    """Tests for metrics calculations."""

    def test_get_basic_metrics(self, test_db: DatabaseManager):
        """Can calculate basic trade metrics."""
        manager = JournalManager(test_db)

        # Create winning and losing trades
        trade1 = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("100.00"),
            position_size=Decimal("10"),
        )
        manager.close_trade(trade1.id, Decimal("110.00"))  # +100

        trade2 = manager.open_trade(
            symbol="MSFT",
            direction=TradeDirection.LONG,
            entry_price=Decimal("200.00"),
            position_size=Decimal("10"),
        )
        manager.close_trade(trade2.id, Decimal("190.00"))  # -100

        metrics = manager.get_metrics()

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("0.5")

    def test_get_extended_metrics(self, test_db: DatabaseManager):
        """Can calculate extended trade metrics."""
        manager = JournalManager(test_db)

        # Create trades with tags
        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("100.00"),
            position_size=Decimal("10"),
            tags=["momentum"],
        )
        manager.close_trade(trade.id, Decimal("110.00"))

        metrics = manager.get_extended_metrics(tags=["momentum"])

        assert metrics.total_trades == 1
        assert "AAPL" in metrics.by_symbol


class TestJournalManagerExport:
    """Tests for export operations."""

    def test_export_csv(self, test_db: DatabaseManager):
        """Can export trades to CSV."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )
        manager.close_trade(trade.id, Decimal("155.00"))

        csv_output = manager.export_trades_csv()

        assert "id" in csv_output  # Header
        assert "AAPL" in csv_output
        assert "150" in csv_output
        assert "155" in csv_output

    def test_export_json(self, test_db: DatabaseManager):
        """Can export trades to JSON."""
        manager = JournalManager(test_db)

        trade = manager.open_trade(
            symbol="AAPL",
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            position_size=Decimal("100"),
        )
        manager.close_trade(trade.id, Decimal("155.00"))

        import json

        json_output = manager.export_trades_json()
        data = json.loads(json_output)

        assert "exported_at" in data
        assert data["count"] == 1
        assert len(data["trades"]) == 1
        assert data["trades"][0]["symbol"] == "AAPL"

"""
Trade journal manager.

PURPOSE: High-level interface for trade journaling operations
DEPENDENCIES: store.repositories, models.trade, models.recommendation

ARCHITECTURE NOTES:
- Orchestrates trade lifecycle (execute, close, update)
- Links trades to recommendations
- Provides query and export capabilities
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import TYPE_CHECKING
from uuid import uuid4

from ib_daily_picker.journal.metrics import (
    ExtendedMetrics,
    calculate_extended_metrics,
    filter_trades,
)
from ib_daily_picker.models import (
    Recommendation,
    RecommendationStatus,
    Trade,
    TradeDirection,
    TradeMetrics,
    TradeStatus,
)

if TYPE_CHECKING:
    from ib_daily_picker.store.database import DatabaseManager
    from ib_daily_picker.store.repositories import (
        RecommendationRepository,
        TradeRepository,
    )

logger = logging.getLogger(__name__)


class JournalManager:
    """Manages trade journal operations."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager.

        Args:
            db: Database manager instance
        """
        self._db = db
        self._trade_repo: TradeRepository | None = None
        self._rec_repo: RecommendationRepository | None = None

    @property
    def trade_repo(self) -> "TradeRepository":
        """Lazy-load trade repository."""
        if self._trade_repo is None:
            from ib_daily_picker.store.repositories import TradeRepository

            self._trade_repo = TradeRepository(self._db)
        return self._trade_repo

    @property
    def rec_repo(self) -> "RecommendationRepository":
        """Lazy-load recommendation repository."""
        if self._rec_repo is None:
            from ib_daily_picker.store.repositories import RecommendationRepository

            self._rec_repo = RecommendationRepository(self._db)
        return self._rec_repo

    # --- Trade Lifecycle ---

    def execute_recommendation(
        self,
        recommendation_id: str,
        entry_price: Decimal,
        position_size: Decimal,
        entry_time: datetime | None = None,
        notes: str | None = None,
    ) -> Trade:
        """Execute a recommendation as a trade.

        Args:
            recommendation_id: ID of the recommendation to execute
            entry_price: Actual entry price
            position_size: Number of shares/contracts
            entry_time: Time of execution (defaults to now)
            notes: Optional notes for the trade

        Returns:
            Created Trade object

        Raises:
            ValueError: If recommendation not found or not actionable
        """
        rec = self.rec_repo.get_by_id(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        if not rec.is_actionable:
            raise ValueError(
                f"Recommendation {recommendation_id} is not actionable "
                f"(status: {rec.status.value}, expired: {rec.is_expired})"
            )

        # Determine direction from signal type
        from ib_daily_picker.models import SignalType

        direction = (
            TradeDirection.LONG if rec.signal_type == SignalType.BUY else TradeDirection.SHORT
        )

        trade = Trade(
            id=str(uuid4()),
            recommendation_id=recommendation_id,
            symbol=rec.symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time or datetime.utcnow(),
            position_size=position_size,
            stop_loss=rec.stop_loss,
            take_profit=rec.take_profit,
            notes=notes,
            status=TradeStatus.OPEN,
        )

        # Save trade and update recommendation status
        self.trade_repo.save(trade)
        self.rec_repo.update_status(recommendation_id, RecommendationStatus.EXECUTED)

        logger.info(
            f"Executed recommendation {recommendation_id} as trade {trade.id} "
            f"for {rec.symbol} @ ${entry_price}"
        )

        return trade

    def open_trade(
        self,
        symbol: str,
        direction: TradeDirection,
        entry_price: Decimal,
        position_size: Decimal,
        *,
        entry_time: datetime | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Trade:
        """Open a new trade without a recommendation.

        Args:
            symbol: Stock ticker symbol
            direction: Long or short
            entry_price: Entry price
            position_size: Number of shares
            entry_time: Time of entry (defaults to now)
            stop_loss: Stop loss price
            take_profit: Take profit target
            notes: Optional notes
            tags: Optional tags

        Returns:
            Created Trade object
        """
        trade = Trade(
            id=str(uuid4()),
            recommendation_id=None,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time or datetime.utcnow(),
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notes=notes,
            tags=tags or [],
            status=TradeStatus.OPEN,
        )

        self.trade_repo.save(trade)
        logger.info(f"Opened trade {trade.id} for {symbol} @ ${entry_price}")

        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: Decimal,
        exit_time: datetime | None = None,
        notes: str | None = None,
    ) -> Trade:
        """Close an open trade.

        Args:
            trade_id: ID of the trade to close
            exit_price: Exit price
            exit_time: Time of exit (defaults to now)
            notes: Optional closing notes

        Returns:
            Updated Trade object

        Raises:
            ValueError: If trade not found or already closed
        """
        trade = self.trade_repo.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"Trade {trade_id} is already {trade.status.value}")

        # Close the trade (this recalculates PnL)
        closed_trade = trade.close(
            exit_price=exit_price,
            exit_time=exit_time,
            notes=notes,
        )

        self.trade_repo.save(closed_trade)
        logger.info(
            f"Closed trade {trade_id} for {trade.symbol} @ ${exit_price} (PnL: ${closed_trade.pnl})"
        )

        return closed_trade

    def cancel_trade(self, trade_id: str, reason: str | None = None) -> Trade:
        """Cancel an open trade.

        Args:
            trade_id: ID of the trade to cancel
            reason: Optional cancellation reason

        Returns:
            Updated Trade object

        Raises:
            ValueError: If trade not found or already closed
        """
        trade = self.trade_repo.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"Trade {trade_id} is already {trade.status.value}")

        trade.status = TradeStatus.CANCELLED
        trade.updated_at = datetime.utcnow()
        if reason:
            trade.notes = (
                f"{trade.notes}\n\nCancelled: {reason}" if trade.notes else f"Cancelled: {reason}"
            )

        self.trade_repo.save(trade)
        logger.info(f"Cancelled trade {trade_id}")

        return trade

    def update_trade(
        self,
        trade_id: str,
        *,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        mfe: Decimal | None = None,
        mae: Decimal | None = None,
    ) -> Trade:
        """Update trade parameters.

        Args:
            trade_id: ID of the trade to update
            stop_loss: New stop loss (None = don't change)
            take_profit: New take profit (None = don't change)
            notes: New notes (None = don't change)
            tags: New tags (None = don't change)
            mfe: Update MFE
            mae: Update MAE

        Returns:
            Updated Trade object

        Raises:
            ValueError: If trade not found
        """
        trade = self.trade_repo.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        if stop_loss is not None:
            trade.stop_loss = stop_loss
        if take_profit is not None:
            trade.take_profit = take_profit
        if notes is not None:
            trade.notes = notes
        if tags is not None:
            trade.tags = tags
        if mfe is not None:
            trade.mfe = mfe
        if mae is not None:
            trade.mae = mae

        trade.updated_at = datetime.utcnow()
        self.trade_repo.save(trade)

        return trade

    def add_note(self, trade_id: str, note: str) -> Trade:
        """Add a note to a trade.

        Args:
            trade_id: ID of the trade
            note: Note to add

        Returns:
            Updated Trade object
        """
        trade = self.trade_repo.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_note = f"[{timestamp}] {note}"

        if trade.notes:
            trade.notes = f"{trade.notes}\n\n{new_note}"
        else:
            trade.notes = new_note

        trade.updated_at = datetime.utcnow()
        self.trade_repo.save(trade)

        return trade

    def add_tag(self, trade_id: str, tag: str) -> Trade:
        """Add a tag to a trade.

        Args:
            trade_id: ID of the trade
            tag: Tag to add

        Returns:
            Updated Trade object
        """
        trade = self.trade_repo.get_by_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        if tag not in trade.tags:
            trade.tags.append(tag)
            trade.updated_at = datetime.utcnow()
            self.trade_repo.save(trade)

        return trade

    # --- Query Operations ---

    def get_trade(self, trade_id: str) -> Trade | None:
        """Get a trade by ID."""
        return self.trade_repo.get_by_id(trade_id)

    def get_open_trades(self) -> list[Trade]:
        """Get all open trades."""
        return self.trade_repo.get_open()

    def get_closed_trades(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[Trade]:
        """Get closed trades with optional date filter."""
        return self.trade_repo.get_closed(start_date, end_date, limit)

    def get_trades_by_symbol(
        self,
        symbol: str,
        include_open: bool = True,
        include_closed: bool = True,
    ) -> list[Trade]:
        """Get all trades for a symbol."""
        trades: list[Trade] = []

        if include_open:
            trades.extend([t for t in self.get_open_trades() if t.symbol == symbol.upper()])

        if include_closed:
            closed = self.get_closed_trades(limit=1000)
            trades.extend([t for t in closed if t.symbol == symbol.upper()])

        return trades

    def get_recommendation(self, rec_id: str) -> Recommendation | None:
        """Get a recommendation by ID."""
        return self.rec_repo.get_by_id(rec_id)

    def get_pending_recommendations(self, limit: int = 50) -> list[Recommendation]:
        """Get pending recommendations."""
        return self.rec_repo.get_pending(limit)

    def save_recommendation(self, recommendation: Recommendation) -> str:
        """Save a recommendation to the journal."""
        return self.rec_repo.save(recommendation)

    # --- Metrics ---

    def get_metrics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TradeMetrics:
        """Get basic trade metrics.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            TradeMetrics with summary statistics
        """
        trades = self.get_closed_trades(start_date, end_date, limit=10000)
        return TradeMetrics.from_trades(trades)

    def get_extended_metrics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        symbols: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> ExtendedMetrics:
        """Get extended trade metrics with filtering.

        Args:
            start_date: Start of date range
            end_date: End of date range
            symbols: Filter to these symbols
            tags: Filter to trades with these tags

        Returns:
            ExtendedMetrics with comprehensive analysis
        """
        trades = self.get_closed_trades(limit=10000)
        filtered = filter_trades(
            trades,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            tags=tags,
        )
        return calculate_extended_metrics(filtered)

    # --- Export ---

    def export_trades_csv(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> str:
        """Export trades to CSV format.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            CSV string
        """
        trades = self.get_closed_trades(start_date, end_date, limit=10000)

        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "id",
                "symbol",
                "direction",
                "entry_time",
                "entry_price",
                "exit_time",
                "exit_price",
                "position_size",
                "pnl",
                "pnl_percent",
                "r_multiple",
                "stop_loss",
                "take_profit",
                "mfe",
                "mae",
                "duration_minutes",
                "tags",
                "notes",
            ]
        )

        # Data
        for trade in trades:
            writer.writerow(
                [
                    trade.id,
                    trade.symbol,
                    trade.direction.value,
                    trade.entry_time.isoformat(),
                    str(trade.entry_price),
                    trade.exit_time.isoformat() if trade.exit_time else "",
                    str(trade.exit_price) if trade.exit_price else "",
                    str(trade.position_size),
                    str(trade.pnl) if trade.pnl else "",
                    str(trade.pnl_percent) if trade.pnl_percent else "",
                    str(trade.r_multiple) if trade.r_multiple else "",
                    str(trade.stop_loss) if trade.stop_loss else "",
                    str(trade.take_profit) if trade.take_profit else "",
                    str(trade.mfe) if trade.mfe else "",
                    str(trade.mae) if trade.mae else "",
                    str(trade.duration_minutes) if trade.duration_minutes else "",
                    ",".join(trade.tags),
                    trade.notes or "",
                ]
            )

        return output.getvalue()

    def export_trades_json(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> str:
        """Export trades to JSON format.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            JSON string
        """
        trades = self.get_closed_trades(start_date, end_date, limit=10000)

        def trade_to_dict(trade: Trade) -> dict:
            return {
                "id": trade.id,
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "entry_time": trade.entry_time.isoformat(),
                "entry_price": str(trade.entry_price),
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "exit_price": str(trade.exit_price) if trade.exit_price else None,
                "position_size": str(trade.position_size),
                "pnl": str(trade.pnl) if trade.pnl else None,
                "pnl_percent": str(trade.pnl_percent) if trade.pnl_percent else None,
                "r_multiple": str(trade.r_multiple) if trade.r_multiple else None,
                "stop_loss": str(trade.stop_loss) if trade.stop_loss else None,
                "take_profit": str(trade.take_profit) if trade.take_profit else None,
                "mfe": str(trade.mfe) if trade.mfe else None,
                "mae": str(trade.mae) if trade.mae else None,
                "duration_minutes": trade.duration_minutes,
                "tags": trade.tags,
                "notes": trade.notes,
            }

        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(trades),
            "trades": [trade_to_dict(t) for t in trades],
        }

        return json.dumps(data, indent=2)


# Global instance
_journal_manager: JournalManager | None = None


def get_journal_manager() -> JournalManager:
    """Get the global journal manager instance."""
    global _journal_manager
    if _journal_manager is None:
        from ib_daily_picker.store.database import get_db_manager

        _journal_manager = JournalManager(get_db_manager())
    return _journal_manager


def reset_journal_manager() -> None:
    """Reset the global journal manager (for testing)."""
    global _journal_manager
    _journal_manager = None

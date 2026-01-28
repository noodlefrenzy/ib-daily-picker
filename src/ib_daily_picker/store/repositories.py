"""
Repository pattern for data access.

PURPOSE: Clean data access layer for domain models
DEPENDENCIES: duckdb

ARCHITECTURE NOTES:
- Repositories abstract database operations
- Domain models in, domain models out (no raw SQL in business logic)
- Support batch operations for efficiency
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from ib_daily_picker.models import (
    OHLCV,
    FlowAlert,
    OHLCVBatch,
    Recommendation,
    RecommendationStatus,
    StockMetadata,
    Trade,
    TradeStatus,
)

if TYPE_CHECKING:
    import duckdb

    from ib_daily_picker.store.database import DatabaseManager


class StockRepository:
    """Repository for stock data (OHLCV and metadata)."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager."""
        self._db = db

    def save_ohlcv(self, ohlcv: OHLCV) -> None:
        """Save single OHLCV record."""
        self.save_ohlcv_batch([ohlcv])

    def save_ohlcv_batch(self, records: list[OHLCV]) -> int:
        """Save batch of OHLCV records. Returns count saved."""
        if not records:
            return 0

        with self._db.duckdb() as conn:
            # Use INSERT OR REPLACE for upsert behavior
            for ohlcv in records:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ohlcv
                    (symbol, date, open, high, low, close, volume,
                     adjusted_close, dividend, stock_split)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ohlcv.symbol,
                        ohlcv.trade_date,
                        float(ohlcv.open_price),
                        float(ohlcv.high_price),
                        float(ohlcv.low_price),
                        float(ohlcv.close_price),
                        ohlcv.volume,
                        float(ohlcv.adjusted_close) if ohlcv.adjusted_close else None,
                        float(ohlcv.dividend),
                        float(ohlcv.stock_split),
                    ],
                )
        return len(records)

    def get_ohlcv(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[OHLCV]:
        """Get OHLCV data for a symbol."""
        symbol = symbol.upper()

        query = "SELECT * FROM ohlcv WHERE symbol = ?"
        params: list = [symbol]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        if limit:
            query += f" LIMIT {limit}"

        with self._db.duckdb() as conn:
            result = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.description]

        return [self._row_to_ohlcv(dict(zip(columns, row))) for row in result]

    def get_ohlcv_batch(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, OHLCVBatch]:
        """Get OHLCV data for multiple symbols."""
        result: dict[str, OHLCVBatch] = {}
        for symbol in symbols:
            ohlcv_list = self.get_ohlcv(symbol, start_date, end_date)
            result[symbol] = OHLCVBatch(symbol=symbol, data=ohlcv_list)
        return result

    def get_latest_date(self, symbol: str) -> date | None:
        """Get most recent date for a symbol."""
        with self._db.duckdb() as conn:
            result = conn.execute(
                "SELECT MAX(date) FROM ohlcv WHERE symbol = ?", [symbol.upper()]
            ).fetchone()
            if result and result[0]:
                return result[0]
        return None

    def get_symbols(self) -> list[str]:
        """Get all symbols with data."""
        with self._db.duckdb() as conn:
            result = conn.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol").fetchall()
        return [row[0] for row in result]

    def save_metadata(self, metadata: StockMetadata) -> None:
        """Save stock metadata."""
        with self._db.duckdb() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stock_metadata
                (symbol, name, sector, industry, market_cap, currency, exchange, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    metadata.symbol,
                    metadata.name,
                    metadata.sector,
                    metadata.industry,
                    metadata.market_cap,
                    metadata.currency,
                    metadata.exchange,
                    metadata.updated_at.isoformat(),
                ],
            )

    def get_metadata(self, symbol: str) -> StockMetadata | None:
        """Get stock metadata."""
        with self._db.duckdb() as conn:
            result = conn.execute(
                "SELECT * FROM stock_metadata WHERE symbol = ?", [symbol.upper()]
            ).fetchone()
            if not result:
                return None
            columns = [desc[0] for desc in conn.description]
            row = dict(zip(columns, result))
            # Handle updated_at which may be datetime or string
            updated_at = row["updated_at"]
            if updated_at is None:
                updated_at = datetime.utcnow()
            elif isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            # else it's already a datetime

            return StockMetadata(
                symbol=row["symbol"],
                name=row["name"],
                sector=row["sector"],
                industry=row["industry"],
                market_cap=row["market_cap"],
                currency=row["currency"],
                exchange=row["exchange"],
                updated_at=updated_at,
            )

    def _row_to_ohlcv(self, row: dict) -> OHLCV:
        """Convert database row to OHLCV model."""
        return OHLCV(
            symbol=row["symbol"],
            trade_date=row["date"],
            open_price=Decimal(str(row["open"])),
            high_price=Decimal(str(row["high"])),
            low_price=Decimal(str(row["low"])),
            close_price=Decimal(str(row["close"])),
            volume=row["volume"],
            adjusted_close=Decimal(str(row["adjusted_close"])) if row["adjusted_close"] else None,
            dividend=Decimal(str(row["dividend"])) if row["dividend"] else Decimal("0"),
            stock_split=Decimal(str(row["stock_split"])) if row["stock_split"] else Decimal("1"),
        )


class FlowRepository:
    """Repository for flow alert data."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager."""
        self._db = db

    def save(self, alert: FlowAlert) -> None:
        """Save single flow alert."""
        self.save_batch([alert])

    def save_batch(self, alerts: list[FlowAlert]) -> int:
        """Save batch of flow alerts. Returns count saved."""
        if not alerts:
            return 0

        with self._db.duckdb() as conn:
            for alert in alerts:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO flow_alerts
                    (id, symbol, alert_time, alert_type, direction, premium,
                     volume, open_interest, strike, expiration, option_type,
                     sentiment, raw_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        alert.id,
                        alert.symbol,
                        alert.alert_time.isoformat(),
                        alert.alert_type.value,
                        alert.direction.value,
                        float(alert.premium) if alert.premium else None,
                        alert.volume,
                        alert.open_interest,
                        float(alert.strike) if alert.strike else None,
                        alert.expiration.isoformat() if alert.expiration else None,
                        alert.option_type.value if alert.option_type else None,
                        alert.sentiment.value,
                        json.dumps(alert.raw_data) if alert.raw_data else None,
                        alert.created_at.isoformat(),
                    ],
                )
        return len(alerts)

    def get_by_symbol(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[FlowAlert]:
        """Get flow alerts for a symbol."""
        symbol = symbol.upper()

        query = "SELECT * FROM flow_alerts WHERE symbol = ?"
        params: list = [symbol]

        if start_time:
            query += " AND alert_time >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND alert_time <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY alert_time DESC"

        if limit:
            query += f" LIMIT {limit}"

        with self._db.duckdb() as conn:
            result = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.description]

        return [self._row_to_alert(dict(zip(columns, row))) for row in result]

    def get_recent(self, limit: int = 100, min_premium: Decimal | None = None) -> list[FlowAlert]:
        """Get most recent flow alerts."""
        query = "SELECT * FROM flow_alerts"
        params: list = []

        if min_premium:
            query += " WHERE premium >= ?"
            params.append(float(min_premium))

        query += " ORDER BY alert_time DESC LIMIT ?"
        params.append(limit)

        with self._db.duckdb() as conn:
            result = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.description]

        return [self._row_to_alert(dict(zip(columns, row))) for row in result]

    def _row_to_alert(self, row: dict) -> FlowAlert:
        """Convert database row to FlowAlert model."""
        from ib_daily_picker.models import AlertType, FlowDirection, OptionType, Sentiment

        # Handle datetime - DuckDB returns datetime objects directly
        alert_time = row["alert_time"]
        if isinstance(alert_time, str):
            alert_time = datetime.fromisoformat(alert_time)

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        # Handle date - may be date object or string
        expiration = row["expiration"]
        if expiration and isinstance(expiration, str):
            expiration = date.fromisoformat(expiration)

        return FlowAlert(
            id=row["id"],
            symbol=row["symbol"],
            alert_time=alert_time,
            alert_type=AlertType(row["alert_type"]),
            direction=FlowDirection(row["direction"]),
            premium=Decimal(str(row["premium"])) if row["premium"] else None,
            volume=row["volume"],
            open_interest=row["open_interest"],
            strike=Decimal(str(row["strike"])) if row["strike"] else None,
            expiration=expiration,
            option_type=OptionType(row["option_type"]) if row["option_type"] else None,
            sentiment=Sentiment(row["sentiment"]),
            raw_data=json.loads(row["raw_data"]) if row["raw_data"] else None,
            created_at=created_at,
        )


class RecommendationRepository:
    """Repository for trade recommendations."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager."""
        self._db = db

    def save(self, rec: Recommendation) -> str:
        """Save recommendation. Returns ID."""
        with self._db.duckdb() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO recommendations
                (id, symbol, strategy_name, signal_type, entry_price, stop_loss,
                 take_profit, position_size, confidence, reasoning, generated_at,
                 expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    rec.id,
                    rec.symbol,
                    rec.strategy_name,
                    rec.signal_type.value,
                    float(rec.entry_price) if rec.entry_price else None,
                    float(rec.stop_loss) if rec.stop_loss else None,
                    float(rec.take_profit) if rec.take_profit else None,
                    float(rec.position_size) if rec.position_size else None,
                    float(rec.confidence),
                    rec.reasoning,
                    rec.generated_at.isoformat(),
                    rec.expires_at.isoformat() if rec.expires_at else None,
                    rec.status.value,
                ],
            )
        return rec.id

    def get_by_id(self, rec_id: str) -> Recommendation | None:
        """Get recommendation by ID."""
        with self._db.duckdb() as conn:
            result = conn.execute("SELECT * FROM recommendations WHERE id = ?", [rec_id]).fetchone()
            if not result:
                return None
            columns = [desc[0] for desc in conn.description]
            return self._row_to_recommendation(dict(zip(columns, result)))

    def get_pending(self, limit: int = 50) -> list[Recommendation]:
        """Get pending recommendations."""
        with self._db.duckdb() as conn:
            result = conn.execute(
                """
                SELECT * FROM recommendations
                WHERE status = ?
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                [RecommendationStatus.PENDING.value, limit],
            ).fetchall()
            columns = [desc[0] for desc in conn.description]
        return [self._row_to_recommendation(dict(zip(columns, row))) for row in result]

    def update_status(self, rec_id: str, status: RecommendationStatus) -> None:
        """Update recommendation status."""
        with self._db.duckdb() as conn:
            conn.execute(
                "UPDATE recommendations SET status = ? WHERE id = ?",
                [status.value, rec_id],
            )

    def _row_to_recommendation(self, row: dict) -> Recommendation:
        """Convert database row to Recommendation model."""
        from ib_daily_picker.models import SignalType

        # Handle datetime - DuckDB returns datetime objects directly
        generated_at = row["generated_at"]
        if isinstance(generated_at, str):
            generated_at = datetime.fromisoformat(generated_at)

        expires_at = row["expires_at"]
        if expires_at and isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        return Recommendation(
            id=row["id"],
            symbol=row["symbol"],
            strategy_name=row["strategy_name"],
            signal_type=SignalType(row["signal_type"]),
            entry_price=Decimal(str(row["entry_price"])) if row["entry_price"] else None,
            stop_loss=Decimal(str(row["stop_loss"])) if row["stop_loss"] else None,
            take_profit=Decimal(str(row["take_profit"])) if row["take_profit"] else None,
            position_size=Decimal(str(row["position_size"])) if row["position_size"] else None,
            confidence=Decimal(str(row["confidence"])),
            reasoning=row["reasoning"],
            generated_at=generated_at,
            expires_at=expires_at,
            status=RecommendationStatus(row["status"]),
        )


class TradeRepository:
    """Repository for trade journal entries."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager."""
        self._db = db

    def save(self, trade: Trade) -> str:
        """Save trade. Returns ID."""
        with self._db.duckdb() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades
                (id, recommendation_id, symbol, direction, entry_price, entry_time,
                 exit_price, exit_time, position_size, stop_loss, take_profit,
                 pnl, pnl_percent, r_multiple, mfe, mae, notes, tags, status,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    trade.id,
                    trade.recommendation_id,
                    trade.symbol,
                    trade.direction.value,
                    float(trade.entry_price),
                    trade.entry_time.isoformat(),
                    float(trade.exit_price) if trade.exit_price else None,
                    trade.exit_time.isoformat() if trade.exit_time else None,
                    float(trade.position_size),
                    float(trade.stop_loss) if trade.stop_loss else None,
                    float(trade.take_profit) if trade.take_profit else None,
                    float(trade.pnl) if trade.pnl else None,
                    float(trade.pnl_percent) if trade.pnl_percent else None,
                    float(trade.r_multiple) if trade.r_multiple else None,
                    float(trade.mfe) if trade.mfe else None,
                    float(trade.mae) if trade.mae else None,
                    trade.notes,
                    json.dumps(trade.tags),
                    trade.status.value,
                    trade.created_at.isoformat(),
                    trade.updated_at.isoformat(),
                ],
            )
        return trade.id

    def get_by_id(self, trade_id: str) -> Trade | None:
        """Get trade by ID."""
        with self._db.duckdb() as conn:
            result = conn.execute("SELECT * FROM trades WHERE id = ?", [trade_id]).fetchone()
            if not result:
                return None
            columns = [desc[0] for desc in conn.description]
            return self._row_to_trade(dict(zip(columns, result)))

    def get_open(self) -> list[Trade]:
        """Get all open trades."""
        with self._db.duckdb() as conn:
            result = conn.execute(
                "SELECT * FROM trades WHERE status = ? ORDER BY entry_time DESC",
                [TradeStatus.OPEN.value],
            ).fetchall()
            columns = [desc[0] for desc in conn.description]
        return [self._row_to_trade(dict(zip(columns, row))) for row in result]

    def get_closed(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[Trade]:
        """Get closed trades."""
        query = "SELECT * FROM trades WHERE status = ?"
        params: list = [TradeStatus.CLOSED.value]

        if start_date:
            query += " AND DATE(entry_time) >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND DATE(entry_time) <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY entry_time DESC LIMIT ?"
        params.append(limit)

        with self._db.duckdb() as conn:
            result = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.description]
        return [self._row_to_trade(dict(zip(columns, row))) for row in result]

    def _row_to_trade(self, row: dict) -> Trade:
        """Convert database row to Trade model."""
        from ib_daily_picker.models import TradeDirection

        def parse_datetime(val: str | datetime | None) -> datetime | None:
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val)

        return Trade(
            id=row["id"],
            recommendation_id=row["recommendation_id"],
            symbol=row["symbol"],
            direction=TradeDirection(row["direction"]),
            entry_price=Decimal(str(row["entry_price"])),
            entry_time=parse_datetime(row["entry_time"]),  # type: ignore
            exit_price=Decimal(str(row["exit_price"])) if row["exit_price"] else None,
            exit_time=parse_datetime(row["exit_time"]),
            position_size=Decimal(str(row["position_size"])),
            stop_loss=Decimal(str(row["stop_loss"])) if row["stop_loss"] else None,
            take_profit=Decimal(str(row["take_profit"])) if row["take_profit"] else None,
            pnl=Decimal(str(row["pnl"])) if row["pnl"] else None,
            pnl_percent=Decimal(str(row["pnl_percent"])) if row["pnl_percent"] else None,
            r_multiple=Decimal(str(row["r_multiple"])) if row["r_multiple"] else None,
            mfe=Decimal(str(row["mfe"])) if row["mfe"] else None,
            mae=Decimal(str(row["mae"])) if row["mae"] else None,
            notes=row["notes"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            status=TradeStatus(row["status"]),
            created_at=parse_datetime(row["created_at"]),  # type: ignore
            updated_at=parse_datetime(row["updated_at"]),  # type: ignore
        )


def generate_id() -> str:
    """Generate a unique ID for records."""
    return str(uuid4())

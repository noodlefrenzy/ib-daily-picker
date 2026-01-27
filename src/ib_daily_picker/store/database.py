"""
Database connection management for DuckDB and SQLite.

PURPOSE: Provide connection factories and context managers for data access
DEPENDENCIES: duckdb, sqlite3

ARCHITECTURE NOTES:
- DuckDB: Used for analytical queries on OHLCV and flow data
- SQLite: Used for application state (sync tracking, configuration)
- Both use connection pooling via context managers
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import duckdb

from ib_daily_picker.config import get_settings

if TYPE_CHECKING:
    from ib_daily_picker.config import Settings


class DatabaseManager:
    """Manages DuckDB and SQLite database connections."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize database manager with settings."""
        self._settings = settings or get_settings()
        self._duckdb_conn: duckdb.DuckDBPyConnection | None = None
        self._initialized = False

    @property
    def duckdb_path(self) -> Path:
        """Get DuckDB database path."""
        return self._settings.database.duckdb_path

    @property
    def sqlite_path(self) -> Path:
        """Get SQLite database path."""
        return self._settings.database.sqlite_path

    def ensure_directories(self) -> None:
        """Ensure database directories exist."""
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        """Initialize database schemas if needed."""
        if self._initialized:
            return

        self.ensure_directories()
        self._init_duckdb_schema()
        self._init_sqlite_schema()
        self._initialized = True

    def _init_duckdb_schema(self) -> None:
        """Initialize DuckDB schema for analytics data."""
        with self.duckdb() as conn:
            # OHLCV data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    open DECIMAL(18, 4) NOT NULL,
                    high DECIMAL(18, 4) NOT NULL,
                    low DECIMAL(18, 4) NOT NULL,
                    close DECIMAL(18, 4) NOT NULL,
                    volume BIGINT NOT NULL,
                    adjusted_close DECIMAL(18, 4),
                    dividend DECIMAL(18, 4) DEFAULT 0,
                    stock_split DECIMAL(18, 4) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                )
            """)

            # Stock metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_metadata (
                    symbol VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    sector VARCHAR,
                    industry VARCHAR,
                    market_cap BIGINT,
                    currency VARCHAR DEFAULT 'USD',
                    exchange VARCHAR,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Flow alerts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_alerts (
                    id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    alert_time TIMESTAMP NOT NULL,
                    alert_type VARCHAR NOT NULL,
                    direction VARCHAR,
                    premium DECIMAL(18, 2),
                    volume BIGINT,
                    open_interest BIGINT,
                    strike DECIMAL(18, 2),
                    expiration DATE,
                    option_type VARCHAR,
                    sentiment VARCHAR,
                    raw_data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Recommendations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    strategy_name VARCHAR NOT NULL,
                    signal_type VARCHAR NOT NULL,
                    entry_price DECIMAL(18, 4),
                    stop_loss DECIMAL(18, 4),
                    take_profit DECIMAL(18, 4),
                    position_size DECIMAL(18, 4),
                    confidence DECIMAL(5, 4),
                    reasoning TEXT,
                    generated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    status VARCHAR DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Trades table (journal)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id VARCHAR PRIMARY KEY,
                    recommendation_id VARCHAR,
                    symbol VARCHAR NOT NULL,
                    direction VARCHAR NOT NULL,
                    entry_price DECIMAL(18, 4) NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_price DECIMAL(18, 4),
                    exit_time TIMESTAMP,
                    position_size DECIMAL(18, 4) NOT NULL,
                    stop_loss DECIMAL(18, 4),
                    take_profit DECIMAL(18, 4),
                    pnl DECIMAL(18, 4),
                    pnl_percent DECIMAL(8, 4),
                    r_multiple DECIMAL(8, 4),
                    mfe DECIMAL(18, 4),
                    mae DECIMAL(18, 4),
                    notes TEXT,
                    tags JSON,
                    status VARCHAR DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for common queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol ON ohlcv(symbol)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv(date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_flow_alerts_symbol ON flow_alerts(symbol)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_flow_alerts_time ON flow_alerts(alert_time)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)"
            )

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite schema for application state."""
        with self.sqlite() as conn:
            cursor = conn.cursor()

            # Sync state tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    last_sync_at TEXT NOT NULL,
                    last_sync_date TEXT,
                    metadata TEXT,
                    PRIMARY KEY (entity_type, entity_id)
                )
            """)

            # Configuration overrides (per-session)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_overrides (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Watchlist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    symbol TEXT PRIMARY KEY,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    tags TEXT
                )
            """)

            conn.commit()

    @contextmanager
    def duckdb(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Context manager for DuckDB connection.

        Yields:
            DuckDB connection for analytical queries.
        """
        conn = duckdb.connect(str(self.duckdb_path))
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def sqlite(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for SQLite connection.

        Yields:
            SQLite connection for state operations.
        """
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_sync_state(
        self, entity_type: str, entity_id: str
    ) -> dict[str, str] | None:
        """Get sync state for an entity.

        Args:
            entity_type: Type of entity (e.g., 'stock', 'flow')
            entity_id: Entity identifier (e.g., ticker symbol)

        Returns:
            Sync state dict or None if not found.
        """
        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT last_sync_at, last_sync_date, metadata
                FROM sync_state
                WHERE entity_type = ? AND entity_id = ?
                """,
                (entity_type, entity_id),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "last_sync_at": row["last_sync_at"],
                    "last_sync_date": row["last_sync_date"],
                    "metadata": row["metadata"],
                }
            return None

    def update_sync_state(
        self,
        entity_type: str,
        entity_id: str,
        last_sync_at: str,
        last_sync_date: str | None = None,
        metadata: str | None = None,
    ) -> None:
        """Update sync state for an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            last_sync_at: ISO timestamp of last sync
            last_sync_date: Last date synced (for incremental)
            metadata: Optional JSON metadata
        """
        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sync_state
                (entity_type, entity_id, last_sync_at, last_sync_date, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity_type, entity_id, last_sync_at, last_sync_date, metadata),
            )
            conn.commit()

    # --- Watchlist Management ---

    def watchlist_add(self, symbol: str, notes: str | None = None, tags: list[str] | None = None) -> bool:
        """Add a symbol to the watchlist.

        Args:
            symbol: Stock ticker symbol
            notes: Optional notes
            tags: Optional list of tags

        Returns:
            True if added, False if already exists
        """
        import json
        from datetime import datetime

        with self.sqlite() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO watchlist (symbol, added_at, notes, tags)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        symbol.upper(),
                        datetime.utcnow().isoformat(),
                        notes,
                        json.dumps(tags) if tags else None,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def watchlist_remove(self, symbol: str) -> bool:
        """Remove a symbol from the watchlist.

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if removed, False if not found
        """
        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM watchlist WHERE symbol = ?",
                (symbol.upper(),),
            )
            conn.commit()
            return cursor.rowcount > 0

    def watchlist_list(self) -> list[dict]:
        """Get all symbols in the watchlist.

        Returns:
            List of watchlist entries with symbol, added_at, notes, tags
        """
        import json

        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, added_at, notes, tags FROM watchlist ORDER BY added_at DESC"
            )
            rows = cursor.fetchall()
            return [
                {
                    "symbol": row["symbol"],
                    "added_at": row["added_at"],
                    "notes": row["notes"],
                    "tags": json.loads(row["tags"]) if row["tags"] else [],
                }
                for row in rows
            ]

    def watchlist_clear(self) -> int:
        """Clear all symbols from the watchlist.

        Returns:
            Number of symbols removed
        """
        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist")
            conn.commit()
            return cursor.rowcount

    def watchlist_contains(self, symbol: str) -> bool:
        """Check if a symbol is in the watchlist.

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if in watchlist
        """
        with self.sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM watchlist WHERE symbol = ?",
                (symbol.upper(),),
            )
            return cursor.fetchone() is not None


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager


def reset_db_manager() -> None:
    """Reset the global database manager (useful for testing)."""
    global _db_manager
    _db_manager = None

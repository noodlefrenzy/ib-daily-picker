"""
Stock data fetcher orchestrator.

PURPOSE: Coordinate stock data fetching with caching and fallback
DEPENDENCIES: yfinance_fetcher, finnhub_fetcher, repositories

ARCHITECTURE NOTES:
- Uses yfinance as primary (free, unlimited)
- Falls back to Finnhub on failure
- Implements incremental fetching (only missing dates)
- Integrates with repository for persistence
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Callable

from ib_daily_picker.config import get_settings
from ib_daily_picker.fetchers.base import (
    FetchProgress,
    FetchResult,
    FetchStatus,
    FetcherWithFallback,
)
from ib_daily_picker.fetchers.finnhub_fetcher import get_finnhub_fetcher
from ib_daily_picker.fetchers.yfinance_fetcher import get_yfinance_fetcher
from ib_daily_picker.models import OHLCV, OHLCVBatch, StockMetadata

if TYPE_CHECKING:
    from ib_daily_picker.store.database import DatabaseManager
    from ib_daily_picker.store.repositories import StockRepository

logger = logging.getLogger(__name__)


class StockDataFetcher:
    """Orchestrates stock data fetching with caching and persistence."""

    def __init__(
        self,
        db: "DatabaseManager | None" = None,
        repo: "StockRepository | None" = None,
    ) -> None:
        """Initialize stock data fetcher.

        Args:
            db: Database manager (defaults to global instance)
            repo: Stock repository (defaults to creating one from db)
        """
        self._db = db
        self._repo = repo
        self._fetcher = FetcherWithFallback(
            get_yfinance_fetcher(),
            get_finnhub_fetcher(),
        )

    def _get_repo(self) -> "StockRepository":
        """Get or create stock repository."""
        if self._repo is not None:
            return self._repo

        if self._db is None:
            from ib_daily_picker.store.database import get_db_manager

            self._db = get_db_manager()

        from ib_daily_picker.store.repositories import StockRepository

        self._repo = StockRepository(self._db)
        return self._repo

    async def fetch_and_store(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        incremental: bool = True,
    ) -> FetchResult[list[OHLCV]]:
        """Fetch OHLCV data and store in database.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (defaults to 5 years ago)
            end_date: End date (defaults to today)
            incremental: Only fetch missing dates (default True)

        Returns:
            FetchResult with fetched data
        """
        symbol = symbol.upper().strip()
        repo = self._get_repo()

        # Determine date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

        # Incremental: only fetch from last known date
        if incremental:
            latest = repo.get_latest_date(symbol)
            if latest and latest >= end_date:
                logger.info(f"{symbol}: Already up to date ({latest})")
                existing = repo.get_ohlcv(symbol, start_date, end_date)
                return FetchResult(
                    data=existing,
                    status=FetchStatus.SUCCESS,
                    source="cache",
                )
            if latest:
                # Fetch from day after latest
                start_date = max(start_date, latest + timedelta(days=1))
                logger.info(f"{symbol}: Incremental fetch from {start_date}")

        # Fetch from API
        result = await self._fetcher.fetch_ohlcv(symbol, start_date, end_date)

        if result.is_success and result.data:
            # Store in database
            count = repo.save_ohlcv_batch(result.data)
            logger.info(f"{symbol}: Stored {count} records")

            # Update sync state
            if self._db:
                self._db.update_sync_state(
                    entity_type="stock",
                    entity_id=symbol,
                    last_sync_at=datetime.utcnow().isoformat(),
                    last_sync_date=end_date.isoformat(),
                )

        # Detect "no new data" vs "invalid ticker" for incremental fetches
        if result.status == FetchStatus.NOT_FOUND and incremental and latest is not None:
            # We have existing data but API returned nothing for the delta period
            # This likely means no new trading data available yet (weekend, holiday, market not closed)
            days_since_latest = (end_date - latest).days
            if days_since_latest <= 5:  # Within a reasonable gap (weekend + buffer)
                logger.info(f"{symbol}: No new data available (latest: {latest})")
                existing = repo.get_ohlcv(symbol, start_date - timedelta(days=5 * 365), latest)
                return FetchResult(
                    data=existing,
                    status=FetchStatus.UP_TO_DATE,
                    source="cache",
                    warnings=[f"No new data since {latest} (data may not be available yet)"],
                )

        return result

    async def fetch_and_store_batch(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        incremental: bool = True,
        progress_callback: Callable[[FetchProgress], None] | None = None,
    ) -> dict[str, FetchResult[list[OHLCV]]]:
        """Fetch OHLCV data for multiple symbols and store.

        Args:
            symbols: List of stock ticker symbols
            start_date: Start date
            end_date: End date
            incremental: Only fetch missing dates
            progress_callback: Optional callback(FetchProgress) for updates

        Returns:
            Dict mapping symbols to FetchResults
        """
        results: dict[str, FetchResult[list[OHLCV]]] = {}
        progress = FetchProgress(total=len(symbols))

        for symbol in symbols:
            progress.current_symbol = symbol
            if progress_callback:
                progress_callback(progress)

            results[symbol] = await self.fetch_and_store(symbol, start_date, end_date, incremental)

            if results[symbol].is_success:
                progress.completed += 1
            else:
                progress.failed += 1

        return results

    async def fetch_metadata_and_store(
        self,
        symbol: str,
        force: bool = False,
    ) -> FetchResult[StockMetadata]:
        """Fetch stock metadata and store in database.

        Args:
            symbol: Stock ticker symbol
            force: Force refresh even if recently updated

        Returns:
            FetchResult with metadata
        """
        symbol = symbol.upper().strip()
        repo = self._get_repo()

        # Check if we have recent metadata
        if not force:
            existing = repo.get_metadata(symbol)
            if existing:
                # Consider metadata fresh if updated within 7 days
                age = datetime.utcnow() - existing.updated_at
                if age < timedelta(days=7):
                    logger.info(f"{symbol}: Using cached metadata (age: {age.days}d)")
                    return FetchResult(
                        data=existing,
                        status=FetchStatus.SUCCESS,
                        source="cache",
                    )

        # Fetch from API
        result = await self._fetcher.fetch_metadata(symbol)

        if result.is_success and result.data:
            repo.save_metadata(result.data)
            logger.info(f"{symbol}: Stored metadata")

        return result

    def get_data_coverage(self) -> dict[str, dict]:
        """Get coverage statistics for stored data.

        Returns:
            Dict with symbols and their data ranges
        """
        repo = self._get_repo()
        symbols = repo.get_symbols()

        coverage = {}
        for symbol in symbols:
            ohlcv = repo.get_ohlcv(symbol, limit=1)
            if ohlcv:
                latest = ohlcv[0]
                # Get earliest date too
                all_data = repo.get_ohlcv(symbol)
                earliest = all_data[-1] if all_data else latest
                coverage[symbol] = {
                    "earliest_date": earliest.trade_date.isoformat(),
                    "latest_date": latest.trade_date.isoformat(),
                    "record_count": len(all_data),
                }

        return coverage


# Singleton instance
_stock_fetcher: StockDataFetcher | None = None


def get_stock_fetcher() -> StockDataFetcher:
    """Get or create singleton StockDataFetcher instance."""
    global _stock_fetcher
    if _stock_fetcher is None:
        _stock_fetcher = StockDataFetcher()
    return _stock_fetcher


def reset_stock_fetcher() -> None:
    """Reset singleton (for testing)."""
    global _stock_fetcher
    _stock_fetcher = None

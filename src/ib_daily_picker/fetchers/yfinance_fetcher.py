"""
YFinance stock data fetcher.

PURPOSE: Fetch stock data from Yahoo Finance via yfinance library
DEPENDENCIES: yfinance, pandas

ARCHITECTURE NOTES:
- Primary fetcher - free, unlimited, comprehensive data
- Supports historical data since IPO
- Includes sector/industry metadata
- Runs sync operations in thread pool for async compatibility
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import yfinance as yf

from ib_daily_picker.fetchers.base import BaseFetcher, FetchResult, FetchStatus
from ib_daily_picker.models import OHLCV, StockMetadata

logger = logging.getLogger(__name__)

# Thread pool for running yfinance sync operations
_executor = ThreadPoolExecutor(max_workers=4)


class YFinanceFetcher(BaseFetcher):
    """Fetcher using Yahoo Finance via yfinance library."""

    @property
    def name(self) -> str:
        """Return fetcher name."""
        return "yfinance"

    @property
    def is_available(self) -> bool:
        """YFinance is always available (no API key required)."""
        return True

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FetchResult[list[OHLCV]]:
        """Fetch OHLCV data from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (defaults to 5 years ago)
            end_date: End date (defaults to today)

        Returns:
            FetchResult containing list of OHLCV records
        """
        started_at = datetime.utcnow()
        symbol = symbol.upper().strip()

        # Default date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=5 * 365)

        try:
            # Run sync yfinance call in thread pool
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                _executor,
                lambda: self._fetch_history(symbol, start_date, end_date),
            )

            if df is None or df.empty:
                return FetchResult(
                    data=None,
                    status=FetchStatus.NOT_FOUND,
                    source=self.name,
                    started_at=started_at,
                    errors=[f"No data found for {symbol}"],
                )

            # Convert DataFrame to OHLCV models
            ohlcv_list = self._df_to_ohlcv(symbol, df)

            logger.info(
                f"YFinance fetch: {symbol} returned {len(ohlcv_list)} records "
                f"({start_date} to {end_date})"
            )

            return FetchResult(
                data=ohlcv_list,
                status=FetchStatus.SUCCESS,
                source=self.name,
                started_at=started_at,
            )

        except Exception as e:
            logger.exception(f"YFinance error for {symbol}: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )

    async def fetch_metadata(self, symbol: str) -> FetchResult[StockMetadata]:
        """Fetch stock metadata from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol

        Returns:
            FetchResult containing StockMetadata
        """
        started_at = datetime.utcnow()
        symbol = symbol.upper().strip()

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                _executor,
                lambda: self._fetch_info(symbol),
            )

            if info is None:
                return FetchResult(
                    data=None,
                    status=FetchStatus.NOT_FOUND,
                    source=self.name,
                    started_at=started_at,
                    errors=[f"No metadata found for {symbol}"],
                )

            metadata = StockMetadata(
                symbol=symbol,
                name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=info.get("marketCap"),
                currency=info.get("currency", "USD"),
                exchange=info.get("exchange"),
            )

            logger.info(f"YFinance metadata: {symbol} - {metadata.name}")

            return FetchResult(
                data=metadata,
                status=FetchStatus.SUCCESS,
                source=self.name,
                started_at=started_at,
            )

        except Exception as e:
            logger.exception(f"YFinance metadata error for {symbol}: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )

    def _fetch_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        """Sync method to fetch history from yfinance."""
        ticker = yf.Ticker(symbol)
        # yfinance end date is exclusive, so add 1 day
        end_str = (end_date + timedelta(days=1)).isoformat()
        df = ticker.history(start=start_date.isoformat(), end=end_str)
        return df

    def _fetch_info(self, symbol: str) -> dict[str, Any] | None:
        """Sync method to fetch ticker info from yfinance."""
        ticker = yf.Ticker(symbol)
        info = ticker.info
        # yfinance returns empty dict for invalid symbols
        if not info or info.get("regularMarketPrice") is None:
            return None
        return info

    def _df_to_ohlcv(self, symbol: str, df: Any) -> list[OHLCV]:
        """Convert pandas DataFrame to list of OHLCV models."""
        ohlcv_list = []

        for idx, row in df.iterrows():
            try:
                # Handle pandas Timestamp index
                trade_date = idx.date() if hasattr(idx, "date") else idx

                ohlcv = OHLCV(
                    symbol=symbol,
                    trade_date=trade_date,
                    open_price=Decimal(str(row["Open"])),
                    high_price=Decimal(str(row["High"])),
                    low_price=Decimal(str(row["Low"])),
                    close_price=Decimal(str(row["Close"])),
                    volume=int(row["Volume"]),
                    dividend=Decimal(str(row.get("Dividends", 0) or 0)),
                    stock_split=Decimal(str(row.get("Stock Splits", 1) or 1)),
                )
                ohlcv_list.append(ohlcv)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid row for {symbol} on {idx}: {e}")
                continue

        # Sort by date ascending
        ohlcv_list.sort(key=lambda x: x.trade_date)
        return ohlcv_list


# Singleton instance for convenience
_yfinance_fetcher: YFinanceFetcher | None = None


def get_yfinance_fetcher() -> YFinanceFetcher:
    """Get or create singleton YFinanceFetcher instance."""
    global _yfinance_fetcher
    if _yfinance_fetcher is None:
        _yfinance_fetcher = YFinanceFetcher()
    return _yfinance_fetcher

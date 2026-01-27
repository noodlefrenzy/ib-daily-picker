"""
Finnhub stock data fetcher.

PURPOSE: Fallback fetcher using Finnhub API
DEPENDENCIES: finnhub-python, httpx

ARCHITECTURE NOTES:
- Secondary/fallback fetcher
- Requires API key (free tier: 60 calls/min)
- Limited to 1 year of data per call
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import finnhub

from ib_daily_picker.config import get_settings
from ib_daily_picker.fetchers.base import BaseFetcher, FetchResult, FetchStatus
from ib_daily_picker.models import OHLCV, StockMetadata

logger = logging.getLogger(__name__)

# Thread pool for running finnhub sync operations
_executor = ThreadPoolExecutor(max_workers=2)


class FinnhubFetcher(BaseFetcher):
    """Fetcher using Finnhub API as fallback source."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with optional API key.

        Args:
            api_key: Finnhub API key (defaults to config)
        """
        self._api_key = api_key
        self._client: finnhub.Client | None = None

    @property
    def name(self) -> str:
        """Return fetcher name."""
        return "finnhub"

    @property
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return self._get_api_key() is not None

    def _get_api_key(self) -> str | None:
        """Get API key from instance or config."""
        if self._api_key:
            return self._api_key
        settings = get_settings()
        return settings.api.finnhub_api_key

    def _get_client(self) -> finnhub.Client:
        """Get or create Finnhub client."""
        if self._client is None:
            api_key = self._get_api_key()
            if not api_key:
                raise ValueError("Finnhub API key not configured")
            self._client = finnhub.Client(api_key=api_key)
        return self._client

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FetchResult[list[OHLCV]]:
        """Fetch OHLCV data from Finnhub.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (defaults to 1 year ago)
            end_date: End date (defaults to today)

        Returns:
            FetchResult containing list of OHLCV records
        """
        started_at = datetime.utcnow()
        symbol = symbol.upper().strip()

        if not self.is_available:
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=["Finnhub API key not configured"],
            )

        # Default date range (Finnhub free tier limits to 1 year)
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        try:
            # Run sync Finnhub call in thread pool
            loop = asyncio.get_event_loop()
            candles = await loop.run_in_executor(
                _executor,
                lambda: self._fetch_candles(symbol, start_date, end_date),
            )

            if candles is None or candles.get("s") == "no_data":
                return FetchResult(
                    data=None,
                    status=FetchStatus.NOT_FOUND,
                    source=self.name,
                    started_at=started_at,
                    errors=[f"No data found for {symbol}"],
                )

            # Convert candles to OHLCV models
            ohlcv_list = self._candles_to_ohlcv(symbol, candles)

            logger.info(
                f"Finnhub fetch: {symbol} returned {len(ohlcv_list)} records "
                f"({start_date} to {end_date})"
            )

            return FetchResult(
                data=ohlcv_list,
                status=FetchStatus.SUCCESS,
                source=self.name,
                started_at=started_at,
            )

        except finnhub.FinnhubAPIException as e:
            logger.exception(f"Finnhub API error for {symbol}: {e}")
            status = FetchStatus.RATE_LIMITED if "limit" in str(e).lower() else FetchStatus.ERROR
            return FetchResult(
                data=None,
                status=status,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )
        except Exception as e:
            logger.exception(f"Finnhub error for {symbol}: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )

    async def fetch_metadata(self, symbol: str) -> FetchResult[StockMetadata]:
        """Fetch stock metadata from Finnhub.

        Args:
            symbol: Stock ticker symbol

        Returns:
            FetchResult containing StockMetadata
        """
        started_at = datetime.utcnow()
        symbol = symbol.upper().strip()

        if not self.is_available:
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=["Finnhub API key not configured"],
            )

        try:
            loop = asyncio.get_event_loop()
            profile = await loop.run_in_executor(
                _executor,
                lambda: self._fetch_profile(symbol),
            )

            if profile is None or not profile.get("name"):
                return FetchResult(
                    data=None,
                    status=FetchStatus.NOT_FOUND,
                    source=self.name,
                    started_at=started_at,
                    errors=[f"No metadata found for {symbol}"],
                )

            metadata = StockMetadata(
                symbol=symbol,
                name=profile.get("name"),
                sector=profile.get("finnhubIndustry"),  # Finnhub uses this field
                industry=profile.get("finnhubIndustry"),
                market_cap=int(profile.get("marketCapitalization", 0) * 1_000_000)
                if profile.get("marketCapitalization")
                else None,
                currency=profile.get("currency", "USD"),
                exchange=profile.get("exchange"),
            )

            logger.info(f"Finnhub metadata: {symbol} - {metadata.name}")

            return FetchResult(
                data=metadata,
                status=FetchStatus.SUCCESS,
                source=self.name,
                started_at=started_at,
            )

        except finnhub.FinnhubAPIException as e:
            logger.exception(f"Finnhub API error for {symbol}: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )
        except Exception as e:
            logger.exception(f"Finnhub metadata error for {symbol}: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )

    def _fetch_candles(
        self, symbol: str, start_date: date, end_date: date
    ) -> dict[str, Any] | None:
        """Sync method to fetch candles from Finnhub."""
        client = self._get_client()
        # Convert dates to Unix timestamps
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp())
        return client.stock_candles(symbol, "D", start_ts, end_ts)

    def _fetch_profile(self, symbol: str) -> dict[str, Any] | None:
        """Sync method to fetch company profile from Finnhub."""
        client = self._get_client()
        return client.company_profile2(symbol=symbol)

    def _candles_to_ohlcv(self, symbol: str, candles: dict[str, Any]) -> list[OHLCV]:
        """Convert Finnhub candles response to list of OHLCV models."""
        ohlcv_list = []

        timestamps = candles.get("t", [])
        opens = candles.get("o", [])
        highs = candles.get("h", [])
        lows = candles.get("l", [])
        closes = candles.get("c", [])
        volumes = candles.get("v", [])

        for i, ts in enumerate(timestamps):
            try:
                trade_date = datetime.fromtimestamp(ts).date()
                ohlcv = OHLCV(
                    symbol=symbol,
                    trade_date=trade_date,
                    open_price=Decimal(str(opens[i])),
                    high_price=Decimal(str(highs[i])),
                    low_price=Decimal(str(lows[i])),
                    close_price=Decimal(str(closes[i])),
                    volume=int(volumes[i]),
                )
                ohlcv_list.append(ohlcv)
            except (IndexError, ValueError) as e:
                logger.warning(f"Skipping invalid candle for {symbol} at {ts}: {e}")
                continue

        # Sort by date ascending
        ohlcv_list.sort(key=lambda x: x.trade_date)
        return ohlcv_list


# Singleton instance
_finnhub_fetcher: FinnhubFetcher | None = None


def get_finnhub_fetcher() -> FinnhubFetcher:
    """Get or create singleton FinnhubFetcher instance."""
    global _finnhub_fetcher
    if _finnhub_fetcher is None:
        _finnhub_fetcher = FinnhubFetcher()
    return _finnhub_fetcher

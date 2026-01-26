"""
Abstract base for data fetchers.

PURPOSE: Define common interface for stock data fetchers
DEPENDENCIES: abc, pydantic

ARCHITECTURE NOTES:
- All fetchers implement the same interface for interchangeability
- FetchResult wraps data with metadata (timing, errors, source)
- Fetchers are async-first for non-blocking I/O
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar

from ib_daily_picker.models import OHLCV, OHLCVBatch, StockMetadata


class FetchStatus(str, Enum):
    """Status of a fetch operation."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some data fetched, some errors
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"


T = TypeVar("T")


@dataclass
class FetchResult(Generic[T]):
    """Result wrapper for fetch operations with metadata."""

    data: T | None = None
    status: FetchStatus = FetchStatus.SUCCESS
    source: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set completed_at if not provided."""
        if self.completed_at is None:
            self.completed_at = datetime.utcnow()

    @property
    def is_success(self) -> bool:
        """True if fetch was successful."""
        return self.status == FetchStatus.SUCCESS

    @property
    def duration_ms(self) -> int:
        """Duration of fetch in milliseconds."""
        if self.completed_at is None:
            return 0
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        if self.status == FetchStatus.SUCCESS:
            self.status = FetchStatus.PARTIAL

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


@dataclass
class FetchProgress:
    """Progress tracking for batch fetch operations."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    current_symbol: str = ""


class BaseFetcher(ABC):
    """Abstract base class for stock data fetchers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this fetcher."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this fetcher is available (API key configured, etc.)."""
        ...

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FetchResult[list[OHLCV]]:
        """Fetch OHLCV data for a single symbol.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive), defaults to today

        Returns:
            FetchResult containing list of OHLCV records
        """
        ...

    @abstractmethod
    async def fetch_metadata(self, symbol: str) -> FetchResult[StockMetadata]:
        """Fetch stock metadata (company info, sector, etc.).

        Args:
            symbol: Stock ticker symbol

        Returns:
            FetchResult containing StockMetadata
        """
        ...

    async def fetch_ohlcv_batch(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        progress_callback: callable | None = None,
    ) -> dict[str, FetchResult[list[OHLCV]]]:
        """Fetch OHLCV data for multiple symbols.

        Default implementation calls fetch_ohlcv for each symbol.
        Subclasses may override for batch optimization.

        Args:
            symbols: List of stock ticker symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            progress_callback: Optional callback(FetchProgress) for progress updates

        Returns:
            Dict mapping symbols to their FetchResults
        """
        results: dict[str, FetchResult[list[OHLCV]]] = {}
        progress = FetchProgress(total=len(symbols))

        for symbol in symbols:
            progress.current_symbol = symbol
            if progress_callback:
                progress_callback(progress)

            results[symbol] = await self.fetch_ohlcv(symbol, start_date, end_date)

            if results[symbol].is_success:
                progress.completed += 1
            else:
                progress.failed += 1

        return results


class FetcherWithFallback:
    """Fetcher that tries multiple sources in order."""

    def __init__(self, primary: BaseFetcher, *fallbacks: BaseFetcher) -> None:
        """Initialize with primary fetcher and optional fallbacks.

        Args:
            primary: Primary fetcher to try first
            fallbacks: Additional fetchers to try if primary fails
        """
        self._fetchers = [primary, *fallbacks]

    @property
    def available_fetchers(self) -> list[BaseFetcher]:
        """Get list of available fetchers."""
        return [f for f in self._fetchers if f.is_available]

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FetchResult[list[OHLCV]]:
        """Fetch OHLCV data, trying fallbacks on failure.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            FetchResult from first successful fetcher
        """
        last_result: FetchResult[list[OHLCV]] | None = None

        for fetcher in self.available_fetchers:
            result = await fetcher.fetch_ohlcv(symbol, start_date, end_date)
            if result.is_success:
                return result
            last_result = result

        # All fetchers failed
        if last_result:
            return last_result

        return FetchResult(
            data=None,
            status=FetchStatus.ERROR,
            source="none",
            errors=["No available fetchers"],
        )

    async def fetch_metadata(self, symbol: str) -> FetchResult[StockMetadata]:
        """Fetch stock metadata, trying fallbacks on failure.

        Args:
            symbol: Stock ticker symbol

        Returns:
            FetchResult from first successful fetcher
        """
        last_result: FetchResult[StockMetadata] | None = None

        for fetcher in self.available_fetchers:
            result = await fetcher.fetch_metadata(symbol)
            if result.is_success:
                return result
            last_result = result

        if last_result:
            return last_result

        return FetchResult(
            data=None,
            status=FetchStatus.ERROR,
            source="none",
            errors=["No available fetchers"],
        )

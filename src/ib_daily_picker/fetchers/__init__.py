"""
Fetchers package - API clients for stock data and flow alerts.

PURPOSE: Data fetching from yfinance, Finnhub, and Unusual Whales
"""

from ib_daily_picker.fetchers.base import (
    BaseFetcher,
    FetchProgress,
    FetchResult,
    FetchStatus,
    FetcherWithFallback,
)
from ib_daily_picker.fetchers.finnhub_fetcher import (
    FinnhubFetcher,
    get_finnhub_fetcher,
)
from ib_daily_picker.fetchers.stock_fetcher import (
    StockDataFetcher,
    get_stock_fetcher,
    reset_stock_fetcher,
)
from ib_daily_picker.fetchers.unusual_whales import (
    UnusualWhalesFetcher,
    get_unusual_whales_fetcher,
    reset_unusual_whales_fetcher,
)
from ib_daily_picker.fetchers.yfinance_fetcher import (
    YFinanceFetcher,
    get_yfinance_fetcher,
)

__all__ = [
    "BaseFetcher",
    "FetcherWithFallback",
    "FetchProgress",
    "FetchResult",
    "FetchStatus",
    "FinnhubFetcher",
    "StockDataFetcher",
    "UnusualWhalesFetcher",
    "YFinanceFetcher",
    "get_finnhub_fetcher",
    "get_stock_fetcher",
    "get_unusual_whales_fetcher",
    "get_yfinance_fetcher",
    "reset_stock_fetcher",
    "reset_unusual_whales_fetcher",
]

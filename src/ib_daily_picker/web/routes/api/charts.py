"""
Chart data API endpoints.

PURPOSE: JSON API for chart data (comparison, indicators, correlations)
DEPENDENCIES: fastapi, pandas, numpy
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ib_daily_picker.analysis.indicators import (
    IndicatorCalculator,
    calculate_bollinger_bands,
    calculate_macd,
)
from ib_daily_picker.config import MARKET_BENCHMARK, SECTOR_ETFS
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import StockRepository
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Response Models ---


class NormalizedPricePoint(BaseModel):
    """A single normalized price point."""

    time: str  # ISO date
    value: float  # Percentage change from start


class CompareSeriesResponse(BaseModel):
    """Price series for one symbol in comparison."""

    symbol: str
    data: list[NormalizedPricePoint]
    start_price: float
    end_price: float
    total_return: float  # Percentage


class CompareResponse(BaseModel):
    """Comparison data for multiple symbols."""

    series: list[CompareSeriesResponse]
    start_date: date
    end_date: date


class IndicatorValue(BaseModel):
    """A single indicator value."""

    time: str
    value: float | None


class IndicatorsResponse(BaseModel):
    """OHLCV data with computed indicators."""

    symbol: str
    ohlcv: list[dict[str, Any]]  # Original OHLCV data
    indicators: dict[str, list[IndicatorValue]]  # Indicator name -> values


class CorrelationEntry(BaseModel):
    """Correlation between two symbols."""

    symbol1: str
    symbol2: str
    correlation: float


class CorrelationResponse(BaseModel):
    """Correlation matrix data."""

    symbols: list[str]
    matrix: list[list[float]]  # NxN correlation matrix
    entries: list[CorrelationEntry]  # Flattened for easy access


# --- Helper Functions ---


def get_date_range(range_code: str) -> tuple[date, date]:
    """Convert range code to start/end dates.

    Args:
        range_code: One of 1W, 1M, 3M, 6M, 1Y, YTD

    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()

    if range_code == "1W":
        start = today - timedelta(days=7)
    elif range_code == "1M":
        start = today - timedelta(days=30)
    elif range_code == "3M":
        start = today - timedelta(days=90)
    elif range_code == "6M":
        start = today - timedelta(days=180)
    elif range_code == "1Y":
        start = today - timedelta(days=365)
    elif range_code == "YTD":
        start = date(today.year, 1, 1)
    else:
        # Default to 3M
        start = today - timedelta(days=90)

    return start, today


def normalize_prices(prices: list[float], dates: list[date]) -> list[NormalizedPricePoint]:
    """Normalize prices to percentage change from first value.

    Args:
        prices: List of prices
        dates: List of corresponding dates

    Returns:
        List of normalized price points
    """
    if not prices:
        return []

    start_price = prices[0]
    if start_price == 0:
        return []

    return [
        NormalizedPricePoint(
            time=d.isoformat(),
            value=round(((p - start_price) / start_price) * 100, 2),
        )
        for p, d in zip(prices, dates)
    ]


# --- Endpoints ---


@router.get("/charts/compare", response_model=CompareResponse)
async def compare_symbols(
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str, Query(description="Comma-separated symbols")] = "",
    benchmark: Annotated[str | None, Query(description="Benchmark symbol")] = None,
    range_code: Annotated[
        str, Query(alias="range", description="Date range: 1W, 1M, 3M, 6M, 1Y, YTD")
    ] = "3M",
    start_date: Annotated[date | None, Query(alias="from")] = None,
    end_date: Annotated[date | None, Query(alias="to")] = None,
) -> CompareResponse:
    """Get normalized price comparison for multiple symbols.

    Normalizes all prices to percentage change from the start date,
    enabling apple-to-apple comparison of different price levels.
    """
    repo = StockRepository(db)

    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol required")

    # Add benchmark if specified
    benchmark_symbol = benchmark.upper() if benchmark else MARKET_BENCHMARK
    if benchmark_symbol not in symbol_list:
        symbol_list.append(benchmark_symbol)

    # Determine date range
    if start_date and end_date:
        range_start, range_end = start_date, end_date
    else:
        range_start, range_end = get_date_range(range_code)

    # Fetch and normalize data for each symbol
    series_list = []
    for symbol in symbol_list:
        ohlcv_list = repo.get_ohlcv(
            symbol,
            start_date=range_start,
            end_date=range_end,
            limit=500,
        )

        if not ohlcv_list:
            continue

        # Reverse to chronological order
        ohlcv_list = list(reversed(ohlcv_list))

        prices = [float(o.close_price) for o in ohlcv_list]
        dates = [o.trade_date for o in ohlcv_list]

        if prices:
            normalized = normalize_prices(prices, dates)
            total_return = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0

            series_list.append(
                CompareSeriesResponse(
                    symbol=symbol,
                    data=normalized,
                    start_price=prices[0],
                    end_price=prices[-1],
                    total_return=round(total_return, 2),
                )
            )

    if not series_list:
        raise HTTPException(status_code=404, detail="No data found for any symbols")

    return CompareResponse(
        series=series_list,
        start_date=range_start,
        end_date=range_end,
    )


@router.get("/charts/indicators/{symbol}", response_model=IndicatorsResponse)
async def get_indicators(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
    indicators: Annotated[
        str, Query(description="Comma-separated indicators: sma_50,sma_200,rsi,macd,bollinger")
    ] = "sma_50,sma_200",
    start_date: Annotated[date | None, Query(alias="from")] = None,
    end_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> IndicatorsResponse:
    """Get OHLCV data with computed technical indicators."""
    repo = StockRepository(db)
    symbol = symbol.upper()

    ohlcv_list = repo.get_ohlcv(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    if not ohlcv_list:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    # Reverse to chronological order for indicator calculation
    ohlcv_list = list(reversed(ohlcv_list))

    # Prepare OHLCV data
    ohlcv_data = [
        {
            "time": o.trade_date.isoformat(),
            "open": float(o.open_price),
            "high": float(o.high_price),
            "low": float(o.low_price),
            "close": float(o.close_price),
            "volume": o.volume,
        }
        for o in ohlcv_list
    ]

    # Parse requested indicators
    indicator_names = [i.strip().lower() for i in indicators.split(",") if i.strip()]

    # Calculate indicators
    calc = IndicatorCalculator(ohlcv_list)
    indicator_results: dict[str, list[IndicatorValue]] = {}

    for ind_name in indicator_names:
        values: list[IndicatorValue] = []

        if ind_name == "sma_50":
            result = calc.calculate("SMA", "sma_50", {"period": 50})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "sma_200":
            result = calc.calculate("SMA", "sma_200", {"period": 200})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "ema_12":
            result = calc.calculate("EMA", "ema_12", {"period": 12})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "ema_26":
            result = calc.calculate("EMA", "ema_26", {"period": 26})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "rsi":
            result = calc.calculate("RSI", "rsi", {"period": 14})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "atr":
            result = calc.calculate("ATR", "atr", {"period": 14})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        elif ind_name == "macd":
            # Return all MACD components
            df = calc.df
            macd_result = calculate_macd(df["close"])
            indicator_results["macd_line"] = _series_to_indicator_values(
                macd_result.macd_line, ohlcv_data
            )
            indicator_results["macd_signal"] = _series_to_indicator_values(
                macd_result.signal_line, ohlcv_data
            )
            indicator_results["macd_histogram"] = _series_to_indicator_values(
                macd_result.histogram, ohlcv_data
            )
            continue  # Skip adding to indicator_results below

        elif ind_name == "bollinger":
            df = calc.df
            bb_result = calculate_bollinger_bands(df["close"])
            indicator_results["bb_upper"] = _series_to_indicator_values(
                bb_result.upper_band, ohlcv_data
            )
            indicator_results["bb_middle"] = _series_to_indicator_values(
                bb_result.middle_band, ohlcv_data
            )
            indicator_results["bb_lower"] = _series_to_indicator_values(
                bb_result.lower_band, ohlcv_data
            )
            continue

        elif ind_name == "volume_sma":
            result = calc.calculate("VOLUME_SMA", "volume_sma", {"period": 20})
            values = _series_to_indicator_values(result.values, ohlcv_data)

        if values:
            indicator_results[ind_name] = values

    return IndicatorsResponse(
        symbol=symbol,
        ohlcv=ohlcv_data,
        indicators=indicator_results,
    )


def _series_to_indicator_values(
    series: "pd.Series[Any]", ohlcv_data: list[dict[str, Any]]
) -> list[IndicatorValue]:
    """Convert pandas Series to list of IndicatorValue."""
    return [
        IndicatorValue(
            time=ohlcv_data[i]["time"],
            value=float(v) if not pd.isna(v) else None,
        )
        for i, v in enumerate(series)
    ]


@router.get("/charts/correlation", response_model=CorrelationResponse)
async def get_correlation(
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str, Query(description="Comma-separated symbols")] = "",
    benchmark: Annotated[str | None, Query(description="Include benchmark")] = None,
    days: Annotated[int, Query(ge=30, le=365)] = 90,
) -> CorrelationResponse:
    """Calculate correlation matrix between symbols.

    Uses daily returns (not prices) for correlation to avoid spurious
    correlations from trending prices.
    """
    repo = StockRepository(db)

    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if len(symbol_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 symbols required")

    # Add benchmark if specified
    if benchmark:
        benchmark_symbol = benchmark.upper()
        if benchmark_symbol not in symbol_list:
            symbol_list.append(benchmark_symbol)

    # Fetch data for each symbol
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    returns_dict: dict[str, "pd.Series[Any]"] = {}

    for symbol in symbol_list:
        ohlcv_list = repo.get_ohlcv(
            symbol,
            start_date=start_date,
            end_date=end_date,
            limit=days + 10,  # Extra buffer
        )

        if len(ohlcv_list) < 20:  # Minimum data requirement
            continue

        # Calculate daily returns
        prices = pd.Series(
            [float(o.close_price) for o in reversed(ohlcv_list)],
            index=[o.trade_date for o in reversed(ohlcv_list)],
        )
        returns = prices.pct_change().dropna()
        returns_dict[symbol] = returns

    if len(returns_dict) < 2:
        raise HTTPException(status_code=404, detail="Not enough data for correlation analysis")

    # Create returns DataFrame aligned by date
    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.dropna()

    if len(returns_df) < 20:
        raise HTTPException(status_code=400, detail="Insufficient overlapping data for correlation")

    # Calculate correlation matrix
    corr_matrix = returns_df.corr()

    # Build response
    symbols_in_matrix = list(corr_matrix.columns)
    matrix = corr_matrix.values.tolist()

    # Round values
    matrix = [[round(v, 4) for v in row] for row in matrix]

    # Build entries list
    entries = []
    for i, sym1 in enumerate(symbols_in_matrix):
        for j, sym2 in enumerate(symbols_in_matrix):
            if i < j:  # Upper triangle only (avoid duplicates)
                corr_value = corr_matrix.iloc[i, j]
                entries.append(
                    CorrelationEntry(
                        symbol1=sym1,
                        symbol2=sym2,
                        correlation=round(float(corr_value), 4),  # type: ignore[arg-type]
                    )
                )

    return CorrelationResponse(
        symbols=symbols_in_matrix,
        matrix=matrix,
        entries=entries,
    )


@router.get("/charts/sector-etf/{sector}")
async def get_sector_etf(sector: str) -> dict[str, str]:
    """Get the ETF symbol for a sector."""
    etf = SECTOR_ETFS.get(sector)
    if not etf:
        # Try case-insensitive match
        for s, e in SECTOR_ETFS.items():
            if s.lower() == sector.lower():
                return {"sector": s, "etf": e}
        raise HTTPException(status_code=404, detail=f"Unknown sector: {sector}")

    return {"sector": sector, "etf": etf}


@router.get("/charts/sector-etfs")
async def list_sector_etfs() -> dict[str, Any]:
    """List all sector ETF mappings."""
    return {
        "etfs": SECTOR_ETFS,
        "benchmark": MARKET_BENCHMARK,
    }

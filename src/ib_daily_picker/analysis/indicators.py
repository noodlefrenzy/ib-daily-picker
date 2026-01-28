"""
Technical indicator calculations.

PURPOSE: Calculate common technical indicators from OHLCV data
DEPENDENCIES: numpy, pandas

ARCHITECTURE NOTES:
- Pure functions for indicator calculations
- Takes OHLCV list and returns series/values
- Supports RSI, SMA, EMA, ATR, MACD, Bollinger Bands
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

import numpy as np
import pandas as pd

from ib_daily_picker.models import OHLCV


@dataclass
class IndicatorResult:
    """Result of an indicator calculation."""

    name: str
    values: pd.Series
    params: dict

    def latest(self) -> float | None:
        """Get the most recent value."""
        if self.values.empty:
            return None
        return float(self.values.iloc[-1])

    def at_index(self, idx: int) -> float | None:
        """Get value at a specific index."""
        if idx < 0 or idx >= len(self.values):
            return None
        return float(self.values.iloc[idx])


def ohlcv_to_dataframe(ohlcv_list: Sequence[OHLCV]) -> pd.DataFrame:
    """Convert OHLCV list to pandas DataFrame.

    Args:
        ohlcv_list: List of OHLCV objects

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    data = []
    for o in ohlcv_list:
        data.append(
            {
                "date": o.trade_date,
                "open": float(o.open_price),
                "high": float(o.high_price),
                "low": float(o.low_price),
                "close": float(o.close_price),
                "volume": o.volume,
            }
        )

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


def calculate_sma(
    data: pd.Series | Sequence[float],
    period: int = 14,
) -> pd.Series:
    """Calculate Simple Moving Average.

    Args:
        data: Price series or sequence
        period: Number of periods

    Returns:
        SMA values as Series
    """
    series = pd.Series(data) if not isinstance(data, pd.Series) else data
    return series.rolling(window=period).mean()


def calculate_ema(
    data: pd.Series | Sequence[float],
    period: int = 14,
) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        data: Price series or sequence
        period: Number of periods

    Returns:
        EMA values as Series
    """
    series = pd.Series(data) if not isinstance(data, pd.Series) else data
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(
    data: pd.Series | Sequence[float],
    period: int = 14,
) -> pd.Series:
    """Calculate Relative Strength Index.

    Args:
        data: Price series or sequence (typically close prices)
        period: RSI period (default 14)

    Returns:
        RSI values as Series (0-100)
    """
    series = pd.Series(data) if not isinstance(data, pd.Series) else data
    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_atr(
    high: pd.Series | Sequence[float],
    low: pd.Series | Sequence[float],
    close: pd.Series | Sequence[float],
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period

    Returns:
        ATR values as Series
    """
    high_s = pd.Series(high) if not isinstance(high, pd.Series) else high
    low_s = pd.Series(low) if not isinstance(low, pd.Series) else low
    close_s = pd.Series(close) if not isinstance(close, pd.Series) else close

    prev_close = close_s.shift(1)

    tr1 = high_s - low_s
    tr2 = (high_s - prev_close).abs()
    tr3 = (low_s - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1 / period, min_periods=period).mean()
    return atr


@dataclass
class MACDResult:
    """Result of MACD calculation."""

    macd_line: pd.Series
    signal_line: pd.Series
    histogram: pd.Series


def calculate_macd(
    data: pd.Series | Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """Calculate MACD (Moving Average Convergence Divergence).

    Args:
        data: Price series (typically close prices)
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line EMA period

    Returns:
        MACDResult with macd_line, signal_line, and histogram
    """
    series = pd.Series(data) if not isinstance(data, pd.Series) else data

    fast_ema = calculate_ema(series, fast_period)
    slow_ema = calculate_ema(series, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return MACDResult(
        macd_line=macd_line,
        signal_line=signal_line,
        histogram=histogram,
    )


@dataclass
class BollingerResult:
    """Result of Bollinger Bands calculation."""

    upper_band: pd.Series
    middle_band: pd.Series
    lower_band: pd.Series
    bandwidth: pd.Series


def calculate_bollinger_bands(
    data: pd.Series | Sequence[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> BollingerResult:
    """Calculate Bollinger Bands.

    Args:
        data: Price series (typically close prices)
        period: SMA period
        std_dev: Number of standard deviations

    Returns:
        BollingerResult with upper, middle, lower bands and bandwidth
    """
    series = pd.Series(data) if not isinstance(data, pd.Series) else data

    middle_band = calculate_sma(series, period)
    std = series.rolling(window=period).std()

    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    bandwidth = (upper_band - lower_band) / middle_band * 100

    return BollingerResult(
        upper_band=upper_band,
        middle_band=middle_band,
        lower_band=lower_band,
        bandwidth=bandwidth,
    )


def calculate_volume_sma(
    volume: pd.Series | Sequence[int],
    period: int = 20,
) -> pd.Series:
    """Calculate Volume Simple Moving Average.

    Args:
        volume: Volume data
        period: SMA period

    Returns:
        Volume SMA as Series
    """
    series = pd.Series(volume) if not isinstance(volume, pd.Series) else volume
    return series.rolling(window=period).mean()


class IndicatorCalculator:
    """Calculate multiple indicators for OHLCV data."""

    def __init__(self, ohlcv_list: Sequence[OHLCV]) -> None:
        """Initialize with OHLCV data.

        Args:
            ohlcv_list: List of OHLCV objects (should be sorted by date)
        """
        self._df = ohlcv_to_dataframe(ohlcv_list)
        self._results: dict[str, IndicatorResult] = {}

    @property
    def df(self) -> pd.DataFrame:
        """Get the underlying DataFrame."""
        return self._df

    def calculate(
        self,
        indicator_type: str,
        name: str,
        params: dict | None = None,
    ) -> IndicatorResult:
        """Calculate an indicator and cache the result.

        Args:
            indicator_type: Type of indicator (RSI, SMA, EMA, ATR, etc.)
            name: Name to give this indicator
            params: Indicator parameters

        Returns:
            IndicatorResult with calculated values
        """
        params = params or {}
        indicator_type = indicator_type.upper()

        # Check cache
        cache_key = f"{name}_{indicator_type}_{hash(frozenset(params.items()))}"
        if cache_key in self._results:
            return self._results[cache_key]

        # Get source data
        source = params.get("source", "close")
        data = self._df[source] if source in self._df.columns else self._df["close"]

        # Calculate based on type
        if indicator_type == "RSI":
            period = params.get("period", 14)
            values = calculate_rsi(data, period)

        elif indicator_type == "SMA":
            period = params.get("period", 14)
            values = calculate_sma(data, period)

        elif indicator_type == "EMA":
            period = params.get("period", 14)
            values = calculate_ema(data, period)

        elif indicator_type == "ATR":
            period = params.get("period", 14)
            values = calculate_atr(
                self._df["high"],
                self._df["low"],
                self._df["close"],
                period,
            )

        elif indicator_type == "MACD":
            fast = params.get("fast_period", 12)
            slow = params.get("slow_period", 26)
            signal = params.get("signal_period", 9)
            macd_result = calculate_macd(data, fast, slow, signal)
            # Return the MACD line by default
            values = macd_result.macd_line

        elif indicator_type == "BOLLINGER":
            period = params.get("period", 20)
            std_dev = params.get("std_dev", 2.0)
            bollinger_result = calculate_bollinger_bands(data, period, std_dev)
            # Return the middle band by default
            values = bollinger_result.middle_band

        elif indicator_type == "VOLUME_SMA":
            period = params.get("period", 20)
            values = calculate_volume_sma(self._df["volume"], period)

        else:
            raise ValueError(f"Unknown indicator type: {indicator_type}")

        result = IndicatorResult(name=name, values=values, params=params)
        self._results[cache_key] = result
        return result

    def get(self, name: str) -> IndicatorResult | None:
        """Get a cached indicator by name.

        Args:
            name: Indicator name

        Returns:
            IndicatorResult or None if not found
        """
        for key, result in self._results.items():
            if result.name == name:
                return result
        return None

    def calculate_all(
        self,
        indicators: list[dict],
    ) -> dict[str, IndicatorResult]:
        """Calculate multiple indicators.

        Args:
            indicators: List of indicator configs (dicts with 'name', 'type', 'params')

        Returns:
            Dict mapping names to IndicatorResults
        """
        results = {}
        for ind in indicators:
            result = self.calculate(
                indicator_type=ind["type"],
                name=ind["name"],
                params=ind.get("params"),
            )
            results[ind["name"]] = result
        return results

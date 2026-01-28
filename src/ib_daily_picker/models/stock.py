"""
Stock domain models.

PURPOSE: Pydantic models for stock data and metadata
DEPENDENCIES: pydantic, decimal

ARCHITECTURE NOTES:
- Use Decimal for all price data (no float drift)
- Dates as datetime.date, timestamps as datetime.datetime with UTC
- Separate OHLCV data from metadata (different update frequencies)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StockMetadata(BaseModel):
    """Stock metadata (company info, sector, etc.)."""

    symbol: str = Field(..., description="Stock ticker symbol")
    name: Optional[str] = Field(None, description="Company name")
    sector: Optional[str] = Field(None, description="Business sector")
    industry: Optional[str] = Field(None, description="Industry classification")
    market_cap: Optional[int] = Field(None, description="Market capitalization")
    currency: str = Field(default="USD", description="Trading currency")
    exchange: Optional[str] = Field(None, description="Stock exchange")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last metadata update"
    )

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper().strip()


class OHLCV(BaseModel):
    """Daily OHLCV (Open, High, Low, Close, Volume) data."""

    symbol: str = Field(..., description="Stock ticker symbol")
    trade_date: date = Field(..., description="Trading date", alias="date")
    open_price: Decimal = Field(..., description="Opening price", alias="open")
    high_price: Decimal = Field(..., description="Highest price", alias="high")
    low_price: Decimal = Field(..., description="Lowest price", alias="low")
    close_price: Decimal = Field(..., description="Closing price", alias="close")
    volume: int = Field(..., description="Trading volume")
    adjusted_close: Optional[Decimal] = Field(None, description="Split-adjusted close")
    dividend: Decimal = Field(default=Decimal("0"), description="Dividend amount")
    stock_split: Decimal = Field(default=Decimal("1"), description="Stock split ratio")

    model_config = {"populate_by_name": True}

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper().strip()

    @field_validator(
        "open_price", "high_price", "low_price", "close_price", "adjusted_close", mode="before"
    )
    @classmethod
    def to_decimal(cls, v: float | str | Decimal | None) -> Decimal | None:
        """Convert price to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("dividend", "stock_split", mode="before")
    @classmethod
    def to_decimal_with_default(cls, v: float | str | Decimal | None) -> Decimal:
        """Convert to Decimal with default handling."""
        if v is None:
            return Decimal("0")
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def model_post_init(self, _context: object) -> None:
        """Validate OHLCV relationships."""
        if self.low_price > self.high_price:
            raise ValueError(
                f"Low ({self.low_price}) cannot be greater than high ({self.high_price})"
            )
        if self.open_price < self.low_price or self.open_price > self.high_price:
            raise ValueError(f"Open ({self.open_price}) must be between low and high")
        if self.close_price < self.low_price or self.close_price > self.high_price:
            raise ValueError(f"Close ({self.close_price}) must be between low and high")

    @property
    def change(self) -> Decimal:
        """Price change from open to close."""
        return self.close_price - self.open_price

    @property
    def change_percent(self) -> Decimal:
        """Percentage change from open to close."""
        if self.open_price == 0:
            return Decimal("0")
        return (self.change / self.open_price) * 100

    @property
    def price_range(self) -> Decimal:
        """Price range (high - low)."""
        return self.high_price - self.low_price

    @property
    def is_bullish(self) -> bool:
        """True if close > open."""
        return self.close_price > self.open_price


class OHLCVBatch(BaseModel):
    """Batch of OHLCV data for a symbol."""

    symbol: str = Field(..., description="Stock ticker symbol")
    data: list[OHLCV] = Field(default_factory=list, description="OHLCV records")

    @property
    def date_range(self) -> tuple[date, date] | None:
        """Return the date range of data."""
        if not self.data:
            return None
        dates = sorted(d.trade_date for d in self.data)
        return (dates[0], dates[-1])

    @property
    def count(self) -> int:
        """Number of records."""
        return len(self.data)


class StockWithData(BaseModel):
    """Stock with both metadata and OHLCV data."""

    metadata: StockMetadata
    ohlcv: list[OHLCV] = Field(default_factory=list)

    @property
    def symbol(self) -> str:
        """Get symbol from metadata."""
        return self.metadata.symbol

    @property
    def latest_price(self) -> Decimal | None:
        """Get most recent closing price."""
        if not self.ohlcv:
            return None
        return max(self.ohlcv, key=lambda x: x.trade_date).close_price

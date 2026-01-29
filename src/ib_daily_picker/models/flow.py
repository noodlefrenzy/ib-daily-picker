"""
Flow domain models.

PURPOSE: Pydantic models for flow alerts and options flow data
DEPENDENCIES: pydantic, decimal

ARCHITECTURE NOTES:
- Flow alerts from Unusual Whales API
- Direction and sentiment enums for type safety
- Premium stored as Decimal for accuracy
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FlowDirection(str, Enum):
    """Direction of the flow (bullish/bearish)."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class OptionType(str, Enum):
    """Option type (call/put)."""

    CALL = "call"
    PUT = "put"


class AlertType(str, Enum):
    """Type of flow alert."""

    UNUSUAL_VOLUME = "unusual_volume"
    UNUSUAL_SWEEP = "unusual_sweep"
    GOLDEN_SWEEP = "golden_sweep"
    BLOCK_TRADE = "block_trade"
    REPEAT_SWEEPS = "repeat_sweeps"
    OPENING_POSITION = "opening_position"
    OTHER = "other"


class Sentiment(str, Enum):
    """Market sentiment indicator."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class FlowAlert(BaseModel):
    """Flow alert from Unusual Whales or similar source."""

    id: str = Field(..., description="Unique alert identifier")
    symbol: str = Field(..., description="Stock ticker symbol")
    alert_time: datetime = Field(..., description="When the alert was triggered")
    alert_type: AlertType = Field(..., description="Type of flow alert")
    direction: FlowDirection = Field(
        default=FlowDirection.UNKNOWN, description="Bullish/bearish direction"
    )
    premium: Decimal | None = Field(None, description="Total premium paid")
    volume: int | None = Field(None, description="Contract volume")
    open_interest: int | None = Field(None, description="Open interest")
    strike: Decimal | None = Field(None, description="Strike price")
    expiration: date | None = Field(None, description="Option expiration date")
    option_type: OptionType | None = Field(None, description="Call or put")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Overall sentiment")
    raw_data: dict[str, Any] | None = Field(None, description="Original API response")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation time"
    )

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper().strip()

    @field_validator("premium", "strike", mode="before")
    @classmethod
    def to_decimal(cls, v: float | str | Decimal | None) -> Decimal | None:
        """Convert to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("alert_type", mode="before")
    @classmethod
    def normalize_alert_type(cls, v: str | AlertType) -> AlertType:
        """Normalize alert type strings."""
        if isinstance(v, AlertType):
            return v
        v_lower = v.lower().replace(" ", "_").replace("-", "_")
        try:
            return AlertType(v_lower)
        except ValueError:
            return AlertType.OTHER

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, v: str | FlowDirection | None) -> FlowDirection:
        """Normalize direction strings."""
        if v is None:
            return FlowDirection.UNKNOWN
        if isinstance(v, FlowDirection):
            return v
        v_lower = v.lower().strip()
        try:
            return FlowDirection(v_lower)
        except ValueError:
            return FlowDirection.UNKNOWN

    @property
    def is_bullish(self) -> bool:
        """True if the flow indicates bullish sentiment."""
        return self.direction == FlowDirection.BULLISH or self.sentiment == Sentiment.BULLISH

    @property
    def is_bearish(self) -> bool:
        """True if the flow indicates bearish sentiment."""
        return self.direction == FlowDirection.BEARISH or self.sentiment == Sentiment.BEARISH

    @property
    def days_to_expiry(self) -> int | None:
        """Days until option expiration."""
        if not self.expiration:
            return None
        delta = self.expiration - self.alert_time.date()
        return delta.days

    @property
    def is_near_term(self) -> bool:
        """True if expiration is within 30 days."""
        dte = self.days_to_expiry
        return dte is not None and dte <= 30


class FlowAlertBatch(BaseModel):
    """Batch of flow alerts."""

    alerts: list[FlowAlert] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def count(self) -> int:
        """Number of alerts."""
        return len(self.alerts)

    @property
    def bullish_count(self) -> int:
        """Number of bullish alerts."""
        return sum(1 for a in self.alerts if a.is_bullish)

    @property
    def bearish_count(self) -> int:
        """Number of bearish alerts."""
        return sum(1 for a in self.alerts if a.is_bearish)

    @property
    def total_premium(self) -> Decimal:
        """Total premium across all alerts."""
        return sum((a.premium or Decimal("0") for a in self.alerts), start=Decimal("0"))

    def filter_by_symbol(self, symbol: str) -> FlowAlertBatch:
        """Filter alerts by symbol."""
        symbol = symbol.upper()
        return FlowAlertBatch(
            alerts=[a for a in self.alerts if a.symbol == symbol],
            fetched_at=self.fetched_at,
        )

    def filter_by_direction(self, direction: FlowDirection) -> FlowAlertBatch:
        """Filter alerts by direction."""
        return FlowAlertBatch(
            alerts=[a for a in self.alerts if a.direction == direction],
            fetched_at=self.fetched_at,
        )

    def filter_by_min_premium(self, min_premium: Decimal) -> FlowAlertBatch:
        """Filter alerts by minimum premium."""
        return FlowAlertBatch(
            alerts=[a for a in self.alerts if a.premium and a.premium >= min_premium],
            fetched_at=self.fetched_at,
        )

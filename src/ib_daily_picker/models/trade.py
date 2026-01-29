"""
Trade domain models.

PURPOSE: Pydantic models for trade journal and execution tracking
DEPENDENCIES: pydantic, decimal

ARCHITECTURE NOTES:
- Trades track actual executions (vs recommendations)
- Calculate PnL, R-multiples, MFE/MAE
- Support tagging and notes for journaling
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class TradeDirection(str, Enum):
    """Direction of the trade."""

    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    """Status of a trade."""

    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Trade(BaseModel):
    """Executed trade for journaling."""

    id: str = Field(..., description="Unique trade identifier")
    recommendation_id: str | None = Field(None, description="Source recommendation ID")
    symbol: str = Field(..., description="Stock ticker symbol")
    direction: TradeDirection = Field(..., description="Long or short")
    entry_price: Decimal = Field(..., description="Entry price")
    entry_time: datetime = Field(..., description="Entry timestamp")
    exit_price: Decimal | None = Field(None, description="Exit price")
    exit_time: datetime | None = Field(None, description="Exit timestamp")
    position_size: Decimal = Field(..., description="Number of shares")
    stop_loss: Decimal | None = Field(None, description="Stop loss price")
    take_profit: Decimal | None = Field(None, description="Take profit target")
    pnl: Decimal | None = Field(None, description="Profit/loss in dollars")
    pnl_percent: Decimal | None = Field(None, description="Profit/loss percentage")
    r_multiple: Decimal | None = Field(None, description="R-multiple (PnL / risk)")
    mfe: Decimal | None = Field(
        None, description="Maximum favorable excursion (best unrealized price)"
    )
    mae: Decimal | None = Field(
        None, description="Maximum adverse excursion (worst unrealized price)"
    )
    notes: str | None = Field(None, description="Trade notes")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    status: TradeStatus = Field(default=TradeStatus.OPEN, description="Trade status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("symbol", mode="before")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase."""
        return v.upper().strip()

    @field_validator(
        "entry_price",
        "exit_price",
        "position_size",
        "stop_loss",
        "take_profit",
        "pnl",
        "pnl_percent",
        "r_multiple",
        "mfe",
        "mae",
        mode="before",
    )
    @classmethod
    def to_decimal(cls, v: float | str | Decimal | None) -> Decimal | None:
        """Convert to Decimal."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def calculate_metrics(self) -> Trade:
        """Calculate PnL metrics if trade is closed."""
        if self.exit_price is not None and self.status == TradeStatus.CLOSED:
            # Calculate PnL
            if self.direction == TradeDirection.LONG:
                price_diff = self.exit_price - self.entry_price
            else:
                price_diff = self.entry_price - self.exit_price

            self.pnl = price_diff * self.position_size
            self.pnl_percent = (price_diff / self.entry_price) * 100

            # Calculate R-multiple if stop loss is set
            if self.stop_loss is not None:
                risk_per_share = abs(self.entry_price - self.stop_loss)
                if risk_per_share > 0:
                    self.r_multiple = price_diff / risk_per_share

        return self

    @property
    def is_open(self) -> bool:
        """Check if trade is still open."""
        return self.status == TradeStatus.OPEN

    @property
    def is_winner(self) -> bool | None:
        """Check if trade was profitable (None if still open)."""
        if self.pnl is None:
            return None
        return self.pnl > 0

    @property
    def risk_amount(self) -> Decimal | None:
        """Calculate total risk amount."""
        if self.stop_loss is None:
            return None
        risk_per_share = abs(self.entry_price - self.stop_loss)
        return risk_per_share * self.position_size

    @property
    def duration_minutes(self) -> int | None:
        """Trade duration in minutes."""
        if self.exit_time is None:
            return None
        delta = self.exit_time - self.entry_time
        return int(delta.total_seconds() / 60)

    def close(
        self,
        exit_price: Decimal,
        exit_time: datetime | None = None,
        notes: str | None = None,
    ) -> Trade:
        """Close the trade with given exit price."""
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.utcnow()
        self.status = TradeStatus.CLOSED
        self.updated_at = datetime.utcnow()
        if notes:
            if self.notes:
                self.notes = f"{self.notes}\n\n{notes}"
            else:
                self.notes = notes

        # Recalculate metrics
        return self.model_validate(self.model_dump())

    def update_excursion(self, current_price: Decimal) -> None:
        """Update MFE/MAE based on current price."""
        if self.direction == TradeDirection.LONG:
            # For long trades, MFE is highest price, MAE is lowest
            if self.mfe is None or current_price > self.mfe:
                self.mfe = current_price
            if self.mae is None or current_price < self.mae:
                self.mae = current_price
        else:
            # For short trades, MFE is lowest price, MAE is highest
            if self.mfe is None or current_price < self.mfe:
                self.mfe = current_price
            if self.mae is None or current_price > self.mae:
                self.mae = current_price
        self.updated_at = datetime.utcnow()


class TradeMetrics(BaseModel):
    """Aggregated trade metrics for analysis."""

    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    total_pnl: Decimal = Field(default=Decimal("0"))
    win_rate: Decimal = Field(default=Decimal("0"))
    avg_winner: Decimal = Field(default=Decimal("0"))
    avg_loser: Decimal = Field(default=Decimal("0"))
    profit_factor: Decimal | None = Field(None)
    avg_r_multiple: Decimal | None = Field(None)
    largest_winner: Decimal = Field(default=Decimal("0"))
    largest_loser: Decimal = Field(default=Decimal("0"))

    @classmethod
    def from_trades(cls, trades: list[Trade]) -> TradeMetrics:
        """Calculate metrics from a list of closed trades."""
        closed = [t for t in trades if t.status == TradeStatus.CLOSED and t.pnl is not None]

        if not closed:
            return cls()

        winners = [t for t in closed if t.pnl and t.pnl > 0]
        losers = [t for t in closed if t.pnl and t.pnl < 0]

        total_pnl = sum((t.pnl for t in closed if t.pnl), start=Decimal("0"))
        gross_profit = sum((t.pnl for t in winners if t.pnl), start=Decimal("0"))
        gross_loss = abs(sum((t.pnl for t in losers if t.pnl), start=Decimal("0")))

        win_rate = (
            Decimal(str(len(winners))) / Decimal(str(len(closed))) if closed else Decimal("0")
        )
        avg_winner = gross_profit / len(winners) if winners else Decimal("0")
        avg_loser = gross_loss / len(losers) if losers else Decimal("0")
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

        r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]
        avg_r = sum(r_multiples, start=Decimal("0")) / len(r_multiples) if r_multiples else None

        pnls = [t.pnl for t in closed if t.pnl is not None]
        largest_winner = max(pnls) if pnls else Decimal("0")
        largest_loser = min(pnls) if pnls else Decimal("0")

        return cls(
            total_trades=len(closed),
            winning_trades=len(winners),
            losing_trades=len(losers),
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            profit_factor=profit_factor,
            avg_r_multiple=avg_r,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
        )

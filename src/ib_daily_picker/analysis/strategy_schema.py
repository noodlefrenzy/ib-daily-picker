"""
Strategy YAML schema definitions.

PURPOSE: Pydantic models for validating strategy YAML files
DEPENDENCIES: pydantic

ARCHITECTURE NOTES:
- Strategies are defined in YAML for easy editing
- Schema validates structure and provides defaults
- Supports indicators, entry/exit conditions, risk profiles
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class IndicatorType(str, Enum):
    """Supported indicator types."""

    RSI = "RSI"
    SMA = "SMA"
    EMA = "EMA"
    ATR = "ATR"
    MACD = "MACD"
    BOLLINGER = "BOLLINGER"
    VWAP = "VWAP"
    VOLUME_SMA = "VOLUME_SMA"


class ConditionOperator(str, Enum):
    """Comparison operators for conditions."""

    LT = "lt"  # less than
    LE = "le"  # less than or equal
    GT = "gt"  # greater than
    GE = "ge"  # greater than or equal
    EQ = "eq"  # equal
    NE = "ne"  # not equal
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"


class ConditionLogic(str, Enum):
    """Logic for combining conditions."""

    ALL = "all"  # AND - all conditions must be true
    ANY = "any"  # OR - any condition must be true


class FlowConditionType(str, Enum):
    """Types of flow-based conditions."""

    FLOW_SIGNAL = "flow_signal"
    PREMIUM_THRESHOLD = "premium_threshold"
    VOLUME_SPIKE = "volume_spike"


class ExitType(str, Enum):
    """Types of exit conditions."""

    PERCENTAGE = "percentage"
    ATR_MULTIPLE = "atr_multiple"
    FIXED_PRICE = "fixed_price"
    TRAILING_STOP = "trailing_stop"


class RiskProfileName(str, Enum):
    """Predefined risk profile names."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class IndicatorConfig(BaseModel):
    """Configuration for a single indicator."""

    name: str = Field(..., description="Unique name for this indicator")
    type: IndicatorType = Field(..., description="Type of indicator")
    params: dict[str, Any] = Field(default_factory=dict, description="Indicator parameters")

    @field_validator("params", mode="before")
    @classmethod
    def ensure_params(cls, v: dict | None) -> dict:
        """Ensure params is a dict."""
        return v or {}

    @model_validator(mode="after")
    def validate_params(self) -> "IndicatorConfig":
        """Validate params based on indicator type."""
        required = {
            IndicatorType.RSI: ["period"],
            IndicatorType.SMA: ["period"],
            IndicatorType.EMA: ["period"],
            IndicatorType.ATR: ["period"],
            IndicatorType.MACD: ["fast_period", "slow_period", "signal_period"],
            IndicatorType.BOLLINGER: ["period", "std_dev"],
            IndicatorType.VOLUME_SMA: ["period"],
        }

        if self.type in required:
            for param in required[self.type]:
                if param not in self.params:
                    # Set defaults
                    defaults = {
                        "period": 14,
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                        "std_dev": 2.0,
                        "source": "close",
                    }
                    if param in defaults:
                        self.params[param] = defaults[param]

        return self


class IndicatorCondition(BaseModel):
    """Condition based on indicator value."""

    type: Literal["indicator_threshold"] = "indicator_threshold"
    indicator: str = Field(..., description="Name of indicator to check")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: float | str = Field(
        ..., description="Value to compare against (number or indicator name)"
    )


class FlowCondition(BaseModel):
    """Condition based on flow data."""

    type: Literal["flow_signal"] = "flow_signal"
    direction: str = Field(..., description="bullish, bearish, or any")
    min_premium: float | None = Field(None, description="Minimum premium in dollars")
    min_volume: int | None = Field(None, description="Minimum volume")
    recency_minutes: int = Field(default=60, description="Look back this many minutes for flow")


class PriceCondition(BaseModel):
    """Condition based on price action."""

    type: Literal["price_action"] = "price_action"
    indicator: str = Field(..., description="Price indicator (e.g., 'close', 'high')")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: float | str = Field(..., description="Value to compare against")


Condition = IndicatorCondition | FlowCondition | PriceCondition


class EntryConfig(BaseModel):
    """Entry signal configuration."""

    conditions: list[Condition] = Field(..., description="List of conditions for entry")
    logic: ConditionLogic = Field(
        default=ConditionLogic.ALL, description="How to combine conditions"
    )


class ExitTarget(BaseModel):
    """Exit target configuration."""

    type: ExitType = Field(..., description="Type of exit")
    value: float = Field(..., description="Value for exit calculation")
    multiplier: float | None = Field(None, description="Multiplier for ATR-based exits")


class ExitConfig(BaseModel):
    """Exit configuration for a strategy."""

    take_profit: ExitTarget | None = Field(None, description="Take profit target")
    stop_loss: ExitTarget | None = Field(None, description="Stop loss target")
    trailing_stop: ExitTarget | None = Field(None, description="Trailing stop")
    time_exit_bars: int | None = Field(None, description="Exit after N bars regardless of price")


class RiskConfig(BaseModel):
    """Risk management configuration."""

    profile: RiskProfileName = Field(
        default=RiskProfileName.MODERATE, description="Risk profile name"
    )
    risk_per_trade: Decimal | None = Field(None, description="Override risk per trade (0-1)")
    max_positions: int | None = Field(None, description="Override max positions")
    min_risk_reward: Decimal | None = Field(None, description="Override minimum risk/reward ratio")

    @field_validator("risk_per_trade", mode="before")
    @classmethod
    def to_decimal(cls, v: float | str | Decimal | None) -> Decimal | None:
        """Convert to Decimal."""
        if v is None:
            return None
        return Decimal(str(v))

    @field_validator("min_risk_reward", mode="before")
    @classmethod
    def to_decimal_rr(cls, v: float | str | Decimal | None) -> Decimal | None:
        """Convert to Decimal."""
        if v is None:
            return None
        return Decimal(str(v))


class StrategyMetadata(BaseModel):
    """Strategy metadata."""

    name: str = Field(..., description="Strategy name")
    version: str = Field(default="1.0.0", description="Strategy version")
    description: str | None = Field(None, description="Strategy description")
    author: str | None = Field(None, description="Strategy author")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class Strategy(BaseModel):
    """Complete strategy definition."""

    strategy: StrategyMetadata = Field(..., description="Strategy metadata")
    indicators: list[IndicatorConfig] = Field(
        default_factory=list, description="Indicators to calculate"
    )
    entry: EntryConfig = Field(..., description="Entry signal configuration")
    exit: ExitConfig = Field(default_factory=ExitConfig, description="Exit configuration")
    risk: RiskConfig = Field(default_factory=RiskConfig, description="Risk configuration")
    filters: dict[str, Any] = Field(default_factory=dict, description="Additional filters")

    @property
    def name(self) -> str:
        """Get strategy name."""
        return self.strategy.name

    @property
    def version(self) -> str:
        """Get strategy version."""
        return self.strategy.version

    def get_indicator(self, name: str) -> IndicatorConfig | None:
        """Get indicator config by name."""
        for ind in self.indicators:
            if ind.name == name:
                return ind
        return None

    def validate_indicators_referenced(self) -> list[str]:
        """Check that all referenced indicators are defined.

        Returns:
            List of missing indicator names
        """
        defined = {ind.name for ind in self.indicators}
        referenced = set()

        # Check entry conditions
        for cond in self.entry.conditions:
            if hasattr(cond, "indicator"):
                referenced.add(cond.indicator)

        missing = referenced - defined
        return list(missing)

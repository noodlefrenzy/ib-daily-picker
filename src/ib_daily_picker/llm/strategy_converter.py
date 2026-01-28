"""
Natural language to YAML strategy converter.

PURPOSE: Convert English strategy descriptions to valid YAML strategies
DEPENDENCIES: llm.client, analysis.strategy_schema

ARCHITECTURE NOTES:
- Uses LLM with structured output for reliable conversion
- Validates output against strategy schema
- Supports incremental refinement
"""

from __future__ import annotations

import logging
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from ib_daily_picker.analysis.strategy_schema import (
    ConditionLogic,
    ConditionOperator,
    EntryConfig,
    ExitConfig,
    ExitTarget,
    ExitType,
    FlowCondition,
    IndicatorCondition,
    IndicatorConfig,
    IndicatorType,
    RiskConfig,
    RiskProfileName,
    Strategy,
    StrategyMetadata,
)
from ib_daily_picker.llm.client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


# Pydantic models for LLM structured output
class LLMIndicator(BaseModel):
    """Indicator specification from LLM."""

    name: str = Field(..., description="Unique identifier like 'rsi_14'")
    type: str = Field(..., description="One of: RSI, SMA, EMA, ATR, MACD, BOLLINGER, VOLUME_SMA")
    period: int = Field(14, description="Lookback period")
    source: str = Field("close", description="Price source: open, high, low, close")


class LLMIndicatorCondition(BaseModel):
    """Indicator-based entry condition from LLM."""

    indicator: str = Field(..., description="Indicator name to check")
    operator: str = Field(
        ..., description="One of: lt, le, gt, ge, eq, ne, cross_above, cross_below"
    )
    value: float | str = Field(..., description="Threshold value or another indicator name")


class LLMFlowCondition(BaseModel):
    """Flow-based entry condition from LLM."""

    direction: str = Field("bullish", description="One of: bullish, bearish, any")
    min_premium: int = Field(100000, description="Minimum premium in dollars")
    recency_minutes: int = Field(60, description="How recent the flow should be")


class LLMExitRule(BaseModel):
    """Exit rule from LLM."""

    type: str = Field(..., description="One of: percentage, atr_multiple, fixed_price")
    value: float = Field(..., description="The value for exit calculation")


class LLMStrategySpec(BaseModel):
    """Full strategy specification from LLM."""

    name: str = Field(..., description="Strategy name")
    description: str = Field(..., description="Brief description of the strategy")
    version: str = Field("1.0.0", description="Version string")

    indicators: list[LLMIndicator] = Field(
        ..., description="List of technical indicators to calculate"
    )

    entry_logic: str = Field(
        "all", description="How to combine conditions: 'all' (AND) or 'any' (OR)"
    )
    indicator_conditions: list[LLMIndicatorCondition] = Field(
        default_factory=list, description="Indicator-based entry conditions"
    )
    flow_conditions: list[LLMFlowCondition] = Field(
        default_factory=list, description="Flow-based entry conditions"
    )

    take_profit: LLMExitRule | None = Field(None, description="Take profit rule")
    stop_loss: LLMExitRule | None = Field(None, description="Stop loss rule")
    trailing_stop: LLMExitRule | None = Field(None, description="Trailing stop rule")

    risk_profile: str = Field("moderate", description="One of: conservative, moderate, aggressive")
    min_risk_reward: float = Field(2.0, description="Minimum risk/reward ratio")


SYSTEM_PROMPT = """You are a trading strategy designer. Your job is to convert natural language descriptions of trading strategies into structured specifications.

When designing a strategy:
1. Identify the key indicators mentioned (RSI, SMA, EMA, ATR, MACD, Bollinger Bands)
2. Extract entry conditions (indicator thresholds, crossovers)
3. Extract exit rules (take profit, stop loss)
4. Determine the risk profile (conservative, moderate, aggressive)

Common patterns:
- "RSI below 30" → RSI oversold condition
- "RSI above 70" → RSI overbought condition
- "price above SMA" → uptrend confirmation
- "bullish flow" → options flow indicating buying interest
- "2:1 risk/reward" → min_risk_reward of 2.0
- "5% take profit" → percentage-based take profit
- "2 ATR stop loss" → ATR multiple stop loss

Default values when not specified:
- RSI period: 14
- SMA period: 50 (for trend), 20 (for short-term)
- EMA period: 20
- ATR period: 14
- Take profit: 5% (percentage)
- Stop loss: 2 ATR or 3% (percentage)
- Risk profile: moderate
- Entry logic: all (require all conditions)"""


class StrategyConverter:
    """Converts natural language to strategy YAML."""

    def __init__(self, client: LLMClient | None = None) -> None:
        """Initialize converter.

        Args:
            client: LLM client to use (default: from settings)
        """
        self._client = client

    @property
    def client(self) -> LLMClient:
        """Lazy-load LLM client."""
        if self._client is None:
            self._client = get_llm_client()
        return self._client

    def convert(self, description: str) -> Strategy:
        """Convert English description to Strategy object.

        Args:
            description: Natural language strategy description

        Returns:
            Validated Strategy object

        Raises:
            ValueError: If conversion fails or result is invalid
        """
        logger.info(f"Converting description: {description[:100]}...")

        # Get structured output from LLM
        prompt = f"""Convert this trading strategy description to a structured specification:

"{description}"

Include all indicators needed for the conditions. If the description is vague, make reasonable assumptions based on common trading practices."""

        try:
            spec = self.client.complete(
                prompt=prompt,
                response_model=LLMStrategySpec,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,  # Lower temperature for more consistent output
            )
        except Exception as e:
            logger.error(f"LLM conversion failed: {e}")
            raise ValueError(f"Failed to convert strategy: {e}")

        # Convert LLM spec to Strategy
        return self._spec_to_strategy(spec)

    def convert_to_yaml(self, description: str) -> str:
        """Convert English description to YAML string.

        Args:
            description: Natural language strategy description

        Returns:
            YAML string of the strategy
        """
        strategy = self.convert(description)
        return self.strategy_to_yaml(strategy)

    def strategy_to_yaml(self, strategy: Strategy) -> str:
        """Convert Strategy object to YAML string.

        Args:
            strategy: Strategy object

        Returns:
            YAML string
        """
        data = {
            "strategy": {
                "name": strategy.name,
                "version": strategy.version,
                "description": strategy.strategy.description,
                "author": strategy.strategy.author,
                "tags": strategy.strategy.tags,
            },
            "indicators": [
                {
                    "name": ind.name,
                    "type": ind.type.value,
                    "params": ind.params,
                }
                for ind in strategy.indicators
            ],
            "entry": {
                "conditions": [],
                "logic": strategy.entry.logic.value,
            },
            "exit": {},
            "risk": {
                "profile": strategy.risk.profile.value,
            },
        }

        # Entry conditions
        for cond in strategy.entry.conditions:
            if hasattr(cond, "indicator"):
                data["entry"]["conditions"].append(
                    {
                        "type": "indicator_threshold",
                        "indicator": cond.indicator,
                        "operator": cond.operator.value,
                        "value": cond.value,
                    }
                )
            elif hasattr(cond, "direction"):
                data["entry"]["conditions"].append(
                    {
                        "type": "flow_signal",
                        "direction": cond.direction,
                        "min_premium": cond.min_premium,
                        "recency_minutes": cond.recency_minutes,
                    }
                )

        # Exit rules
        if strategy.exit.take_profit:
            data["exit"]["take_profit"] = {
                "type": strategy.exit.take_profit.type.value,
                "value": strategy.exit.take_profit.value,
            }
        if strategy.exit.stop_loss:
            data["exit"]["stop_loss"] = {
                "type": strategy.exit.stop_loss.type.value,
                "value": strategy.exit.stop_loss.value,
            }
        if strategy.exit.trailing_stop:
            data["exit"]["trailing_stop"] = {
                "type": strategy.exit.trailing_stop.type.value,
                "value": strategy.exit.trailing_stop.value,
            }

        # Risk settings
        if strategy.risk.min_risk_reward:
            data["risk"]["min_risk_reward"] = float(strategy.risk.min_risk_reward)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _spec_to_strategy(self, spec: LLMStrategySpec) -> Strategy:
        """Convert LLM spec to Strategy object."""
        # Build indicators
        indicators = []
        for ind in spec.indicators:
            try:
                ind_type = IndicatorType(ind.type.upper())
            except ValueError:
                logger.warning(f"Unknown indicator type: {ind.type}, defaulting to RSI")
                ind_type = IndicatorType.RSI

            params = {"period": ind.period}
            if ind.source and ind.source != "close":
                params["source"] = ind.source

            indicators.append(
                IndicatorConfig(
                    name=ind.name,
                    type=ind_type,
                    params=params,
                )
            )

        # Build entry conditions
        conditions: list[IndicatorCondition | FlowCondition] = []

        for ic in spec.indicator_conditions:
            try:
                op = ConditionOperator(ic.operator.lower())
            except ValueError:
                op = ConditionOperator.GT

            conditions.append(
                IndicatorCondition(
                    type="indicator_threshold",
                    indicator=ic.indicator,
                    operator=op,
                    value=ic.value,
                )
            )

        for fc in spec.flow_conditions:
            conditions.append(
                FlowCondition(
                    type="flow_signal",
                    direction=fc.direction.lower(),
                    min_premium=fc.min_premium,
                    recency_minutes=fc.recency_minutes,
                )
            )

        # Entry logic
        try:
            logic = ConditionLogic(spec.entry_logic.lower())
        except ValueError:
            logic = ConditionLogic.ALL

        entry = EntryConfig(conditions=conditions, logic=logic)

        # Exit rules
        def make_exit_target(rule: LLMExitRule | None) -> ExitTarget | None:
            if not rule:
                return None
            try:
                exit_type = ExitType(rule.type.lower())
            except ValueError:
                exit_type = ExitType.PERCENTAGE
            return ExitTarget(type=exit_type, value=rule.value)

        exit_config = ExitConfig(
            take_profit=make_exit_target(spec.take_profit),
            stop_loss=make_exit_target(spec.stop_loss),
            trailing_stop=make_exit_target(spec.trailing_stop),
        )

        # Risk config
        try:
            risk_profile = RiskProfileName(spec.risk_profile.lower())
        except ValueError:
            risk_profile = RiskProfileName.MODERATE

        risk = RiskConfig(
            profile=risk_profile,
            min_risk_reward=spec.min_risk_reward,
        )

        # Metadata
        metadata = StrategyMetadata(
            name=spec.name,
            version=spec.version,
            description=spec.description,
            author="LLM Generated",
            tags=["llm-generated"],
        )

        return Strategy(
            strategy=metadata,
            indicators=indicators,
            entry=entry,
            exit=exit_config,
            risk=risk,
        )


def convert_description_to_strategy(description: str) -> Strategy:
    """Convenience function to convert description to Strategy.

    Args:
        description: Natural language strategy description

    Returns:
        Validated Strategy object
    """
    converter = StrategyConverter()
    return converter.convert(description)


def convert_description_to_yaml(description: str) -> str:
    """Convenience function to convert description to YAML.

    Args:
        description: Natural language strategy description

    Returns:
        YAML string
    """
    converter = StrategyConverter()
    return converter.convert_to_yaml(description)

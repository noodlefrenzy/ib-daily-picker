"""
Strategy condition evaluator.

PURPOSE: Evaluate strategy entry/exit conditions against market data
DEPENDENCIES: analysis.indicators, analysis.strategy_schema

ARCHITECTURE NOTES:
- Evaluates indicator-based and flow-based conditions
- Returns evaluation result with reasoning
- Supports backtesting mode (historical evaluation)
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from ib_daily_picker.analysis.indicators import IndicatorCalculator
from ib_daily_picker.analysis.strategy_schema import (
    ConditionLogic,
    ConditionOperator,
    ExitType,
    Strategy,
)
from ib_daily_picker.models import OHLCV, FlowAlert

if TYPE_CHECKING:
    from ib_daily_picker.analysis.strategy_schema import (
        EntryConfig,
        FlowCondition,
        IndicatorCondition,
    )

logger = logging.getLogger(__name__)


@dataclass
class ConditionResult:
    """Result of evaluating a single condition."""

    condition_type: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    reason: str = ""


@dataclass
class EvaluationResult:
    """Result of evaluating entry/exit conditions."""

    symbol: str
    timestamp: datetime
    entry_signal: bool = False
    exit_signal: bool = False
    conditions_passed: list[ConditionResult] = field(default_factory=list)
    conditions_failed: list[ConditionResult] = field(default_factory=list)
    indicator_values: dict[str, float] = field(default_factory=dict)
    current_price: Decimal | None = None
    suggested_stop_loss: Decimal | None = None
    suggested_take_profit: Decimal | None = None
    confidence: float = 0.0
    reasoning: str = ""

    @property
    def total_conditions(self) -> int:
        """Total number of conditions evaluated."""
        return len(self.conditions_passed) + len(self.conditions_failed)

    @property
    def pass_rate(self) -> float:
        """Percentage of conditions that passed."""
        if self.total_conditions == 0:
            return 0.0
        return len(self.conditions_passed) / self.total_conditions


class StrategyEvaluator:
    """Evaluates strategy conditions against market data."""

    def __init__(self, strategy: Strategy) -> None:
        """Initialize with a strategy.

        Args:
            strategy: The strategy to evaluate
        """
        self._strategy = strategy

    @property
    def strategy(self) -> Strategy:
        """Get the strategy being evaluated."""
        return self._strategy

    def evaluate(
        self,
        symbol: str,
        ohlcv_data: Sequence[OHLCV],
        flow_alerts: Sequence[FlowAlert] | None = None,
        evaluation_time: datetime | None = None,
    ) -> EvaluationResult:
        """Evaluate strategy conditions for a symbol.

        Args:
            symbol: Stock ticker symbol
            ohlcv_data: Historical OHLCV data (most recent last)
            flow_alerts: Recent flow alerts for the symbol
            evaluation_time: Time of evaluation (for backtesting)

        Returns:
            EvaluationResult with signal and reasoning
        """
        evaluation_time = evaluation_time or datetime.utcnow()

        result = EvaluationResult(
            symbol=symbol.upper(),
            timestamp=evaluation_time,
        )

        if not ohlcv_data:
            result.reasoning = "No OHLCV data available"
            return result

        # Get current price
        latest_ohlcv = max(ohlcv_data, key=lambda x: x.trade_date)
        result.current_price = latest_ohlcv.close_price

        # Calculate indicators
        calculator = IndicatorCalculator(ohlcv_data)
        for ind_config in self._strategy.indicators:
            ind_result = calculator.calculate(
                indicator_type=ind_config.type.value,
                name=ind_config.name,
                params=ind_config.params,
            )
            latest_value = ind_result.latest()
            if latest_value is not None:
                result.indicator_values[ind_config.name] = latest_value

        # Evaluate entry conditions
        entry_passed, entry_results = self._evaluate_entry(
            self._strategy.entry,
            result.indicator_values,
            flow_alerts or [],
            evaluation_time,
        )

        for r in entry_results:
            if r.passed:
                result.conditions_passed.append(r)
            else:
                result.conditions_failed.append(r)

        result.entry_signal = entry_passed

        # Calculate confidence based on pass rate
        result.confidence = result.pass_rate

        # Calculate exit levels if entry signal
        if result.entry_signal and result.current_price:
            self._calculate_exit_levels(result, calculator)

        # Generate reasoning
        result.reasoning = self._generate_reasoning(result)

        return result

    def _evaluate_entry(
        self,
        entry_config: EntryConfig,
        indicator_values: dict[str, float],
        flow_alerts: Sequence[FlowAlert],
        evaluation_time: datetime,
    ) -> tuple[bool, list[ConditionResult]]:
        """Evaluate entry conditions.

        Returns:
            Tuple of (all_passed, list_of_results)
        """
        results: list[ConditionResult] = []

        for condition in entry_config.conditions:
            if hasattr(condition, "indicator"):
                # Indicator condition
                result = self._evaluate_indicator_condition(condition, indicator_values)
            elif hasattr(condition, "direction"):
                # Flow condition
                result = self._evaluate_flow_condition(condition, flow_alerts, evaluation_time)
            else:
                # Price action or other condition
                result = ConditionResult(
                    condition_type="unknown",
                    passed=False,
                    reason="Unknown condition type",
                )

            results.append(result)

        # Apply logic
        if entry_config.logic == ConditionLogic.ALL:
            passed = all(r.passed for r in results)
        else:  # ANY
            passed = any(r.passed for r in results)

        return passed, results

    def _evaluate_indicator_condition(
        self,
        condition: IndicatorCondition,
        indicator_values: dict[str, float],
    ) -> ConditionResult:
        """Evaluate an indicator-based condition."""
        indicator_name = condition.indicator
        current_value = indicator_values.get(indicator_name)

        if current_value is None:
            return ConditionResult(
                condition_type="indicator",
                passed=False,
                reason=f"Indicator {indicator_name} not calculated",
            )

        # Get threshold value (may be number or another indicator)
        if isinstance(condition.value, str):
            threshold = indicator_values.get(condition.value)
            if threshold is None:
                return ConditionResult(
                    condition_type="indicator",
                    passed=False,
                    reason=f"Reference indicator {condition.value} not found",
                )
        else:
            threshold = float(condition.value)

        # Evaluate comparison
        passed = self._compare(current_value, condition.operator, threshold)

        return ConditionResult(
            condition_type="indicator",
            passed=passed,
            value=current_value,
            threshold=threshold,
            reason=f"{indicator_name}={current_value:.2f} {condition.operator.value} {threshold:.2f}",
        )

    def _evaluate_flow_condition(
        self,
        condition: FlowCondition,
        flow_alerts: Sequence[FlowAlert],
        evaluation_time: datetime,
    ) -> ConditionResult:
        """Evaluate a flow-based condition."""
        # Filter by recency
        cutoff_time = evaluation_time - timedelta(minutes=condition.recency_minutes)
        recent_alerts = [a for a in flow_alerts if a.alert_time >= cutoff_time]

        if not recent_alerts:
            return ConditionResult(
                condition_type="flow",
                passed=False,
                reason=f"No flow alerts in last {condition.recency_minutes} minutes",
            )

        # Filter by direction
        direction = condition.direction.lower()
        if direction == "bullish":
            matching = [a for a in recent_alerts if a.is_bullish]
        elif direction == "bearish":
            matching = [a for a in recent_alerts if a.is_bearish]
        else:  # "any"
            matching = recent_alerts

        if not matching:
            return ConditionResult(
                condition_type="flow",
                passed=False,
                reason=f"No {direction} flow alerts found",
            )

        # Check premium threshold
        if condition.min_premium:
            matching = [
                a
                for a in matching
                if a.premium and a.premium >= Decimal(str(condition.min_premium))
            ]

        if not matching:
            return ConditionResult(
                condition_type="flow",
                passed=False,
                reason=f"No flow alerts with premium >= ${condition.min_premium:,.0f}",
            )

        # Check volume threshold
        if condition.min_volume:
            matching = [a for a in matching if a.volume and a.volume >= condition.min_volume]

        if not matching:
            return ConditionResult(
                condition_type="flow",
                passed=False,
                reason=f"No flow alerts with volume >= {condition.min_volume}",
            )

        total_premium = sum((a.premium for a in matching if a.premium), start=Decimal("0"))

        return ConditionResult(
            condition_type="flow",
            passed=True,
            value=float(total_premium),
            reason=f"Found {len(matching)} {direction} alerts (${total_premium:,.0f} total premium)",
        )

    def _compare(
        self,
        value: float,
        operator: ConditionOperator,
        threshold: float,
    ) -> bool:
        """Compare value against threshold using operator."""
        if operator == ConditionOperator.LT:
            return value < threshold
        elif operator == ConditionOperator.LE:
            return value <= threshold
        elif operator == ConditionOperator.GT:
            return value > threshold
        elif operator == ConditionOperator.GE:
            return value >= threshold
        elif operator == ConditionOperator.EQ:
            return abs(value - threshold) < 0.0001
        elif operator == ConditionOperator.NE:
            return abs(value - threshold) >= 0.0001
        else:
            return False

    def _calculate_exit_levels(
        self,
        result: EvaluationResult,
        calculator: IndicatorCalculator,
    ) -> None:
        """Calculate stop loss and take profit levels."""
        if result.current_price is None:
            return

        price = float(result.current_price)
        exit_config = self._strategy.exit

        # Calculate stop loss
        if exit_config.stop_loss:
            if exit_config.stop_loss.type == ExitType.PERCENTAGE:
                pct = exit_config.stop_loss.value / 100
                result.suggested_stop_loss = Decimal(str(price * (1 - pct)))

            elif exit_config.stop_loss.type == ExitType.ATR_MULTIPLE:
                atr_value = result.indicator_values.get("atr_14")
                if atr_value is None:
                    # Calculate ATR if not already calculated
                    atr_result = calculator.calculate("ATR", "atr_sl", {"period": 14})
                    atr_value = atr_result.latest()

                if atr_value:
                    multiplier = exit_config.stop_loss.multiplier or exit_config.stop_loss.value
                    result.suggested_stop_loss = Decimal(str(price - (atr_value * multiplier)))

            elif exit_config.stop_loss.type == ExitType.FIXED_PRICE:
                result.suggested_stop_loss = Decimal(str(exit_config.stop_loss.value))

        # Calculate take profit
        if exit_config.take_profit:
            if exit_config.take_profit.type == ExitType.PERCENTAGE:
                pct = exit_config.take_profit.value / 100
                result.suggested_take_profit = Decimal(str(price * (1 + pct)))

            elif exit_config.take_profit.type == ExitType.ATR_MULTIPLE:
                atr_value = result.indicator_values.get("atr_14")
                if atr_value is None:
                    atr_result = calculator.calculate("ATR", "atr_tp", {"period": 14})
                    atr_value = atr_result.latest()

                if atr_value:
                    multiplier = exit_config.take_profit.multiplier or exit_config.take_profit.value
                    result.suggested_take_profit = Decimal(str(price + (atr_value * multiplier)))

            elif exit_config.take_profit.type == ExitType.FIXED_PRICE:
                result.suggested_take_profit = Decimal(str(exit_config.take_profit.value))

    def _generate_reasoning(self, result: EvaluationResult) -> str:
        """Generate human-readable reasoning for the evaluation."""
        lines = []

        if result.entry_signal:
            lines.append(f"Entry signal for {result.symbol}")
        else:
            lines.append(f"No entry signal for {result.symbol}")

        lines.append(
            f"Conditions: {len(result.conditions_passed)}/{result.total_conditions} passed"
        )

        if result.conditions_failed:
            lines.append("Failed conditions:")
            for c in result.conditions_failed:
                lines.append(f"  - {c.reason}")

        if result.entry_signal and result.current_price:
            lines.append(f"Current price: ${result.current_price:.2f}")
            if result.suggested_stop_loss:
                lines.append(f"Suggested stop: ${result.suggested_stop_loss:.2f}")
            if result.suggested_take_profit:
                lines.append(f"Suggested target: ${result.suggested_take_profit:.2f}")

        return "\n".join(lines)

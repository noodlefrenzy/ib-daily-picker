"""
Signal generation from strategy evaluations.

PURPOSE: Generate trade recommendations from evaluated strategies
DEPENDENCIES: analysis.evaluator, models.recommendation

ARCHITECTURE NOTES:
- Converts EvaluationResult to Recommendation
- Applies risk profile for position sizing
- Generates unique recommendation IDs
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence
from uuid import uuid4

from ib_daily_picker.analysis.evaluator import EvaluationResult, StrategyEvaluator
from ib_daily_picker.config import get_settings
from ib_daily_picker.models import (
    OHLCV,
    FlowAlert,
    Recommendation,
    RecommendationBatch,
    SignalType,
)

if TYPE_CHECKING:
    from ib_daily_picker.analysis.strategy_schema import RiskProfileName, Strategy

logger = logging.getLogger(__name__)


# Risk profile configurations
RISK_PROFILES = {
    "conservative": {
        "risk_per_trade": Decimal("0.005"),  # 0.5%
        "min_risk_reward": Decimal("3.0"),
        "max_positions": 5,
        "max_sector_exposure": Decimal("0.20"),
    },
    "moderate": {
        "risk_per_trade": Decimal("0.01"),  # 1%
        "min_risk_reward": Decimal("2.0"),
        "max_positions": 8,
        "max_sector_exposure": Decimal("0.30"),
    },
    "aggressive": {
        "risk_per_trade": Decimal("0.02"),  # 2%
        "min_risk_reward": Decimal("1.5"),
        "max_positions": 10,
        "max_sector_exposure": Decimal("0.40"),
    },
}


class SignalGenerator:
    """Generates trade recommendations from strategy evaluations."""

    def __init__(
        self,
        strategy: "Strategy",
        account_size: Decimal | None = None,
    ) -> None:
        """Initialize signal generator.

        Args:
            strategy: The strategy to use for signal generation
            account_size: Account size for position sizing (optional)
        """
        self._strategy = strategy
        self._evaluator = StrategyEvaluator(strategy)
        self._account_size = account_size or Decimal("100000")

    @property
    def strategy(self) -> "Strategy":
        """Get the strategy."""
        return self._strategy

    def generate(
        self,
        symbol: str,
        ohlcv_data: Sequence[OHLCV],
        flow_alerts: Sequence[FlowAlert] | None = None,
        evaluation_time: datetime | None = None,
    ) -> Recommendation | None:
        """Generate a recommendation for a single symbol.

        Args:
            symbol: Stock ticker symbol
            ohlcv_data: Historical OHLCV data
            flow_alerts: Recent flow alerts
            evaluation_time: Time of evaluation (for backtesting)

        Returns:
            Recommendation if entry signal, None otherwise
        """
        evaluation = self._evaluator.evaluate(
            symbol=symbol,
            ohlcv_data=ohlcv_data,
            flow_alerts=flow_alerts,
            evaluation_time=evaluation_time,
        )

        if not evaluation.entry_signal:
            return None

        return self._create_recommendation(evaluation)

    def generate_batch(
        self,
        symbols_data: dict[str, tuple[Sequence[OHLCV], Sequence[FlowAlert] | None]],
        evaluation_time: datetime | None = None,
    ) -> RecommendationBatch:
        """Generate recommendations for multiple symbols.

        Args:
            symbols_data: Dict mapping symbols to (ohlcv_data, flow_alerts) tuples
            evaluation_time: Time of evaluation

        Returns:
            RecommendationBatch with all recommendations
        """
        recommendations = []

        for symbol, (ohlcv_data, flow_alerts) in symbols_data.items():
            rec = self.generate(
                symbol=symbol,
                ohlcv_data=ohlcv_data,
                flow_alerts=flow_alerts,
                evaluation_time=evaluation_time,
            )
            if rec:
                recommendations.append(rec)

        return RecommendationBatch(
            recommendations=recommendations,
            generated_at=evaluation_time or datetime.utcnow(),
            strategy_name=self._strategy.name,
        )

    def _create_recommendation(
        self,
        evaluation: EvaluationResult,
    ) -> Recommendation:
        """Create a Recommendation from an EvaluationResult."""
        # Get risk profile settings
        profile_name = self._strategy.risk.profile.value
        risk_config = RISK_PROFILES.get(profile_name, RISK_PROFILES["moderate"])

        # Apply strategy overrides
        risk_per_trade = Decimal(str(self._strategy.risk.risk_per_trade or risk_config["risk_per_trade"]))
        min_risk_reward = Decimal(str(self._strategy.risk.min_risk_reward or risk_config["min_risk_reward"]))

        # Calculate position size based on risk
        position_size = None
        if evaluation.current_price and evaluation.suggested_stop_loss:
            risk_per_share = abs(evaluation.current_price - evaluation.suggested_stop_loss)
            if risk_per_share > 0:
                risk_amount = self._account_size * risk_per_trade
                position_size = risk_amount / risk_per_share

        # Check risk/reward ratio
        if evaluation.suggested_stop_loss and evaluation.suggested_take_profit and evaluation.current_price:
            risk = abs(evaluation.current_price - evaluation.suggested_stop_loss)
            reward = abs(evaluation.suggested_take_profit - evaluation.current_price)
            if risk > 0:
                risk_reward = reward / risk
                if risk_reward < float(min_risk_reward):
                    logger.info(
                        f"R:R ratio {risk_reward:.2f} below minimum {min_risk_reward}"
                    )

        # Set expiration (default 24 hours)
        expires_at = evaluation.timestamp + timedelta(hours=24)

        return Recommendation(
            id=str(uuid4()),
            symbol=evaluation.symbol,
            strategy_name=self._strategy.name,
            signal_type=SignalType.BUY,
            entry_price=evaluation.current_price,
            stop_loss=evaluation.suggested_stop_loss,
            take_profit=evaluation.suggested_take_profit,
            position_size=position_size,
            confidence=Decimal(str(evaluation.confidence)),
            reasoning=evaluation.reasoning,
            generated_at=evaluation.timestamp,
            expires_at=expires_at,
        )


class MultiStrategySignalGenerator:
    """Generates signals using multiple strategies."""

    def __init__(
        self,
        strategies: list["Strategy"],
        account_size: Decimal | None = None,
    ) -> None:
        """Initialize with multiple strategies.

        Args:
            strategies: List of strategies to evaluate
            account_size: Account size for position sizing
        """
        self._generators = [
            SignalGenerator(s, account_size) for s in strategies
        ]

    def generate(
        self,
        symbol: str,
        ohlcv_data: Sequence[OHLCV],
        flow_alerts: Sequence[FlowAlert] | None = None,
    ) -> list[Recommendation]:
        """Generate recommendations from all strategies.

        Args:
            symbol: Stock ticker symbol
            ohlcv_data: Historical OHLCV data
            flow_alerts: Recent flow alerts

        Returns:
            List of recommendations (one per matching strategy)
        """
        recommendations = []

        for generator in self._generators:
            rec = generator.generate(symbol, ohlcv_data, flow_alerts)
            if rec:
                recommendations.append(rec)

        return recommendations

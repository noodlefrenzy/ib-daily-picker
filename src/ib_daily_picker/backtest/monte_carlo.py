"""
Monte Carlo simulation for backtest robustness testing.

PURPOSE: Validate strategy robustness by testing across thousands of scenarios
DEPENDENCIES: backtest.metrics, models.trade

ARCHITECTURE NOTES:
- Separates genuinely robust strategies from lucky ones
- Supports trade shuffling, removal, and execution variance simulation
- Generates percentile distributions and equity cones for visualization

WHY: A single backtest shows "what happened" with one sequence of trades.
Monte Carlo shows "what could happen" - the range of possible outcomes.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

import numpy as np

from ib_daily_picker.backtest.metrics import (
    BacktestMetrics,
    EquityCurvePoint,
    calculate_backtest_metrics,
)
from ib_daily_picker.backtest.runner import BacktestResult
from ib_daily_picker.models import Trade, TradeStatus

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation."""

    num_simulations: int = 1000
    random_seed: int | None = None
    shuffle_trades: bool = True  # Randomize trade sequence
    trade_removal: bool = False  # Simulate missed entries
    trade_removal_pct: Decimal = Decimal("0.10")  # 10% removal by default
    execution_variance: bool = False  # Add random slippage
    slippage_std_pct: Decimal = Decimal("0.002")  # 0.2% std deviation
    confidence_levels: list[int] = field(default_factory=lambda: [5, 25, 50, 75, 95])


@dataclass
class PercentileDistribution:
    """Statistical distribution of a metric across simulations."""

    metric_name: str
    p5: Decimal
    p25: Decimal
    p50: Decimal  # median
    p75: Decimal
    p95: Decimal
    mean: Decimal
    std_dev: Decimal

    @classmethod
    def from_values(cls, metric_name: str, values: list[Decimal]) -> PercentileDistribution:
        """Calculate distribution from list of values."""
        if not values:
            zero = Decimal("0")
            return cls(
                metric_name=metric_name,
                p5=zero,
                p25=zero,
                p50=zero,
                p75=zero,
                p95=zero,
                mean=zero,
                std_dev=zero,
            )

        # Convert to floats for numpy calculations
        float_values = [float(v) for v in values]
        arr = np.array(float_values)

        percentiles = np.percentile(arr, [5, 25, 50, 75, 95])
        mean = np.mean(arr)
        std = np.std(arr)

        return cls(
            metric_name=metric_name,
            p5=Decimal(str(round(percentiles[0], 4))),
            p25=Decimal(str(round(percentiles[1], 4))),
            p50=Decimal(str(round(percentiles[2], 4))),
            p75=Decimal(str(round(percentiles[3], 4))),
            p95=Decimal(str(round(percentiles[4], 4))),
            mean=Decimal(str(round(mean, 4))),
            std_dev=Decimal(str(round(std, 4))),
        )


@dataclass
class EquityConePoint:
    """Single point on the equity cone (confidence bands over time)."""

    date: date
    p5: Decimal
    p25: Decimal
    median: Decimal
    p75: Decimal
    p95: Decimal


@dataclass
class MonteCarloResult:
    """Complete result of Monte Carlo simulation."""

    strategy_name: str
    config: MonteCarloConfig
    base_result: BacktestResult
    num_simulations: int
    total_return_dist: PercentileDistribution
    max_drawdown_dist: PercentileDistribution
    win_rate_dist: PercentileDistribution
    sharpe_ratio_dist: PercentileDistribution | None
    profit_factor_dist: PercentileDistribution | None
    equity_cone: list[EquityConePoint]
    probability_of_loss: Decimal  # % sims with negative return
    probability_of_ruin: Decimal  # % sims with >50% drawdown
    simulation_returns: list[Decimal]  # Raw data for histogram


class MonteCarloRunner:
    """Runs Monte Carlo simulations on backtest results."""

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        """Initialize runner with configuration.

        Args:
            config: Monte Carlo configuration. If None, uses defaults.
        """
        self.config = config or MonteCarloConfig()
        self._rng: np.random.Generator | None = None

    @property
    def rng(self) -> np.random.Generator:
        """Get random number generator, initializing if needed."""
        if self._rng is None:
            self._rng = np.random.default_rng(self.config.random_seed)
        return self._rng

    def run(self, base_result: BacktestResult) -> MonteCarloResult:
        """Run Monte Carlo simulation on a backtest result.

        Args:
            base_result: BacktestResult from a standard backtest run

        Returns:
            MonteCarloResult with distributions and equity cone

        Raises:
            ValueError: If base_result has no trades or metrics
        """
        if not base_result.trades:
            raise ValueError("Cannot run Monte Carlo on backtest with no trades")

        if not base_result.metrics:
            raise ValueError("Cannot run Monte Carlo on backtest without metrics")

        logger.info(
            f"Starting Monte Carlo simulation: {self.config.num_simulations} sims "
            f"(shuffle={self.config.shuffle_trades}, "
            f"removal={self.config.trade_removal}, "
            f"slippage={self.config.execution_variance})"
        )

        # Get only closed trades with PnL
        base_trades = [
            t for t in base_result.trades if t.status == TradeStatus.CLOSED and t.pnl is not None
        ]

        if not base_trades:
            raise ValueError("No closed trades with PnL to simulate")

        # Run simulations
        simulation_metrics: list[BacktestMetrics] = []
        simulation_equity_curves: list[list[EquityCurvePoint]] = []

        for i in range(self.config.num_simulations):
            # Transform trades for this simulation
            sim_trades = self._transform_trades(base_trades.copy())

            if not sim_trades:
                # If all trades removed, skip this simulation
                continue

            # Calculate metrics for this simulation
            metrics = calculate_backtest_metrics(
                trades=sim_trades,
                initial_capital=base_result.config.initial_capital,
                start_date=base_result.config.start_date,
                end_date=base_result.config.end_date,
                strategy_name=f"{base_result.strategy_name}_sim_{i}",
            )

            simulation_metrics.append(metrics)
            if metrics.equity_curve:
                simulation_equity_curves.append(metrics.equity_curve)

        if not simulation_metrics:
            raise ValueError("All simulations resulted in empty trades")

        # Build distributions
        total_return_dist = PercentileDistribution.from_values(
            "total_return_pct",
            [m.total_return_pct for m in simulation_metrics],
        )

        max_drawdown_dist = PercentileDistribution.from_values(
            "max_drawdown_pct",
            [m.max_drawdown_pct for m in simulation_metrics],
        )

        win_rate_dist = PercentileDistribution.from_values(
            "win_rate",
            [m.win_rate * 100 for m in simulation_metrics],  # Convert to percentage
        )

        # Sharpe ratio (only if available in simulations)
        sharpe_values = [m.sharpe_ratio for m in simulation_metrics if m.sharpe_ratio is not None]
        sharpe_ratio_dist = (
            PercentileDistribution.from_values("sharpe_ratio", sharpe_values)
            if sharpe_values
            else None
        )

        # Profit factor (only if available)
        pf_values = [m.profit_factor for m in simulation_metrics if m.profit_factor is not None]
        profit_factor_dist = (
            PercentileDistribution.from_values("profit_factor", pf_values) if pf_values else None
        )

        # Calculate probabilities
        returns = [m.total_return_pct for m in simulation_metrics]
        negative_returns = sum(1 for r in returns if r < 0)
        probability_of_loss = Decimal(str(round(negative_returns / len(returns), 4)))

        ruin_count = sum(1 for m in simulation_metrics if m.max_drawdown_pct > 50)
        probability_of_ruin = Decimal(str(round(ruin_count / len(simulation_metrics), 4)))

        # Build equity cone
        equity_cone = self._build_equity_cone(simulation_equity_curves)

        logger.info(
            f"Monte Carlo complete: "
            f"P(Loss)={probability_of_loss:.1%}, "
            f"Median Return={total_return_dist.p50:.2f}%"
        )

        return MonteCarloResult(
            strategy_name=base_result.strategy_name,
            config=self.config,
            base_result=base_result,
            num_simulations=len(simulation_metrics),
            total_return_dist=total_return_dist,
            max_drawdown_dist=max_drawdown_dist,
            win_rate_dist=win_rate_dist,
            sharpe_ratio_dist=sharpe_ratio_dist,
            profit_factor_dist=profit_factor_dist,
            equity_cone=equity_cone,
            probability_of_loss=probability_of_loss,
            probability_of_ruin=probability_of_ruin,
            simulation_returns=returns,
        )

    def _transform_trades(self, trades: list[Trade]) -> list[Trade]:
        """Apply configured transformations to trades.

        Args:
            trades: List of trades to transform

        Returns:
            Transformed list of trades
        """
        result = trades.copy()

        # Apply trade removal first (before shuffling)
        if self.config.trade_removal:
            result = self._apply_trade_removal(result)

        # Apply shuffle
        if self.config.shuffle_trades:
            result = self._apply_shuffle(result)

        # Apply execution variance (slippage)
        if self.config.execution_variance:
            result = self._apply_slippage(result)

        return result

    def _apply_shuffle(self, trades: list[Trade]) -> list[Trade]:
        """Shuffle trade order and reassign dates sequentially.

        This tests sequence risk - what if trades occurred in different order?

        Args:
            trades: Original trades

        Returns:
            Shuffled trades with reassigned dates
        """
        if len(trades) <= 1:
            return trades

        # Get original date range
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        first_date = sorted_trades[0].entry_time.date()
        date_offsets = [(t.entry_time.date() - first_date).days for t in sorted_trades]

        # Shuffle the trades
        indices = list(range(len(trades)))
        self.rng.shuffle(indices)

        # Create new trades with reassigned dates
        result = []
        for new_idx, orig_idx in enumerate(indices):
            trade = copy.deepcopy(trades[orig_idx])

            # Assign dates based on new position
            if new_idx < len(date_offsets):
                offset = timedelta(days=date_offsets[new_idx])
                trade.entry_time = datetime.combine(first_date + offset, trade.entry_time.time())
                orig_exit = trades[orig_idx].exit_time
                if trade.exit_time and orig_exit:
                    # Maintain same hold duration
                    duration = orig_exit - trades[orig_idx].entry_time
                    trade.exit_time = trade.entry_time + duration

            result.append(trade)

        return result

    def _apply_trade_removal(self, trades: list[Trade]) -> list[Trade]:
        """Randomly remove a percentage of trades.

        This simulates missed entries - what if we missed some signals?

        Args:
            trades: Original trades

        Returns:
            Trades with some removed
        """
        if len(trades) <= 1:
            return trades  # Never remove all trades

        removal_pct = float(self.config.trade_removal_pct)
        num_to_remove = max(1, int(len(trades) * removal_pct))

        # Never remove more than n-1 trades
        num_to_remove = min(num_to_remove, len(trades) - 1)

        # Random indices to remove
        remove_indices = set(self.rng.choice(len(trades), size=num_to_remove, replace=False))

        return [t for i, t in enumerate(trades) if i not in remove_indices]

    def _apply_slippage(self, trades: list[Trade]) -> list[Trade]:
        """Add random execution variance (slippage) to entry/exit prices.

        This simulates execution variance - what if fills were worse?

        Args:
            trades: Original trades

        Returns:
            Trades with slippage applied
        """
        std_pct = float(self.config.slippage_std_pct)
        result = []

        for trade in trades:
            trade = copy.deepcopy(trade)

            # Apply random slippage to entry and exit
            entry_slippage = Decimal(str(1 + self.rng.normal(0, std_pct)))
            trade.entry_price = trade.entry_price * entry_slippage

            if trade.exit_price:
                exit_slippage = Decimal(str(1 + self.rng.normal(0, std_pct)))
                trade.exit_price = trade.exit_price * exit_slippage

            # Recalculate PnL
            if trade.exit_price and trade.status == TradeStatus.CLOSED:
                from ib_daily_picker.models import TradeDirection

                if trade.direction == TradeDirection.LONG:
                    price_diff = trade.exit_price - trade.entry_price
                else:
                    price_diff = trade.entry_price - trade.exit_price

                trade.pnl = price_diff * trade.position_size
                trade.pnl_percent = (price_diff / trade.entry_price) * 100

            result.append(trade)

        return result

    def _build_equity_cone(
        self,
        equity_curves: list[list[EquityCurvePoint]],
    ) -> list[EquityConePoint]:
        """Build equity cone from multiple simulation equity curves.

        Args:
            equity_curves: List of equity curves from simulations

        Returns:
            List of EquityConePoint representing the confidence bands
        """
        if not equity_curves:
            return []

        # Collect all unique dates across all curves
        all_dates: set[date] = set()
        for curve in equity_curves:
            for point in curve:
                all_dates.add(point.date)

        if not all_dates:
            return []

        # Sort dates
        sorted_dates = sorted(all_dates)

        # For each date, collect equity values from all simulations
        cone_points = []
        for d in sorted_dates:
            equities: list[float] = []

            for curve in equity_curves:
                # Find equity at this date (or interpolate)
                for point in curve:
                    if point.date == d:
                        equities.append(float(point.equity))
                        break
                    elif point.date > d:
                        # Date not in this curve, skip
                        break

            if len(equities) >= 5:  # Need enough samples for percentiles
                arr = np.array(equities)
                percentiles = np.percentile(arr, [5, 25, 50, 75, 95])

                cone_points.append(
                    EquityConePoint(
                        date=d,
                        p5=Decimal(str(round(percentiles[0], 2))),
                        p25=Decimal(str(round(percentiles[1], 2))),
                        median=Decimal(str(round(percentiles[2], 2))),
                        p75=Decimal(str(round(percentiles[3], 2))),
                        p95=Decimal(str(round(percentiles[4], 2))),
                    )
                )

        return cone_points

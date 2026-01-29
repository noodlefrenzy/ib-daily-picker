"""
Tests for Monte Carlo simulation module.

TEST DOC: Monte Carlo Robustness Testing

WHAT: Tests for Monte Carlo simulation on backtest results
WHY: Validate that simulation transformations and statistics are correct
HOW: Create sample trades, run simulations, verify distributions

CASES:
- Trade transformations (shuffle, removal, slippage)
- Percentile distribution calculation
- Reproducibility with seeds
- Edge cases (single trade, all winners)

EDGE CASES:
- Single trade: Cannot shuffle, minimal removal
- All winners: Low variance in metrics
- Zero trades: Should raise error
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from ib_daily_picker.backtest.metrics import calculate_backtest_metrics
from ib_daily_picker.backtest.monte_carlo import (
    EquityConePoint,
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloRunner,
    PercentileDistribution,
)
from ib_daily_picker.backtest.runner import BacktestConfig, BacktestResult
from ib_daily_picker.models import Trade, TradeDirection, TradeStatus


def create_trade(
    symbol: str = "AAPL",
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: Decimal = Decimal("100"),
    exit_price: Decimal = Decimal("110"),
    position_size: Decimal = Decimal("10"),
    stop_loss: Decimal = Decimal("95"),
    entry_date: date | None = None,
    exit_date: date | None = None,
    trade_id: str | None = None,
) -> Trade:
    """Helper to create test trades."""
    today = date.today()
    return Trade(
        id=trade_id or f"test-{datetime.now().timestamp()}",
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        entry_time=datetime.combine(entry_date or today - timedelta(days=5), datetime.min.time()),
        exit_price=exit_price,
        exit_time=datetime.combine(exit_date or today, datetime.min.time()),
        position_size=position_size,
        stop_loss=stop_loss,
        status=TradeStatus.CLOSED,
    )


def create_backtest_result(trades: list[Trade]) -> BacktestResult:
    """Create a BacktestResult with metrics from trades."""
    today = date.today()
    config = BacktestConfig(
        start_date=today - timedelta(days=30),
        end_date=today,
        initial_capital=Decimal("10000"),
    )
    result = BacktestResult(
        strategy_name="test_strategy",
        config=config,
        trades=trades,
    )
    result.metrics = calculate_backtest_metrics(
        trades=trades,
        initial_capital=config.initial_capital,
        start_date=config.start_date,
        end_date=config.end_date,
    )
    return result


class TestTradeTransformations:
    """Tests for trade transformation functions."""

    def test_shuffle_preserves_trade_count(self):
        """Shuffle should not change the number of trades."""
        today = date.today()
        trades = [
            create_trade(entry_date=today - timedelta(days=10), trade_id=f"t{i}") for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=10,
            shuffle_trades=True,
            trade_removal=False,
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        transformed = runner._apply_shuffle(trades.copy())

        assert len(transformed) == len(trades)

    def test_shuffle_preserves_total_return(self):
        """Shuffling should preserve total return (just change sequence)."""
        today = date.today()
        # Create trades with different PnLs
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),  # Big winner
                entry_date=today - timedelta(days=10),
                exit_date=today - timedelta(days=9),
                trade_id="t1",
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),  # Loser
                entry_date=today - timedelta(days=8),
                exit_date=today - timedelta(days=7),
                trade_id="t2",
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("105"),  # Small winner
                entry_date=today - timedelta(days=6),
                exit_date=today - timedelta(days=5),
                trade_id="t3",
            ),
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=True,
            trade_removal=False,
            random_seed=42,
        )
        runner = MonteCarloRunner(config)

        # Run Monte Carlo
        mc_result = runner.run(result)

        # With shuffle only (no removal), total return should be constant
        # because we're just reordering the same trades
        returns = mc_result.simulation_returns
        assert len(set(returns)) == 1, "Shuffle-only should have constant total return"

        # The return should match the base result
        base_return = result.metrics.total_return_pct if result.metrics else Decimal("0")
        assert returns[0] == base_return

    def test_removal_removes_correct_percentage(self):
        """Removal should remove approximately the right percentage."""
        today = date.today()
        trades = [
            create_trade(entry_date=today - timedelta(days=10), trade_id=f"t{i}")
            for i in range(100)
        ]

        config = MonteCarloConfig(
            num_simulations=1,
            shuffle_trades=False,
            trade_removal=True,
            trade_removal_pct=Decimal("0.20"),  # 20%
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        transformed = runner._apply_trade_removal(trades.copy())

        # Should remove approximately 20 trades (20%)
        removed_count = len(trades) - len(transformed)
        assert 15 <= removed_count <= 25, f"Expected ~20 removed, got {removed_count}"

    def test_removal_never_removes_all_trades(self):
        """Removal should never leave zero trades."""
        today = date.today()
        trades = [
            create_trade(entry_date=today - timedelta(days=10), trade_id=f"t{i}") for i in range(5)
        ]

        config = MonteCarloConfig(
            num_simulations=1,
            shuffle_trades=False,
            trade_removal=True,
            trade_removal_pct=Decimal("0.90"),  # 90% - aggressive removal
            random_seed=42,
        )
        runner = MonteCarloRunner(config)

        for _ in range(100):  # Try many times
            transformed = runner._apply_trade_removal(trades.copy())
            assert len(transformed) >= 1, "Should never remove all trades"

    def test_slippage_follows_distribution(self):
        """Slippage should produce prices around the original."""
        today = date.today()
        original_price = Decimal("100")
        trades = [
            create_trade(
                entry_price=original_price,
                exit_price=Decimal("110"),
                entry_date=today - timedelta(days=10),
                trade_id=f"t{i}",
            )
            for i in range(100)
        ]

        config = MonteCarloConfig(
            num_simulations=1,
            shuffle_trades=False,
            trade_removal=False,
            execution_variance=True,
            slippage_std_pct=Decimal("0.01"),  # 1% std
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        transformed = runner._apply_slippage(trades.copy())

        # Check that prices changed but are still reasonable
        entry_prices = [float(t.entry_price) for t in transformed]
        mean_entry = sum(entry_prices) / len(entry_prices)

        # Mean should be close to original (within 5%)
        assert abs(mean_entry - float(original_price)) < 5, "Mean should be near original"

        # Should have some variance
        min_price = min(entry_prices)
        max_price = max(entry_prices)
        assert max_price > min_price, "Should have price variance"


class TestPercentileCalculation:
    """Tests for percentile distribution calculations."""

    def test_percentiles_ordered_correctly(self):
        """Percentiles should be in ascending order: p5 <= p25 <= p50 <= p75 <= p95."""
        values = [Decimal(str(i)) for i in range(100)]
        dist = PercentileDistribution.from_values("test", values)

        assert dist.p5 <= dist.p25
        assert dist.p25 <= dist.p50
        assert dist.p50 <= dist.p75
        assert dist.p75 <= dist.p95

    def test_known_distribution(self):
        """Test against known values."""
        # Simple sequence: 0 to 99
        values = [Decimal(str(i)) for i in range(100)]
        dist = PercentileDistribution.from_values("test", values)

        # p50 (median) should be around 49.5
        assert 49 <= float(dist.p50) <= 50

        # p5 should be around 4.95
        assert 4 <= float(dist.p5) <= 6

        # p95 should be around 94.05
        assert 93 <= float(dist.p95) <= 96

    def test_empty_values_returns_zeros(self):
        """Empty value list should return all zeros."""
        dist = PercentileDistribution.from_values("test", [])

        assert dist.p5 == Decimal("0")
        assert dist.p50 == Decimal("0")
        assert dist.p95 == Decimal("0")
        assert dist.mean == Decimal("0")
        assert dist.std_dev == Decimal("0")


class TestReproducibility:
    """Tests for random seed reproducibility."""

    def test_same_seed_same_results(self):
        """Same seed should produce identical results."""
        today = date.today()
        trades = [
            create_trade(
                entry_price=Decimal(str(100 + i)),
                exit_price=Decimal(str(110 + i)),
                entry_date=today - timedelta(days=10 + i),
                exit_date=today - timedelta(days=9 + i),
                trade_id=f"t{i}",
            )
            for i in range(20)
        ]
        result = create_backtest_result(trades)

        config1 = MonteCarloConfig(
            num_simulations=50,
            shuffle_trades=True,
            trade_removal=True,
            trade_removal_pct=Decimal("0.10"),
            random_seed=12345,
        )
        config2 = MonteCarloConfig(
            num_simulations=50,
            shuffle_trades=True,
            trade_removal=True,
            trade_removal_pct=Decimal("0.10"),
            random_seed=12345,
        )

        runner1 = MonteCarloRunner(config1)
        runner2 = MonteCarloRunner(config2)

        mc_result1 = runner1.run(result)
        mc_result2 = runner2.run(result)

        # Results should be identical
        assert mc_result1.simulation_returns == mc_result2.simulation_returns
        assert mc_result1.total_return_dist.p50 == mc_result2.total_return_dist.p50

    def test_different_seed_different_results_with_removal(self):
        """Different seeds should produce different results when using removal."""
        today = date.today()
        # Create trades with varying PnLs (not all the same %)
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal(str(100 + (i * 5))),  # Different profits: +0, +5, +10, etc.
                entry_date=today - timedelta(days=30 - i),
                exit_date=today - timedelta(days=29 - i),
                trade_id=f"t{i}",
            )
            for i in range(20)
        ]
        result = create_backtest_result(trades)

        # Use trade removal to create variance
        config1 = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=False,
            trade_removal=True,
            trade_removal_pct=Decimal("0.30"),  # Remove 30%
            random_seed=11111,
        )
        config2 = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=False,
            trade_removal=True,
            trade_removal_pct=Decimal("0.30"),
            random_seed=22222,
        )

        runner1 = MonteCarloRunner(config1)
        runner2 = MonteCarloRunner(config2)

        mc_result1 = runner1.run(result)
        mc_result2 = runner2.run(result)

        # With different seeds and removal of varying-value trades,
        # we should see different return distributions
        # Compare the standard deviations or means to verify different outcomes
        returns1 = set(mc_result1.simulation_returns)
        returns2 = set(mc_result2.simulation_returns)

        # The sets of unique returns should differ
        assert returns1 != returns2, "Different seeds should produce different simulations"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_trade_works(self):
        """Single trade should still work (minimal simulation)."""
        today = date.today()
        trades = [
            create_trade(
                entry_date=today - timedelta(days=5),
                exit_date=today,
                trade_id="single",
            ),
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=True,  # No effect with 1 trade
            trade_removal=False,  # Can't remove the only trade
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        # Should complete successfully
        assert mc_result.num_simulations > 0

        # All simulations should have same return (only 1 trade, no variance)
        assert len(set(mc_result.simulation_returns)) == 1

    def test_all_winners_low_variance(self):
        """All winning trades should produce low variance in win rate."""
        today = date.today()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),  # Always winner
                entry_date=today - timedelta(days=10 - i),
                exit_date=today - timedelta(days=9 - i),
                trade_id=f"t{i}",
            )
            for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=True,
            trade_removal=False,  # No removal to keep all winners
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        # Win rate should be 100% across all simulations
        assert mc_result.win_rate_dist.p5 == Decimal("100")
        assert mc_result.win_rate_dist.p95 == Decimal("100")

    def test_zero_trades_raises_error(self):
        """No trades should raise an error."""
        result = create_backtest_result([])

        config = MonteCarloConfig(num_simulations=100, random_seed=42)
        runner = MonteCarloRunner(config)

        with pytest.raises(ValueError, match="no trades"):
            runner.run(result)

    def test_no_metrics_raises_error(self):
        """Missing metrics should raise an error."""
        today = date.today()
        trades = [
            create_trade(entry_date=today - timedelta(days=5), trade_id="t1"),
        ]
        config = BacktestConfig(
            start_date=today - timedelta(days=30),
            end_date=today,
        )
        result = BacktestResult(
            strategy_name="test",
            config=config,
            trades=trades,
            metrics=None,  # Explicitly no metrics
        )

        mc_config = MonteCarloConfig(num_simulations=100, random_seed=42)
        runner = MonteCarloRunner(mc_config)

        with pytest.raises(ValueError, match="without metrics"):
            runner.run(result)


class TestMonteCarloResult:
    """Tests for MonteCarloResult structure."""

    def test_result_has_all_fields(self):
        """MonteCarloResult should have all expected fields."""
        today = date.today()
        trades = [
            create_trade(
                entry_date=today - timedelta(days=10 - i),
                exit_date=today - timedelta(days=9 - i),
                trade_id=f"t{i}",
            )
            for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=50,
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        # Check all fields exist
        assert mc_result.strategy_name == "test_strategy"
        assert mc_result.config == config
        assert mc_result.base_result == result
        assert mc_result.num_simulations > 0
        assert mc_result.total_return_dist is not None
        assert mc_result.max_drawdown_dist is not None
        assert mc_result.win_rate_dist is not None
        assert isinstance(mc_result.probability_of_loss, Decimal)
        assert isinstance(mc_result.probability_of_ruin, Decimal)
        assert isinstance(mc_result.simulation_returns, list)

    def test_probability_of_loss_valid_range(self):
        """Probability of loss should be between 0 and 1."""
        today = date.today()
        # Mix of winners and losers
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110") if i % 2 == 0 else Decimal("90"),
                entry_date=today - timedelta(days=10 - i),
                exit_date=today - timedelta(days=9 - i),
                trade_id=f"t{i}",
            )
            for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(
            num_simulations=100,
            shuffle_trades=True,
            random_seed=42,
        )
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        assert Decimal("0") <= mc_result.probability_of_loss <= Decimal("1")
        assert Decimal("0") <= mc_result.probability_of_ruin <= Decimal("1")


class TestReporter:
    """Tests for Monte Carlo reporter functions."""

    def test_format_console_output(self):
        """Console formatter should produce readable output."""
        from ib_daily_picker.backtest.reporter import format_monte_carlo_console

        today = date.today()
        trades = [
            create_trade(
                entry_date=today - timedelta(days=10 - i),
                exit_date=today - timedelta(days=9 - i),
                trade_id=f"t{i}",
            )
            for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(num_simulations=50, random_seed=42)
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        output = format_monte_carlo_console(mc_result)

        assert "MONTE CARLO RESULTS" in output
        assert "test_strategy" in output
        assert "RISK ASSESSMENT" in output
        assert "Probability of Loss" in output
        assert "METRIC DISTRIBUTIONS" in output

    def test_format_json_output(self):
        """JSON formatter should produce valid JSON."""
        import json

        from ib_daily_picker.backtest.reporter import format_monte_carlo_json

        today = date.today()
        trades = [
            create_trade(
                entry_date=today - timedelta(days=10 - i),
                exit_date=today - timedelta(days=9 - i),
                trade_id=f"t{i}",
            )
            for i in range(10)
        ]
        result = create_backtest_result(trades)

        config = MonteCarloConfig(num_simulations=50, random_seed=42)
        runner = MonteCarloRunner(config)
        mc_result = runner.run(result)

        json_str = format_monte_carlo_json(mc_result)
        data = json.loads(json_str)

        assert data["strategy"] == "test_strategy"
        assert "config" in data
        assert "risk_assessment" in data
        assert "distributions" in data
        assert "simulation_returns" in data

"""
Tests for backtest runner and metrics.

TEST DOC: Backtest Runner

WHAT: Tests for backtest execution and metrics calculation
WHY: Ensure accurate historical strategy evaluation
HOW: Create sample trades and verify metric calculations

CASES:
- Calculate metrics from trades
- Equity curve generation
- Streak analysis
- Drawdown calculation
- Report formatting

EDGE CASES:
- Empty trades: Returns default metrics
- All winners: No max drawdown
- All losers: 100% drawdown
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from ib_daily_picker.backtest.metrics import (
    BacktestMetrics,
    EquityCurvePoint,
    calculate_backtest_metrics,
    compare_strategies,
)
from ib_daily_picker.backtest.reporter import (
    format_comparison_table,
    format_console_report,
    format_json_report,
    format_trades_table,
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
) -> Trade:
    """Helper to create test trades."""
    today = date.today()
    return Trade(
        id=f"test-{datetime.now().timestamp()}",
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


class TestCalculateBacktestMetrics:
    """Tests for calculate_backtest_metrics function."""

    def test_empty_trades_returns_default_metrics(self):
        """Empty trade list returns default metrics."""
        metrics = calculate_backtest_metrics([])
        assert metrics.total_trades == 0
        assert metrics.total_pnl == Decimal("0")

    def test_single_winning_trade(self):
        """Single winning trade calculates correctly."""
        trade = create_trade(
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            position_size=Decimal("10"),
        )
        metrics = calculate_backtest_metrics(
            [trade],
            initial_capital=Decimal("10000"),
        )

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.total_pnl == Decimal("100")  # (110-100) * 10
        assert metrics.win_rate == Decimal("1")

    def test_mixed_trades_statistics(self):
        """Mixed trades calculate correct statistics."""
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_date=date.today() - timedelta(days=10),
            ),  # +100
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                entry_date=date.today() - timedelta(days=5),
            ),  # -100
        ]
        metrics = calculate_backtest_metrics(
            trades,
            initial_capital=Decimal("10000"),
        )

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("0.5")
        assert metrics.total_pnl == Decimal("0")

    def test_profit_factor_calculation(self):
        """Profit factor calculated correctly."""
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                entry_date=date.today() - timedelta(days=10),
            ),  # +200
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                entry_date=date.today() - timedelta(days=5),
            ),  # -100
        ]
        metrics = calculate_backtest_metrics(trades)

        assert metrics.profit_factor == Decimal("2")  # 200 / 100

    def test_capital_tracking(self):
        """Initial and final capital tracked correctly."""
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
            ),  # +100
        ]
        metrics = calculate_backtest_metrics(
            trades,
            initial_capital=Decimal("10000"),
        )

        assert metrics.initial_capital == Decimal("10000")
        assert metrics.final_capital == Decimal("10100")
        assert metrics.total_return == Decimal("100")
        assert metrics.total_return_pct == Decimal("1")

    def test_consecutive_streaks(self):
        """Max consecutive wins/losses tracked."""
        today = date.today()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_date=today - timedelta(days=5),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("115"),
                entry_date=today - timedelta(days=4),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                entry_date=today - timedelta(days=3),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                entry_date=today - timedelta(days=2),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("85"),
                entry_date=today - timedelta(days=1),
            ),
        ]
        metrics = calculate_backtest_metrics(trades)

        assert metrics.max_consecutive_wins == 3
        assert metrics.max_consecutive_losses == 2


class TestEquityCurve:
    """Tests for equity curve generation."""

    def test_equity_curve_generation(self):
        """Equity curve generated from trades."""
        today = date.today()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                exit_date=today - timedelta(days=2),
            ),  # +100
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("105"),
                exit_date=today - timedelta(days=1),
            ),  # +50
        ]
        metrics = calculate_backtest_metrics(
            trades,
            initial_capital=Decimal("10000"),
        )

        assert len(metrics.equity_curve) == 2

    def test_drawdown_tracking(self):
        """Drawdown tracked in equity curve."""
        today = date.today()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                exit_date=today - timedelta(days=3),
            ),  # +200 (peak)
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                exit_date=today - timedelta(days=2),
            ),  # -100 (drawdown)
        ]
        metrics = calculate_backtest_metrics(
            trades,
            initial_capital=Decimal("10000"),
        )

        assert metrics.max_drawdown > Decimal("0")


class TestBacktestConfig:
    """Tests for BacktestConfig."""

    def test_default_config(self):
        """Default config values."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert config.initial_capital == Decimal("100000")
        assert config.max_positions == 5
        assert config.use_stop_loss is True
        assert config.use_take_profit is True


class TestReporter:
    """Tests for report formatting."""

    def test_format_console_report(self):
        """Console report formats correctly."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),
        ]
        result = BacktestResult(
            strategy_name="Test Strategy",
            config=BacktestConfig(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            ),
            trades=trades,
            signals_generated=10,
            signals_executed=5,
            signals_skipped=5,
        )
        result.metrics = calculate_backtest_metrics(trades)

        report = format_console_report(result)

        assert "Test Strategy" in report
        assert "CAPITAL" in report
        assert "TRADE STATISTICS" in report
        assert "RISK METRICS" in report

    def test_format_json_report(self):
        """JSON report formats correctly."""
        import json

        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),
        ]
        result = BacktestResult(
            strategy_name="Test Strategy",
            config=BacktestConfig(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            ),
            trades=trades,
        )
        result.metrics = calculate_backtest_metrics(trades)

        json_str = format_json_report(result)
        data = json.loads(json_str)

        assert data["strategy"] == "Test Strategy"
        assert "capital" in data
        assert "trades" in data
        assert "risk" in data

    def test_format_trades_table(self):
        """Trades table formats correctly."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("95")),
        ]
        result = BacktestResult(
            strategy_name="Test",
            config=BacktestConfig(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            ),
            trades=trades,
        )

        table = format_trades_table(result)

        assert "AAPL" in table
        assert "long" in table


class TestCompareStrategies:
    """Tests for strategy comparison."""

    def test_compare_multiple_strategies(self):
        """Compare function works with multiple strategies."""
        metrics1 = BacktestMetrics(
            strategy_name="Strategy A",
            total_return_pct=Decimal("10"),
            win_rate=Decimal("0.6"),
            profit_factor=Decimal("1.5"),
            max_drawdown_pct=Decimal("5"),
            sharpe_ratio=Decimal("1.2"),
            total_trades=100,
        )

        metrics2 = BacktestMetrics(
            strategy_name="Strategy B",
            total_return_pct=Decimal("15"),
            win_rate=Decimal("0.55"),
            profit_factor=Decimal("1.8"),
            max_drawdown_pct=Decimal("8"),
            sharpe_ratio=Decimal("1.0"),
            total_trades=80,
        )

        comparison = compare_strategies([metrics1, metrics2])

        assert len(comparison["strategies"]) == 2
        assert "total_return_pct" in comparison["rankings"]
        # Strategy B has higher return
        assert comparison["rankings"]["total_return_pct"][0] == "Strategy B"

    def test_format_comparison_table(self):
        """Comparison table formats correctly."""
        trades1 = [create_trade(entry_price=Decimal("100"), exit_price=Decimal("110"))]
        trades2 = [create_trade(entry_price=Decimal("100"), exit_price=Decimal("105"))]

        result1 = BacktestResult(
            strategy_name="Strategy A",
            config=BacktestConfig(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)),
            trades=trades1,
        )
        result1.metrics = calculate_backtest_metrics(trades1, strategy_name="Strategy A")

        result2 = BacktestResult(
            strategy_name="Strategy B",
            config=BacktestConfig(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)),
            trades=trades2,
        )
        result2.metrics = calculate_backtest_metrics(trades2, strategy_name="Strategy B")

        table = format_comparison_table([result1, result2])

        assert "Strategy A" in table
        assert "Strategy B" in table
        assert "Return" in table
        assert "Win%" in table

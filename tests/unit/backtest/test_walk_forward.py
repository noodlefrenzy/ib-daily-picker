"""
Tests for walk-forward analysis functionality.

TEST DOC: Walk-Forward Validation

WHAT: Tests for walk-forward analysis and reporting
WHY: Validate that rolling window analysis and metrics are correct
HOW: Create mock backtest results, verify aggregation and reporting

CASES:
- Window generation from date range
- Aggregate statistics calculation
- Consistency scoring
- Console and JSON output formatting

EDGE CASES:
- Single window result
- All windows profitable
- All windows unprofitable
- Empty results list
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from ib_daily_picker.backtest.metrics import BacktestMetrics
from ib_daily_picker.backtest.reporter import (
    format_walk_forward_console,
    format_walk_forward_json,
)
from ib_daily_picker.backtest.runner import BacktestConfig, BacktestResult


def create_mock_result(
    window_num: int,
    start_date: date,
    end_date: date,
    total_return_pct: Decimal,
    win_rate: Decimal = Decimal("0.55"),
    max_drawdown_pct: Decimal = Decimal("5.0"),
    total_trades: int = 10,
    total_pnl: Decimal | None = None,
) -> BacktestResult:
    """Create a mock BacktestResult for testing."""
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("100000"),
    )

    if total_pnl is None:
        total_pnl = Decimal("100000") * total_return_pct / 100

    winning_trades = int(total_trades * float(win_rate))
    losing_trades = total_trades - winning_trades

    metrics = BacktestMetrics(
        strategy_name=f"test_strategy (Window {window_num})",
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("100000"),
        final_capital=Decimal("100000") + total_pnl,
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        avg_trade_pnl=total_pnl / total_trades if total_trades > 0 else Decimal("0"),
        avg_winner=Decimal("100"),
        avg_loser=Decimal("-50"),
        max_drawdown=Decimal("5000"),
        max_drawdown_pct=max_drawdown_pct,
    )

    result = BacktestResult(
        strategy_name=f"test_strategy (Window {window_num})",
        config=config,
        trades=[],
        metrics=metrics,
    )

    return result


class TestWalkForwardConsoleOutput:
    """Tests for console output formatting."""

    def test_console_output_contains_header(self):
        """Console output should have proper header."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "WALK-FORWARD ANALYSIS" in output
        assert "test_strategy" in output

    def test_console_output_shows_configuration(self):
        """Console output should show in-sample and out-sample config."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "252 days" in output
        assert "63 days" in output
        assert "Windows Tested:" in output

    def test_console_output_shows_each_window(self):
        """Console output should list each window's results."""
        today = date.today()
        results = [
            create_mock_result(
                1,
                today - timedelta(days=126),
                today - timedelta(days=64),
                Decimal("3.5"),
            ),
            create_mock_result(
                2,
                today - timedelta(days=63),
                today,
                Decimal("2.0"),
            ),
        ]

        output = format_walk_forward_console(results, 252, 63)

        # Should have 2 windows listed
        assert "OUT-OF-SAMPLE RESULTS BY WINDOW" in output
        # Both returns should appear
        assert "3.50%" in output or "3.5%" in output
        assert "2.00%" in output or "2.0%" in output

    def test_console_output_shows_aggregate_stats(self):
        """Console output should show aggregate statistics."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=126), today - timedelta(days=64), Decimal("5.0")),
            create_mock_result(2, today - timedelta(days=63), today, Decimal("3.0")),
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "AGGREGATE OUT-OF-SAMPLE STATISTICS" in output
        assert "Total Trades:" in output
        assert "Combined Return:" in output
        assert "Aggregate Win Rate:" in output

    def test_console_output_shows_robustness_assessment(self):
        """Console output should include robustness assessment."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.0")),
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "ROBUSTNESS INDICATORS" in output
        assert "Positive Windows:" in output
        assert "Assessment:" in output

    def test_strong_assessment_for_high_consistency(self):
        """Should show 'Strong' for 70%+ positive windows."""
        today = date.today()
        # 4 out of 5 positive = 80%
        results = [
            create_mock_result(i, today - timedelta(days=63 * (5 - i)), today - timedelta(days=63 * (4 - i)),
                             Decimal("5.0") if i < 4 else Decimal("-1.0"))
            for i in range(5)
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "[Strong]" in output

    def test_weak_assessment_for_low_consistency(self):
        """Should show 'Weak' for <50% positive windows."""
        today = date.today()
        # 1 out of 5 positive = 20%
        results = [
            create_mock_result(i, today - timedelta(days=63 * (5 - i)), today - timedelta(days=63 * (4 - i)),
                             Decimal("-2.0") if i < 4 else Decimal("5.0"))
            for i in range(5)
        ]

        output = format_walk_forward_console(results, 252, 63)

        assert "[Weak]" in output

    def test_empty_results_handled(self):
        """Empty results should return appropriate message."""
        output = format_walk_forward_console([], 252, 63)
        assert "No walk-forward results available" in output


class TestWalkForwardJsonOutput:
    """Tests for JSON output formatting."""

    def test_json_output_is_valid_json(self):
        """JSON output should parse without errors."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert isinstance(data, dict)

    def test_json_contains_strategy_name(self):
        """JSON should contain strategy name."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["strategy"] == "test_strategy"

    def test_json_contains_config(self):
        """JSON should contain configuration."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["config"]["in_sample_days"] == 252
        assert data["config"]["out_sample_days"] == 63
        assert data["config"]["num_windows"] == 1

    def test_json_contains_windows(self):
        """JSON should contain individual window results."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=126), today - timedelta(days=64), Decimal("3.5")),
            create_mock_result(2, today - timedelta(days=63), today, Decimal("2.0")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert len(data["windows"]) == 2
        assert data["windows"][0]["window"] == 1
        assert data["windows"][1]["window"] == 2

    def test_json_contains_aggregate(self):
        """JSON should contain aggregate statistics."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("5.5")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert "aggregate" in data
        assert "total_trades" in data["aggregate"]
        assert "combined_return_pct" in data["aggregate"]
        assert "positive_windows" in data["aggregate"]
        assert "consistency_pct" in data["aggregate"]

    def test_json_combined_return_calculation(self):
        """JSON combined return should chain returns correctly."""
        today = date.today()
        # Two 10% returns should compound to ~21%
        results = [
            create_mock_result(1, today - timedelta(days=126), today - timedelta(days=64), Decimal("10.0")),
            create_mock_result(2, today - timedelta(days=63), today, Decimal("10.0")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        combined = Decimal(data["aggregate"]["combined_return_pct"])
        # (1.10 * 1.10 - 1) * 100 = 21%
        assert Decimal("20") < combined < Decimal("22")


class TestWalkForwardAggregation:
    """Tests for aggregate metric calculations."""

    def test_combined_return_chains_correctly(self):
        """Combined return should use geometric compounding."""
        today = date.today()
        # 5% then -5% should be ~0.25% loss (not 0%)
        results = [
            create_mock_result(1, today - timedelta(days=126), today - timedelta(days=64), Decimal("5.0")),
            create_mock_result(2, today - timedelta(days=63), today, Decimal("-5.0")),
        ]

        # Verify console output runs without error
        _console = format_walk_forward_console(results, 252, 63)
        assert len(_console) > 0

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        combined = Decimal(data["aggregate"]["combined_return_pct"])
        # 1.05 * 0.95 = 0.9975 -> -0.25%
        assert combined < Decimal("0")

    def test_positive_windows_counted_correctly(self):
        """Should count positive windows accurately."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=189), today - timedelta(days=127), Decimal("5.0")),  # positive
            create_mock_result(2, today - timedelta(days=126), today - timedelta(days=64), Decimal("-2.0")),  # negative
            create_mock_result(3, today - timedelta(days=63), today, Decimal("3.0")),  # positive
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["aggregate"]["positive_windows"] == 2
        # 2/3 = 66.7%
        assert 66 < data["aggregate"]["consistency_pct"] < 68


class TestWalkForwardEdgeCases:
    """Tests for edge cases."""

    def test_single_window(self):
        """Should handle single window correctly."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("7.5")),
        ]

        output = format_walk_forward_console(results, 252, 63)
        json_str = format_walk_forward_json(results, 252, 63)

        assert "1/1" in output  # "1/1 (100%)"
        data = json.loads(json_str)
        assert data["aggregate"]["consistency_pct"] == 100.0

    def test_all_positive_windows(self):
        """All positive windows should show 100% consistency."""
        today = date.today()
        results = [
            create_mock_result(i, today - timedelta(days=63 * (3 - i)), today - timedelta(days=63 * (2 - i)), Decimal("5.0"))
            for i in range(3)
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["aggregate"]["positive_windows"] == 3
        assert data["aggregate"]["consistency_pct"] == 100.0

    def test_all_negative_windows(self):
        """All negative windows should show 0% consistency."""
        today = date.today()
        results = [
            create_mock_result(i, today - timedelta(days=63 * (3 - i)), today - timedelta(days=63 * (2 - i)), Decimal("-2.0"))
            for i in range(3)
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["aggregate"]["positive_windows"] == 0
        assert data["aggregate"]["consistency_pct"] == 0.0

    def test_zero_return_not_counted_as_positive(self):
        """Zero return should not be counted as positive."""
        today = date.today()
        results = [
            create_mock_result(1, today - timedelta(days=63), today, Decimal("0.0")),
        ]

        json_str = format_walk_forward_json(results, 252, 63)
        data = json.loads(json_str)

        assert data["aggregate"]["positive_windows"] == 0

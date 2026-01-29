"""
Backtest package - Historical strategy evaluation.

PURPOSE: Replay historical data, calculate performance metrics
"""

from ib_daily_picker.backtest.metrics import (
    BacktestMetrics,
    EquityCurvePoint,
    calculate_backtest_metrics,
    compare_strategies,
)
from ib_daily_picker.backtest.monte_carlo import (
    EquityConePoint,
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloRunner,
    PercentileDistribution,
)
from ib_daily_picker.backtest.reporter import (
    export_equity_curve_csv,
    format_comparison_table,
    format_console_report,
    format_json_report,
    format_monte_carlo_console,
    format_monte_carlo_json,
    format_trades_table,
    format_walk_forward_console,
    format_walk_forward_json,
)
from ib_daily_picker.backtest.runner import (
    BacktestConfig,
    BacktestPosition,
    BacktestResult,
    BacktestRunner,
    run_walk_forward,
)

__all__ = [
    # Metrics
    "BacktestMetrics",
    "EquityCurvePoint",
    "calculate_backtest_metrics",
    "compare_strategies",
    # Monte Carlo
    "EquityConePoint",
    "MonteCarloConfig",
    "MonteCarloResult",
    "MonteCarloRunner",
    "PercentileDistribution",
    # Reporter
    "export_equity_curve_csv",
    "format_comparison_table",
    "format_console_report",
    "format_json_report",
    "format_monte_carlo_console",
    "format_monte_carlo_json",
    "format_trades_table",
    "format_walk_forward_console",
    "format_walk_forward_json",
    # Runner
    "BacktestConfig",
    "BacktestPosition",
    "BacktestResult",
    "BacktestRunner",
    "run_walk_forward",
]

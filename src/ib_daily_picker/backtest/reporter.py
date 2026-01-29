"""
Backtest report generation.

PURPOSE: Generate formatted reports from backtest results
DEPENDENCIES: backtest.runner, backtest.metrics

ARCHITECTURE NOTES:
- Supports console, JSON, and HTML output
- Includes equity curves and trade tables
- Comparison reports for multiple strategies
"""

from __future__ import annotations

import json
from decimal import Decimal
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ib_daily_picker.backtest.monte_carlo import MonteCarloResult, PercentileDistribution
    from ib_daily_picker.backtest.runner import BacktestResult


def format_console_report(result: BacktestResult) -> str:
    """Format backtest result for console output.

    Args:
        result: BacktestResult from runner

    Returns:
        Formatted string for console display
    """
    if not result.metrics:
        return "No metrics available - backtest may have failed."

    m = result.metrics
    lines = []

    lines.append(f"{'=' * 60}")
    lines.append(f"BACKTEST REPORT: {result.strategy_name}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    # Period info
    lines.append("PERIOD")
    lines.append(f"  Start Date:       {m.start_date}")
    lines.append(f"  End Date:         {m.end_date}")
    lines.append(f"  Trading Days:     {m.trading_days}")
    lines.append("")

    # Capital
    lines.append("CAPITAL")
    lines.append(f"  Initial:          ${m.initial_capital:,.2f}")
    lines.append(f"  Final:            ${m.final_capital:,.2f}")
    lines.append(f"  Total Return:     ${m.total_return:,.2f} ({m.total_return_pct:.2f}%)")
    lines.append("")

    # Trade statistics
    lines.append("TRADE STATISTICS")
    lines.append(f"  Total Trades:     {m.total_trades}")
    lines.append(f"  Winning Trades:   {m.winning_trades}")
    lines.append(f"  Losing Trades:    {m.losing_trades}")
    lines.append(f"  Win Rate:         {float(m.win_rate) * 100:.1f}%")
    lines.append("")

    # PnL metrics
    lines.append("PROFIT/LOSS")
    lines.append(f"  Total PnL:        ${m.total_pnl:,.2f}")
    lines.append(f"  Gross Profit:     ${m.gross_profit:,.2f}")
    lines.append(f"  Gross Loss:       ${m.gross_loss:,.2f}")
    lines.append(f"  Avg Trade:        ${m.avg_trade_pnl:,.2f}")
    lines.append(f"  Avg Winner:       ${m.avg_winner:,.2f}")
    lines.append(f"  Avg Loser:        ${m.avg_loser:,.2f}")
    lines.append(f"  Largest Winner:   ${m.largest_winner:,.2f}")
    lines.append(f"  Largest Loser:    ${m.largest_loser:,.2f}")
    lines.append("")

    # Risk metrics
    lines.append("RISK METRICS")
    if m.profit_factor:
        lines.append(f"  Profit Factor:    {m.profit_factor:.2f}")
    lines.append(f"  Expectancy:       ${m.expectancy:,.2f}")
    if m.avg_r_multiple:
        lines.append(f"  Avg R-Multiple:   {m.avg_r_multiple:.2f}")
    lines.append(f"  Max Win Streak:   {m.max_consecutive_wins}")
    lines.append(f"  Max Loss Streak:  {m.max_consecutive_losses}")
    lines.append("")

    # Drawdown
    lines.append("DRAWDOWN")
    lines.append(f"  Max Drawdown:     ${m.max_drawdown:,.2f} ({m.max_drawdown_pct:.2f}%)")
    if m.max_drawdown_date:
        lines.append(f"  Max DD Date:      {m.max_drawdown_date}")
    lines.append(f"  Avg Drawdown:     ${m.avg_drawdown:,.2f}")
    lines.append("")

    # Risk-adjusted returns
    lines.append("RISK-ADJUSTED RETURNS")
    if m.sharpe_ratio:
        lines.append(f"  Sharpe Ratio:     {m.sharpe_ratio:.2f}")
    if m.calmar_ratio:
        lines.append(f"  Calmar Ratio:     {m.calmar_ratio:.2f}")
    if m.cagr:
        lines.append(f"  CAGR:             {m.cagr:.2f}%")
    if m.annual_volatility:
        lines.append(f"  Ann. Volatility:  {m.annual_volatility:.2f}%")
    lines.append("")

    # Execution metrics
    lines.append("EXECUTION")
    lines.append(f"  Signals Generated: {result.signals_generated}")
    lines.append(f"  Signals Executed:  {result.signals_executed}")
    lines.append(f"  Signals Skipped:   {result.signals_skipped}")
    lines.append(f"  Avg Hold Time:    {m.avg_hold_time_days:.1f} days")
    lines.append(f"  Avg Position:     {m.avg_position_size:.1f} shares")
    lines.append("")

    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


def format_json_report(result: BacktestResult) -> str:
    """Format backtest result as JSON.

    Args:
        result: BacktestResult from runner

    Returns:
        JSON string
    """
    if not result.metrics:
        return json.dumps({"error": "No metrics available"})

    m = result.metrics

    def decimal_to_str(val: Decimal | None) -> str | None:
        return str(val) if val is not None else None

    data = {
        "strategy": result.strategy_name,
        "period": {
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "trading_days": m.trading_days,
        },
        "capital": {
            "initial": decimal_to_str(m.initial_capital),
            "final": decimal_to_str(m.final_capital),
            "total_return": decimal_to_str(m.total_return),
            "total_return_pct": decimal_to_str(m.total_return_pct),
        },
        "trades": {
            "total": m.total_trades,
            "winners": m.winning_trades,
            "losers": m.losing_trades,
            "win_rate": decimal_to_str(m.win_rate),
        },
        "pnl": {
            "total": decimal_to_str(m.total_pnl),
            "gross_profit": decimal_to_str(m.gross_profit),
            "gross_loss": decimal_to_str(m.gross_loss),
            "avg_trade": decimal_to_str(m.avg_trade_pnl),
            "avg_winner": decimal_to_str(m.avg_winner),
            "avg_loser": decimal_to_str(m.avg_loser),
            "largest_winner": decimal_to_str(m.largest_winner),
            "largest_loser": decimal_to_str(m.largest_loser),
        },
        "risk": {
            "profit_factor": decimal_to_str(m.profit_factor),
            "expectancy": decimal_to_str(m.expectancy),
            "avg_r_multiple": decimal_to_str(m.avg_r_multiple),
            "max_win_streak": m.max_consecutive_wins,
            "max_loss_streak": m.max_consecutive_losses,
        },
        "drawdown": {
            "max": decimal_to_str(m.max_drawdown),
            "max_pct": decimal_to_str(m.max_drawdown_pct),
            "max_date": m.max_drawdown_date.isoformat() if m.max_drawdown_date else None,
            "avg": decimal_to_str(m.avg_drawdown),
        },
        "risk_adjusted": {
            "sharpe_ratio": decimal_to_str(m.sharpe_ratio),
            "calmar_ratio": decimal_to_str(m.calmar_ratio),
            "cagr": decimal_to_str(m.cagr),
            "annual_volatility": decimal_to_str(m.annual_volatility),
        },
        "execution": {
            "signals_generated": result.signals_generated,
            "signals_executed": result.signals_executed,
            "signals_skipped": result.signals_skipped,
            "avg_hold_days": decimal_to_str(m.avg_hold_time_days),
            "avg_position_size": decimal_to_str(m.avg_position_size),
        },
        "trades_detail": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction.value,
                "entry_date": t.entry_time.date().isoformat(),
                "exit_date": t.exit_time.date().isoformat() if t.exit_time else None,
                "entry_price": str(t.entry_price),
                "exit_price": str(t.exit_price) if t.exit_price else None,
                "pnl": str(t.pnl) if t.pnl else None,
                "r_multiple": str(t.r_multiple) if t.r_multiple else None,
            }
            for t in result.trades[:100]  # Limit to 100 trades
        ],
    }

    return json.dumps(data, indent=2)


def format_trades_table(result: BacktestResult, limit: int = 50) -> str:
    """Format trades as a text table.

    Args:
        result: BacktestResult from runner
        limit: Maximum trades to show

    Returns:
        Formatted table string
    """
    if not result.trades:
        return "No trades executed."

    lines = []
    header = f"{'Symbol':<8} {'Dir':<6} {'Entry':>10} {'Exit':>10} {'PnL':>12} {'R':>6} {'Days':>5}"
    lines.append(header)
    lines.append("-" * len(header))

    for trade in result.trades[:limit]:
        entry = f"${trade.entry_price:.2f}"
        exit_price = f"${trade.exit_price:.2f}" if trade.exit_price else "-"
        pnl = f"${trade.pnl:,.2f}" if trade.pnl else "-"
        r_mult = f"{trade.r_multiple:.1f}R" if trade.r_multiple else "-"
        days = str(trade.duration_minutes // 1440) if trade.duration_minutes else "-"

        lines.append(
            f"{trade.symbol:<8} {trade.direction.value:<6} {entry:>10} {exit_price:>10} "
            f"{pnl:>12} {r_mult:>6} {days:>5}"
        )

    if len(result.trades) > limit:
        lines.append(f"... and {len(result.trades) - limit} more trades")

    return "\n".join(lines)


def format_comparison_table(results: list[BacktestResult]) -> str:
    """Format comparison of multiple backtest results.

    Args:
        results: List of BacktestResult from different strategies

    Returns:
        Formatted comparison table
    """
    if not results:
        return "No results to compare."

    lines = []

    header = (
        f"{'Strategy':<30} {'Return':>10} {'Win%':>8} {'PF':>8} "
        f"{'MaxDD':>10} {'Sharpe':>8} {'Trades':>8}"
    )
    lines.append(header)
    lines.append("=" * len(header))

    for result in results:
        if not result.metrics:
            continue

        m = result.metrics
        name = result.strategy_name[:30]
        ret = f"{m.total_return_pct:.1f}%"
        win_rate = f"{float(m.win_rate) * 100:.1f}%"
        pf = f"{m.profit_factor:.2f}" if m.profit_factor else "-"
        max_dd = f"{m.max_drawdown_pct:.1f}%"
        sharpe = f"{m.sharpe_ratio:.2f}" if m.sharpe_ratio else "-"
        trades = str(m.total_trades)

        lines.append(
            f"{name:<30} {ret:>10} {win_rate:>8} {pf:>8} {max_dd:>10} {sharpe:>8} {trades:>8}"
        )

    return "\n".join(lines)


def export_equity_curve_csv(result: BacktestResult) -> str:
    """Export equity curve as CSV.

    Args:
        result: BacktestResult from runner

    Returns:
        CSV string
    """
    if not result.metrics or not result.metrics.equity_curve:
        return "date,equity,drawdown,drawdown_pct\n"

    output = StringIO()
    output.write("date,equity,drawdown,drawdown_pct\n")

    for point in result.metrics.equity_curve:
        output.write(
            f"{point.date.isoformat()},{point.equity},{point.drawdown},{point.drawdown_pct}\n"
        )

    return output.getvalue()


def format_monte_carlo_console(result: MonteCarloResult) -> str:
    """Format Monte Carlo result for console output.

    Args:
        result: MonteCarloResult from simulation

    Returns:
        Formatted string for console display
    """
    lines = []

    lines.append(f"{'=' * 60}")
    lines.append(f"MONTE CARLO RESULTS ({result.num_simulations} simulations)")
    lines.append(f"Strategy: {result.strategy_name}")
    lines.append(f"{'=' * 60}")
    lines.append("")

    # Configuration summary
    config = result.config
    config_parts = []
    if config.shuffle_trades:
        config_parts.append("shuffle")
    if config.trade_removal:
        config_parts.append(f"removal({config.trade_removal_pct:.0%})")
    if config.execution_variance:
        config_parts.append(f"slippage({config.slippage_std_pct:.2%})")
    lines.append(f"Transformations: {', '.join(config_parts) if config_parts else 'none'}")
    if config.random_seed is not None:
        lines.append(f"Random Seed: {config.random_seed}")
    lines.append("")

    # Risk assessment
    lines.append("RISK ASSESSMENT")
    lines.append(f"  Probability of Loss:  {float(result.probability_of_loss) * 100:.1f}%")
    lines.append(f"  Probability of Ruin:  {float(result.probability_of_ruin) * 100:.1f}%")
    lines.append(f"  Expected Worst DD:    {result.max_drawdown_dist.p95:.1f}%")
    lines.append("")

    # Metric distributions table
    lines.append("METRIC DISTRIBUTIONS")
    lines.append(
        _format_distribution_table(
            [
                result.total_return_dist,
                result.max_drawdown_dist,
                result.win_rate_dist,
            ]
        )
    )
    lines.append("")

    # Optional metrics
    if result.sharpe_ratio_dist:
        lines.append(
            f"  Sharpe Ratio:    5th={result.sharpe_ratio_dist.p5:.2f}  "
            f"50th={result.sharpe_ratio_dist.p50:.2f}  "
            f"95th={result.sharpe_ratio_dist.p95:.2f}"
        )

    if result.profit_factor_dist:
        lines.append(
            f"  Profit Factor:   5th={result.profit_factor_dist.p5:.2f}  "
            f"50th={result.profit_factor_dist.p50:.2f}  "
            f"95th={result.profit_factor_dist.p95:.2f}"
        )

    lines.append("")

    # Base vs median comparison
    base_return = (
        result.base_result.metrics.total_return_pct if result.base_result.metrics else Decimal("0")
    )
    median_return = result.total_return_dist.p50
    diff = base_return - median_return
    comparison = "above" if diff > 0 else "below" if diff < 0 else "at"
    lines.append(f"Base Result vs Median: {diff:+.2f}% (base performed {comparison} median)")

    lines.append("")
    lines.append(f"{'=' * 60}")

    return "\n".join(lines)


def _format_distribution_table(distributions: list[PercentileDistribution]) -> str:
    """Format a table of percentile distributions.

    Args:
        distributions: List of PercentileDistribution objects

    Returns:
        Formatted table string
    """
    # Header
    header = f"  {'Metric':<14} {'5th':>8} {'25th':>8} {'50th':>8} {'75th':>8} {'95th':>8}"
    separator = f"  {'-' * 14} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 8}"

    lines = [header, separator]

    # Format metric name for display
    name_map = {
        "total_return_pct": "Total Return",
        "max_drawdown_pct": "Max Drawdown",
        "win_rate": "Win Rate",
        "sharpe_ratio": "Sharpe Ratio",
        "profit_factor": "Profit Factor",
    }

    for dist in distributions:
        name = name_map.get(dist.metric_name, dist.metric_name)

        # Format values with appropriate precision
        if dist.metric_name in ("total_return_pct", "max_drawdown_pct", "win_rate"):
            # Percentages
            values = [
                f"{float(dist.p5):.1f}%",
                f"{float(dist.p25):.1f}%",
                f"{float(dist.p50):.1f}%",
                f"{float(dist.p75):.1f}%",
                f"{float(dist.p95):.1f}%",
            ]
        else:
            # Ratios
            values = [
                f"{float(dist.p5):.2f}",
                f"{float(dist.p25):.2f}",
                f"{float(dist.p50):.2f}",
                f"{float(dist.p75):.2f}",
                f"{float(dist.p95):.2f}",
            ]

        lines.append(
            f"  {name:<14} {values[0]:>8} {values[1]:>8} {values[2]:>8} "
            f"{values[3]:>8} {values[4]:>8}"
        )

    return "\n".join(lines)


def format_monte_carlo_json(result: MonteCarloResult) -> str:
    """Format Monte Carlo result as JSON.

    Args:
        result: MonteCarloResult from simulation

    Returns:
        JSON string
    """

    def decimal_to_str(val: Decimal | None) -> str | None:
        return str(val) if val is not None else None

    def dist_to_dict(dist: PercentileDistribution | None) -> dict | None:
        if dist is None:
            return None
        return {
            "metric_name": dist.metric_name,
            "p5": decimal_to_str(dist.p5),
            "p25": decimal_to_str(dist.p25),
            "p50": decimal_to_str(dist.p50),
            "p75": decimal_to_str(dist.p75),
            "p95": decimal_to_str(dist.p95),
            "mean": decimal_to_str(dist.mean),
            "std_dev": decimal_to_str(dist.std_dev),
        }

    data = {
        "strategy": result.strategy_name,
        "config": {
            "num_simulations": result.config.num_simulations,
            "random_seed": result.config.random_seed,
            "shuffle_trades": result.config.shuffle_trades,
            "trade_removal": result.config.trade_removal,
            "trade_removal_pct": decimal_to_str(result.config.trade_removal_pct),
            "execution_variance": result.config.execution_variance,
            "slippage_std_pct": decimal_to_str(result.config.slippage_std_pct),
        },
        "num_simulations": result.num_simulations,
        "risk_assessment": {
            "probability_of_loss": decimal_to_str(result.probability_of_loss),
            "probability_of_ruin": decimal_to_str(result.probability_of_ruin),
        },
        "distributions": {
            "total_return": dist_to_dict(result.total_return_dist),
            "max_drawdown": dist_to_dict(result.max_drawdown_dist),
            "win_rate": dist_to_dict(result.win_rate_dist),
            "sharpe_ratio": dist_to_dict(result.sharpe_ratio_dist),
            "profit_factor": dist_to_dict(result.profit_factor_dist),
        },
        "equity_cone": [
            {
                "date": point.date.isoformat(),
                "p5": decimal_to_str(point.p5),
                "p25": decimal_to_str(point.p25),
                "median": decimal_to_str(point.median),
                "p75": decimal_to_str(point.p75),
                "p95": decimal_to_str(point.p95),
            }
            for point in result.equity_cone
        ],
        "simulation_returns": [decimal_to_str(r) for r in result.simulation_returns],
        "base_result": {
            "total_return_pct": decimal_to_str(
                result.base_result.metrics.total_return_pct if result.base_result.metrics else None
            ),
            "max_drawdown_pct": decimal_to_str(
                result.base_result.metrics.max_drawdown_pct if result.base_result.metrics else None
            ),
            "total_trades": result.base_result.metrics.total_trades
            if result.base_result.metrics
            else 0,
        },
    }

    return json.dumps(data, indent=2)


def format_walk_forward_console(
    results: list[BacktestResult],
    in_sample_days: int,
    out_sample_days: int,
) -> str:
    """Format walk-forward results for console output.

    Args:
        results: List of BacktestResult from each out-of-sample window
        in_sample_days: Training period length
        out_sample_days: Testing period length

    Returns:
        Formatted string for console display
    """
    if not results:
        return "No walk-forward results available."

    lines = []
    strategy_name = results[0].strategy_name.split(" (Window")[0]

    lines.append(f"{'=' * 70}")
    lines.append(f"WALK-FORWARD ANALYSIS: {strategy_name}")
    lines.append(f"{'=' * 70}")
    lines.append("")
    lines.append("Configuration:")
    lines.append(f"  In-Sample Period:   {in_sample_days} days (~{in_sample_days // 21} months)")
    lines.append(f"  Out-of-Sample:      {out_sample_days} days (~{out_sample_days // 21} months)")
    lines.append(f"  Windows Tested:     {len(results)}")
    lines.append("")

    # Window-by-window summary table
    lines.append("OUT-OF-SAMPLE RESULTS BY WINDOW")
    lines.append(
        f"  {'Window':<8} {'Period':<25} {'Trades':>7} {'Return':>10} {'Win Rate':>10} {'Max DD':>10}"
    )
    lines.append(f"  {'-' * 8} {'-' * 25} {'-' * 7} {'-' * 10} {'-' * 10} {'-' * 10}")

    total_trades = 0
    total_pnl = Decimal("0")
    wins = 0
    losses = 0
    max_dd_all = Decimal("0")

    for i, result in enumerate(results, 1):
        m = result.metrics
        if not m:
            continue

        period = f"{m.start_date} - {m.end_date}"
        total_trades += m.total_trades
        total_pnl += m.total_pnl
        wins += m.winning_trades
        losses += m.losing_trades
        if m.max_drawdown_pct > max_dd_all:
            max_dd_all = m.max_drawdown_pct

        lines.append(
            f"  {i:<8} {period:<25} {m.total_trades:>7} "
            f"{float(m.total_return_pct):>9.2f}% {float(m.win_rate) * 100:>9.1f}% "
            f"{float(m.max_drawdown_pct):>9.2f}%"
        )

    lines.append("")

    # Aggregate statistics
    lines.append("AGGREGATE OUT-OF-SAMPLE STATISTICS")
    aggregate_win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

    # Calculate combined return
    # Chain the returns: (1 + r1) * (1 + r2) * ... - 1
    combined_return = Decimal("1")
    for result in results:
        if result.metrics:
            combined_return *= Decimal("1") + result.metrics.total_return_pct / 100
    combined_return = (combined_return - 1) * 100

    lines.append(f"  Total Trades:       {total_trades}")
    lines.append(f"  Total PnL:          ${float(total_pnl):,.2f}")
    lines.append(f"  Combined Return:    {float(combined_return):.2f}%")
    lines.append(f"  Aggregate Win Rate: {aggregate_win_rate * 100:.1f}%")
    lines.append(f"  Worst Window DD:    {float(max_dd_all):.2f}%")
    lines.append("")

    # Consistency analysis
    positive_windows = sum(1 for r in results if r.metrics and r.metrics.total_return_pct > 0)
    consistency_pct = positive_windows / len(results) * 100 if results else 0

    lines.append("ROBUSTNESS INDICATORS")
    lines.append(
        f"  Positive Windows:   {positive_windows}/{len(results)} ({consistency_pct:.0f}%)"
    )

    if consistency_pct >= 70:
        lines.append("  Assessment:         [Strong] Strategy shows consistent edge across periods")
    elif consistency_pct >= 50:
        lines.append("  Assessment:         [Moderate] Strategy profitable in majority of windows")
    else:
        lines.append("  Assessment:         [Weak] Strategy may be overfit to specific periods")

    lines.append("")
    lines.append(f"{'=' * 70}")

    return "\n".join(lines)


def format_walk_forward_json(
    results: list[BacktestResult],
    in_sample_days: int,
    out_sample_days: int,
) -> str:
    """Format walk-forward results as JSON.

    Args:
        results: List of BacktestResult from each out-of-sample window
        in_sample_days: Training period length
        out_sample_days: Testing period length

    Returns:
        JSON string
    """

    def decimal_to_str(val: Decimal | None) -> str | None:
        return str(val) if val is not None else None

    strategy_name = results[0].strategy_name.split(" (Window")[0] if results else "unknown"

    windows = []
    for i, result in enumerate(results, 1):
        m = result.metrics
        if not m:
            continue

        windows.append(
            {
                "window": i,
                "start_date": m.start_date.isoformat(),
                "end_date": m.end_date.isoformat(),
                "total_trades": m.total_trades,
                "total_pnl": decimal_to_str(m.total_pnl),
                "total_return_pct": decimal_to_str(m.total_return_pct),
                "win_rate": decimal_to_str(m.win_rate),
                "max_drawdown_pct": decimal_to_str(m.max_drawdown_pct),
                "sharpe_ratio": decimal_to_str(m.sharpe_ratio),
                "profit_factor": decimal_to_str(m.profit_factor),
            }
        )

    # Calculate aggregates
    total_trades = sum(w["total_trades"] for w in windows)
    positive_windows = sum(1 for r in results if r.metrics and r.metrics.total_return_pct > 0)

    # Combined return
    combined_return = Decimal("1")
    for result in results:
        if result.metrics:
            combined_return *= Decimal("1") + result.metrics.total_return_pct / 100
    combined_return = (combined_return - 1) * 100

    data = {
        "strategy": strategy_name,
        "config": {
            "in_sample_days": in_sample_days,
            "out_sample_days": out_sample_days,
            "num_windows": len(results),
        },
        "windows": windows,
        "aggregate": {
            "total_trades": total_trades,
            "combined_return_pct": decimal_to_str(combined_return),
            "positive_windows": positive_windows,
            "consistency_pct": round(positive_windows / len(results) * 100, 1) if results else 0,
        },
    }

    return json.dumps(data, indent=2)

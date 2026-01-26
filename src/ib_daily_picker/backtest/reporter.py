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
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ib_daily_picker.backtest.metrics import BacktestMetrics
    from ib_daily_picker.backtest.runner import BacktestResult


def format_console_report(result: "BacktestResult") -> str:
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


def format_json_report(result: "BacktestResult") -> str:
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


def format_trades_table(result: "BacktestResult", limit: int = 50) -> str:
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


def format_comparison_table(results: list["BacktestResult"]) -> str:
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


def export_equity_curve_csv(result: "BacktestResult") -> str:
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

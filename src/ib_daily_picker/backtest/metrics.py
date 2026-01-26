"""
Backtest metrics calculations.

PURPOSE: Calculate performance metrics from backtest results
DEPENDENCIES: models.trade

ARCHITECTURE NOTES:
- Extends TradeMetrics with backtest-specific calculations
- Includes Sharpe ratio, max drawdown, CAGR
- Supports benchmark comparison
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ib_daily_picker.models import Trade


@dataclass
class EquityCurvePoint:
    """Single point on equity curve."""

    date: date
    equity: Decimal
    drawdown: Decimal = Decimal("0")
    drawdown_pct: Decimal = Decimal("0")


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics."""

    # Basic info
    strategy_name: str = ""
    start_date: date | None = None
    end_date: date | None = None
    trading_days: int = 0

    # Capital metrics
    initial_capital: Decimal = Decimal("100000")
    final_capital: Decimal = Decimal("100000")
    total_return: Decimal = Decimal("0")
    total_return_pct: Decimal = Decimal("0")

    # Trade metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: Decimal = Decimal("0")

    # PnL metrics
    total_pnl: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    avg_trade_pnl: Decimal = Decimal("0")
    avg_winner: Decimal = Decimal("0")
    avg_loser: Decimal = Decimal("0")
    largest_winner: Decimal = Decimal("0")
    largest_loser: Decimal = Decimal("0")

    # Risk metrics
    profit_factor: Decimal | None = None
    expectancy: Decimal = Decimal("0")
    avg_r_multiple: Decimal | None = None
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Drawdown metrics
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    max_drawdown_date: date | None = None
    avg_drawdown: Decimal = Decimal("0")
    max_drawdown_duration_days: int = 0

    # Risk-adjusted returns
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    calmar_ratio: Decimal | None = None

    # Annualized metrics
    cagr: Decimal | None = None
    annual_volatility: Decimal | None = None

    # Exposure metrics
    avg_position_size: Decimal = Decimal("0")
    avg_hold_time_days: Decimal = Decimal("0")
    max_concurrent_positions: int = 0
    time_in_market_pct: Decimal = Decimal("0")

    # Equity curve
    equity_curve: list[EquityCurvePoint] = field(default_factory=list)


def calculate_backtest_metrics(
    trades: list["Trade"],
    initial_capital: Decimal = Decimal("100000"),
    start_date: date | None = None,
    end_date: date | None = None,
    strategy_name: str = "",
    risk_free_rate: Decimal = Decimal("0.02"),  # 2% annual
) -> BacktestMetrics:
    """Calculate comprehensive backtest metrics from trade list.

    Args:
        trades: List of closed trades (chronologically sorted)
        initial_capital: Starting capital
        start_date: Backtest start date
        end_date: Backtest end date
        strategy_name: Name of strategy
        risk_free_rate: Annual risk-free rate for Sharpe calculation

    Returns:
        BacktestMetrics with all performance data
    """
    from ib_daily_picker.models import TradeStatus

    metrics = BacktestMetrics(
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    # Filter to closed trades with PnL
    closed = [t for t in trades if t.status == TradeStatus.CLOSED and t.pnl is not None]

    if not closed:
        return metrics

    # Sort by entry time
    closed = sorted(closed, key=lambda t: t.entry_time)

    # Calculate date range
    if not start_date:
        start_date = closed[0].entry_time.date()
        metrics.start_date = start_date
    if not end_date:
        end_date = closed[-1].exit_time.date() if closed[-1].exit_time else date.today()
        metrics.end_date = end_date

    metrics.trading_days = (end_date - start_date).days if start_date and end_date else 0

    # Basic trade counts
    winners = [t for t in closed if t.pnl and t.pnl > 0]
    losers = [t for t in closed if t.pnl and t.pnl < 0]
    break_even = [t for t in closed if t.pnl == Decimal("0")]

    metrics.total_trades = len(closed)
    metrics.winning_trades = len(winners)
    metrics.losing_trades = len(losers)
    metrics.break_even_trades = len(break_even)

    # Win rate
    if closed:
        metrics.win_rate = Decimal(str(len(winners))) / Decimal(str(len(closed)))

    # PnL calculations
    all_pnls = [t.pnl for t in closed if t.pnl is not None]
    metrics.total_pnl = sum(all_pnls, start=Decimal("0"))
    metrics.gross_profit = sum((t.pnl for t in winners if t.pnl), start=Decimal("0"))
    metrics.gross_loss = abs(sum((t.pnl for t in losers if t.pnl), start=Decimal("0")))

    # Average PnL
    if closed:
        metrics.avg_trade_pnl = metrics.total_pnl / len(closed)
    if winners:
        metrics.avg_winner = metrics.gross_profit / len(winners)
    if losers:
        metrics.avg_loser = metrics.gross_loss / len(losers)

    # Largest winner/loser
    if all_pnls:
        metrics.largest_winner = max(all_pnls)
        metrics.largest_loser = min(all_pnls)

    # Final capital
    metrics.final_capital = initial_capital + metrics.total_pnl
    metrics.total_return = metrics.final_capital - initial_capital
    if initial_capital > 0:
        metrics.total_return_pct = (metrics.total_return / initial_capital) * 100

    # Profit factor
    if metrics.gross_loss > 0:
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss

    # Expectancy
    loss_rate = Decimal("1") - metrics.win_rate
    metrics.expectancy = (
        metrics.win_rate * metrics.avg_winner - loss_rate * metrics.avg_loser
    )

    # R-multiple
    r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]
    if r_multiples:
        metrics.avg_r_multiple = sum(r_multiples, start=Decimal("0")) / len(r_multiples)

    # Consecutive wins/losses
    metrics.max_consecutive_wins, metrics.max_consecutive_losses = _calculate_streaks(closed)

    # Equity curve and drawdown
    equity_curve = _build_equity_curve(closed, initial_capital)
    metrics.equity_curve = equity_curve

    if equity_curve:
        drawdowns = [e.drawdown for e in equity_curve]
        metrics.max_drawdown = max(drawdowns) if drawdowns else Decimal("0")

        drawdown_pcts = [e.drawdown_pct for e in equity_curve]
        metrics.max_drawdown_pct = max(drawdown_pcts) if drawdown_pcts else Decimal("0")

        # Find max drawdown date
        for point in equity_curve:
            if point.drawdown == metrics.max_drawdown:
                metrics.max_drawdown_date = point.date
                break

        # Average drawdown
        if drawdowns:
            metrics.avg_drawdown = sum(drawdowns, start=Decimal("0")) / len(drawdowns)

    # Hold time
    hold_times = []
    for trade in closed:
        if trade.exit_time:
            delta = trade.exit_time - trade.entry_time
            hold_times.append(delta.total_seconds() / 86400)  # Days

    if hold_times:
        metrics.avg_hold_time_days = Decimal(str(sum(hold_times) / len(hold_times)))

    # Position size
    sizes = [float(t.position_size) for t in closed]
    if sizes:
        metrics.avg_position_size = Decimal(str(sum(sizes) / len(sizes)))

    # Risk-adjusted returns (if we have enough data)
    if metrics.trading_days >= 30:
        # Simple Sharpe approximation
        daily_returns = _calculate_daily_returns(equity_curve)
        if daily_returns and len(daily_returns) >= 10:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = variance ** 0.5

            if std_dev > 0:
                annualized_return = avg_return * 252
                annualized_std = std_dev * (252 ** 0.5)
                metrics.annual_volatility = Decimal(str(annualized_std))

                # Sharpe = (Return - RiskFree) / StdDev
                excess_return = Decimal(str(annualized_return)) - risk_free_rate
                metrics.sharpe_ratio = excess_return / Decimal(str(annualized_std))

                # Calmar = CAGR / Max Drawdown
                if metrics.max_drawdown_pct > 0 and metrics.trading_days > 0:
                    years = Decimal(str(metrics.trading_days)) / Decimal("365")
                    if years > 0:
                        cagr = (
                            (metrics.final_capital / metrics.initial_capital)
                            ** (Decimal("1") / years)
                        ) - Decimal("1")
                        metrics.cagr = cagr * 100
                        metrics.calmar_ratio = metrics.cagr / metrics.max_drawdown_pct

    return metrics


def _calculate_streaks(trades: list["Trade"]) -> tuple[int, int]:
    """Calculate max consecutive wins and losses."""
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for trade in trades:
        if trade.pnl is None:
            continue

        if trade.pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif trade.pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            # Break even doesn't affect streaks
            pass

    return max_wins, max_losses


def _build_equity_curve(
    trades: list["Trade"],
    initial_capital: Decimal,
) -> list[EquityCurvePoint]:
    """Build equity curve from trades."""
    if not trades:
        return []

    curve = []
    current_equity = initial_capital
    peak_equity = initial_capital

    # Get unique exit dates
    trade_dates: dict[date, Decimal] = {}
    for trade in trades:
        if trade.exit_time and trade.pnl:
            exit_date = trade.exit_time.date()
            trade_dates.setdefault(exit_date, Decimal("0"))
            trade_dates[exit_date] += trade.pnl

    # Build curve
    for d, daily_pnl in sorted(trade_dates.items()):
        current_equity += daily_pnl
        peak_equity = max(peak_equity, current_equity)

        drawdown = peak_equity - current_equity
        drawdown_pct = (drawdown / peak_equity * 100) if peak_equity > 0 else Decimal("0")

        curve.append(EquityCurvePoint(
            date=d,
            equity=current_equity,
            drawdown=drawdown,
            drawdown_pct=drawdown_pct,
        ))

    return curve


def _calculate_daily_returns(equity_curve: list[EquityCurvePoint]) -> list[float]:
    """Calculate daily percentage returns from equity curve."""
    if len(equity_curve) < 2:
        return []

    returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = float(equity_curve[i - 1].equity)
        curr_equity = float(equity_curve[i].equity)
        if prev_equity > 0:
            daily_return = (curr_equity - prev_equity) / prev_equity
            returns.append(daily_return)

    return returns


def compare_strategies(
    metrics_list: list[BacktestMetrics],
) -> dict[str, Any]:
    """Compare multiple strategy backtest results.

    Args:
        metrics_list: List of BacktestMetrics from different strategies

    Returns:
        Comparison dict with rankings
    """
    if not metrics_list:
        return {}

    comparison: dict[str, list[dict[str, Any]] | dict[str, list[str]]] = {
        "strategies": [],
        "rankings": {},
    }

    # Collect comparable values
    for m in metrics_list:
        comparison["strategies"].append({
            "name": m.strategy_name,
            "total_return_pct": float(m.total_return_pct),
            "win_rate": float(m.win_rate),
            "profit_factor": float(m.profit_factor) if m.profit_factor else 0,
            "max_drawdown_pct": float(m.max_drawdown_pct),
            "sharpe_ratio": float(m.sharpe_ratio) if m.sharpe_ratio else 0,
            "total_trades": m.total_trades,
        })

    # Calculate rankings for each metric
    for key in ["total_return_pct", "win_rate", "profit_factor", "sharpe_ratio"]:
        ranked = sorted(
            comparison["strategies"],
            key=lambda x: x[key],
            reverse=True,
        )
        comparison["rankings"][key] = [s["name"] for s in ranked]

    # For drawdown, lower is better
    ranked = sorted(
        comparison["strategies"],
        key=lambda x: x["max_drawdown_pct"],
    )
    comparison["rankings"]["max_drawdown_pct"] = [s["name"] for s in ranked]

    return comparison

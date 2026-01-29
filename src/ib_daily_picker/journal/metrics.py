"""
Trade journal metrics calculations.

PURPOSE: Extended metrics for trade analysis and journaling
DEPENDENCIES: models.trade

ARCHITECTURE NOTES:
- Extends TradeMetrics with time-based and strategy-level analysis
- Supports filtering by date ranges, tags, symbols
- Calculates drawdown, streak analysis, and expectancy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ib_daily_picker.models import Trade


@dataclass
class StreakInfo:
    """Information about winning/losing streaks."""

    current_streak: int = 0
    current_streak_type: str = "none"  # "win", "loss", "none"
    max_win_streak: int = 0
    max_loss_streak: int = 0


@dataclass
class DrawdownInfo:
    """Drawdown analysis."""

    current_drawdown: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_date: date | None = None
    recovery_days: int | None = None


@dataclass
class TimeAnalysis:
    """Time-based trade analysis."""

    trades_by_day: dict[str, int] = field(default_factory=dict)  # day name -> count
    trades_by_hour: dict[int, int] = field(default_factory=dict)  # hour -> count
    avg_hold_time_minutes: float = 0.0
    shortest_trade_minutes: int | None = None
    longest_trade_minutes: int | None = None


@dataclass
class StrategyAnalysis:
    """Per-strategy analysis."""

    strategy_name: str
    total_trades: int = 0
    win_rate: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    avg_r_multiple: Decimal | None = None
    profit_factor: Decimal | None = None


@dataclass
class ExtendedMetrics:
    """Extended trade journal metrics."""

    # Basic metrics (summary)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")

    # Average metrics
    avg_winner: Decimal = Decimal("0")
    avg_loser: Decimal = Decimal("0")
    avg_trade: Decimal = Decimal("0")
    avg_r_multiple: Decimal | None = None

    # Risk metrics
    profit_factor: Decimal | None = None
    expectancy: Decimal = Decimal("0")
    largest_winner: Decimal = Decimal("0")
    largest_loser: Decimal = Decimal("0")

    # Streak analysis
    streak: StreakInfo = field(default_factory=StreakInfo)

    # Drawdown analysis
    drawdown: DrawdownInfo = field(default_factory=DrawdownInfo)

    # Time analysis
    time_analysis: TimeAnalysis = field(default_factory=TimeAnalysis)

    # Per-strategy breakdown
    by_strategy: list[StrategyAnalysis] = field(default_factory=list)

    # Per-symbol breakdown
    by_symbol: dict[str, dict] = field(default_factory=dict)

    # Per-tag breakdown
    by_tag: dict[str, dict] = field(default_factory=dict)


def calculate_extended_metrics(trades: list[Trade]) -> ExtendedMetrics:
    """Calculate extended metrics from a list of trades.

    Args:
        trades: List of Trade objects (should include closed trades)

    Returns:
        ExtendedMetrics with comprehensive analysis
    """
    from ib_daily_picker.models import TradeStatus

    # Filter to closed trades with PnL
    closed = [t for t in trades if t.status == TradeStatus.CLOSED and t.pnl is not None]

    if not closed:
        return ExtendedMetrics()

    metrics = ExtendedMetrics()

    # Basic counts
    winners = [t for t in closed if t.pnl and t.pnl > 0]
    losers = [t for t in closed if t.pnl and t.pnl < 0]
    break_even = [t for t in closed if t.pnl == Decimal("0")]

    metrics.total_trades = len(closed)
    metrics.winning_trades = len(winners)
    metrics.losing_trades = len(losers)
    metrics.break_even_trades = len(break_even)

    # PnL calculations
    metrics.total_pnl = sum((t.pnl for t in closed if t.pnl), start=Decimal("0"))
    gross_profit = sum((t.pnl for t in winners if t.pnl), start=Decimal("0"))
    gross_loss = abs(sum((t.pnl for t in losers if t.pnl), start=Decimal("0")))

    # Win rate
    metrics.win_rate = (
        Decimal(str(len(winners))) / Decimal(str(len(closed))) if closed else Decimal("0")
    )

    # Averages
    metrics.avg_winner = gross_profit / len(winners) if winners else Decimal("0")
    metrics.avg_loser = gross_loss / len(losers) if losers else Decimal("0")
    metrics.avg_trade = metrics.total_pnl / len(closed) if closed else Decimal("0")

    # R-multiple
    r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]
    if r_multiples:
        metrics.avg_r_multiple = sum(r_multiples, start=Decimal("0")) / len(r_multiples)

    # Profit factor
    if gross_loss > 0:
        metrics.profit_factor = gross_profit / gross_loss

    # Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
    loss_rate = Decimal("1") - metrics.win_rate
    metrics.expectancy = metrics.win_rate * metrics.avg_winner - loss_rate * metrics.avg_loser

    # Largest winner/loser
    pnls = [t.pnl for t in closed if t.pnl is not None]
    metrics.largest_winner = max(pnls) if pnls else Decimal("0")
    metrics.largest_loser = min(pnls) if pnls else Decimal("0")

    # Streak analysis
    metrics.streak = _calculate_streaks(closed)

    # Drawdown analysis
    metrics.drawdown = _calculate_drawdown(closed)

    # Time analysis
    metrics.time_analysis = _calculate_time_analysis(closed)

    # Per-strategy breakdown
    metrics.by_strategy = _calculate_by_strategy(closed)

    # Per-symbol breakdown
    metrics.by_symbol = _calculate_by_symbol(closed)

    # Per-tag breakdown
    metrics.by_tag = _calculate_by_tag(closed)

    return metrics


def _calculate_streaks(trades: list[Trade]) -> StreakInfo:
    """Calculate winning/losing streak information."""
    if not trades:
        return StreakInfo()

    # Sort by entry time
    sorted_trades = sorted(trades, key=lambda t: t.entry_time)

    info = StreakInfo()
    current_streak = 0
    current_type = "none"

    for trade in sorted_trades:
        if trade.pnl is None:
            continue

        is_win = trade.pnl > 0

        if is_win:
            if current_type == "win":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "win"
            info.max_win_streak = max(info.max_win_streak, current_streak)
        else:
            if current_type == "loss":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "loss"
            info.max_loss_streak = max(info.max_loss_streak, current_streak)

    info.current_streak = current_streak
    info.current_streak_type = current_type

    return info


def _calculate_drawdown(trades: list[Trade]) -> DrawdownInfo:
    """Calculate drawdown metrics."""
    if not trades:
        return DrawdownInfo()

    # Sort by exit time for equity curve
    sorted_trades = sorted(
        [t for t in trades if t.exit_time],
        key=lambda t: t.exit_time,  # type: ignore
    )

    if not sorted_trades:
        return DrawdownInfo()

    info = DrawdownInfo()
    cumulative_pnl = Decimal("0")
    peak_pnl = Decimal("0")
    max_drawdown = Decimal("0")
    max_dd_date: date | None = None

    for trade in sorted_trades:
        if trade.pnl is None or trade.exit_time is None:
            continue

        cumulative_pnl += trade.pnl
        peak_pnl = max(peak_pnl, cumulative_pnl)

        current_dd = peak_pnl - cumulative_pnl
        if current_dd > max_drawdown:
            max_drawdown = current_dd
            max_dd_date = trade.exit_time.date()

    info.current_drawdown = peak_pnl - cumulative_pnl
    info.max_drawdown = max_drawdown
    info.max_drawdown_date = max_dd_date

    return info


def _calculate_time_analysis(trades: list[Trade]) -> TimeAnalysis:
    """Calculate time-based analysis."""
    if not trades:
        return TimeAnalysis()

    analysis = TimeAnalysis()
    hold_times: list[int] = []

    for trade in trades:
        # Day of week
        day_name = trade.entry_time.strftime("%A")
        analysis.trades_by_day[day_name] = analysis.trades_by_day.get(day_name, 0) + 1

        # Hour of day
        hour = trade.entry_time.hour
        analysis.trades_by_hour[hour] = analysis.trades_by_hour.get(hour, 0) + 1

        # Hold time
        duration = trade.duration_minutes
        if duration is not None:
            hold_times.append(duration)

    if hold_times:
        analysis.avg_hold_time_minutes = sum(hold_times) / len(hold_times)
        analysis.shortest_trade_minutes = min(hold_times)
        analysis.longest_trade_minutes = max(hold_times)

    return analysis


def _calculate_by_strategy(trades: list[Trade]) -> list[StrategyAnalysis]:
    """Calculate per-strategy breakdown."""
    from ib_daily_picker.models import TradeStatus

    # Group by strategy (via recommendation relationship)
    strategy_trades: dict[str, list[Trade]] = {}

    for trade in trades:
        # Use "Unknown" for trades without recommendation
        strategy = "Unknown"
        if hasattr(trade, "_strategy_name"):
            strategy = trade._strategy_name  # type: ignore
        strategy_trades.setdefault(strategy, []).append(trade)

    results = []
    for strategy_name, strat_trades in strategy_trades.items():
        analysis = StrategyAnalysis(strategy_name=strategy_name)

        closed = [t for t in strat_trades if t.status == TradeStatus.CLOSED and t.pnl is not None]
        winners = [t for t in closed if t.pnl and t.pnl > 0]
        losers = [t for t in closed if t.pnl and t.pnl < 0]

        analysis.total_trades = len(closed)
        analysis.win_rate = (
            Decimal(str(len(winners))) / Decimal(str(len(closed))) if closed else Decimal("0")
        )
        analysis.total_pnl = sum((t.pnl for t in closed if t.pnl), start=Decimal("0"))

        r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]
        if r_multiples:
            analysis.avg_r_multiple = sum(r_multiples, start=Decimal("0")) / len(r_multiples)

        gross_profit = sum((t.pnl for t in winners if t.pnl), start=Decimal("0"))
        gross_loss = abs(sum((t.pnl for t in losers if t.pnl), start=Decimal("0")))
        if gross_loss > 0:
            analysis.profit_factor = gross_profit / gross_loss

        results.append(analysis)

    return results


def _calculate_by_symbol(trades: list[Trade]) -> dict[str, dict]:
    """Calculate per-symbol breakdown."""
    symbol_stats: dict[str, dict] = {}

    for trade in trades:
        symbol = trade.symbol
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {
                "total_trades": 0,
                "winning_trades": 0,
                "total_pnl": Decimal("0"),
            }

        symbol_stats[symbol]["total_trades"] += 1
        if trade.pnl and trade.pnl > 0:
            symbol_stats[symbol]["winning_trades"] += 1
        if trade.pnl:
            symbol_stats[symbol]["total_pnl"] += trade.pnl

    # Calculate win rates
    for stats in symbol_stats.values():
        stats["win_rate"] = (
            Decimal(str(stats["winning_trades"])) / Decimal(str(stats["total_trades"]))
            if stats["total_trades"] > 0
            else Decimal("0")
        )

    return symbol_stats


def _calculate_by_tag(trades: list[Trade]) -> dict[str, dict]:
    """Calculate per-tag breakdown."""
    tag_stats: dict[str, dict] = {}

    for trade in trades:
        for tag in trade.tags:
            if tag not in tag_stats:
                tag_stats[tag] = {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl": Decimal("0"),
                }

            tag_stats[tag]["total_trades"] += 1
            if trade.pnl and trade.pnl > 0:
                tag_stats[tag]["winning_trades"] += 1
            if trade.pnl:
                tag_stats[tag]["total_pnl"] += trade.pnl

    # Calculate win rates
    for stats in tag_stats.values():
        stats["win_rate"] = (
            Decimal(str(stats["winning_trades"])) / Decimal(str(stats["total_trades"]))
            if stats["total_trades"] > 0
            else Decimal("0")
        )

    return tag_stats


def filter_trades(
    trades: list[Trade],
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    symbols: list[str] | None = None,
    tags: list[str] | None = None,
    min_pnl: Decimal | None = None,
    max_pnl: Decimal | None = None,
) -> list[Trade]:
    """Filter trades by various criteria.

    Args:
        trades: List of trades to filter
        start_date: Include trades on or after this date
        end_date: Include trades on or before this date
        symbols: Include only these symbols
        tags: Include trades with any of these tags
        min_pnl: Minimum PnL threshold
        max_pnl: Maximum PnL threshold

    Returns:
        Filtered list of trades
    """
    result = trades

    if start_date:
        result = [t for t in result if t.entry_time.date() >= start_date]

    if end_date:
        result = [t for t in result if t.entry_time.date() <= end_date]

    if symbols:
        symbols_upper = [s.upper() for s in symbols]
        result = [t for t in result if t.symbol in symbols_upper]

    if tags:
        result = [t for t in result if any(tag in t.tags for tag in tags)]

    if min_pnl is not None:
        result = [t for t in result if t.pnl is not None and t.pnl >= min_pnl]

    if max_pnl is not None:
        result = [t for t in result if t.pnl is not None and t.pnl <= max_pnl]

    return result

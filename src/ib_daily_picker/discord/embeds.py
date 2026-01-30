"""
Discord embed formatters for IB Daily Picker.

PURPOSE: Create rich Discord embeds for analysis results, signals, etc.
DEPENDENCIES: discord.py, models

ARCHITECTURE NOTES:
- Embeds provide formatted display of analysis data
- Color-coded by signal type (green=buy, red=sell, yellow=hold)
- Include relevant metrics and reasoning
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import discord

from ib_daily_picker.models import (
    Recommendation,
    RecommendationBatch,
    SignalType,
)

if TYPE_CHECKING:
    from ib_daily_picker.journal.metrics import ExtendedMetrics


# Signal colors
SIGNAL_COLORS = {
    SignalType.BUY: discord.Color.green(),
    SignalType.SELL: discord.Color.red(),
    SignalType.HOLD: discord.Color.gold(),
    SignalType.AVOID: discord.Color.dark_grey(),
}


def format_price(value: Decimal | None) -> str:
    """Format a price for display."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_percent(value: Decimal | float | None) -> str:
    """Format a percentage for display."""
    if value is None:
        return "N/A"
    if isinstance(value, Decimal):
        value = float(value)
    return f"{value:.1%}"


def format_confidence(confidence: Decimal) -> str:
    """Format confidence score with visual indicator."""
    conf_float = float(confidence)
    bars = int(conf_float * 5)  # 0-5 bars
    bar_str = "█" * bars + "░" * (5 - bars)
    return f"{bar_str} {conf_float:.0%}"


def create_recommendation_embed(rec: Recommendation) -> discord.Embed:
    """Create an embed for a single recommendation.

    Args:
        rec: The recommendation to display

    Returns:
        Formatted Discord embed
    """
    color = SIGNAL_COLORS.get(rec.signal_type, discord.Color.blue())

    embed = discord.Embed(
        title=f"{rec.signal_type.value.upper()} Signal: {rec.symbol}",
        description=rec.reasoning[:500] if rec.reasoning else "No reasoning provided",
        color=color,
        timestamp=rec.generated_at,
    )

    # Price targets
    embed.add_field(
        name="Entry",
        value=format_price(rec.entry_price),
        inline=True,
    )
    embed.add_field(
        name="Stop Loss",
        value=format_price(rec.stop_loss),
        inline=True,
    )
    embed.add_field(
        name="Target",
        value=format_price(rec.take_profit),
        inline=True,
    )

    # Risk/reward
    if rec.risk_reward_ratio:
        embed.add_field(
            name="Risk/Reward",
            value=f"{float(rec.risk_reward_ratio):.2f}:1",
            inline=True,
        )

    # Confidence
    embed.add_field(
        name="Confidence",
        value=format_confidence(rec.confidence),
        inline=True,
    )

    # Position size
    if rec.position_size:
        embed.add_field(
            name="Position Size",
            value=f"{int(rec.position_size)} shares",
            inline=True,
        )

    embed.set_footer(text=f"Strategy: {rec.strategy_name}")

    return embed


def create_signals_list_embed(
    batch: RecommendationBatch,
    title: str = "Current Signals",
) -> discord.Embed:
    """Create an embed listing multiple recommendations.

    Args:
        batch: Batch of recommendations
        title: Embed title

    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title=title,
        description=f"Found {batch.count} signal(s), {batch.actionable_count} actionable",
        color=discord.Color.blue(),
        timestamp=batch.generated_at,
    )

    # Group by signal type
    for signal_type in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]:
        filtered = batch.filter_by_signal(signal_type)
        if filtered.count == 0:
            continue

        # Build field value
        lines = []
        for rec in filtered.recommendations[:5]:  # Limit to 5 per type
            conf_pct = f"{float(rec.confidence):.0%}"
            price_str = format_price(rec.entry_price)
            lines.append(f"**{rec.symbol}** @ {price_str} ({conf_pct})")

        if filtered.count > 5:
            lines.append(f"*...and {filtered.count - 5} more*")

        embed.add_field(
            name=f"{signal_type.value.upper()} ({filtered.count})",
            value="\n".join(lines),
            inline=False,
        )

    if batch.strategy_name:
        embed.set_footer(text=f"Strategy: {batch.strategy_name}")

    return embed


def create_analysis_progress_embed(
    current: int,
    total: int,
    current_symbol: str | None = None,
) -> discord.Embed:
    """Create a progress embed for ongoing analysis.

    Args:
        current: Current item number
        total: Total items to process
        current_symbol: Symbol currently being processed

    Returns:
        Formatted Discord embed
    """
    progress = current / total if total > 0 else 0
    bar_length = 20
    filled = int(progress * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    embed = discord.Embed(
        title="Analysis in Progress",
        description=f"```{bar}``` {current}/{total} ({progress:.0%})",
        color=discord.Color.orange(),
    )

    if current_symbol:
        embed.add_field(name="Current", value=current_symbol, inline=True)

    return embed


def create_metrics_embed(metrics: ExtendedMetrics) -> discord.Embed:
    """Create an embed for trading performance metrics.

    Args:
        metrics: Performance metrics to display

    Returns:
        Formatted Discord embed
    """
    # Determine color based on total P&L
    if metrics.total_pnl > 0:
        color = discord.Color.green()
    elif metrics.total_pnl < 0:
        color = discord.Color.red()
    else:
        color = discord.Color.gold()

    embed = discord.Embed(
        title="Trading Performance",
        color=color,
    )

    # Overview
    embed.add_field(
        name="Total P&L",
        value=format_price(metrics.total_pnl),
        inline=True,
    )
    embed.add_field(
        name="Win Rate",
        value=format_percent(metrics.win_rate),
        inline=True,
    )
    embed.add_field(
        name="Trades",
        value=str(metrics.total_trades),
        inline=True,
    )

    # Wins/Losses
    embed.add_field(
        name="Wins",
        value=str(metrics.winning_trades),
        inline=True,
    )
    embed.add_field(
        name="Losses",
        value=str(metrics.losing_trades),
        inline=True,
    )
    embed.add_field(
        name="Avg Trade",
        value=format_price(metrics.avg_trade),
        inline=True,
    )

    # Risk metrics
    if metrics.profit_factor:
        embed.add_field(
            name="Profit Factor",
            value=f"{float(metrics.profit_factor):.2f}",
            inline=True,
        )
    if metrics.drawdown and metrics.drawdown.max_drawdown:
        embed.add_field(
            name="Max Drawdown",
            value=format_price(metrics.drawdown.max_drawdown),
            inline=True,
        )

    return embed


def create_data_status_embed(
    stock_coverage: dict[str, tuple[str, str]],
    flow_coverage: dict[str, int],
    last_update: datetime | None,
) -> discord.Embed:
    """Create an embed for data coverage status.

    Args:
        stock_coverage: Dict mapping symbols to (first_date, last_date) tuples
        flow_coverage: Dict mapping symbols to alert counts
        last_update: Timestamp of last data update

    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Data Coverage Status",
        color=discord.Color.blue(),
    )

    # Stock data summary
    if stock_coverage:
        lines = []
        for symbol, (first_date, last_date) in list(stock_coverage.items())[:10]:
            lines.append(f"**{symbol}**: {first_date} to {last_date}")
        if len(stock_coverage) > 10:
            lines.append(f"*...and {len(stock_coverage) - 10} more*")
        embed.add_field(
            name=f"Stock Data ({len(stock_coverage)} symbols)",
            value="\n".join(lines) if lines else "No data",
            inline=False,
        )

    # Flow data summary
    if flow_coverage:
        total_alerts = sum(flow_coverage.values())
        top_symbols = sorted(flow_coverage.items(), key=lambda x: x[1], reverse=True)[:5]
        lines = [f"**{sym}**: {count} alerts" for sym, count in top_symbols]
        embed.add_field(
            name=f"Flow Alerts ({total_alerts} total)",
            value="\n".join(lines) if lines else "No alerts",
            inline=False,
        )

    # Last update
    if last_update:
        embed.set_footer(text=f"Last updated: {last_update.strftime('%Y-%m-%d %H:%M UTC')}")

    return embed


def create_error_embed(
    title: str,
    message: str,
    suggestion: str | None = None,
) -> discord.Embed:
    """Create an error embed.

    Args:
        title: Error title
        message: Error message
        suggestion: Optional suggestion for resolution

    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title=f"Error: {title}",
        description=message,
        color=discord.Color.red(),
    )

    if suggestion:
        embed.add_field(
            name="Suggestion",
            value=suggestion,
            inline=False,
        )

    return embed

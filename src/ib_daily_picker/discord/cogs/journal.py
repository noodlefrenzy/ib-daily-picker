"""
Journal Discord commands.

PURPOSE: Discord slash commands for trade journal and metrics
DEPENDENCIES: discord.py, journal module

ARCHITECTURE NOTES:
- Displays trading performance metrics
- Shows recent trades
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ib_daily_picker.discord.embeds import (
    create_error_embed,
    create_metrics_embed,
    format_percent,
    format_price,
)

if TYPE_CHECKING:
    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)


class JournalCog(commands.Cog, name="Journal"):
    """Trade journal commands."""

    def __init__(self, bot: IBPickerBot) -> None:
        self.bot = bot

    @app_commands.command(name="metrics", description="Show trading performance metrics")
    @app_commands.describe(
        days="Number of days to include (default: all)",
        strategy="Filter by strategy name",
    )
    async def metrics(
        self,
        interaction: discord.Interaction,
        days: int | None = None,
        strategy: str | None = None,
    ) -> None:
        """Show trading performance metrics."""
        await interaction.response.defer(thinking=True)

        try:
            from datetime import UTC, datetime, timedelta

            from ib_daily_picker.journal.manager import JournalManager
            from ib_daily_picker.journal.metrics import calculate_extended_metrics
            from ib_daily_picker.store.database import get_db_manager

            db = get_db_manager()
            manager = JournalManager(db)

            # Get trades with optional filters
            trades = manager.get_closed_trades()

            # Apply date filter
            if days:
                cutoff = datetime.now(UTC) - timedelta(days=days)
                trades = [t for t in trades if t.exit_time and t.exit_time >= cutoff]

            # Apply strategy filter
            if strategy:
                # Filter trades by strategy (via recommendation)
                # For now, just note that we'd need to look up the recommendation
                pass

            if not trades:
                embed = discord.Embed(
                    title="No Trades Found",
                    description="No closed trades in the specified period.",
                    color=discord.Color.gold(),
                )
                if days:
                    embed.add_field(name="Period", value=f"Last {days} days", inline=True)
                embed.set_footer(text="Record trades with the CLI or web interface")
                await interaction.followup.send(embed=embed)
                return

            # Calculate metrics
            metrics = calculate_extended_metrics(trades)

            embed = create_metrics_embed(metrics)

            # Add period info
            if days:
                embed.add_field(name="Period", value=f"Last {days} days", inline=True)
            else:
                embed.add_field(name="Period", value="All time", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in metrics command")
            embed = create_error_embed("Metrics Failed", str(e))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="trades", description="Show recent trades")
    @app_commands.describe(
        limit="Number of trades to show (default: 10)",
        symbol="Filter by symbol",
    )
    async def trades(
        self,
        interaction: discord.Interaction,
        limit: int = 10,
        symbol: str | None = None,
    ) -> None:
        """Show recent trades."""
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.journal.manager import JournalManager
            from ib_daily_picker.store.database import get_db_manager

            db = get_db_manager()
            manager = JournalManager(db)

            # Get trades
            trades = manager.get_closed_trades(limit=limit * 2)  # Get extra to filter

            # Apply symbol filter
            if symbol:
                symbol = symbol.upper()
                trades = [t for t in trades if t.symbol == symbol]

            trades = trades[:limit]

            if not trades:
                embed = discord.Embed(
                    title="No Trades Found",
                    description="No trades match the criteria.",
                    color=discord.Color.gold(),
                )
                if symbol:
                    embed.add_field(name="Filter", value=f"Symbol: {symbol}", inline=True)
                await interaction.followup.send(embed=embed)
                return

            # Create trades embed
            embed = discord.Embed(
                title="Recent Trades",
                description=f"Showing {len(trades)} trade(s)",
                color=discord.Color.blue(),
            )

            for trade in trades:
                # Determine profit/loss emoji
                if trade.pnl and trade.pnl > 0:
                    emoji = "🟢"
                elif trade.pnl and trade.pnl < 0:
                    emoji = "🔴"
                else:
                    emoji = "⚪"

                # Format trade info
                pnl_str = format_price(trade.pnl) if trade.pnl else "N/A"
                pnl_pct_str = format_percent(trade.pnl_percent) if trade.pnl_percent else ""

                entry_str = format_price(trade.entry_price)
                exit_str = format_price(trade.exit_price) if trade.exit_price else "Open"

                date_str = (
                    trade.exit_time.strftime("%m/%d")
                    if trade.exit_time
                    else trade.entry_time.strftime("%m/%d")
                )

                embed.add_field(
                    name=f"{emoji} {trade.symbol} ({date_str})",
                    value=f"Entry: {entry_str} → Exit: {exit_str}\nP&L: {pnl_str} ({pnl_pct_str})",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in trades command")
            embed = create_error_embed("Trades Failed", str(e))
            await interaction.followup.send(embed=embed)


async def setup(bot: IBPickerBot) -> None:
    """Set up the cog."""
    await bot.add_cog(JournalCog(bot))

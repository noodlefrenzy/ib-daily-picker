"""
Core Discord bot commands.

PURPOSE: Basic bot commands like /ping, /help, /about
DEPENDENCIES: discord.py
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ib_daily_picker import __version__

if TYPE_CHECKING:
    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)


class CoreCog(commands.Cog, name="Core"):
    """Core bot commands for health checks and information."""

    def __init__(self, bot: IBPickerBot) -> None:
        self.bot = bot
        self._start_time = datetime.now(UTC)

    @app_commands.command(name="ping", description="Check if the bot is responsive")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Respond with latency information."""
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="Pong!",
            color=discord.Color.green() if latency_ms < 200 else discord.Color.yellow(),
        )
        embed.add_field(name="Latency", value=f"{latency_ms}ms", inline=True)
        embed.add_field(name="Status", value="Online", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction) -> None:
        """Display help information about available commands."""
        embed = discord.Embed(
            title="IB Daily Picker - Help",
            description="Stock opportunity identification using flow data and price action.",
            color=discord.Color.blue(),
        )

        # Core commands
        core_cmds = [
            ("`/ping`", "Check bot responsiveness"),
            ("`/help`", "Show this help message"),
            ("`/about`", "About the bot and version info"),
        ]
        embed.add_field(
            name="Core Commands",
            value="\n".join(f"{cmd} - {desc}" for cmd, desc in core_cmds),
            inline=False,
        )

        # Analysis commands (will be added in Phase 2)
        analysis_cmds = [
            ("`/analyze`", "Run strategy analysis"),
            ("`/signals`", "Show pending recommendations"),
        ]
        embed.add_field(
            name="Analysis Commands",
            value="\n".join(f"{cmd} - {desc}" for cmd, desc in analysis_cmds),
            inline=False,
        )

        # Data commands (will be added in Phase 3)
        data_cmds = [
            ("`/fetch stocks`", "Update stock data"),
            ("`/fetch flows`", "Update flow data"),
            ("`/status`", "Data coverage status"),
            ("`/watchlist`", "List watched symbols"),
        ]
        embed.add_field(
            name="Data Commands",
            value="\n".join(f"{cmd} - {desc}" for cmd, desc in data_cmds),
            inline=False,
        )

        # Journal commands (will be added in Phase 3)
        journal_cmds = [
            ("`/metrics`", "Show trading performance"),
        ]
        embed.add_field(
            name="Journal Commands",
            value="\n".join(f"{cmd} - {desc}" for cmd, desc in journal_cmds),
            inline=False,
        )

        embed.set_footer(text=f"IB Daily Picker v{__version__}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="about", description="About the bot and version info")
    async def about(self, interaction: discord.Interaction) -> None:
        """Display information about the bot."""
        uptime = datetime.now(UTC) - self._start_time
        uptime_str = str(uptime).split(".")[0]  # Remove microseconds

        embed = discord.Embed(
            title="IB Daily Picker",
            description=(
                "A stock opportunity identification tool that correlates "
                "market flow data with price action."
            ),
            color=discord.Color.blue(),
        )

        embed.add_field(name="Version", value=__version__, inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(
            name="Guilds",
            value=str(len(self.bot.guilds)),
            inline=True,
        )

        # Settings info
        settings = self.bot.settings
        embed.add_field(
            name="Tracked Symbols",
            value=str(len(settings.basket.default_tickers)),
            inline=True,
        )
        embed.add_field(
            name="LLM Provider",
            value=settings.api.llm_provider,
            inline=True,
        )
        embed.add_field(
            name="Daily Analysis",
            value="Enabled" if settings.discord.daily_enabled else "Disabled",
            inline=True,
        )

        embed.set_footer(
            text="Built with discord.py",
            icon_url="https://cdn.discordapp.com/icons/336642139381301249/3aa641b21acded468308a37eef43d7b3.png",
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: IBPickerBot) -> None:
    """Set up the cog."""
    await bot.add_cog(CoreCog(bot))

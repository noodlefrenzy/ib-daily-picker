"""
Admin Discord commands.

PURPOSE: Bot administration and schedule management
DEPENDENCIES: discord.py

ARCHITECTURE NOTES:
- Schedule control commands
- Bot status and diagnostics
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ib_daily_picker.discord.embeds import create_error_embed

if TYPE_CHECKING:
    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)


class ScheduleGroup(app_commands.Group):
    """Group of schedule commands."""

    def __init__(self, bot: IBPickerBot) -> None:
        super().__init__(name="schedule", description="Manage scheduled analysis")
        self.bot = bot

    @app_commands.command(name="status", description="Show scheduler status")
    async def schedule_status(self, interaction: discord.Interaction) -> None:
        """Show the status of the daily scheduler."""
        scheduler = getattr(self.bot, "_scheduler", None)
        settings = self.bot.settings.discord

        embed = discord.Embed(
            title="Scheduler Status",
            color=discord.Color.blue(),
        )

        # Enabled status
        embed.add_field(
            name="Enabled",
            value="Yes" if settings.daily_enabled else "No",
            inline=True,
        )

        # Configured time
        embed.add_field(
            name="Scheduled Time",
            value=f"{settings.daily_time} ET",
            inline=True,
        )

        # Strategy
        embed.add_field(
            name="Strategy",
            value=settings.daily_strategy,
            inline=True,
        )

        # Channel
        if settings.daily_channel_id:
            channel = self.bot.get_channel(settings.daily_channel_id)
            channel_name = getattr(channel, "name", "Unknown") if channel else "Not found"
            embed.add_field(
                name="Channel",
                value=f"#{channel_name}",
                inline=True,
            )
        else:
            embed.add_field(
                name="Channel",
                value="Not configured",
                inline=True,
            )

        # Running status
        if scheduler:
            embed.add_field(
                name="Running",
                value="Yes" if scheduler.is_running else "No",
                inline=True,
            )
            if scheduler.next_iteration:
                embed.add_field(
                    name="Next Run",
                    value=scheduler.next_iteration.strftime("%Y-%m-%d %H:%M %Z"),
                    inline=True,
                )
        else:
            embed.add_field(
                name="Running",
                value="Not initialized",
                inline=True,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="run", description="Run daily analysis now")
    async def schedule_run(self, interaction: discord.Interaction) -> None:
        """Trigger daily analysis immediately."""
        await interaction.response.defer(thinking=True)

        scheduler = getattr(self.bot, "_scheduler", None)
        if not scheduler:
            embed = create_error_embed(
                "Scheduler Not Available",
                "The scheduler is not initialized.",
            )
            await interaction.followup.send(embed=embed)
            return

        # Run the analysis
        success = await scheduler.run_now()

        if success:
            embed = discord.Embed(
                title="Analysis Complete",
                description="Daily analysis has been run. Check the configured channel for results.",
                color=discord.Color.green(),
            )
        else:
            embed = create_error_embed(
                "Analysis Failed",
                "Failed to run daily analysis. Check logs for details.",
            )

        await interaction.followup.send(embed=embed)


class AdminCog(commands.Cog, name="Admin"):
    """Admin commands for bot management."""

    def __init__(self, bot: IBPickerBot) -> None:
        self.bot = bot
        self.schedule_group = ScheduleGroup(bot)
        bot.tree.add_command(self.schedule_group)

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self.bot.tree.remove_command(self.schedule_group.name)


async def setup(bot: IBPickerBot) -> None:
    """Set up the cog."""
    await bot.add_cog(AdminCog(bot))

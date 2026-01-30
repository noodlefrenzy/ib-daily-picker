"""
Main Discord bot class for IB Daily Picker.

PURPOSE: Discord bot setup and lifecycle management
DEPENDENCIES: discord.py, config

ARCHITECTURE NOTES:
- Uses discord.py's commands.Bot for slash command support
- Loads cogs dynamically for modular command handling
- Manages bot lifecycle (startup, shutdown, reconnection)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from ib_daily_picker.config import Settings

logger = logging.getLogger(__name__)


class IBPickerBot(commands.Bot):
    """Discord bot for IB Daily Picker stock analysis."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the bot with configuration.

        Args:
            settings: Application settings including Discord config
        """
        from ib_daily_picker.discord.scheduler import DailyAnalysisScheduler

        self._settings = settings
        self._guild_id = settings.discord.guild_id
        self._scheduler = DailyAnalysisScheduler(self)

        # Set up intents - we only need minimal intents for slash commands
        intents = discord.Intents.default()
        intents.message_content = False  # Not needed for slash commands

        super().__init__(
            command_prefix="!",  # Fallback, we use slash commands
            intents=intents,
            help_command=None,  # We'll use slash command /help
        )

    @property
    def settings(self) -> Settings:
        """Get the bot settings."""
        return self._settings

    async def setup_hook(self) -> None:
        """Called when the bot is starting up.

        Loads all cogs and syncs slash commands.
        """
        # Load cogs
        await self._load_cogs()

        # Sync commands
        if self._guild_id:
            # Sync to specific guild for faster development
            guild = discord.Object(id=self._guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {self._guild_id}")
        else:
            # Sync globally (takes up to an hour to propagate)
            await self.tree.sync()
            logger.info("Synced commands globally")

    async def _load_cogs(self) -> None:
        """Load all cog modules."""
        cog_modules = [
            "ib_daily_picker.discord.cogs.core",
            "ib_daily_picker.discord.cogs.analysis",
            "ib_daily_picker.discord.cogs.data",
            "ib_daily_picker.discord.cogs.journal",
            "ib_daily_picker.discord.cogs.admin",
        ]

        for module in cog_modules:
            try:
                await self.load_extension(module)
                logger.info(f"Loaded cog: {module}")
            except Exception as e:
                logger.error(f"Failed to load cog {module}: {e}")
                raise

    async def on_ready(self) -> None:
        """Called when the bot has connected to Discord."""
        if self.user:
            logger.info(f"Bot connected as {self.user} (ID: {self.user.id})")
        else:
            logger.info("Bot connected")

        # Log guild information
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        for guild in self.guilds:
            logger.info(f"  - {guild.name} (ID: {guild.id})")

        # Start the scheduler
        self._scheduler.start()

    async def on_command_error(
        self,
        ctx: commands.Context,  # type: ignore[type-arg]
        error: commands.CommandError,
    ) -> None:
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands

        logger.error(f"Command error: {error}", exc_info=error)

    async def close(self) -> None:
        """Clean up resources on shutdown."""
        # Stop the scheduler
        self._scheduler.stop()
        await super().close()

    def run_bot(self) -> None:
        """Run the bot with the configured token."""
        token = self._settings.discord.token
        if not token:
            raise ValueError(
                "Discord token not configured. Set DISCORD_TOKEN environment variable."
            )

        self.run(token, log_handler=None)  # Use our own logging config


async def create_bot(settings: Settings) -> IBPickerBot:
    """Create and configure the bot instance.

    Args:
        settings: Application settings

    Returns:
        Configured bot instance (not yet started)
    """
    return IBPickerBot(settings)


def run_bot(settings: Settings) -> None:
    """Create and run the Discord bot.

    Args:
        settings: Application settings including Discord config
    """
    bot = IBPickerBot(settings)
    bot.run_bot()

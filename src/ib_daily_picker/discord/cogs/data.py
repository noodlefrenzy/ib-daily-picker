"""
Data management Discord commands.

PURPOSE: Discord slash commands for data fetching and status
DEPENDENCIES: discord.py, fetchers, store

ARCHITECTURE NOTES:
- Wraps existing fetcher functionality for Discord
- Provides data coverage status
- Manages watchlist display
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ib_daily_picker.discord.embeds import (
    create_data_status_embed,
    create_error_embed,
)

if TYPE_CHECKING:
    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)


class FetchGroup(app_commands.Group):
    """Group of fetch commands."""

    def __init__(self, bot: IBPickerBot) -> None:
        super().__init__(name="fetch", description="Fetch data from external sources")
        self.bot = bot

    @app_commands.command(name="stocks", description="Fetch latest stock data")
    @app_commands.describe(
        symbols="Comma-separated list of symbols (defaults to basket)",
        days="Number of days of history to fetch (default: 30)",
    )
    async def fetch_stocks(
        self,
        interaction: discord.Interaction,
        symbols: str | None = None,
        days: int = 30,
    ) -> None:
        """Fetch stock data for specified symbols."""
        await interaction.response.defer(thinking=True)

        try:
            from datetime import timedelta

            from ib_daily_picker.fetchers.stock_fetcher import StockDataFetcher
            from ib_daily_picker.store.database import get_db_manager

            settings = self.bot.settings

            # Get symbols
            if symbols:
                ticker_list = [s.strip().upper() for s in symbols.split(",")]
            else:
                ticker_list = settings.basket.default_tickers

            # Calculate date range
            from datetime import date

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Fetch data
            db = get_db_manager()
            fetcher = StockDataFetcher(db)

            success_count = 0
            error_count = 0
            errors: list[str] = []

            for ticker in ticker_list:
                try:
                    result = await fetcher.fetch_and_store(
                        ticker,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if result.is_success:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(f"{ticker}: {', '.join(result.errors)}")
                except Exception as e:
                    error_count += 1
                    errors.append(f"{ticker}: {e}")
                    logger.warning(f"Failed to fetch {ticker}: {e}")

            # Create response embed
            if success_count > 0:
                color = discord.Color.green() if error_count == 0 else discord.Color.gold()
                embed = discord.Embed(
                    title="Stock Data Fetched",
                    description=f"Successfully fetched data for {success_count} symbol(s)",
                    color=color,
                )
                embed.add_field(name="Symbols", value=str(success_count), inline=True)
                embed.add_field(name="Days", value=str(days), inline=True)
                if error_count > 0:
                    embed.add_field(name="Errors", value=str(error_count), inline=True)
                    embed.add_field(
                        name="Failed",
                        value="\n".join(errors[:5]),
                        inline=False,
                    )
            else:
                embed = create_error_embed(
                    "No Data Fetched",
                    "Failed to fetch data for all symbols.",
                    "Check the symbol list or try again later.",
                )
                if errors:
                    embed.add_field(
                        name="Errors",
                        value="\n".join(errors[:5]),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in fetch stocks command")
            embed = create_error_embed("Fetch Failed", str(e))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="flows", description="Fetch latest flow alerts")
    @app_commands.describe(
        symbols="Comma-separated list of symbols (defaults to basket)",
    )
    async def fetch_flows(
        self,
        interaction: discord.Interaction,
        symbols: str | None = None,
    ) -> None:
        """Fetch flow alerts for specified symbols."""
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.fetchers.unusual_whales import UnusualWhalesFetcher
            from ib_daily_picker.store.database import get_db_manager
            from ib_daily_picker.store.repositories import FlowRepository

            settings = self.bot.settings

            # Check API key
            if not settings.api.unusual_whales_api_key:
                embed = create_error_embed(
                    "API Key Not Configured",
                    "Unusual Whales API key is not set.",
                    "Set IB_PICKER_UNUSUAL_WHALES_API_KEY environment variable.",
                )
                await interaction.followup.send(embed=embed)
                return

            # Get symbols
            if symbols:
                ticker_list = [s.strip().upper() for s in symbols.split(",")]
            else:
                ticker_list = settings.basket.default_tickers

            # Fetch data
            fetcher = UnusualWhalesFetcher(settings.api.unusual_whales_api_key)
            db = get_db_manager()
            repo = FlowRepository(db)

            total_alerts = 0
            error_count = 0
            errors: list[str] = []

            # Fetch flow alerts (async API)
            try:
                result = await fetcher.fetch_flow_alerts(symbols=ticker_list)
                if result.is_success and result.data:
                    repo.save_batch(list(result.data.alerts))
                    total_alerts = len(result.data.alerts)
                elif not result.is_success:
                    error_count = 1
                    errors.append(", ".join(result.errors) or "Unknown error")
            except Exception as e:
                error_count = 1
                errors.append(str(e))
                logger.warning(f"Failed to fetch flow alerts: {e}")

            # Create response embed
            if total_alerts > 0 or error_count < len(ticker_list):
                color = discord.Color.green() if error_count == 0 else discord.Color.gold()
                embed = discord.Embed(
                    title="Flow Data Fetched",
                    description=f"Fetched {total_alerts} flow alert(s)",
                    color=color,
                )
                embed.add_field(name="Symbols Checked", value=str(len(ticker_list)), inline=True)
                embed.add_field(name="Alerts Found", value=str(total_alerts), inline=True)
                if error_count > 0:
                    embed.add_field(name="Errors", value=str(error_count), inline=True)
            else:
                embed = create_error_embed(
                    "No Flow Data Fetched",
                    "Failed to fetch flow data.",
                    "Check API key and try again.",
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in fetch flows command")
            embed = create_error_embed("Fetch Failed", str(e))
            await interaction.followup.send(embed=embed)


class DataCog(commands.Cog, name="Data"):
    """Data management commands."""

    def __init__(self, bot: IBPickerBot) -> None:
        self.bot = bot
        self.fetch_group = FetchGroup(bot)
        bot.tree.add_command(self.fetch_group)

    async def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        self.bot.tree.remove_command(self.fetch_group.name)

    @app_commands.command(name="status", description="Show data coverage status")
    async def status(self, interaction: discord.Interaction) -> None:
        """Show data coverage status."""
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.store.database import get_db_manager
            from ib_daily_picker.store.repositories import FlowRepository, StockRepository

            db = get_db_manager()
            stock_repo = StockRepository(db)
            flow_repo = FlowRepository(db)

            # Get symbols we have data for
            symbols = stock_repo.get_symbols()

            # Build coverage info
            stock_coverage: dict[str, tuple[str, str]] = {}
            for symbol in symbols[:20]:  # Limit to first 20
                latest_date = stock_repo.get_latest_date(symbol)
                if latest_date:
                    # Get earliest date by querying
                    ohlcv_data = stock_repo.get_ohlcv(symbol, limit=1000)
                    if ohlcv_data:
                        earliest = min(o.trade_date for o in ohlcv_data)
                        stock_coverage[symbol] = (
                            earliest.isoformat(),
                            latest_date.isoformat(),
                        )

            # Get flow alerts (recent)
            flow_alerts = flow_repo.get_recent(limit=500)
            flow_coverage: dict[str, int] = {}
            for alert in flow_alerts:
                flow_coverage[alert.symbol] = flow_coverage.get(alert.symbol, 0) + 1

            embed = create_data_status_embed(
                stock_coverage=stock_coverage,
                flow_coverage=flow_coverage,
                last_update=None,  # We don't track this currently
            )

            # Add symbol count
            embed.add_field(
                name="Total Symbols Tracked",
                value=str(len(symbols)),
                inline=True,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in status command")
            embed = create_error_embed("Status Failed", str(e))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="watchlist", description="Show watched symbols")
    async def watchlist(self, interaction: discord.Interaction) -> None:
        """Show the current watchlist/basket."""
        settings = self.bot.settings
        tickers = settings.basket.default_tickers

        embed = discord.Embed(
            title="Watchlist",
            description=f"Currently tracking {len(tickers)} symbol(s)",
            color=discord.Color.blue(),
        )

        # Group tickers by rows for display
        chunk_size = 5
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            embed.add_field(
                name=f"Symbols {i + 1}-{min(i + chunk_size, len(tickers))}",
                value=" | ".join(f"`{t}`" for t in chunk),
                inline=False,
            )

        # Show any sector filters
        if settings.basket.include_sectors:
            embed.add_field(
                name="Include Sectors",
                value=", ".join(settings.basket.include_sectors),
                inline=True,
            )
        if settings.basket.exclude_sectors:
            embed.add_field(
                name="Exclude Sectors",
                value=", ".join(settings.basket.exclude_sectors),
                inline=True,
            )

        embed.set_footer(text="Configure with 'ib-picker config set default_tickers'")

        await interaction.response.send_message(embed=embed)


async def setup(bot: IBPickerBot) -> None:
    """Set up the cog."""
    await bot.add_cog(DataCog(bot))

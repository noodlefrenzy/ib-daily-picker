"""
Analysis Discord commands.

PURPOSE: Discord slash commands for running analysis and viewing signals
DEPENDENCIES: discord.py, analysis module

ARCHITECTURE NOTES:
- Wraps existing analysis functionality for Discord
- Uses embeds for rich output formatting
- Handles async operation with deferred responses
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ib_daily_picker.discord.embeds import (
    create_error_embed,
    create_recommendation_embed,
    create_signals_list_embed,
)

if TYPE_CHECKING:
    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)


class AnalysisCog(commands.Cog, name="Analysis"):
    """Analysis commands for running strategies and viewing signals."""

    def __init__(self, bot: IBPickerBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="analyze",
        description="Run strategy analysis on stocks",
    )
    @app_commands.describe(
        strategy="Strategy name to use (from strategies folder)",
        symbols="Comma-separated list of symbols (e.g., AAPL,MSFT,GOOGL)",
    )
    async def analyze(
        self,
        interaction: discord.Interaction,
        strategy: str,
        symbols: str | None = None,
    ) -> None:
        """Run analysis using a specified strategy.

        Args:
            interaction: Discord interaction
            strategy: Strategy name
            symbols: Optional comma-separated symbols (defaults to basket)
        """
        # Defer response since analysis may take time
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.analysis import StrategyEvaluator
            from ib_daily_picker.analysis.signals import SignalGenerator
            from ib_daily_picker.analysis.strategy_loader import get_strategy_loader
            from ib_daily_picker.models import RecommendationBatch
            from ib_daily_picker.store.database import get_db_manager
            from ib_daily_picker.store.repositories import (
                RecommendationRepository,
                StockRepository,
            )

            # Load strategy
            loader = get_strategy_loader()
            try:
                strat = loader.load(strategy)
            except FileNotFoundError:
                embed = create_error_embed(
                    "Strategy Not Found",
                    f"Strategy '{strategy}' was not found.",
                    "Use `/strategies` to see available strategies.",
                )
                await interaction.followup.send(embed=embed)
                return
            except Exception as e:
                embed = create_error_embed(
                    "Strategy Load Failed",
                    str(e),
                )
                await interaction.followup.send(embed=embed)
                return

            # Get symbols
            settings = self.bot.settings
            if symbols:
                ticker_list = [s.strip().upper() for s in symbols.split(",")]
            else:
                ticker_list = settings.basket.default_tickers[:10]

            # Initialize components
            db = get_db_manager()
            stock_repo = StockRepository(db)
            rec_repo = RecommendationRepository(db)

            evaluator = StrategyEvaluator(strat)
            generator = SignalGenerator(strat)

            # Run analysis
            results = []
            errors = []
            for ticker in ticker_list:
                try:
                    ohlcv = stock_repo.get_ohlcv(ticker, limit=200)
                    if not ohlcv:
                        errors.append(f"{ticker}: No data")
                        continue
                    eval_result = evaluator.evaluate(ticker, ohlcv, flow_alerts=[])
                    if eval_result.entry_signal:
                        results.append(eval_result)
                except Exception as e:
                    errors.append(f"{ticker}: {e}")
                    logger.warning(f"Error evaluating {ticker}: {e}")

            if not results:
                embed = discord.Embed(
                    title="Analysis Complete",
                    description=f"No signals triggered for {len(ticker_list)} symbols.",
                    color=discord.Color.gold(),
                )
                embed.add_field(
                    name="Analyzed",
                    value=", ".join(ticker_list),
                    inline=False,
                )
                if errors:
                    embed.add_field(
                        name="Errors",
                        value="\n".join(errors[:5]),
                        inline=False,
                    )
                embed.set_footer(text=f"Strategy: {strat.name}")
                await interaction.followup.send(embed=embed)
                return

            # Generate recommendations from evaluation results
            recommendations = []
            for eval_result in results:
                rec = generator.generate(
                    symbol=eval_result.symbol,
                    ohlcv_data=stock_repo.get_ohlcv(eval_result.symbol, limit=200) or [],
                    flow_alerts=[],
                )
                if rec:
                    recommendations.append(rec)
                    rec_repo.save(rec)

            signal_result = RecommendationBatch(
                recommendations=recommendations,
                strategy_name=strat.name,
            )

            # Create response embed
            embed = create_signals_list_embed(
                signal_result,
                title=f"Analysis Results - {strat.name}",
            )
            embed.add_field(
                name="Symbols Analyzed",
                value=str(len(ticker_list)),
                inline=True,
            )
            if errors:
                embed.add_field(
                    name="Errors",
                    value=str(len(errors)),
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error in analyze command")
            embed = create_error_embed(
                "Analysis Failed",
                str(e),
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="signals",
        description="Show pending trade recommendations",
    )
    @app_commands.describe(
        limit="Maximum number of signals to show (default: 10)",
        strategy="Filter by strategy name",
    )
    async def signals(
        self,
        interaction: discord.Interaction,
        limit: int = 10,
        strategy: str | None = None,
    ) -> None:
        """Show pending recommendations.

        Args:
            interaction: Discord interaction
            limit: Max signals to display
            strategy: Optional strategy filter
        """
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.models import RecommendationBatch
            from ib_daily_picker.store.database import get_db_manager
            from ib_daily_picker.store.repositories import RecommendationRepository

            db = get_db_manager()
            rec_repo = RecommendationRepository(db)

            # Get pending recommendations
            all_recs = rec_repo.get_pending(limit=limit * 2)  # Get extra to filter

            # Filter by strategy if specified
            if strategy:
                all_recs = [r for r in all_recs if r.strategy_name == strategy]

            # Filter actionable and limit
            recs = [r for r in all_recs if r.is_actionable][:limit]

            if not recs:
                embed = discord.Embed(
                    title="No Pending Signals",
                    description="There are no actionable signals at this time.",
                    color=discord.Color.gold(),
                )
                if strategy:
                    embed.add_field(
                        name="Filter",
                        value=f"Strategy: {strategy}",
                        inline=False,
                    )
                embed.set_footer(text="Run /analyze to generate new signals")
                await interaction.followup.send(embed=embed)
                return

            # Create batch for display
            batch = RecommendationBatch(
                recommendations=recs,
                strategy_name=strategy,
            )

            embed = create_signals_list_embed(batch, title="Pending Signals")
            await interaction.followup.send(embed=embed)

            # If only a few signals, also show detailed embeds
            if len(recs) <= 3:
                for rec in recs:
                    detail_embed = create_recommendation_embed(rec)
                    await interaction.followup.send(embed=detail_embed)

        except Exception as e:
            logger.exception("Error in signals command")
            embed = create_error_embed(
                "Failed to Load Signals",
                str(e),
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="strategies",
        description="List available trading strategies",
    )
    async def strategies(self, interaction: discord.Interaction) -> None:
        """List all available strategies."""
        await interaction.response.defer(thinking=True)

        try:
            from ib_daily_picker.analysis.strategy_loader import get_strategy_loader

            loader = get_strategy_loader()
            strategies_list = loader.list_strategies()

            if not strategies_list:
                embed = discord.Embed(
                    title="No Strategies Found",
                    description="No strategy files found in the strategies directory.",
                    color=discord.Color.gold(),
                )
                embed.add_field(
                    name="Directory",
                    value=str(loader.strategies_dir),
                    inline=False,
                )
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(
                title="Available Strategies",
                description=f"Found {len(strategies_list)} strategy(ies)",
                color=discord.Color.blue(),
            )

            for strat in strategies_list:
                name = strat["name"]
                version = strat["version"]
                desc = strat.get("description", "No description")[:100]
                embed.add_field(
                    name=f"{name} (v{version})",
                    value=desc if desc else "No description",
                    inline=False,
                )

            embed.set_footer(text="Use /analyze strategy:<name> to run analysis")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error listing strategies")
            embed = create_error_embed(
                "Failed to List Strategies",
                str(e),
            )
            await interaction.followup.send(embed=embed)


async def setup(bot: IBPickerBot) -> None:
    """Set up the cog."""
    await bot.add_cog(AnalysisCog(bot))

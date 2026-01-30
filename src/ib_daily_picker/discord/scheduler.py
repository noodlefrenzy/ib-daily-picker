"""
Discord bot scheduled tasks.

PURPOSE: Daily analysis automation using discord.ext.tasks
DEPENDENCIES: discord.py

ARCHITECTURE NOTES:
- Uses discord.ext.tasks for reliable scheduling
- Runs at configured time (default 09:30 ET)
- Posts analysis results to configured channel
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from discord.ext import tasks

if TYPE_CHECKING:
    import discord

    from ib_daily_picker.discord.bot import IBPickerBot

logger = logging.getLogger(__name__)

# Eastern Time zone for market hours
ET = ZoneInfo("America/New_York")


def parse_time_str(time_str: str) -> time:
    """Parse a time string like '09:30' to a time object.

    Args:
        time_str: Time in HH:MM format

    Returns:
        time object
    """
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM")

    hour = int(parts[0])
    minute = int(parts[1])

    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        raise ValueError(f"Invalid time: {time_str}")

    return time(hour=hour, minute=minute, tzinfo=ET)


class DailyAnalysisScheduler:
    """Manages scheduled daily analysis tasks."""

    def __init__(self, bot: IBPickerBot) -> None:
        """Initialize scheduler.

        Args:
            bot: The Discord bot instance
        """
        from collections.abc import Callable, Coroutine
        from typing import Any

        self._bot = bot
        self._task: tasks.Loop[Callable[[], Coroutine[Any, Any, None]]] | None = None
        self._last_run: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Check if the daily task is running."""
        return self._task is not None and self._task.is_running()

    @property
    def next_iteration(self) -> datetime | None:
        """Get the next scheduled run time."""
        if self._task is None:
            return None
        return self._task.next_iteration

    def start(self) -> None:
        """Start the daily analysis task."""
        settings = self._bot.settings.discord

        if not settings.daily_enabled:
            logger.info("Daily analysis is disabled")
            return

        if not settings.daily_channel_id:
            logger.warning("Daily analysis channel not configured, skipping scheduler")
            return

        # Parse configured time
        try:
            run_time = parse_time_str(settings.daily_time)
        except ValueError as e:
            logger.error(f"Invalid daily_time configuration: {e}")
            return

        # Create the task
        @tasks.loop(time=run_time)
        async def daily_analysis() -> None:
            """Run daily analysis at the scheduled time."""
            await self._run_daily_analysis()

        @daily_analysis.before_loop
        async def before_daily_analysis() -> None:
            """Wait until bot is ready."""
            await self._bot.wait_until_ready()

        self._task = daily_analysis
        self._task.start()
        logger.info(f"Started daily analysis scheduler at {settings.daily_time} ET")

    def stop(self) -> None:
        """Stop the daily analysis task."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("Stopped daily analysis scheduler")

    async def run_now(self) -> bool:
        """Run analysis immediately (manual trigger).

        Returns:
            True if analysis was run successfully
        """
        try:
            await self._run_daily_analysis()
            return True
        except Exception:
            logger.exception("Error running manual analysis")
            return False

    async def _run_daily_analysis(self) -> None:
        """Execute the daily analysis workflow."""
        settings = self._bot.settings.discord

        if not settings.daily_channel_id:
            logger.error("Daily channel ID not configured")
            return

        # Get the channel
        channel = self._bot.get_channel(settings.daily_channel_id)
        if channel is None:
            logger.error(f"Daily channel {settings.daily_channel_id} not found")
            return

        if not hasattr(channel, "send"):
            logger.error(f"Channel {settings.daily_channel_id} is not a text channel")
            return

        text_channel: discord.TextChannel = channel  # type: ignore[assignment]

        logger.info(f"Running daily analysis for channel {text_channel.name}")

        try:
            # Import here to avoid circular imports
            from ib_daily_picker.analysis import StrategyEvaluator
            from ib_daily_picker.analysis.signals import SignalGenerator
            from ib_daily_picker.analysis.strategy_loader import get_strategy_loader
            from ib_daily_picker.discord.embeds import (
                create_error_embed,
                create_signals_list_embed,
            )
            from ib_daily_picker.models import RecommendationBatch
            from ib_daily_picker.store.database import get_db_manager
            from ib_daily_picker.store.repositories import (
                RecommendationRepository,
                StockRepository,
            )

            # Load strategy
            loader = get_strategy_loader()
            try:
                strategy = loader.load(settings.daily_strategy)
            except FileNotFoundError:
                embed = create_error_embed(
                    "Strategy Not Found",
                    f"Daily strategy '{settings.daily_strategy}' not found.",
                )
                await text_channel.send(embed=embed)
                return

            # Get basket symbols
            basket = self._bot.settings.basket.default_tickers

            # Initialize components
            db = get_db_manager()
            stock_repo = StockRepository(db)
            rec_repo = RecommendationRepository(db)
            evaluator = StrategyEvaluator(strategy)
            generator = SignalGenerator(strategy)

            # Run analysis
            results = []
            for ticker in basket:
                try:
                    ohlcv = stock_repo.get_ohlcv(ticker, limit=200)
                    if not ohlcv:
                        continue
                    eval_result = evaluator.evaluate(ticker, ohlcv, flow_alerts=[])
                    if eval_result.entry_signal:
                        results.append(eval_result)
                except Exception as e:
                    logger.warning(f"Error evaluating {ticker}: {e}")

            # Generate recommendations
            recommendations = []
            for eval_result in results:
                ohlcv = stock_repo.get_ohlcv(eval_result.symbol, limit=200)
                rec = generator.generate(
                    symbol=eval_result.symbol,
                    ohlcv_data=ohlcv or [],
                    flow_alerts=[],
                )
                if rec:
                    recommendations.append(rec)
                    rec_repo.save(rec)

            # Create and send embed
            batch = RecommendationBatch(
                recommendations=recommendations,
                strategy_name=strategy.name,
                generated_at=datetime.now(UTC),
            )

            embed = create_signals_list_embed(
                batch,
                title=f"Daily Analysis - {datetime.now(ET).strftime('%Y-%m-%d')}",
            )
            embed.add_field(
                name="Strategy",
                value=strategy.name,
                inline=True,
            )
            embed.add_field(
                name="Symbols Analyzed",
                value=str(len(basket)),
                inline=True,
            )

            await text_channel.send(embed=embed)

            self._last_run = datetime.now(UTC)
            logger.info(f"Daily analysis complete: {len(recommendations)} signals")

        except Exception as e:
            logger.exception("Error in daily analysis")
            try:
                embed = create_error_embed("Daily Analysis Failed", str(e))
                await text_channel.send(embed=embed)
            except Exception:
                logger.exception("Failed to send error message")

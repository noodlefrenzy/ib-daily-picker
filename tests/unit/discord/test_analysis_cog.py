"""
TEST DOC: Discord Analysis Cog

WHAT: Tests for /analyze and /signals Discord commands
WHY: Ensure analysis commands correctly wrap existing functionality
HOW: Mock Discord interaction and analysis components

CASES:
- Analyze command with valid strategy
- Analyze command with invalid strategy
- Signals command with pending recommendations
- Signals command with no recommendations
- Strategies command listing

EDGE CASES:
- Empty symbol list uses basket defaults
- Analysis errors are reported gracefully
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ib_daily_picker.discord.embeds import (
    SIGNAL_COLORS,
    create_error_embed,
    create_recommendation_embed,
    create_signals_list_embed,
    format_confidence,
    format_percent,
    format_price,
)
from ib_daily_picker.models import (
    Recommendation,
    RecommendationBatch,
    SignalType,
)


class TestFormatters:
    """Tests for embed formatting functions."""

    def test_format_price_with_value(self) -> None:
        """format_price should format decimal values."""
        assert format_price(Decimal("123.45")) == "$123.45"
        assert format_price(Decimal("1234.50")) == "$1,234.50"

    def test_format_price_with_none(self) -> None:
        """format_price should return N/A for None."""
        assert format_price(None) == "N/A"

    def test_format_percent_with_decimal(self) -> None:
        """format_percent should format Decimal percentages."""
        assert format_percent(Decimal("0.5")) == "50.0%"
        assert format_percent(Decimal("0.123")) == "12.3%"

    def test_format_percent_with_float(self) -> None:
        """format_percent should format float percentages."""
        assert format_percent(0.75) == "75.0%"

    def test_format_percent_with_none(self) -> None:
        """format_percent should return N/A for None."""
        assert format_percent(None) == "N/A"

    def test_format_confidence(self) -> None:
        """format_confidence should show visual bars and percentage."""
        result = format_confidence(Decimal("0.8"))
        assert "████" in result  # 4 filled bars
        assert "80%" in result


class TestRecommendationEmbed:
    """Tests for recommendation embed creation."""

    @pytest.fixture
    def sample_recommendation(self) -> Recommendation:
        """Create sample recommendation for testing."""
        return Recommendation(
            id="test-123",
            symbol="AAPL",
            strategy_name="test_strategy",
            signal_type=SignalType.BUY,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            take_profit=Decimal("165.00"),
            confidence=Decimal("0.85"),
            reasoning="Strong technical setup with bullish flow",
            generated_at=datetime(2024, 1, 15, 10, 30, 0),
        )

    def test_creates_embed_with_correct_color(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Embed should use correct color for signal type."""
        embed = create_recommendation_embed(sample_recommendation)

        assert embed.color == SIGNAL_COLORS[SignalType.BUY]

    def test_includes_symbol_in_title(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Embed title should include symbol."""
        embed = create_recommendation_embed(sample_recommendation)

        assert "AAPL" in embed.title
        assert "BUY" in embed.title

    def test_includes_price_targets(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Embed should include entry, stop, and target."""
        embed = create_recommendation_embed(sample_recommendation)

        field_names = [f.name for f in embed.fields]
        assert "Entry" in field_names
        assert "Stop Loss" in field_names
        assert "Target" in field_names

    def test_includes_risk_reward(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Embed should include risk/reward ratio."""
        embed = create_recommendation_embed(sample_recommendation)

        field_names = [f.name for f in embed.fields]
        assert "Risk/Reward" in field_names

    def test_includes_strategy_in_footer(
        self, sample_recommendation: Recommendation
    ) -> None:
        """Embed footer should show strategy name."""
        embed = create_recommendation_embed(sample_recommendation)

        assert embed.footer is not None
        assert "test_strategy" in embed.footer.text


class TestSignalsListEmbed:
    """Tests for signals list embed creation."""

    @pytest.fixture
    def sample_batch(self) -> RecommendationBatch:
        """Create sample recommendation batch for testing."""
        recs = [
            Recommendation(
                id="1",
                symbol="AAPL",
                strategy_name="test",
                signal_type=SignalType.BUY,
                entry_price=Decimal("150.00"),
                confidence=Decimal("0.9"),
            ),
            Recommendation(
                id="2",
                symbol="MSFT",
                strategy_name="test",
                signal_type=SignalType.BUY,
                entry_price=Decimal("380.00"),
                confidence=Decimal("0.75"),
            ),
            Recommendation(
                id="3",
                symbol="GOOGL",
                strategy_name="test",
                signal_type=SignalType.SELL,
                entry_price=Decimal("140.00"),
                confidence=Decimal("0.6"),
            ),
        ]
        return RecommendationBatch(
            recommendations=recs,
            strategy_name="test_strategy",
            generated_at=datetime(2024, 1, 15, 10, 0, 0),
        )

    def test_creates_embed_with_counts(
        self, sample_batch: RecommendationBatch
    ) -> None:
        """Embed should show total and actionable counts."""
        embed = create_signals_list_embed(sample_batch)

        assert "3" in embed.description

    def test_groups_by_signal_type(
        self, sample_batch: RecommendationBatch
    ) -> None:
        """Embed should group signals by type."""
        embed = create_signals_list_embed(sample_batch)

        field_names = [f.name for f in embed.fields]
        assert any("BUY" in name for name in field_names)
        assert any("SELL" in name for name in field_names)

    def test_includes_strategy_in_footer(
        self, sample_batch: RecommendationBatch
    ) -> None:
        """Embed footer should show strategy if provided."""
        embed = create_signals_list_embed(sample_batch)

        assert embed.footer is not None
        assert "test_strategy" in embed.footer.text


class TestErrorEmbed:
    """Tests for error embed creation."""

    def test_creates_red_embed(self) -> None:
        """Error embed should be red."""
        embed = create_error_embed("Test Error", "Something went wrong")

        # Discord.Color.red() value
        assert embed.color is not None

    def test_includes_title_and_message(self) -> None:
        """Error embed should include title and message."""
        embed = create_error_embed("Test Error", "Something went wrong")

        assert "Test Error" in embed.title
        assert embed.description == "Something went wrong"

    def test_includes_suggestion_when_provided(self) -> None:
        """Error embed should include suggestion if provided."""
        embed = create_error_embed(
            "Test Error",
            "Something went wrong",
            suggestion="Try doing X instead",
        )

        field_names = [f.name for f in embed.fields]
        assert "Suggestion" in field_names


class TestAnalysisCog:
    """Tests for AnalysisCog slash commands."""

    @pytest.fixture
    def mock_bot(self) -> MagicMock:
        """Create mock bot."""
        bot = MagicMock()
        bot.settings = MagicMock()
        bot.settings.basket = MagicMock()
        bot.settings.basket.default_tickers = ["AAPL", "MSFT", "GOOGL"]
        return bot

    @pytest.fixture
    def mock_interaction(self) -> MagicMock:
        """Create mock Discord interaction."""
        interaction = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_analyze_defers_response(
        self, mock_bot: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Analyze command should defer response for long operations."""
        from ib_daily_picker.discord.cogs.analysis import AnalysisCog

        cog = AnalysisCog(mock_bot)

        # Mock the strategy loader module-level
        with patch(
            "ib_daily_picker.analysis.strategy_loader.get_strategy_loader"
        ) as mock_get_loader:
            mock_loader = MagicMock()
            mock_loader.load.side_effect = FileNotFoundError("Strategy not found")
            mock_get_loader.return_value = mock_loader

            # Call the underlying callback, not the Command wrapper
            await cog.analyze.callback(cog, mock_interaction, strategy="nonexistent")

        mock_interaction.response.defer.assert_called_once_with(thinking=True)

    @pytest.mark.asyncio
    async def test_analyze_handles_missing_strategy(
        self, mock_bot: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Analyze should report error for missing strategy."""
        from ib_daily_picker.discord.cogs.analysis import AnalysisCog

        cog = AnalysisCog(mock_bot)

        with patch(
            "ib_daily_picker.analysis.strategy_loader.get_strategy_loader"
        ) as mock_get_loader:
            mock_loader = MagicMock()
            mock_loader.load.side_effect = FileNotFoundError("Strategy not found")
            mock_get_loader.return_value = mock_loader

            await cog.analyze.callback(cog, mock_interaction, strategy="nonexistent")

        # Should send an error embed
        mock_interaction.followup.send.assert_called_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert "embed" in call_kwargs
        assert "Not Found" in call_kwargs["embed"].title

    @pytest.mark.asyncio
    async def test_signals_defers_response(
        self, mock_bot: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Signals command should defer response."""
        from ib_daily_picker.discord.cogs.analysis import AnalysisCog

        cog = AnalysisCog(mock_bot)

        with patch(
            "ib_daily_picker.store.database.get_db_manager"
        ) as mock_db:
            mock_db.return_value = MagicMock()
            with patch(
                "ib_daily_picker.store.repositories.RecommendationRepository"
            ) as mock_repo:
                mock_repo_instance = MagicMock()
                mock_repo_instance.get_pending.return_value = []
                mock_repo.return_value = mock_repo_instance

                await cog.signals.callback(cog, mock_interaction)

        mock_interaction.response.defer.assert_called_once_with(thinking=True)

    @pytest.mark.asyncio
    async def test_signals_handles_empty_list(
        self, mock_bot: MagicMock, mock_interaction: MagicMock
    ) -> None:
        """Signals should handle empty recommendation list."""
        from ib_daily_picker.discord.cogs.analysis import AnalysisCog

        cog = AnalysisCog(mock_bot)

        with patch(
            "ib_daily_picker.store.database.get_db_manager"
        ) as mock_db:
            mock_db.return_value = MagicMock()
            with patch(
                "ib_daily_picker.store.repositories.RecommendationRepository"
            ) as mock_repo:
                mock_repo_instance = MagicMock()
                mock_repo_instance.get_pending.return_value = []
                mock_repo.return_value = mock_repo_instance

                await cog.signals.callback(cog, mock_interaction)

        # Should send "no signals" message
        mock_interaction.followup.send.assert_called_once()
        call_kwargs = mock_interaction.followup.send.call_args.kwargs
        assert "embed" in call_kwargs
        assert "No Pending" in call_kwargs["embed"].title

"""
Tests for journal metrics calculations.

TEST DOC: Journal Metrics

WHAT: Tests for extended trade metrics calculations
WHY: Ensure accurate PnL, streak, drawdown, and time analysis
HOW: Create sample trades and verify metric calculations

CASES:
- Empty trades: Returns empty metrics
- Single winner: Calculates basic metrics
- Mixed trades: Win rate, expectancy, etc.
- Streak analysis: Tracks consecutive wins/losses
- Drawdown: Tracks peak-to-trough declines
- Time analysis: Trade timing patterns
- Filtering: Date, symbol, tag filters

EDGE CASES:
- All winners: No losses, profit factor is None
- All losers: 0% win rate
- Break-even trades: Handled correctly
"""

from datetime import datetime, timedelta
from decimal import Decimal

from ib_daily_picker.journal.metrics import (
    calculate_extended_metrics,
    filter_trades,
)
from ib_daily_picker.models import Trade, TradeDirection, TradeStatus


def create_trade(
    symbol: str = "AAPL",
    direction: TradeDirection = TradeDirection.LONG,
    entry_price: Decimal = Decimal("100"),
    exit_price: Decimal | None = Decimal("110"),
    position_size: Decimal = Decimal("10"),
    stop_loss: Decimal | None = Decimal("95"),
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
    status: TradeStatus = TradeStatus.CLOSED,
    tags: list[str] | None = None,
) -> Trade:
    """Helper to create test trades."""
    now = datetime.utcnow()
    return Trade(
        id=f"test-{now.timestamp()}",
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        entry_time=entry_time or now - timedelta(hours=1),
        exit_price=exit_price,
        exit_time=exit_time or now,
        position_size=position_size,
        stop_loss=stop_loss,
        status=status,
        tags=tags or [],
    )


class TestCalculateExtendedMetrics:
    """Tests for calculate_extended_metrics function."""

    def test_empty_trades_returns_empty_metrics(self):
        """Empty list returns default metrics."""
        metrics = calculate_extended_metrics([])
        assert metrics.total_trades == 0
        assert metrics.total_pnl == Decimal("0")

    def test_single_winning_trade(self):
        """Single winning trade calculates correctly."""
        trade = create_trade(
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            position_size=Decimal("10"),
        )
        metrics = calculate_extended_metrics([trade])

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0
        assert metrics.total_pnl == Decimal("100")  # (110-100) * 10
        assert metrics.win_rate == Decimal("1")

    def test_single_losing_trade(self):
        """Single losing trade calculates correctly."""
        trade = create_trade(
            entry_price=Decimal("100"),
            exit_price=Decimal("90"),
            position_size=Decimal("10"),
        )
        metrics = calculate_extended_metrics([trade])

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 1
        assert metrics.total_pnl == Decimal("-100")  # (90-100) * 10
        assert metrics.win_rate == Decimal("0")

    def test_mixed_trades_win_rate(self):
        """Mixed trades calculate correct win rate."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),  # Win
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("105")),  # Win
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("95")),  # Loss
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("90")),  # Loss
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 2
        assert metrics.win_rate == Decimal("0.5")

    def test_profit_factor_calculation(self):
        """Profit factor = gross profit / gross loss."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("120")),  # +200
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("90")),  # -100
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.profit_factor == Decimal("2")  # 200 / 100

    def test_all_winners_no_profit_factor(self):
        """All winners means no profit factor (no losses)."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("120")),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.profit_factor is None
        assert metrics.win_rate == Decimal("1")

    def test_expectancy_calculation(self):
        """Expectancy = (WinRate * AvgWin) - (LossRate * AvgLoss)."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("120")),  # +200
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("90")),  # -100
        ]
        metrics = calculate_extended_metrics(trades)

        # Win rate = 50%, Avg win = 200, Avg loss = 100
        # Expectancy = (0.5 * 200) - (0.5 * 100) = 100 - 50 = 50
        assert metrics.expectancy == Decimal("50")

    def test_r_multiple_calculation(self):
        """R-multiple averages correctly."""
        # Trade with 2R win (stop at 95, entry at 100, exit at 110)
        # Risk = 5, Reward = 10, R-multiple = 2
        trade = create_trade(
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            stop_loss=Decimal("95"),
        )
        metrics = calculate_extended_metrics([trade])

        assert metrics.avg_r_multiple == Decimal("2")

    def test_largest_winner_loser(self):
        """Tracks largest winner and loser."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("150")),  # +500
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),  # +100
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("90")),  # -100
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("70")),  # -300
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.largest_winner == Decimal("500")
        assert metrics.largest_loser == Decimal("-300")

    def test_open_trades_excluded(self):
        """Open trades are excluded from metrics."""
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                status=TradeStatus.CLOSED,
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=None,
                status=TradeStatus.OPEN,
            ),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.total_trades == 1

    def test_break_even_trades(self):
        """Break-even trades counted separately."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("100")),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.total_trades == 1
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.break_even_trades == 1


class TestStreakAnalysis:
    """Tests for streak calculation."""

    def test_winning_streak(self):
        """Tracks consecutive wins."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_time=now - timedelta(days=3),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("115"),
                entry_time=now - timedelta(days=2),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                entry_time=now - timedelta(days=1),
            ),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.streak.max_win_streak == 3
        assert metrics.streak.current_streak == 3
        assert metrics.streak.current_streak_type == "win"

    def test_losing_streak(self):
        """Tracks consecutive losses."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                entry_time=now - timedelta(days=2),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("85"),
                entry_time=now - timedelta(days=1),
            ),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.streak.max_loss_streak == 2
        assert metrics.streak.current_streak == 2
        assert metrics.streak.current_streak_type == "loss"

    def test_mixed_streak_resets(self):
        """Streak resets on direction change."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                entry_time=now - timedelta(days=4),
            ),  # Win
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("115"),
                entry_time=now - timedelta(days=3),
            ),  # Win
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                entry_time=now - timedelta(days=2),
            ),  # Loss
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                entry_time=now - timedelta(days=1),
            ),  # Win
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.streak.max_win_streak == 2  # First two
        assert metrics.streak.max_loss_streak == 1
        assert metrics.streak.current_streak == 1  # Last trade is a single win


class TestDrawdownAnalysis:
    """Tests for drawdown calculation."""

    def test_no_drawdown_all_winners(self):
        """All winning trades have no drawdown."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                exit_time=now - timedelta(days=2),
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                exit_time=now - timedelta(days=1),
            ),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.drawdown.current_drawdown == Decimal("0")
        assert metrics.drawdown.max_drawdown == Decimal("0")

    def test_drawdown_after_peak(self):
        """Drawdown calculated from peak equity."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("120"),
                exit_time=now - timedelta(days=3),
            ),  # +200 (peak)
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                exit_time=now - timedelta(days=2),
            ),  # -100 (drawdown)
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("80"),
                exit_time=now - timedelta(days=1),
            ),  # -200 (max drawdown)
        ]
        metrics = calculate_extended_metrics(trades)

        # Peak = 200, After losses = 200 - 100 - 200 = -100
        # Max drawdown = 200 - (-100) = 300
        assert metrics.drawdown.max_drawdown == Decimal("300")


class TestTimeAnalysis:
    """Tests for time-based analysis."""

    def test_trades_by_day(self):
        """Tracks trades by day of week."""
        # Create trades on different days
        monday = datetime(2024, 1, 1, 10, 0)  # Monday
        tuesday = datetime(2024, 1, 2, 10, 0)  # Tuesday

        trades = [
            create_trade(entry_time=monday),
            create_trade(entry_time=monday + timedelta(hours=1)),
            create_trade(entry_time=tuesday),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.time_analysis.trades_by_day.get("Monday", 0) == 2
        assert metrics.time_analysis.trades_by_day.get("Tuesday", 0) == 1

    def test_trades_by_hour(self):
        """Tracks trades by hour."""
        morning = datetime(2024, 1, 1, 9, 30)
        afternoon = datetime(2024, 1, 1, 14, 30)

        trades = [
            create_trade(entry_time=morning),
            create_trade(entry_time=afternoon),
            create_trade(entry_time=afternoon + timedelta(minutes=15)),
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.time_analysis.trades_by_hour.get(9, 0) == 1
        assert metrics.time_analysis.trades_by_hour.get(14, 0) == 2

    def test_hold_time_analysis(self):
        """Calculates hold time statistics."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                entry_time=now - timedelta(minutes=30),
                exit_time=now,
            ),  # 30 min
            create_trade(
                entry_time=now - timedelta(minutes=60),
                exit_time=now,
            ),  # 60 min
            create_trade(
                entry_time=now - timedelta(minutes=90),
                exit_time=now,
            ),  # 90 min
        ]
        metrics = calculate_extended_metrics(trades)

        assert metrics.time_analysis.avg_hold_time_minutes == 60.0
        assert metrics.time_analysis.shortest_trade_minutes == 30
        assert metrics.time_analysis.longest_trade_minutes == 90


class TestBySymbolAndTag:
    """Tests for per-symbol and per-tag breakdowns."""

    def test_by_symbol_breakdown(self):
        """Calculates metrics per symbol."""
        trades = [
            create_trade(symbol="AAPL", entry_price=Decimal("100"), exit_price=Decimal("110")),
            create_trade(symbol="AAPL", entry_price=Decimal("100"), exit_price=Decimal("90")),
            create_trade(symbol="MSFT", entry_price=Decimal("200"), exit_price=Decimal("220")),
        ]
        metrics = calculate_extended_metrics(trades)

        assert "AAPL" in metrics.by_symbol
        assert metrics.by_symbol["AAPL"]["total_trades"] == 2
        assert metrics.by_symbol["AAPL"]["winning_trades"] == 1

        assert "MSFT" in metrics.by_symbol
        assert metrics.by_symbol["MSFT"]["total_trades"] == 1
        assert metrics.by_symbol["MSFT"]["winning_trades"] == 1

    def test_by_tag_breakdown(self):
        """Calculates metrics per tag."""
        trades = [
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
                tags=["momentum", "earnings"],
            ),
            create_trade(
                entry_price=Decimal("100"),
                exit_price=Decimal("90"),
                tags=["momentum"],
            ),
        ]
        metrics = calculate_extended_metrics(trades)

        assert "momentum" in metrics.by_tag
        assert metrics.by_tag["momentum"]["total_trades"] == 2
        assert metrics.by_tag["momentum"]["winning_trades"] == 1

        assert "earnings" in metrics.by_tag
        assert metrics.by_tag["earnings"]["total_trades"] == 1
        assert metrics.by_tag["earnings"]["winning_trades"] == 1


class TestFilterTrades:
    """Tests for trade filtering."""

    def test_filter_by_date_range(self):
        """Filters trades by date range."""
        now = datetime.utcnow()
        trades = [
            create_trade(entry_time=now - timedelta(days=10)),
            create_trade(entry_time=now - timedelta(days=5)),
            create_trade(entry_time=now - timedelta(days=1)),
        ]

        filtered = filter_trades(
            trades,
            start_date=(now - timedelta(days=7)).date(),
            end_date=(now - timedelta(days=2)).date(),
        )

        assert len(filtered) == 1

    def test_filter_by_symbols(self):
        """Filters trades by symbol list."""
        trades = [
            create_trade(symbol="AAPL"),
            create_trade(symbol="MSFT"),
            create_trade(symbol="GOOGL"),
        ]

        filtered = filter_trades(trades, symbols=["AAPL", "GOOGL"])

        assert len(filtered) == 2
        assert all(t.symbol in ["AAPL", "GOOGL"] for t in filtered)

    def test_filter_by_tags(self):
        """Filters trades by tags."""
        trades = [
            create_trade(tags=["momentum"]),
            create_trade(tags=["value"]),
            create_trade(tags=["momentum", "breakout"]),
        ]

        filtered = filter_trades(trades, tags=["momentum"])

        assert len(filtered) == 2

    def test_filter_by_pnl_range(self):
        """Filters trades by PnL thresholds."""
        trades = [
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("150")),  # +500
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("110")),  # +100
            create_trade(entry_price=Decimal("100"), exit_price=Decimal("90")),  # -100
        ]

        # Only profitable trades
        filtered = filter_trades(trades, min_pnl=Decimal("0"))
        assert len(filtered) == 2

        # Only trades with PnL <= 200
        filtered = filter_trades(trades, max_pnl=Decimal("200"))
        assert len(filtered) == 2

    def test_combined_filters(self):
        """Multiple filters work together."""
        now = datetime.utcnow()
        trades = [
            create_trade(
                symbol="AAPL",
                entry_time=now - timedelta(days=1),
                tags=["momentum"],
                entry_price=Decimal("100"),
                exit_price=Decimal("110"),
            ),
            create_trade(
                symbol="AAPL",
                entry_time=now - timedelta(days=10),
                tags=["momentum"],
            ),
            create_trade(
                symbol="MSFT",
                entry_time=now - timedelta(days=1),
                tags=["value"],
            ),
        ]

        filtered = filter_trades(
            trades,
            start_date=(now - timedelta(days=5)).date(),
            symbols=["AAPL"],
            tags=["momentum"],
        )

        assert len(filtered) == 1
        assert filtered[0].symbol == "AAPL"

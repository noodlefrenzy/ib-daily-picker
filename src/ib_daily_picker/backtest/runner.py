"""
Backtest runner for historical strategy evaluation.

PURPOSE: Replay historical data to evaluate strategy performance
DEPENDENCIES: analysis.evaluator, analysis.signals, store.repositories

ARCHITECTURE NOTES:
- Simulates strategy execution on historical data
- Tracks position state and PnL
- Supports walk-forward validation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence
from uuid import uuid4

from ib_daily_picker.analysis.evaluator import StrategyEvaluator
from ib_daily_picker.backtest.metrics import BacktestMetrics, calculate_backtest_metrics
from ib_daily_picker.models import OHLCV, FlowAlert, Trade, TradeDirection, TradeStatus

if TYPE_CHECKING:
    from ib_daily_picker.analysis.strategy_schema import Strategy
    from ib_daily_picker.store.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""

    start_date: date
    end_date: date
    initial_capital: Decimal = Decimal("100000")
    position_size_pct: Decimal = Decimal("0.10")  # 10% per position
    max_positions: int = 5
    commission_per_trade: Decimal = Decimal("0")  # Per-trade commission
    slippage_pct: Decimal = Decimal("0.001")  # 0.1% slippage
    use_stop_loss: bool = True
    use_take_profit: bool = True


@dataclass
class BacktestPosition:
    """Represents an open position during backtest."""

    trade_id: str
    symbol: str
    direction: TradeDirection
    entry_price: Decimal
    entry_date: date
    position_size: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    strategy_name: str
    config: BacktestConfig
    trades: list[Trade] = field(default_factory=list)
    metrics: BacktestMetrics | None = None
    signals_generated: int = 0
    signals_executed: int = 0
    signals_skipped: int = 0


class BacktestRunner:
    """Runs backtests on historical data."""

    def __init__(self, db: "DatabaseManager") -> None:
        """Initialize with database manager.

        Args:
            db: Database manager for accessing historical data
        """
        self._db = db
        self._stock_repo = None
        self._flow_repo = None

    @property
    def stock_repo(self):
        """Lazy-load stock repository."""
        if self._stock_repo is None:
            from ib_daily_picker.store.repositories import StockRepository

            self._stock_repo = StockRepository(self._db)
        return self._stock_repo

    @property
    def flow_repo(self):
        """Lazy-load flow repository."""
        if self._flow_repo is None:
            from ib_daily_picker.store.repositories import FlowRepository

            self._flow_repo = FlowRepository(self._db)
        return self._flow_repo

    def run(
        self,
        strategy: "Strategy",
        symbols: list[str],
        config: BacktestConfig,
    ) -> BacktestResult:
        """Run backtest for a strategy on given symbols.

        Args:
            strategy: Strategy to backtest
            symbols: List of symbols to trade
            config: Backtest configuration

        Returns:
            BacktestResult with trades and metrics
        """
        logger.info(
            f"Starting backtest for {strategy.name} on {len(symbols)} symbols "
            f"from {config.start_date} to {config.end_date}"
        )

        result = BacktestResult(
            strategy_name=strategy.name,
            config=config,
        )

        evaluator = StrategyEvaluator(strategy)

        # Track positions and capital
        open_positions: dict[str, BacktestPosition] = {}
        capital = config.initial_capital
        closed_trades: list[Trade] = []

        # Get date range
        current_date = config.start_date
        trading_days = 0

        while current_date <= config.end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            trading_days += 1

            # Process each symbol
            for symbol in symbols:
                # Check for exit signals on open positions
                if symbol in open_positions:
                    position = open_positions[symbol]
                    trade = self._check_exit(
                        position=position,
                        current_date=current_date,
                        config=config,
                    )
                    if trade:
                        closed_trades.append(trade)
                        capital += trade.pnl if trade.pnl else Decimal("0")
                        del open_positions[symbol]

                # Skip if max positions reached
                if len(open_positions) >= config.max_positions:
                    continue

                # Skip if already in position
                if symbol in open_positions:
                    continue

                # Get historical data for evaluation
                ohlcv_data = self._get_ohlcv_for_date(symbol, current_date)
                if not ohlcv_data or len(ohlcv_data) < 20:  # Need enough history
                    continue

                # Get flow alerts
                flow_alerts = self._get_flow_for_date(symbol, current_date)

                # Evaluate strategy
                evaluation = evaluator.evaluate(
                    symbol=symbol,
                    ohlcv_data=ohlcv_data,
                    flow_alerts=flow_alerts,
                    evaluation_time=datetime.combine(current_date, datetime.min.time()),
                )

                result.signals_generated += 1

                # Check for entry signal
                if evaluation.entry_signal and evaluation.current_price:
                    # Calculate position size
                    position_value = capital * config.position_size_pct
                    shares = position_value / evaluation.current_price

                    # Apply slippage
                    entry_price = evaluation.current_price * (Decimal("1") + config.slippage_pct)

                    # Create position
                    position = BacktestPosition(
                        trade_id=str(uuid4()),
                        symbol=symbol,
                        direction=TradeDirection.LONG,  # Currently only long
                        entry_price=entry_price,
                        entry_date=current_date,
                        position_size=shares,
                        stop_loss=evaluation.suggested_stop_loss if config.use_stop_loss else None,
                        take_profit=evaluation.suggested_take_profit
                        if config.use_take_profit
                        else None,
                        mfe=entry_price,
                        mae=entry_price,
                    )

                    # Deduct commission
                    capital -= config.commission_per_trade

                    open_positions[symbol] = position
                    result.signals_executed += 1

                    logger.debug(
                        f"{current_date}: Entered {symbol} @ ${entry_price:.2f} "
                        f"(size: {shares:.0f})"
                    )
                else:
                    result.signals_skipped += 1

            current_date += timedelta(days=1)

        # Close any remaining positions at end of backtest
        for symbol, position in open_positions.items():
            # Get last available price
            ohlcv = self._get_ohlcv_for_date(symbol, config.end_date)
            if ohlcv:
                exit_price = ohlcv[0].close_price  # Most recent
                trade = self._close_position(
                    position=position,
                    exit_price=exit_price,
                    exit_date=config.end_date,
                    config=config,
                )
                closed_trades.append(trade)

        result.trades = closed_trades

        # Calculate metrics
        result.metrics = calculate_backtest_metrics(
            trades=closed_trades,
            initial_capital=config.initial_capital,
            start_date=config.start_date,
            end_date=config.end_date,
            strategy_name=strategy.name,
        )

        logger.info(
            f"Backtest complete: {len(closed_trades)} trades, "
            f"PnL: ${result.metrics.total_pnl:,.2f}, "
            f"Win Rate: {float(result.metrics.win_rate) * 100:.1f}%"
        )

        return result

    def _get_ohlcv_for_date(
        self,
        symbol: str,
        as_of_date: date,
        lookback_days: int = 100,
    ) -> list[OHLCV]:
        """Get OHLCV data up to (and including) a specific date.

        Returns data sorted with most recent first.
        """
        start = as_of_date - timedelta(days=lookback_days)
        data = self.stock_repo.get_ohlcv(
            symbol=symbol,
            start_date=start,
            end_date=as_of_date,
        )
        return sorted(data, key=lambda x: x.trade_date, reverse=True)

    def _get_flow_for_date(
        self,
        symbol: str,
        on_date: date,
    ) -> list[FlowAlert]:
        """Get flow alerts for a specific date."""
        start_time = datetime.combine(on_date, datetime.min.time())
        end_time = datetime.combine(on_date, datetime.max.time())
        return self.flow_repo.get_by_symbol(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
        )

    def _check_exit(
        self,
        position: BacktestPosition,
        current_date: date,
        config: BacktestConfig,
    ) -> Trade | None:
        """Check if position should be exited.

        Returns Trade if exited, None if still open.
        """
        # Get current price
        ohlcv = self._get_ohlcv_for_date(position.symbol, current_date)
        if not ohlcv:
            return None

        today_ohlcv = None
        for bar in ohlcv:
            if bar.trade_date == current_date:
                today_ohlcv = bar
                break

        if not today_ohlcv:
            return None

        # Update MFE/MAE
        high = today_ohlcv.high_price
        low = today_ohlcv.low_price
        close = today_ohlcv.close_price

        if position.direction == TradeDirection.LONG:
            if position.mfe is None or high > position.mfe:
                position.mfe = high
            if position.mae is None or low < position.mae:
                position.mae = low
        else:
            if position.mfe is None or low < position.mfe:
                position.mfe = low
            if position.mae is None or high > position.mae:
                position.mae = high

        exit_price: Decimal | None = None
        exit_reason = ""

        # Check stop loss
        if position.stop_loss and config.use_stop_loss:
            if position.direction == TradeDirection.LONG:
                if low <= position.stop_loss:
                    exit_price = position.stop_loss
                    exit_reason = "Stop loss"
            else:
                if high >= position.stop_loss:
                    exit_price = position.stop_loss
                    exit_reason = "Stop loss"

        # Check take profit
        if exit_price is None and position.take_profit and config.use_take_profit:
            if position.direction == TradeDirection.LONG:
                if high >= position.take_profit:
                    exit_price = position.take_profit
                    exit_reason = "Take profit"
            else:
                if low <= position.take_profit:
                    exit_price = position.take_profit
                    exit_reason = "Take profit"

        if exit_price:
            return self._close_position(
                position=position,
                exit_price=exit_price,
                exit_date=current_date,
                config=config,
                notes=exit_reason,
            )

        return None

    def _close_position(
        self,
        position: BacktestPosition,
        exit_price: Decimal,
        exit_date: date,
        config: BacktestConfig,
        notes: str = "",
    ) -> Trade:
        """Close a position and return completed Trade."""
        # Apply slippage
        if position.direction == TradeDirection.LONG:
            actual_exit = exit_price * (Decimal("1") - config.slippage_pct)
        else:
            actual_exit = exit_price * (Decimal("1") + config.slippage_pct)

        # Calculate PnL
        if position.direction == TradeDirection.LONG:
            pnl_per_share = actual_exit - position.entry_price
        else:
            pnl_per_share = position.entry_price - actual_exit

        pnl = pnl_per_share * position.position_size - config.commission_per_trade

        # Calculate R-multiple
        r_multiple: Decimal | None = None
        if position.stop_loss:
            risk_per_share = abs(position.entry_price - position.stop_loss)
            if risk_per_share > 0:
                r_multiple = pnl_per_share / risk_per_share

        trade = Trade(
            id=position.trade_id,
            symbol=position.symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            entry_time=datetime.combine(position.entry_date, datetime.min.time()),
            exit_price=actual_exit,
            exit_time=datetime.combine(exit_date, datetime.min.time()),
            position_size=position.position_size,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            pnl=pnl,
            pnl_percent=(pnl_per_share / position.entry_price) * 100,
            r_multiple=r_multiple,
            mfe=position.mfe,
            mae=position.mae,
            notes=notes,
            status=TradeStatus.CLOSED,
        )

        logger.debug(
            f"{exit_date}: Exited {position.symbol} @ ${actual_exit:.2f} (PnL: ${pnl:.2f}, {notes})"
        )

        return trade


def run_walk_forward(
    strategy: "Strategy",
    symbols: list[str],
    db: "DatabaseManager",
    start_date: date,
    end_date: date,
    in_sample_days: int = 252,  # ~1 year
    out_sample_days: int = 63,  # ~3 months
    initial_capital: Decimal = Decimal("100000"),
) -> list[BacktestResult]:
    """Run walk-forward analysis.

    Splits data into rolling in-sample/out-sample periods.

    Args:
        strategy: Strategy to test
        symbols: Symbols to trade
        db: Database manager
        start_date: Start of analysis period
        end_date: End of analysis period
        in_sample_days: Training period days
        out_sample_days: Testing period days
        initial_capital: Starting capital

    Returns:
        List of BacktestResult for each out-of-sample period
    """
    results: list[BacktestResult] = []
    runner = BacktestRunner(db)

    current_start = start_date
    window = 0

    while current_start + timedelta(days=in_sample_days + out_sample_days) <= end_date:
        window += 1

        # In-sample period (for optimization, not currently used)
        in_sample_start = current_start
        in_sample_end = in_sample_start + timedelta(days=in_sample_days)

        # Out-of-sample period (what we test)
        out_sample_start = in_sample_end + timedelta(days=1)
        out_sample_end = out_sample_start + timedelta(days=out_sample_days)

        logger.info(f"Walk-forward window {window}: OOS {out_sample_start} to {out_sample_end}")

        config = BacktestConfig(
            start_date=out_sample_start,
            end_date=min(out_sample_end, end_date),
            initial_capital=initial_capital,
        )

        result = runner.run(strategy, symbols, config)
        result.strategy_name = f"{strategy.name} (Window {window})"
        results.append(result)

        # Move forward by out-of-sample days
        current_start += timedelta(days=out_sample_days)

    return results

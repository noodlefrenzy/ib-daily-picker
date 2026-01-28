"""
Backtest API endpoints.

PURPOSE: JSON API for running backtests and retrieving results
DEPENDENCIES: fastapi
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ib_daily_picker.analysis import get_strategy_loader
from ib_daily_picker.backtest import (
    BacktestConfig,
    BacktestRunner,
    compare_strategies,
)
from ib_daily_picker.config import get_settings
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Request/Response Models ---


class BacktestRequest(BaseModel):
    """Request to run a backtest."""

    strategy: str
    start_date: date
    end_date: date
    symbols: list[str] | None = None  # None = use default basket
    initial_capital: Decimal = Decimal("100000")
    position_size_pct: Decimal = Decimal("0.10")
    max_positions: int = 5


class TradeResult(BaseModel):
    """Individual trade result."""

    symbol: str
    direction: str
    entry_price: str
    exit_price: str | None
    entry_date: str
    exit_date: str | None
    pnl: str | None
    pnl_percent: str | None


class MetricsResponse(BaseModel):
    """Backtest metrics response."""

    strategy_name: str
    start_date: str | None
    end_date: str | None
    initial_capital: str
    final_capital: str
    total_return_pct: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: str
    total_pnl: str
    profit_factor: str | None
    max_drawdown_pct: str
    sharpe_ratio: str | None
    avg_hold_time_days: str


class EquityCurvePoint(BaseModel):
    """Single point on equity curve."""

    date: str
    equity: str
    drawdown_pct: str


class BacktestResponse(BaseModel):
    """Backtest result response."""

    strategy: str
    config: dict
    trades: list[TradeResult]
    metrics: MetricsResponse
    equity_curve: list[EquityCurvePoint]


class CompareRequest(BaseModel):
    """Request to compare strategies."""

    strategies: list[str]
    start_date: date
    end_date: date
    symbols: list[str] | None = None


class StrategyComparisonResult(BaseModel):
    """Comparison result for a single strategy."""

    name: str
    total_return_pct: float
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_trades: int


class CompareResponse(BaseModel):
    """Strategy comparison response."""

    strategies: list[StrategyComparisonResult]
    rankings: dict[str, list[str]]


# --- Endpoints ---


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> BacktestResponse:
    """Run a backtest with specified parameters."""
    loader = get_strategy_loader()

    try:
        strategy = loader.load(request.strategy)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Strategy {request.strategy} not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get symbols
    if request.symbols:
        symbols = [s.upper() for s in request.symbols]
    else:
        settings = get_settings()
        symbols = settings.basket.default_tickers

    # Build config
    config = BacktestConfig(
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        position_size_pct=request.position_size_pct,
        max_positions=request.max_positions,
    )

    # Run backtest
    runner = BacktestRunner(db)
    result = runner.run(strategy, symbols, config)

    # Build response
    trades = []
    for t in result.trades:
        trades.append(
            TradeResult(
                symbol=t.symbol,
                direction=t.direction.value,
                entry_price=str(t.entry_price),
                exit_price=str(t.exit_price) if t.exit_price else None,
                entry_date=t.entry_time.strftime("%Y-%m-%d"),
                exit_date=t.exit_time.strftime("%Y-%m-%d") if t.exit_time else None,
                pnl=str(t.pnl) if t.pnl else None,
                pnl_percent=str(t.pnl_percent) if t.pnl_percent else None,
            )
        )

    # Build metrics response
    m = result.metrics
    metrics = MetricsResponse(
        strategy_name=m.strategy_name if m else "",
        start_date=str(m.start_date) if m and m.start_date else None,
        end_date=str(m.end_date) if m and m.end_date else None,
        initial_capital=str(m.initial_capital) if m else str(request.initial_capital),
        final_capital=str(m.final_capital) if m else str(request.initial_capital),
        total_return_pct=str(m.total_return_pct) if m else "0",
        total_trades=m.total_trades if m else 0,
        winning_trades=m.winning_trades if m else 0,
        losing_trades=m.losing_trades if m else 0,
        win_rate=str(m.win_rate) if m else "0",
        total_pnl=str(m.total_pnl) if m else "0",
        profit_factor=str(m.profit_factor) if m and m.profit_factor else None,
        max_drawdown_pct=str(m.max_drawdown_pct) if m else "0",
        sharpe_ratio=str(m.sharpe_ratio) if m and m.sharpe_ratio else None,
        avg_hold_time_days=str(m.avg_hold_time_days) if m else "0",
    )

    # Build equity curve
    equity_curve = []
    if m and m.equity_curve:
        for point in m.equity_curve:
            equity_curve.append(
                EquityCurvePoint(
                    date=str(point.date),
                    equity=str(point.equity),
                    drawdown_pct=str(point.drawdown_pct),
                )
            )

    return BacktestResponse(
        strategy=strategy.name,
        config={
            "start_date": str(request.start_date),
            "end_date": str(request.end_date),
            "initial_capital": str(request.initial_capital),
            "position_size_pct": str(request.position_size_pct),
            "max_positions": request.max_positions,
            "symbols": symbols,
        },
        trades=trades,
        metrics=metrics,
        equity_curve=equity_curve,
    )


@router.get("/backtest/stream")
async def stream_backtest(
    strategy: Annotated[str, Query()],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str | None, Query()] = None,
    initial_capital: Annotated[Decimal, Query()] = Decimal("100000"),
) -> StreamingResponse:
    """Stream backtest progress via SSE.

    Use this endpoint for real-time progress updates in the UI.
    """

    async def generate_events() -> AsyncGenerator[str, None]:
        loader = get_strategy_loader()

        try:
            strat = loader.load(strategy)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Get symbols
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
        else:
            settings = get_settings()
            symbol_list = settings.basket.default_tickers

        yield f"data: {json.dumps({'type': 'start', 'strategy': strat.name, 'symbols': len(symbol_list), 'start_date': str(start_date), 'end_date': str(end_date)})}\n\n"

        # Run the backtest (this is synchronous but we'll emit progress)
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )

        yield f"data: {json.dumps({'type': 'progress', 'status': 'running', 'message': 'Running backtest...'})}\n\n"

        runner = BacktestRunner(db)
        result = runner.run(strat, symbol_list, config)

        # Small delay to ensure UI updates
        await asyncio.sleep(0.1)

        # Emit trades as they're "discovered"
        for i, trade in enumerate(result.trades):
            trade_data = {
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "entry_price": str(trade.entry_price),
                "exit_price": str(trade.exit_price) if trade.exit_price else None,
                "pnl": str(trade.pnl) if trade.pnl else None,
            }
            yield f"data: {json.dumps({'type': 'trade', 'index': i + 1, 'total': len(result.trades), 'trade': trade_data})}\n\n"
            await asyncio.sleep(0.05)

        # Emit final metrics
        if result.metrics:
            m = result.metrics
            metrics_data = {
                "total_return_pct": str(m.total_return_pct),
                "total_trades": m.total_trades,
                "win_rate": str(m.win_rate),
                "profit_factor": str(m.profit_factor) if m.profit_factor else None,
                "max_drawdown_pct": str(m.max_drawdown_pct),
                "sharpe_ratio": str(m.sharpe_ratio) if m.sharpe_ratio else None,
            }

            # Build equity curve for chart
            equity_curve = []
            for point in m.equity_curve:
                equity_curve.append(
                    {
                        "date": str(point.date),
                        "equity": str(point.equity),
                    }
                )

            yield f"data: {json.dumps({'type': 'complete', 'metrics': metrics_data, 'equity_curve': equity_curve})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'complete', 'metrics': None, 'equity_curve': []})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/backtest/compare", response_model=CompareResponse)
async def compare_backtest_strategies(
    request: CompareRequest,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> CompareResponse:
    """Compare multiple strategies over the same period."""
    loader = get_strategy_loader()

    # Get symbols
    if request.symbols:
        symbols = [s.upper() for s in request.symbols]
    else:
        settings = get_settings()
        symbols = settings.basket.default_tickers

    # Build config
    config = BacktestConfig(
        start_date=request.start_date,
        end_date=request.end_date,
    )

    # Run backtests for each strategy
    runner = BacktestRunner(db)
    metrics_list = []

    for strategy_name in request.strategies:
        try:
            strategy = loader.load(strategy_name)
            result = runner.run(strategy, symbols, config)
            if result.metrics:
                metrics_list.append(result.metrics)
        except Exception:
            # Skip strategies that fail to load
            continue

    # Compare
    comparison = compare_strategies(metrics_list)

    # Build response
    strategies = []
    for s in comparison.get("strategies", []):
        strategies.append(
            StrategyComparisonResult(
                name=s["name"],
                total_return_pct=s["total_return_pct"],
                win_rate=s["win_rate"],
                profit_factor=s["profit_factor"],
                max_drawdown_pct=s["max_drawdown_pct"],
                sharpe_ratio=s["sharpe_ratio"],
                total_trades=s["total_trades"],
            )
        )

    rankings = comparison.get("rankings", {})

    return CompareResponse(
        strategies=strategies,
        rankings=rankings,
    )

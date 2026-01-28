"""
Analysis API endpoints.

PURPOSE: JSON API for running analysis and generating signals
DEPENDENCIES: fastapi
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ib_daily_picker.analysis import (
    StrategyEvaluator,
    get_strategy_loader,
)
from ib_daily_picker.config import get_settings
from ib_daily_picker.journal import get_journal_manager
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import StockRepository
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Request/Response Models ---


class AnalyzeRequest(BaseModel):
    """Request to run analysis."""

    strategy: str
    symbols: list[str] | None = None  # None = use default basket


class SignalResult(BaseModel):
    """Signal result from analysis."""

    symbol: str
    signal_type: str
    entry_price: str | None
    stop_loss: str | None
    take_profit: str | None
    confidence: float
    reasoning: str | None


class AnalyzeResponse(BaseModel):
    """Analysis response."""

    strategy: str
    symbols_analyzed: int
    signals: list[SignalResult]
    saved_count: int


# --- Endpoints ---


@router.post("/analyze", response_model=AnalyzeResponse)
async def run_analysis(
    request: AnalyzeRequest,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> AnalyzeResponse:
    """Run analysis with a strategy and generate signals."""
    loader = get_strategy_loader()
    strategy = loader.load(request.strategy)

    # Get symbols
    if request.symbols:
        symbols = [s.upper() for s in request.symbols]
    else:
        settings = get_settings()
        symbols = settings.basket.default_tickers

    # Get OHLCV data
    stock_repo = StockRepository(db)
    signals_list = []

    for symbol in symbols:
        ohlcv = stock_repo.get_ohlcv(symbol, limit=200)
        if not ohlcv:
            continue

        # Run evaluator
        evaluator = StrategyEvaluator(strategy)
        result = evaluator.evaluate(symbol, ohlcv)

        if result.signal and result.signal.signal_type.value in ["buy", "sell"]:
            signals_list.append(
                SignalResult(
                    symbol=result.symbol,
                    signal_type=result.signal.signal_type.value,
                    entry_price=str(result.signal.entry_price)
                    if result.signal.entry_price
                    else None,
                    stop_loss=str(result.signal.stop_loss) if result.signal.stop_loss else None,
                    take_profit=str(result.signal.take_profit)
                    if result.signal.take_profit
                    else None,
                    confidence=float(result.signal.confidence),
                    reasoning=result.signal.reasoning,
                )
            )

    # Save recommendations
    journal = get_journal_manager()
    saved_count = 0
    for sig in signals_list:
        from uuid import uuid4

        from ib_daily_picker.models import Recommendation, SignalType

        rec = Recommendation(
            id=str(uuid4()),
            symbol=sig.symbol,
            strategy_name=strategy.name,
            signal_type=SignalType(sig.signal_type),
            entry_price=sig.entry_price,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            confidence=sig.confidence,
            reasoning=sig.reasoning,
            generated_at=datetime.utcnow(),
        )
        journal.save_recommendation(rec)
        saved_count += 1

    return AnalyzeResponse(
        strategy=strategy.name,
        symbols_analyzed=len(symbols),
        signals=signals_list,
        saved_count=saved_count,
    )


@router.get("/analyze/stream")
async def stream_analysis(
    strategy: Annotated[str, Query()],
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    """Stream analysis progress via SSE.

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

        yield f"data: {json.dumps({'type': 'start', 'strategy': strat.name, 'total': len(symbol_list)})}\n\n"

        stock_repo = StockRepository(db)
        signals_found = []

        for i, symbol in enumerate(symbol_list, 1):
            yield f"data: {json.dumps({'type': 'progress', 'symbol': symbol, 'current': i, 'total': len(symbol_list)})}\n\n"

            ohlcv = stock_repo.get_ohlcv(symbol, limit=200)
            if not ohlcv:
                yield f"data: {json.dumps({'type': 'skip', 'symbol': symbol, 'reason': 'no data'})}\n\n"
                continue

            evaluator = StrategyEvaluator(strat)
            result = evaluator.evaluate(symbol, ohlcv)

            if result.signal and result.signal.signal_type.value in ["buy", "sell"]:
                signal_data = {
                    "symbol": result.symbol,
                    "signal_type": result.signal.signal_type.value,
                    "confidence": float(result.signal.confidence),
                }
                signals_found.append(signal_data)
                yield f"data: {json.dumps({'type': 'signal', 'signal': signal_data})}\n\n"

            # Small delay to allow UI updates
            await asyncio.sleep(0.05)

        yield f"data: {json.dumps({'type': 'complete', 'total_signals': len(signals_found)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

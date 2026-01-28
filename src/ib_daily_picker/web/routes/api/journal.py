"""
Journal API endpoints.

PURPOSE: JSON API for trade journal operations
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ib_daily_picker.journal import JournalManager
from ib_daily_picker.models import TradeDirection
from ib_daily_picker.web.dependencies import get_journal

router = APIRouter()


# --- Response Models ---


class TradeResponse(BaseModel):
    """Trade response."""

    id: str
    symbol: str
    direction: str
    entry_price: str
    entry_time: datetime
    exit_price: str | None = None
    exit_time: datetime | None = None
    position_size: str
    stop_loss: str | None = None
    take_profit: str | None = None
    pnl: str | None = None
    pnl_percent: str | None = None
    r_multiple: str | None = None
    status: str
    notes: str | None = None
    tags: list[str]


class TradeListResponse(BaseModel):
    """List of trades."""

    trades: list[TradeResponse]
    total: int


class TradeMetricsResponse(BaseModel):
    """Trade metrics response."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float | None
    total_pnl: str | None
    average_win: str | None
    average_loss: str | None
    profit_factor: float | None
    average_r_multiple: float | None


# --- Helper ---


def _trade_to_response(trade) -> TradeResponse:  # noqa: ANN001
    """Convert Trade model to response."""
    return TradeResponse(
        id=trade.id,
        symbol=trade.symbol,
        direction=trade.direction.value,
        entry_price=str(trade.entry_price),
        entry_time=trade.entry_time,
        exit_price=str(trade.exit_price) if trade.exit_price else None,
        exit_time=trade.exit_time,
        position_size=str(trade.position_size),
        stop_loss=str(trade.stop_loss) if trade.stop_loss else None,
        take_profit=str(trade.take_profit) if trade.take_profit else None,
        pnl=str(trade.pnl) if trade.pnl else None,
        pnl_percent=str(trade.pnl_percent) if trade.pnl_percent else None,
        r_multiple=str(trade.r_multiple) if trade.r_multiple else None,
        status=trade.status.value,
        notes=trade.notes,
        tags=trade.tags or [],
    )


# --- Endpoints ---


@router.get("/trades", response_model=TradeListResponse)
async def list_trades(
    journal: Annotated[JournalManager, Depends(get_journal)],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> TradeListResponse:
    """List trades.

    Args:
        status: Filter by status (open, closed, all). Default: all.
        limit: Maximum number of trades to return.
    """
    trades = []

    if status == "open":
        trades = journal.get_open_trades()
    elif status == "closed":
        trades = journal.get_closed_trades(limit=limit)
    else:
        # All trades
        open_trades = journal.get_open_trades()
        closed_trades = journal.get_closed_trades(limit=limit - len(open_trades))
        trades = open_trades + closed_trades

    return TradeListResponse(
        trades=[_trade_to_response(t) for t in trades],
        total=len(trades),
    )


@router.get("/trades/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: str,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> TradeResponse:
    """Get a specific trade by ID."""
    trade = journal.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    return _trade_to_response(trade)


@router.get("/trades/metrics", response_model=TradeMetricsResponse)
async def get_trade_metrics(
    journal: Annotated[JournalManager, Depends(get_journal)],
    start_date: Annotated[date | None, Query(alias="from")] = None,
    end_date: Annotated[date | None, Query(alias="to")] = None,
) -> TradeMetricsResponse:
    """Get trade metrics."""
    metrics = journal.get_metrics(start_date=start_date, end_date=end_date)

    return TradeMetricsResponse(
        total_trades=metrics.total_trades,
        winning_trades=metrics.winning_trades,
        losing_trades=metrics.losing_trades,
        win_rate=float(metrics.win_rate) if metrics.win_rate else None,
        total_pnl=str(metrics.total_pnl) if metrics.total_pnl else None,
        average_win=str(metrics.average_win) if metrics.average_win else None,
        average_loss=str(metrics.average_loss) if metrics.average_loss else None,
        profit_factor=float(metrics.profit_factor) if metrics.profit_factor else None,
        average_r_multiple=float(metrics.average_r_multiple)
        if metrics.average_r_multiple
        else None,
    )


# --- Request Models ---


class OpenTradeRequest(BaseModel):
    """Request to open a new trade."""

    symbol: str
    direction: str  # long or short
    entry_price: float
    position_size: float
    stop_loss: float | None = None
    take_profit: float | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CloseTradeRequest(BaseModel):
    """Request to close a trade."""

    exit_price: float
    notes: str | None = None


class AddNoteRequest(BaseModel):
    """Request to add a note to a trade."""

    note: str


class ExecuteRecommendationRequest(BaseModel):
    """Request to execute a recommendation."""

    entry_price: float
    position_size: float
    notes: str | None = None


# --- Write Endpoints ---


@router.post("/trades", response_model=TradeResponse)
async def open_trade(
    request: OpenTradeRequest,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> TradeResponse:
    """Open a new trade."""
    try:
        direction = TradeDirection(request.direction.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid direction: {request.direction}")

    trade = journal.open_trade(
        symbol=request.symbol.upper(),
        direction=direction,
        entry_price=Decimal(str(request.entry_price)),
        position_size=Decimal(str(request.position_size)),
        stop_loss=Decimal(str(request.stop_loss)) if request.stop_loss else None,
        take_profit=Decimal(str(request.take_profit)) if request.take_profit else None,
        notes=request.notes,
        tags=request.tags,
    )

    return _trade_to_response(trade)


@router.post("/trades/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: str,
    request: CloseTradeRequest,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> TradeResponse:
    """Close an open trade."""
    try:
        trade = journal.close_trade(
            trade_id=trade_id,
            exit_price=Decimal(str(request.exit_price)),
            notes=request.notes,
        )
        return _trade_to_response(trade)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trades/{trade_id}/note", response_model=TradeResponse)
async def add_trade_note(
    trade_id: str,
    request: AddNoteRequest,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> TradeResponse:
    """Add a note to a trade."""
    try:
        trade = journal.add_note(trade_id=trade_id, note=request.note)
        return _trade_to_response(trade)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/recommendations/{rec_id}/execute", response_model=TradeResponse)
async def execute_recommendation(
    rec_id: str,
    request: ExecuteRecommendationRequest,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> TradeResponse:
    """Execute a recommendation as a trade."""
    try:
        trade = journal.execute_recommendation(
            recommendation_id=rec_id,
            entry_price=Decimal(str(request.entry_price)),
            position_size=Decimal(str(request.position_size)),
            notes=request.notes,
        )
        return _trade_to_response(trade)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

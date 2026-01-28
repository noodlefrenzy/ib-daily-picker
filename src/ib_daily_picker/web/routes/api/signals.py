"""
Signals API endpoints.

PURPOSE: JSON API for trading signals and recommendations
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ib_daily_picker.models import RecommendationStatus
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import RecommendationRepository
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Response Models ---


class SignalResponse(BaseModel):
    """Trading signal/recommendation response."""

    id: str
    symbol: str
    signal_type: str
    entry_price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    confidence: float
    reasoning: str | None = None
    strategy_name: str
    generated_at: datetime
    status: str
    is_actionable: bool


class SignalListResponse(BaseModel):
    """List of signals."""

    signals: list[SignalResponse]
    total: int


# --- Endpoints ---


@router.get("/signals", response_model=SignalListResponse)
async def list_signals(
    db: Annotated[DatabaseManager, Depends(get_db)],
    status: Annotated[str | None, Query()] = "pending",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SignalListResponse:
    """List trading signals/recommendations.

    Args:
        status: Filter by status (pending, executed, expired, skipped). Default: pending.
        limit: Maximum number of signals to return.
    """
    repo = RecommendationRepository(db)

    if status == "pending" or status is None:
        recommendations = repo.get_pending(limit=limit)
    else:
        # For other statuses, we need to query differently
        # For now, just get pending
        recommendations = repo.get_pending(limit=limit)

    signals = [
        SignalResponse(
            id=rec.id,
            symbol=rec.symbol,
            signal_type=rec.signal_type.value,
            entry_price=str(rec.entry_price) if rec.entry_price else None,
            stop_loss=str(rec.stop_loss) if rec.stop_loss else None,
            take_profit=str(rec.take_profit) if rec.take_profit else None,
            confidence=float(rec.confidence),
            reasoning=rec.reasoning,
            strategy_name=rec.strategy_name,
            generated_at=rec.generated_at,
            status=rec.status.value,
            is_actionable=rec.is_actionable,
        )
        for rec in recommendations
    ]

    return SignalListResponse(signals=signals, total=len(signals))


@router.get("/signals/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> SignalResponse:
    """Get a specific signal by ID."""
    repo = RecommendationRepository(db)
    rec = repo.get_by_id(signal_id)

    if not rec:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    return SignalResponse(
        id=rec.id,
        symbol=rec.symbol,
        signal_type=rec.signal_type.value,
        entry_price=str(rec.entry_price) if rec.entry_price else None,
        stop_loss=str(rec.stop_loss) if rec.stop_loss else None,
        take_profit=str(rec.take_profit) if rec.take_profit else None,
        confidence=float(rec.confidence),
        reasoning=rec.reasoning,
        strategy_name=rec.strategy_name,
        generated_at=rec.generated_at,
        status=rec.status.value,
        is_actionable=rec.is_actionable,
    )


@router.post("/signals/{signal_id}/skip")
async def skip_signal(
    signal_id: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> dict[str, str]:
    """Mark a signal as skipped (cancelled)."""
    repo = RecommendationRepository(db)
    rec = repo.get_by_id(signal_id)

    if not rec:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    repo.update_status(signal_id, RecommendationStatus.CANCELLED)
    return {"status": "skipped", "id": signal_id}

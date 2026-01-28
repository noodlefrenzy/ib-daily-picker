"""
Watchlist API endpoints.

PURPOSE: JSON API for watchlist management
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Request/Response Models ---


class WatchlistItemResponse(BaseModel):
    """Watchlist item response."""

    symbol: str
    added_at: str
    notes: str | None = None
    tags: list[str]


class WatchlistResponse(BaseModel):
    """Watchlist response."""

    items: list[WatchlistItemResponse]
    total: int


class AddToWatchlistRequest(BaseModel):
    """Request to add symbol to watchlist."""

    symbol: str
    notes: str | None = None
    tags: list[str] | None = None


# --- Endpoints ---


@router.get("/watchlist", response_model=WatchlistResponse)
async def list_watchlist(
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> WatchlistResponse:
    """Get all watchlist items."""
    items = db.watchlist_list()

    return WatchlistResponse(
        items=[
            WatchlistItemResponse(
                symbol=item["symbol"],
                added_at=item["added_at"],
                notes=item["notes"],
                tags=item["tags"] or [],
            )
            for item in items
        ],
        total=len(items),
    )


@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_to_watchlist(
    request: AddToWatchlistRequest,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> WatchlistItemResponse:
    """Add a symbol to the watchlist."""
    symbol = request.symbol.upper()

    if db.watchlist_contains(symbol):
        raise HTTPException(status_code=400, detail=f"{symbol} already in watchlist")

    success = db.watchlist_add(symbol, notes=request.notes, tags=request.tags)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to add {symbol}")

    # Get the item we just added
    items = db.watchlist_list()
    item = next((i for i in items if i["symbol"] == symbol), None)

    if not item:
        raise HTTPException(status_code=500, detail="Failed to retrieve added item")

    return WatchlistItemResponse(
        symbol=item["symbol"],
        added_at=item["added_at"],
        notes=item["notes"],
        tags=item["tags"] or [],
    )


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> dict[str, str]:
    """Remove a symbol from the watchlist."""
    symbol = symbol.upper()

    if not db.watchlist_contains(symbol):
        raise HTTPException(status_code=404, detail=f"{symbol} not in watchlist")

    success = db.watchlist_remove(symbol)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to remove {symbol}")

    return {"status": "removed", "symbol": symbol}

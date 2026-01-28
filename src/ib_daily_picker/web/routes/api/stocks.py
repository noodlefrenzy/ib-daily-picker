"""
Stock API endpoints.

PURPOSE: JSON API for stock data (OHLCV, metadata)
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from ib_daily_picker.models import OHLCV

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import StockRepository
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Response Models ---


class OHLCVResponse(BaseModel):
    """OHLCV data response."""

    symbol: str
    date: date
    open: str  # Decimal as string for JSON
    high: str
    low: str
    close: str
    volume: int
    adjusted_close: str | None = None

    @classmethod
    def from_ohlcv(cls, ohlcv: OHLCV) -> OHLCVResponse:
        """Create from domain model."""

        return cls(
            symbol=ohlcv.symbol,
            date=ohlcv.trade_date,
            open=str(ohlcv.open_price),
            high=str(ohlcv.high_price),
            low=str(ohlcv.low_price),
            close=str(ohlcv.close_price),
            volume=ohlcv.volume,
            adjusted_close=str(ohlcv.adjusted_close) if ohlcv.adjusted_close else None,
        )


class StockMetadataResponse(BaseModel):
    """Stock metadata response."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    exchange: str | None = None


class StockSummaryResponse(BaseModel):
    """Summary of a stock with key metrics."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    latest_close: str | None = None
    latest_date: date | None = None
    data_points: int = 0


class StockListResponse(BaseModel):
    """List of stocks with data."""

    stocks: list[StockSummaryResponse]
    total: int


# --- Endpoints ---


@router.get("/stocks", response_model=StockListResponse)
async def list_stocks(
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> StockListResponse:
    """List all stocks with data in the database."""
    repo = StockRepository(db)
    symbols = repo.get_symbols()

    stocks = []
    for symbol in symbols:
        # Get latest OHLCV
        ohlcv_list = repo.get_ohlcv(symbol, limit=1)
        latest = ohlcv_list[0] if ohlcv_list else None

        # Get metadata
        metadata = repo.get_metadata(symbol)

        # Count data points
        all_ohlcv = repo.get_ohlcv(symbol)
        data_points = len(all_ohlcv)

        stocks.append(
            StockSummaryResponse(
                symbol=symbol,
                name=metadata.name if metadata else None,
                sector=metadata.sector if metadata else None,
                latest_close=str(latest.close_price) if latest else None,
                latest_date=latest.trade_date if latest else None,
                data_points=data_points,
            )
        )

    return StockListResponse(stocks=stocks, total=len(stocks))


@router.get("/stocks/{symbol}", response_model=StockSummaryResponse)
async def get_stock(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> StockSummaryResponse:
    """Get stock summary by symbol."""
    repo = StockRepository(db)
    symbol = symbol.upper()

    # Get latest OHLCV
    ohlcv_list = repo.get_ohlcv(symbol, limit=1)
    if not ohlcv_list:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    latest = ohlcv_list[0]

    # Get metadata
    metadata = repo.get_metadata(symbol)

    # Count data points
    all_ohlcv = repo.get_ohlcv(symbol)

    return StockSummaryResponse(
        symbol=symbol,
        name=metadata.name if metadata else None,
        sector=metadata.sector if metadata else None,
        latest_close=str(latest.close_price),
        latest_date=latest.trade_date,
        data_points=len(all_ohlcv),
    )


@router.get("/stocks/{symbol}/ohlcv", response_model=list[OHLCVResponse])
async def get_stock_ohlcv(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
    start_date: Annotated[date | None, Query(alias="from")] = None,
    end_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[OHLCVResponse]:
    """Get OHLCV data for a stock.

    Returns data in descending date order (newest first).
    """
    repo = StockRepository(db)
    symbol = symbol.upper()

    ohlcv_list = repo.get_ohlcv(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    if not ohlcv_list:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    return [OHLCVResponse.from_ohlcv(o) for o in ohlcv_list]


@router.get("/stocks/{symbol}/metadata", response_model=StockMetadataResponse)
async def get_stock_metadata(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> StockMetadataResponse:
    """Get metadata for a stock."""
    repo = StockRepository(db)
    symbol = symbol.upper()

    metadata = repo.get_metadata(symbol)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Metadata not found for {symbol}")

    return StockMetadataResponse(
        symbol=metadata.symbol,
        name=metadata.name,
        sector=metadata.sector,
        industry=metadata.industry,
        market_cap=metadata.market_cap,
        exchange=metadata.exchange,
    )

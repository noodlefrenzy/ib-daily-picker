"""
Chart pages routes.

PURPOSE: HTML pages for chart comparison, portfolio, and correlation views
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.config import MARKET_BENCHMARK, SECTOR_ETFS
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import StockRepository
from ib_daily_picker.web.dependencies import get_db
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/charts/compare", response_class=HTMLResponse)
async def compare_page(
    request: Request,
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str | None, Query(description="Comma-separated symbols")] = None,
) -> HTMLResponse:
    """Render the stock comparison page."""
    templates = get_templates()
    repo = StockRepository(db)

    # Get available symbols from database
    available_symbols = repo.get_symbols()

    # Parse initial symbols from query param
    initial_symbols = []
    if symbols:
        initial_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    context = {
        "request": request,
        "initial_symbols": initial_symbols,
        "available_symbols": available_symbols,
        "benchmark": MARKET_BENCHMARK,
        "sector_etfs": SECTOR_ETFS,
    }

    return templates.TemplateResponse(request, "pages/stock_compare.html", context)


@router.get("/charts/portfolio", response_class=HTMLResponse)
async def portfolio_page(
    request: Request,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> HTMLResponse:
    """Render the portfolio analytics page."""
    templates = get_templates()

    # Get portfolio data from journal trades
    # For now, pass empty data - the page will fetch via API
    context = {
        "request": request,
    }

    return templates.TemplateResponse(request, "pages/portfolio.html", context)


@router.get("/charts/correlations", response_class=HTMLResponse)
async def correlations_page(
    request: Request,
    db: Annotated[DatabaseManager, Depends(get_db)],
    symbols: Annotated[str | None, Query(description="Comma-separated symbols")] = None,
) -> HTMLResponse:
    """Render the correlation analysis page."""
    templates = get_templates()
    repo = StockRepository(db)

    # Get available symbols from database
    available_symbols = repo.get_symbols()

    # Parse initial symbols from query param
    initial_symbols = []
    if symbols:
        initial_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    context = {
        "request": request,
        "initial_symbols": initial_symbols,
        "available_symbols": available_symbols,
        "benchmark": MARKET_BENCHMARK,
        "sector_etfs": SECTOR_ETFS,
    }

    return templates.TemplateResponse(request, "pages/correlations.html", context)

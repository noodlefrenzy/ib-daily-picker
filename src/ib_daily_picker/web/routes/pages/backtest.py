"""
Backtest page routes.

PURPOSE: HTML pages for backtesting UI
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.analysis import get_strategy_loader
from ib_daily_picker.config import get_settings
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/backtest", response_class=HTMLResponse)
async def backtest_page(
    request: Request,
) -> HTMLResponse:
    """Render the backtest page."""
    templates = get_templates()

    # Get strategies
    loader = get_strategy_loader()
    strategies = loader.list_strategies()

    # Get default symbols
    settings = get_settings()
    default_symbols = settings.basket.default_tickers

    context = {
        "request": request,
        "strategies": strategies,
        "default_symbols": default_symbols,
    }

    return templates.TemplateResponse(request, "pages/backtest.html", context)

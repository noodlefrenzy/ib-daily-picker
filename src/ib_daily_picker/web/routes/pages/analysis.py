"""
Analysis page routes.

PURPOSE: HTML pages for analysis and strategy views
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.analysis import get_strategy_loader
from ib_daily_picker.config import get_settings
from ib_daily_picker.journal import get_journal_manager
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(
    request: Request,
) -> HTMLResponse:
    """Render the analysis page."""
    templates = get_templates()

    # Get strategies
    loader = get_strategy_loader()
    strategies = loader.list_strategies()

    # Get pending recommendations
    journal = get_journal_manager()
    pending = journal.get_pending_recommendations(limit=20)

    # Get default symbols
    settings = get_settings()
    default_symbols = settings.basket.default_tickers

    context = {
        "request": request,
        "strategies": strategies,
        "pending_recommendations": pending,
        "default_symbols": default_symbols,
    }

    return templates.TemplateResponse(request, "pages/analysis.html", context)


@router.get("/strategies", response_class=HTMLResponse)
async def strategies_page(
    request: Request,
) -> HTMLResponse:
    """Render the strategies list page."""
    templates = get_templates()

    loader = get_strategy_loader()
    strategies = loader.list_strategies()

    context = {
        "request": request,
        "strategies": strategies,
    }

    return templates.TemplateResponse(request, "pages/strategies.html", context)


@router.get("/strategies/{name}", response_class=HTMLResponse)
async def strategy_detail_page(
    request: Request,
    name: str,
) -> HTMLResponse:
    """Render the strategy detail page."""
    templates = get_templates()

    loader = get_strategy_loader()

    try:
        strategy = loader.load(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")

    context = {
        "request": request,
        "strategy": strategy,
    }

    return templates.TemplateResponse(request, "pages/strategy_detail.html", context)

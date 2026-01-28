"""
Journal page route.

PURPOSE: HTML page for trade journal view
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.journal import JournalManager
from ib_daily_picker.web.dependencies import get_journal
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/journal", response_class=HTMLResponse)
async def journal_page(
    request: Request,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> HTMLResponse:
    """Render the trade journal page."""
    templates = get_templates()

    # Get trades
    open_trades = journal.get_open_trades()
    closed_trades = journal.get_closed_trades(limit=100)

    # Get metrics
    metrics = journal.get_metrics()

    # Get pending recommendations
    pending_recommendations = journal.get_pending_recommendations(limit=10)

    context = {
        "request": request,
        "open_trades": open_trades,
        "closed_trades": closed_trades,
        "metrics": metrics,
        "pending_recommendations": pending_recommendations,
    }

    return templates.TemplateResponse(request, "pages/journal.html", context)


@router.get("/journal/open-trade-form", response_class=HTMLResponse)
async def open_trade_form(
    request: Request,
    symbol: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Render the open trade form modal."""
    templates = get_templates()
    return templates.TemplateResponse(
        request, "components/open_trade_form.html", {"request": request, "symbol": symbol}
    )


@router.get("/journal/trades/{trade_id}/close-form", response_class=HTMLResponse)
async def close_trade_form(
    request: Request,
    trade_id: str,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> HTMLResponse:
    """Render the close trade form modal."""
    trade = journal.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

    templates = get_templates()
    return templates.TemplateResponse(
        request, "components/close_trade_form.html", {"request": request, "trade": trade}
    )


@router.get("/journal/recommendations/{rec_id}/execute-form", response_class=HTMLResponse)
async def execute_recommendation_form(
    request: Request,
    rec_id: str,
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> HTMLResponse:
    """Render the execute recommendation form modal."""
    rec = journal.get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    templates = get_templates()
    return templates.TemplateResponse(
        request, "components/execute_recommendation_form.html", {"request": request, "rec": rec}
    )

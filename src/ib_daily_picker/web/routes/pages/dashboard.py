"""
Dashboard page route.

PURPOSE: Main dashboard showing portfolio summary, recent signals, data status
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.journal import JournalManager
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import RecommendationRepository
from ib_daily_picker.web.dependencies import get_db, get_journal
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Annotated[DatabaseManager, Depends(get_db)],
    journal: Annotated[JournalManager, Depends(get_journal)],
) -> HTMLResponse:
    """Render the main dashboard page."""
    templates = get_templates()

    # Get portfolio summary
    open_trades = journal.get_open_trades()
    metrics = journal.get_metrics()

    # Calculate portfolio value
    total_invested = sum(t.entry_price * t.position_size for t in open_trades)
    open_pnl = Decimal("0")  # Would need current prices to calculate

    # Get recent signals
    rec_repo = RecommendationRepository(db)
    recent_signals = rec_repo.get_pending(limit=5)

    # Get flow alerts count
    with db.duckdb() as conn:
        flow_result = conn.execute("SELECT COUNT(*) FROM flow_alerts").fetchone()
        flow_count = flow_result[0] if flow_result else 0

        # Get OHLCV stats
        ohlcv_result = conn.execute("""
            SELECT COUNT(DISTINCT symbol), COUNT(*), MAX(date)
            FROM ohlcv
        """).fetchone()
        ohlcv_symbols = ohlcv_result[0] if ohlcv_result else 0
        ohlcv_rows = ohlcv_result[1] if ohlcv_result else 0
        ohlcv_latest = ohlcv_result[2] if ohlcv_result else None

    # Get watchlist
    watchlist = db.watchlist_list()

    context = {
        "request": request,
        # Portfolio
        "open_trades": open_trades,
        "open_trades_count": len(open_trades),
        "total_invested": total_invested,
        "open_pnl": open_pnl,
        # Metrics
        "total_trades": metrics.total_trades,
        "win_rate": float(metrics.win_rate) * 100 if metrics.win_rate else 0,
        "total_pnl": metrics.total_pnl,
        "profit_factor": float(metrics.profit_factor) if metrics.profit_factor else None,
        # Signals
        "recent_signals": recent_signals,
        "pending_signals_count": len(recent_signals),
        # Data status
        "stock_count": ohlcv_symbols,
        "ohlcv_rows": ohlcv_rows,
        "latest_data_date": ohlcv_latest,
        "flow_count": flow_count,
        # Watchlist
        "watchlist": watchlist,
        "watchlist_count": len(watchlist),
        # Meta
        "now": datetime.now(UTC),
    }

    return templates.TemplateResponse(request, "pages/dashboard.html", context)

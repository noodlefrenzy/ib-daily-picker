"""
Stock pages routes.

PURPOSE: HTML pages for stock list and detail views
DEPENDENCIES: fastapi, jinja2
"""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from ib_daily_picker.analysis.indicators import IndicatorCalculator
from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import FlowRepository, StockRepository
from ib_daily_picker.web.dependencies import get_db
from ib_daily_picker.web.main import get_templates

router = APIRouter()


@router.get("/stocks", response_class=HTMLResponse)
async def stocks_list(
    request: Request,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> HTMLResponse:
    """Render the stocks list page."""
    templates = get_templates()
    repo = StockRepository(db)

    symbols = repo.get_symbols()
    stocks = []

    for symbol in symbols:
        ohlcv_list = repo.get_ohlcv(symbol, limit=1)
        latest = ohlcv_list[0] if ohlcv_list else None
        metadata = repo.get_metadata(symbol)

        # Get all OHLCV for count
        all_ohlcv = repo.get_ohlcv(symbol)

        stocks.append(
            {
                "symbol": symbol,
                "name": metadata.name if metadata else None,
                "sector": metadata.sector if metadata else None,
                "latest_close": latest.close_price if latest else None,
                "latest_date": latest.trade_date if latest else None,
                "data_points": len(all_ohlcv),
                "change_pct": _calculate_change_pct(all_ohlcv) if len(all_ohlcv) >= 2 else None,
            }
        )

    context = {
        "request": request,
        "stocks": stocks,
        "total": len(stocks),
    }

    return templates.TemplateResponse(request, "pages/stocks.html", context)


@router.get("/stocks/{symbol}", response_class=HTMLResponse)
async def stock_detail(
    request: Request,
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
) -> HTMLResponse:
    """Render the stock detail page with chart."""
    templates = get_templates()
    symbol = symbol.upper()

    stock_repo = StockRepository(db)
    flow_repo = FlowRepository(db)

    # Get OHLCV data
    ohlcv_list = stock_repo.get_ohlcv(symbol, limit=200)
    if not ohlcv_list:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get metadata
    metadata = stock_repo.get_metadata(symbol)

    # Get flow alerts
    flow_alerts = flow_repo.get_by_symbol(symbol, limit=20)

    # Prepare chart data (reverse for chronological order)
    # Include volume for histogram
    chart_data = [
        {
            "time": o.trade_date.isoformat(),
            "open": float(o.open_price),
            "high": float(o.high_price),
            "low": float(o.low_price),
            "close": float(o.close_price),
            "volume": o.volume,
        }
        for o in reversed(ohlcv_list)
    ]

    # Calculate indicators for overlay
    indicator_data = {}
    if ohlcv_list:
        calc = IndicatorCalculator(list(reversed(ohlcv_list)))
        sma_50 = calc.calculate("SMA", "sma_50", {"period": 50})
        sma_200 = calc.calculate("SMA", "sma_200", {"period": 200})

        # Convert to chart-compatible format (aligned with OHLCV dates)
        indicator_data["sma_50"] = [
            {"time": chart_data[i]["time"], "value": float(v) if not pd.isna(v) else None}
            for i, v in enumerate(sma_50.values)
        ]
        indicator_data["sma_200"] = [
            {"time": chart_data[i]["time"], "value": float(v) if not pd.isna(v) else None}
            for i, v in enumerate(sma_200.values)
        ]

    # Prepare flow alert markers for chart
    flow_markers = []
    for alert in flow_alerts:
        marker_time = alert.alert_time.date().isoformat()
        flow_markers.append(
            {
                "time": marker_time,
                "position": "aboveBar" if alert.direction.value == "bullish" else "belowBar",
                "color": "#00c853" if alert.sentiment.value == "bullish" else "#ff5252",
                "shape": "arrowUp" if alert.direction.value == "bullish" else "arrowDown",
                "text": alert.alert_type.value[:3].upper(),
            }
        )

    # Calculate key stats
    latest = ohlcv_list[0]
    stats = {
        "latest_close": latest.close_price,
        "latest_date": latest.trade_date,
        "volume": latest.volume,
        "high_52w": max(o.high_price for o in ohlcv_list) if ohlcv_list else None,
        "low_52w": min(o.low_price for o in ohlcv_list) if ohlcv_list else None,
        "data_points": len(ohlcv_list),
    }

    # Check if in watchlist
    in_watchlist = db.watchlist_contains(symbol)

    context = {
        "request": request,
        "symbol": symbol,
        "metadata": metadata,
        "stats": stats,
        "chart_data": chart_data,
        "indicator_data": indicator_data,
        "flow_markers": flow_markers,
        "flow_alerts": flow_alerts,
        "in_watchlist": in_watchlist,
    }

    return templates.TemplateResponse(request, "pages/stock_detail.html", context)


def _calculate_change_pct(ohlcv_list: list) -> float | None:  # type: ignore[type-arg]
    """Calculate daily change percentage."""
    if len(ohlcv_list) < 2:
        return None
    current = ohlcv_list[0].close_price
    previous = ohlcv_list[1].close_price
    if previous == 0:
        return None
    return float((current - previous) / previous * 100)

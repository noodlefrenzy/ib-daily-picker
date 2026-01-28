"""
Flow alerts API endpoints.

PURPOSE: JSON API for flow alert data
DEPENDENCIES: fastapi
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ib_daily_picker.store.database import DatabaseManager
from ib_daily_picker.store.repositories import FlowRepository
from ib_daily_picker.web.dependencies import get_db

router = APIRouter()


# --- Response Models ---


class FlowAlertResponse(BaseModel):
    """Flow alert response."""

    id: str
    symbol: str
    alert_time: datetime
    alert_type: str
    direction: str
    premium: str | None = None
    volume: int | None = None
    open_interest: int | None = None
    strike: str | None = None
    expiration: str | None = None
    option_type: str | None = None
    sentiment: str


class FlowListResponse(BaseModel):
    """List of flow alerts."""

    flows: list[FlowAlertResponse]
    total: int


# --- Endpoints ---


@router.get("/flows", response_model=FlowListResponse)
async def list_flows(
    db: Annotated[DatabaseManager, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    min_premium: Annotated[float | None, Query(alias="min-premium")] = None,
) -> FlowListResponse:
    """List recent flow alerts.

    Args:
        limit: Maximum number of alerts to return.
        min_premium: Minimum premium filter.
    """
    repo = FlowRepository(db)
    premium_filter = Decimal(str(min_premium)) if min_premium else None
    alerts = repo.get_recent(limit=limit, min_premium=premium_filter)

    flows = [
        FlowAlertResponse(
            id=alert.id,
            symbol=alert.symbol,
            alert_time=alert.alert_time,
            alert_type=alert.alert_type.value,
            direction=alert.direction.value,
            premium=str(alert.premium) if alert.premium else None,
            volume=alert.volume,
            open_interest=alert.open_interest,
            strike=str(alert.strike) if alert.strike else None,
            expiration=alert.expiration.isoformat() if alert.expiration else None,
            option_type=alert.option_type.value if alert.option_type else None,
            sentiment=alert.sentiment.value,
        )
        for alert in alerts
    ]

    return FlowListResponse(flows=flows, total=len(flows))


@router.get("/flows/{symbol}", response_model=FlowListResponse)
async def get_flows_by_symbol(
    symbol: str,
    db: Annotated[DatabaseManager, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> FlowListResponse:
    """Get flow alerts for a specific symbol."""
    repo = FlowRepository(db)
    alerts = repo.get_by_symbol(symbol.upper(), limit=limit)

    flows = [
        FlowAlertResponse(
            id=alert.id,
            symbol=alert.symbol,
            alert_time=alert.alert_time,
            alert_type=alert.alert_type.value,
            direction=alert.direction.value,
            premium=str(alert.premium) if alert.premium else None,
            volume=alert.volume,
            open_interest=alert.open_interest,
            strike=str(alert.strike) if alert.strike else None,
            expiration=alert.expiration.isoformat() if alert.expiration else None,
            option_type=alert.option_type.value if alert.option_type else None,
            sentiment=alert.sentiment.value,
        )
        for alert in alerts
    ]

    return FlowListResponse(flows=flows, total=len(flows))

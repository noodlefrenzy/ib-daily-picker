"""
FastAPI application factory.

PURPOSE: Create and configure the FastAPI application
DEPENDENCIES: fastapi, jinja2

ARCHITECTURE NOTES:
- Uses factory pattern for testing flexibility
- Jinja2 templates for server-side rendering
- Static files for CSS/JS assets
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from ib_daily_picker.store.database import DatabaseManager

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(db: DatabaseManager | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db: Optional database manager for testing. If None, uses global instance.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="IB Daily Picker",
        description="Stock opportunity identification using flow data and price action",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Store custom db if provided (for testing)
    if db is not None:
        app.state.db = db

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Setup templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    app.state.templates = templates

    # Register routers
    from ib_daily_picker.web.routes.api import analysis as api_analysis
    from ib_daily_picker.web.routes.api import backtest as api_backtest
    from ib_daily_picker.web.routes.api import flows as api_flows
    from ib_daily_picker.web.routes.api import journal as api_journal
    from ib_daily_picker.web.routes.api import signals as api_signals
    from ib_daily_picker.web.routes.api import stocks as api_stocks
    from ib_daily_picker.web.routes.api import strategies as api_strategies
    from ib_daily_picker.web.routes.api import watchlist as api_watchlist
    from ib_daily_picker.web.routes.pages import (
        analysis,
        backtest,
        dashboard,
        journal,
        stocks,
    )

    # API routes
    app.include_router(api_stocks.router, prefix="/api", tags=["stocks"])
    app.include_router(api_signals.router, prefix="/api", tags=["signals"])
    app.include_router(api_flows.router, prefix="/api", tags=["flows"])
    app.include_router(api_journal.router, prefix="/api", tags=["journal"])
    app.include_router(api_watchlist.router, prefix="/api", tags=["watchlist"])
    app.include_router(api_strategies.router, prefix="/api", tags=["strategies"])
    app.include_router(api_analysis.router, prefix="/api", tags=["analysis"])
    app.include_router(api_backtest.router, prefix="/api", tags=["backtest"])

    # Page routes
    app.include_router(dashboard.router, tags=["pages"])
    app.include_router(stocks.router, tags=["pages"])
    app.include_router(journal.router, tags=["pages"])
    app.include_router(analysis.router, tags=["pages"])
    app.include_router(backtest.router, tags=["pages"])

    # Health check
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "ib-daily-picker"}

    return app


# Template helper - can be imported by route modules
def get_templates() -> Jinja2Templates:
    """Get Jinja2 templates instance."""
    return Jinja2Templates(directory=TEMPLATES_DIR)

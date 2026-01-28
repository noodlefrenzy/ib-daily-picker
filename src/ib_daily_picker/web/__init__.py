"""
Web application module for IB Daily Picker.

PURPOSE: FastAPI web UI for the stock analysis tool
DEPENDENCIES: fastapi, uvicorn, jinja2

ARCHITECTURE NOTES:
- HTMX for interactive UI without complex JavaScript
- TradingView Lightweight Charts for financial charting
- SSE for real-time scan progress
- Reuses existing repositories and managers from CLI
"""

from ib_daily_picker.web.main import create_app

__all__ = ["create_app"]

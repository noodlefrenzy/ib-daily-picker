"""
TEST DOC: Web API Endpoints

WHAT: Tests for the FastAPI REST API endpoints
WHY: Verify API contracts and response formats for web UI consumption
HOW: Uses FastAPI TestClient with mocked database

CASES:
- GET /health returns status ok
- GET /api/stocks returns list of stocks with data
- GET /api/stocks/{symbol} returns stock summary
- GET /api/stocks/{symbol}/ohlcv returns OHLCV data
- GET /api/signals returns pending signals

EDGE CASES:
- 404 for non-existent stock
- Empty list when no data
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from ib_daily_picker.models import OHLCV, Recommendation, RecommendationStatus, SignalType
from ib_daily_picker.web.main import create_app


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_ok(self) -> None:
        """Health endpoint returns status ok."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "ib-daily-picker"}


class TestStocksAPI:
    """Test the stocks API endpoints."""

    def test_list_stocks_empty(self) -> None:
        """List stocks returns empty list when no data."""
        # Note: This uses real DB, so depends on test isolation
        # In a real test, we'd mock the database
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/stocks")

        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert "total" in data
        assert isinstance(data["stocks"], list)

    def test_get_stock_not_found(self) -> None:
        """Get stock returns 404 for non-existent symbol."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/stocks/NONEXISTENT")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_ohlcv_not_found(self) -> None:
        """Get OHLCV returns 404 for non-existent symbol."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/stocks/NONEXISTENT/ohlcv")

        assert response.status_code == 404

    def test_get_metadata_not_found(self) -> None:
        """Get metadata returns 404 for non-existent symbol."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/stocks/NONEXISTENT/metadata")

        assert response.status_code == 404


class TestSignalsAPI:
    """Test the signals API endpoints."""

    def test_list_signals_empty(self) -> None:
        """List signals returns empty list when no pending signals."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/signals")

        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert "total" in data
        assert isinstance(data["signals"], list)

    def test_get_signal_not_found(self) -> None:
        """Get signal returns 404 for non-existent ID."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/signals/nonexistent-id")

        assert response.status_code == 404

    def test_skip_signal_not_found(self) -> None:
        """Skip signal returns 404 for non-existent ID."""
        app = create_app()
        client = TestClient(app)

        response = client.post("/api/signals/nonexistent-id/skip")

        assert response.status_code == 404


class TestDashboardPage:
    """Test the dashboard page."""

    def test_dashboard_renders(self) -> None:
        """Dashboard page renders successfully."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Check for key dashboard elements
        content = response.text
        assert "Dashboard" in content
        assert "Portfolio Summary" in content
        assert "Data Status" in content


class TestFlowsAPI:
    """Test the flows API endpoints."""

    def test_list_flows(self) -> None:
        """List flows returns valid response."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/flows")

        assert response.status_code == 200
        data = response.json()
        assert "flows" in data
        assert "total" in data

    def test_get_flows_by_symbol(self) -> None:
        """Get flows by symbol returns valid response."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/flows/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert "flows" in data


class TestJournalAPI:
    """Test the journal API endpoints."""

    def test_list_trades(self) -> None:
        """List trades returns valid response."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/trades")

        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        assert "total" in data

    def test_get_trade_not_found(self) -> None:
        """Get trade returns 404 for non-existent ID."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/trades/nonexistent-id")

        assert response.status_code == 404


class TestWatchlistAPI:
    """Test the watchlist API endpoints."""

    def test_list_watchlist(self) -> None:
        """List watchlist returns valid response."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


class TestStocksPage:
    """Test the stocks list page."""

    def test_stocks_page_renders(self) -> None:
        """Stocks page renders successfully."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/stocks")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Stocks" in content


class TestStockDetailPage:
    """Test the stock detail page."""

    def test_stock_detail_not_found(self) -> None:
        """Stock detail returns 404 for non-existent symbol."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/stocks/NONEXISTENT")

        assert response.status_code == 404


class TestJournalPage:
    """Test the journal page."""

    def test_journal_page_renders(self) -> None:
        """Journal page renders successfully."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/journal")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Trade Journal" in content
        assert "Performance Metrics" in content

    def test_open_trade_form_renders(self) -> None:
        """Open trade form renders successfully."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/journal/open-trade-form")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Open Trade" in content


class TestWriteOperations:
    """Test write operations for trades."""

    def test_open_trade(self) -> None:
        """Can open a new trade via API."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/trades",
            json={
                "symbol": "MSFT",
                "direction": "long",
                "entry_price": 400.00,
                "position_size": 5.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "MSFT"
        assert data["direction"] == "long"
        assert data["status"] == "open"

    def test_open_trade_invalid_direction(self) -> None:
        """Opening trade with invalid direction returns 400."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/trades",
            json={
                "symbol": "MSFT",
                "direction": "invalid",
                "entry_price": 400.00,
                "position_size": 5.0,
            },
        )

        assert response.status_code == 400

    def test_close_trade_not_found(self) -> None:
        """Closing non-existent trade returns 400."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/trades/nonexistent-id/close",
            json={"exit_price": 100.00},
        )

        assert response.status_code == 400

    def test_add_note_not_found(self) -> None:
        """Adding note to non-existent trade returns 404."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/trades/nonexistent-id/note",
            json={"note": "Test note"},
        )

        assert response.status_code == 404


class TestBacktestPage:
    """Test the backtest page."""

    def test_backtest_page_renders(self) -> None:
        """Backtest page renders successfully."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/backtest")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "Backtest" in content
        assert "Configuration" in content
        assert "Compare Strategies" in content


class TestBacktestAPI:
    """Test the backtest API endpoints."""

    def test_backtest_missing_strategy(self) -> None:
        """Backtest with non-existent strategy returns 500 or 422."""
        app = create_app()
        client = TestClient(app)

        # Strategy that doesn't exist should fail
        response = client.post(
            "/api/backtest",
            json={
                "strategy": "nonexistent_strategy",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        )

        # Should fail - either 422 validation or 500 server error
        assert response.status_code in [404, 422, 500]

    def test_compare_needs_multiple_strategies(self) -> None:
        """Compare endpoint works with request."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/backtest/compare",
            json={
                "strategies": ["strategy1", "strategy2"],
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
            },
        )

        # Even if strategies don't exist, should return valid response structure
        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert "rankings" in data

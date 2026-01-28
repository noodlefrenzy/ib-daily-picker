"""
Unusual Whales flow alerts fetcher.

PURPOSE: Fetch options flow alerts from Unusual Whales API
DEPENDENCIES: httpx

ARCHITECTURE NOTES:
- Rate limiting: 120 req/min
- Cache TTL: 15-30 minutes for flow alerts
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from ib_daily_picker.config import get_settings
from ib_daily_picker.fetchers.base import FetchResult, FetchStatus
from ib_daily_picker.models import (
    AlertType,
    FlowAlert,
    FlowAlertBatch,
    FlowDirection,
    OptionType,
    Sentiment,
)

logger = logging.getLogger(__name__)

# Unusual Whales API base URL
UW_API_BASE = "https://api.unusualwhales.com"


class UnusualWhalesFetcher:
    """Fetcher for Unusual Whales flow alerts API."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with optional API key.

        Args:
            api_key: UW API key (defaults to config)
        """
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: datetime | None = None
        self._min_request_interval = timedelta(milliseconds=500)  # 120 req/min = 500ms

    @property
    def name(self) -> str:
        """Return fetcher name."""
        return "unusual_whales"

    @property
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return self._get_api_key() is not None

    def _get_api_key(self) -> str | None:
        """Get API key from instance or config."""
        if self._api_key:
            return self._api_key
        settings = get_settings()
        return settings.api.unusual_whales_api_key

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            api_key = self._get_api_key()
            if not api_key:
                raise ValueError("Unusual Whales API key not configured")

            self._client = httpx.AsyncClient(
                base_url=UW_API_BASE,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time:
            elapsed = datetime.utcnow() - self._last_request_time
            if elapsed < self._min_request_interval:
                wait_time = (self._min_request_interval - elapsed).total_seconds()
                await asyncio.sleep(wait_time)
        self._last_request_time = datetime.utcnow()

    async def fetch_flow_alerts(
        self,
        symbols: list[str] | None = None,
        min_premium: Decimal | None = None,
        limit: int = 100,
    ) -> FetchResult[FlowAlertBatch]:
        """Fetch recent flow alerts.

        Args:
            symbols: Filter by symbols (optional)
            min_premium: Minimum premium filter (optional)
            limit: Maximum number of alerts to return

        Returns:
            FetchResult containing FlowAlertBatch
        """
        started_at = datetime.utcnow()

        if not self.is_available:
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=["Unusual Whales API key not configured"],
            )

        try:
            await self._rate_limit()

            client = await self._get_client()

            # Build query parameters
            params: dict[str, Any] = {"limit": limit}
            if symbols:
                params["symbols"] = ",".join(s.upper() for s in symbols)
            if min_premium:
                params["min_premium"] = float(min_premium)

            logger.info(f"UW API call: flow-alerts with params {params}")

            response = await client.get("/api/option-trades/flow-alerts", params=params)
            response.raise_for_status()

            data = response.json()
            alerts = self._parse_alerts(data)

            logger.info(f"UW API: Retrieved {len(alerts)} flow alerts")

            return FetchResult(
                data=FlowAlertBatch(alerts=alerts, fetched_at=datetime.utcnow()),
                status=FetchStatus.SUCCESS,
                source=self.name,
                started_at=started_at,
            )

        except httpx.HTTPStatusError as e:
            status = (
                FetchStatus.RATE_LIMITED if e.response.status_code == 429 else FetchStatus.ERROR
            )
            logger.error(f"UW API HTTP error: {e.response.status_code}")
            return FetchResult(
                data=None,
                status=status,
                source=self.name,
                started_at=started_at,
                errors=[f"HTTP {e.response.status_code}: {e.response.text}"],
            )
        except Exception as e:
            logger.exception(f"UW API error: {e}")
            return FetchResult(
                data=None,
                status=FetchStatus.ERROR,
                source=self.name,
                started_at=started_at,
                errors=[str(e)],
            )

    async def fetch_flow_alerts_for_symbol(
        self,
        symbol: str,
        limit: int = 50,
    ) -> FetchResult[list[FlowAlert]]:
        """Fetch flow alerts for a specific symbol.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of alerts

        Returns:
            FetchResult containing list of FlowAlerts
        """
        result = await self.fetch_flow_alerts(symbols=[symbol], limit=limit)

        if result.is_success and result.data:
            return FetchResult(
                data=result.data.alerts,
                status=result.status,
                source=result.source,
                started_at=result.started_at,
                completed_at=result.completed_at,
            )

        return FetchResult(
            data=None,
            status=result.status,
            source=result.source,
            started_at=result.started_at,
            completed_at=result.completed_at,
            errors=result.errors,
        )

    def _parse_alerts(self, data: dict[str, Any]) -> list[FlowAlert]:
        """Parse API response into FlowAlert models."""
        alerts = []

        # Handle different response structures
        alert_data = data.get("data", data.get("alerts", []))
        if isinstance(alert_data, dict):
            alert_data = alert_data.get("alerts", [])

        for item in alert_data:
            try:
                alert = self._parse_single_alert(item)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                logger.warning(f"Failed to parse alert: {e}")
                continue

        return alerts

    def _parse_single_alert(self, item: dict[str, Any]) -> FlowAlert | None:
        """Parse a single alert from API response."""
        # Generate ID if not present
        alert_id = item.get("id") or f"uw_{item.get('timestamp', datetime.utcnow().timestamp())}"

        # Parse timestamp
        timestamp = item.get("timestamp") or item.get("date")
        if isinstance(timestamp, str):
            try:
                alert_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                alert_time = datetime.utcnow()
        elif isinstance(timestamp, (int, float)):
            alert_time = datetime.fromtimestamp(timestamp)
        else:
            alert_time = datetime.utcnow()

        # Parse direction/sentiment
        sentiment_str = (item.get("sentiment") or item.get("direction") or "").lower()
        if "bull" in sentiment_str:
            direction = FlowDirection.BULLISH
            sentiment = Sentiment.BULLISH
        elif "bear" in sentiment_str:
            direction = FlowDirection.BEARISH
            sentiment = Sentiment.BEARISH
        else:
            direction = FlowDirection.NEUTRAL
            sentiment = Sentiment.NEUTRAL

        # Parse option type
        opt_type_str = (item.get("option_type") or item.get("put_call") or "").lower()
        option_type = (
            OptionType.CALL
            if "call" in opt_type_str
            else OptionType.PUT
            if "put" in opt_type_str
            else None
        )

        # Parse alert type
        alert_type_str = (item.get("alert_type") or item.get("type") or "unusual_volume").lower()
        try:
            alert_type = AlertType(alert_type_str.replace(" ", "_").replace("-", "_"))
        except ValueError:
            alert_type = AlertType.OTHER

        # Parse expiration
        exp_str = item.get("expiration") or item.get("expiry")
        expiration = None
        if exp_str:
            try:
                if isinstance(exp_str, str):
                    expiration = date.fromisoformat(exp_str[:10])
                elif isinstance(exp_str, date):
                    expiration = exp_str
            except ValueError:
                pass

        return FlowAlert(
            id=str(alert_id),
            symbol=item.get("symbol", "").upper(),
            alert_time=alert_time,
            alert_type=alert_type,
            direction=direction,
            premium=Decimal(str(item["premium"])) if item.get("premium") else None,
            volume=item.get("volume"),
            open_interest=item.get("open_interest") or item.get("oi"),
            strike=Decimal(str(item["strike"])) if item.get("strike") else None,
            expiration=expiration,
            option_type=option_type,
            sentiment=sentiment,
            raw_data=item,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton instance
_uw_fetcher: UnusualWhalesFetcher | None = None


def get_unusual_whales_fetcher() -> UnusualWhalesFetcher:
    """Get or create singleton UnusualWhalesFetcher instance."""
    global _uw_fetcher
    if _uw_fetcher is None:
        _uw_fetcher = UnusualWhalesFetcher()
    return _uw_fetcher


def reset_unusual_whales_fetcher() -> None:
    """Reset singleton (for testing)."""
    global _uw_fetcher
    _uw_fetcher = None

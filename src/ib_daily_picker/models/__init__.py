"""
Models package - Domain models and data structures.

PURPOSE: Pydantic models for Stock, Flow, FlowAlert, Trade, etc.
"""

from ib_daily_picker.models.flow import (
    AlertType,
    FlowAlert,
    FlowAlertBatch,
    FlowDirection,
    OptionType,
    Sentiment,
)
from ib_daily_picker.models.recommendation import (
    Recommendation,
    RecommendationBatch,
    RecommendationStatus,
    SignalType,
)
from ib_daily_picker.models.stock import OHLCV, OHLCVBatch, StockMetadata, StockWithData
from ib_daily_picker.models.trade import (
    Trade,
    TradeDirection,
    TradeMetrics,
    TradeStatus,
)

__all__ = [
    # Stock
    "OHLCV",
    "OHLCVBatch",
    "StockMetadata",
    "StockWithData",
    # Flow
    "AlertType",
    "FlowAlert",
    "FlowAlertBatch",
    "FlowDirection",
    "OptionType",
    "Sentiment",
    # Recommendation
    "Recommendation",
    "RecommendationBatch",
    "RecommendationStatus",
    "SignalType",
    # Trade
    "Trade",
    "TradeDirection",
    "TradeMetrics",
    "TradeStatus",
]

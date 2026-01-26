"""
Journal package - Trade journaling and metrics.

PURPOSE: Track trades, calculate metrics, and export journal data
"""

from ib_daily_picker.journal.manager import (
    JournalManager,
    get_journal_manager,
    reset_journal_manager,
)
from ib_daily_picker.journal.metrics import (
    DrawdownInfo,
    ExtendedMetrics,
    StrategyAnalysis,
    StreakInfo,
    TimeAnalysis,
    calculate_extended_metrics,
    filter_trades,
)

__all__ = [
    # Manager
    "JournalManager",
    "get_journal_manager",
    "reset_journal_manager",
    # Metrics
    "DrawdownInfo",
    "ExtendedMetrics",
    "StrategyAnalysis",
    "StreakInfo",
    "TimeAnalysis",
    "calculate_extended_metrics",
    "filter_trades",
]

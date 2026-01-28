"""
FastAPI dependency injection.

PURPOSE: Provide dependency injection for database, settings, and managers
DEPENDENCIES: fastapi

ARCHITECTURE NOTES:
- Reuses global instances from CLI (get_db_manager, get_settings, etc.)
- Async-compatible wrappers for FastAPI Depends()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ib_daily_picker.config import get_settings
from ib_daily_picker.journal import get_journal_manager
from ib_daily_picker.store.database import get_db_manager

if TYPE_CHECKING:
    from ib_daily_picker.config import Settings
    from ib_daily_picker.journal import JournalManager
    from ib_daily_picker.store.database import DatabaseManager


def get_settings_dep() -> Settings:
    """Dependency: get app settings."""
    return get_settings()


def get_db() -> DatabaseManager:
    """Dependency: get database manager."""
    return get_db_manager()


def get_journal() -> JournalManager:
    """Dependency: get journal manager."""
    return get_journal_manager()

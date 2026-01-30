"""
Discord bot package for IB Daily Picker.

PURPOSE: Discord interface for stock analysis and alerts
DEPENDENCIES: discord.py
"""

from ib_daily_picker.discord.bot import IBPickerBot, run_bot

__all__ = ["IBPickerBot", "run_bot"]

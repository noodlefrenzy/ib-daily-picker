"""
LLM package - Natural language to strategy conversion.

PURPOSE: Convert English descriptions to YAML strategies using LLM
"""

from ib_daily_picker.llm.client import (
    AnthropicClient,
    LLMClient,
    OllamaClient,
    get_llm_client,
)
from ib_daily_picker.llm.strategy_converter import (
    LLMStrategySpec,
    StrategyConverter,
    convert_description_to_strategy,
    convert_description_to_yaml,
)

__all__ = [
    # Client
    "AnthropicClient",
    "LLMClient",
    "OllamaClient",
    "get_llm_client",
    # Converter
    "LLMStrategySpec",
    "StrategyConverter",
    "convert_description_to_strategy",
    "convert_description_to_yaml",
]

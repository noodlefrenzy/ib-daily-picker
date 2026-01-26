"""
Tests for LLM strategy converter.

TEST DOC: Strategy Converter

WHAT: Tests for converting natural language to strategy YAML
WHY: Ensure reliable strategy generation from descriptions
HOW: Mock LLM client, test conversion logic

CASES:
- LLM spec to Strategy conversion
- Strategy to YAML serialization
- Various indicator types
- Flow conditions

EDGE CASES:
- Unknown indicator types
- Invalid operators
- Missing fields
"""

from typing import Type
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from ib_daily_picker.analysis.strategy_schema import (
    ConditionLogic,
    ConditionOperator,
    IndicatorType,
    RiskProfileName,
)
from ib_daily_picker.llm.client import LLMClient
from ib_daily_picker.llm.strategy_converter import (
    LLMExitRule,
    LLMFlowCondition,
    LLMIndicator,
    LLMIndicatorCondition,
    LLMStrategySpec,
    StrategyConverter,
)


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self, spec: LLMStrategySpec):
        self._spec = spec

    def complete(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> BaseModel:
        return self._spec

    def complete_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        return "Mock response"


class TestLLMStrategySpec:
    """Tests for LLM strategy spec model."""

    def test_basic_spec_creation(self):
        """Can create basic spec."""
        spec = LLMStrategySpec(
            name="Test Strategy",
            description="A test strategy",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=30),
            ],
        )

        assert spec.name == "Test Strategy"
        assert len(spec.indicators) == 1
        assert len(spec.indicator_conditions) == 1

    def test_spec_with_flow_conditions(self):
        """Can create spec with flow conditions."""
        spec = LLMStrategySpec(
            name="Flow Strategy",
            description="Uses flow data",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            flow_conditions=[
                LLMFlowCondition(direction="bullish", min_premium=100000),
            ],
        )

        assert len(spec.flow_conditions) == 1
        assert spec.flow_conditions[0].direction == "bullish"

    def test_spec_with_exit_rules(self):
        """Can create spec with exit rules."""
        spec = LLMStrategySpec(
            name="Exit Strategy",
            description="Has exit rules",
            indicators=[],
            take_profit=LLMExitRule(type="percentage", value=5.0),
            stop_loss=LLMExitRule(type="atr_multiple", value=2.0),
        )

        assert spec.take_profit is not None
        assert spec.take_profit.type == "percentage"
        assert spec.stop_loss is not None
        assert spec.stop_loss.type == "atr_multiple"


class TestStrategyConverter:
    """Tests for strategy converter."""

    def test_convert_basic_strategy(self):
        """Can convert basic LLM spec to Strategy."""
        spec = LLMStrategySpec(
            name="RSI Oversold",
            description="Buy when RSI is oversold",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=30),
            ],
            entry_logic="all",
            risk_profile="moderate",
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("Buy when RSI below 30")

        assert strategy.name == "RSI Oversold"
        assert len(strategy.indicators) == 1
        assert strategy.indicators[0].type == IndicatorType.RSI
        assert len(strategy.entry.conditions) == 1
        assert strategy.entry.logic == ConditionLogic.ALL

    def test_convert_with_flow_conditions(self):
        """Can convert strategy with flow conditions."""
        spec = LLMStrategySpec(
            name="RSI with Flow",
            description="RSI oversold with bullish flow",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=35),
            ],
            flow_conditions=[
                LLMFlowCondition(direction="bullish", min_premium=50000),
            ],
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("RSI below 35 with bullish flow")

        assert len(strategy.entry.conditions) == 2
        # Check for both indicator and flow conditions
        has_indicator = any(hasattr(c, "indicator") for c in strategy.entry.conditions)
        has_flow = any(hasattr(c, "direction") for c in strategy.entry.conditions)
        assert has_indicator
        assert has_flow

    def test_convert_with_exit_rules(self):
        """Can convert strategy with exit rules."""
        spec = LLMStrategySpec(
            name="Full Strategy",
            description="Complete strategy with exits",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=30),
            ],
            take_profit=LLMExitRule(type="percentage", value=5.0),
            stop_loss=LLMExitRule(type="atr_multiple", value=2.0),
            trailing_stop=LLMExitRule(type="percentage", value=3.0),
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("RSI strategy with 5% target and 2 ATR stop")

        assert strategy.exit.take_profit is not None
        assert strategy.exit.take_profit.value == 5.0
        assert strategy.exit.stop_loss is not None
        assert strategy.exit.stop_loss.value == 2.0
        assert strategy.exit.trailing_stop is not None

    def test_unknown_indicator_defaults_to_rsi(self):
        """Unknown indicator type defaults to RSI."""
        spec = LLMStrategySpec(
            name="Unknown Indicator",
            description="Uses unknown indicator",
            indicators=[
                LLMIndicator(name="unknown_14", type="UNKNOWN_TYPE", period=14),
            ],
            indicator_conditions=[],
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("Some strategy")

        assert strategy.indicators[0].type == IndicatorType.RSI

    def test_unknown_operator_defaults_to_gt(self):
        """Unknown operator defaults to greater than."""
        spec = LLMStrategySpec(
            name="Unknown Operator",
            description="Uses unknown operator",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="invalid", value=50),
            ],
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("Some strategy")

        cond = strategy.entry.conditions[0]
        assert hasattr(cond, "operator")
        assert cond.operator == ConditionOperator.GT

    def test_unknown_risk_profile_defaults_to_moderate(self):
        """Unknown risk profile defaults to moderate."""
        spec = LLMStrategySpec(
            name="Unknown Risk",
            description="Uses unknown risk profile",
            indicators=[],
            indicator_conditions=[],
            risk_profile="super_aggressive",  # Invalid
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("Some strategy")

        assert strategy.risk.profile == RiskProfileName.MODERATE


class TestStrategyToYaml:
    """Tests for Strategy to YAML conversion."""

    def test_strategy_to_yaml(self):
        """Can convert strategy to YAML."""
        spec = LLMStrategySpec(
            name="YAML Test",
            description="Test YAML output",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=30),
            ],
            take_profit=LLMExitRule(type="percentage", value=5.0),
            risk_profile="aggressive",
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        yaml_str = converter.convert_to_yaml("Test strategy")

        # Check YAML structure
        assert "strategy:" in yaml_str
        assert "name: YAML Test" in yaml_str
        assert "indicators:" in yaml_str
        assert "rsi_14" in yaml_str
        assert "entry:" in yaml_str
        assert "exit:" in yaml_str
        assert "risk:" in yaml_str

    def test_yaml_roundtrip(self):
        """YAML output can be parsed back."""
        import yaml

        spec = LLMStrategySpec(
            name="Roundtrip Test",
            description="Test roundtrip",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=30),
            ],
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        yaml_str = converter.convert_to_yaml("Test")
        parsed = yaml.safe_load(yaml_str)

        assert parsed["strategy"]["name"] == "Roundtrip Test"
        assert len(parsed["indicators"]) == 1
        assert parsed["indicators"][0]["name"] == "rsi_14"


class TestMultipleIndicators:
    """Tests for strategies with multiple indicators."""

    def test_multiple_indicators(self):
        """Can handle multiple indicators."""
        spec = LLMStrategySpec(
            name="Multi-Indicator",
            description="Uses multiple indicators",
            indicators=[
                LLMIndicator(name="rsi_14", type="RSI", period=14),
                LLMIndicator(name="sma_50", type="SMA", period=50),
                LLMIndicator(name="atr_14", type="ATR", period=14),
            ],
            indicator_conditions=[
                LLMIndicatorCondition(indicator="rsi_14", operator="lt", value=35),
                LLMIndicatorCondition(indicator="sma_50", operator="gt", value="price"),
            ],
        )

        mock_client = MockLLMClient(spec)
        converter = StrategyConverter(client=mock_client)

        strategy = converter.convert("Multi-indicator strategy")

        assert len(strategy.indicators) == 3
        indicator_types = [i.type for i in strategy.indicators]
        assert IndicatorType.RSI in indicator_types
        assert IndicatorType.SMA in indicator_types
        assert IndicatorType.ATR in indicator_types

"""
Analysis package - Strategy evaluation and signal generation.

PURPOSE: YAML strategy loading, indicator calculations, and trade signals
"""

from ib_daily_picker.analysis.evaluator import (
    ConditionResult,
    EvaluationResult,
    StrategyEvaluator,
)
from ib_daily_picker.analysis.indicators import (
    BollingerResult,
    IndicatorCalculator,
    IndicatorResult,
    MACDResult,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_volume_sma,
    ohlcv_to_dataframe,
)
from ib_daily_picker.analysis.signals import (
    RISK_PROFILES,
    MultiStrategySignalGenerator,
    SignalGenerator,
)
from ib_daily_picker.analysis.strategy_loader import (
    StrategyLoader,
    StrategyValidationError,
    get_strategy_loader,
    reset_strategy_loader,
)
from ib_daily_picker.analysis.strategy_schema import (
    ConditionLogic,
    ConditionOperator,
    EntryConfig,
    ExitConfig,
    ExitTarget,
    ExitType,
    FlowCondition,
    IndicatorCondition,
    IndicatorConfig,
    IndicatorType,
    RiskConfig,
    RiskProfileName,
    Strategy,
    StrategyMetadata,
)

__all__ = [
    # Evaluator
    "ConditionResult",
    "EvaluationResult",
    "StrategyEvaluator",
    # Indicators
    "BollingerResult",
    "IndicatorCalculator",
    "IndicatorResult",
    "MACDResult",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_ema",
    "calculate_macd",
    "calculate_rsi",
    "calculate_sma",
    "calculate_volume_sma",
    "ohlcv_to_dataframe",
    # Signals
    "RISK_PROFILES",
    "MultiStrategySignalGenerator",
    "SignalGenerator",
    # Strategy loader
    "StrategyLoader",
    "StrategyValidationError",
    "get_strategy_loader",
    "reset_strategy_loader",
    # Strategy schema
    "ConditionLogic",
    "ConditionOperator",
    "EntryConfig",
    "ExitConfig",
    "ExitTarget",
    "ExitType",
    "FlowCondition",
    "IndicatorCondition",
    "IndicatorConfig",
    "IndicatorType",
    "RiskConfig",
    "RiskProfileName",
    "Strategy",
    "StrategyMetadata",
]

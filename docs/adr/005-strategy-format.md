# ADR-005: Strategy Definition Format (YAML)

## Status
Accepted

## Context
Trading strategies need to be:
- Defined by users without writing Python code
- Validated before execution
- Version controlled
- Shareable and readable

The strategy must specify:
- Technical indicators to calculate
- Entry conditions (indicator thresholds, flow signals)
- Exit rules (take profit, stop loss, trailing stop)
- Risk parameters

Options evaluated:
- **YAML**: Human-readable, widely understood
- **JSON**: Machine-friendly, verbose for humans
- **TOML**: Good for config, less common for complex structures
- **Python DSL**: Powerful but requires code execution
- **GUI builder**: Accessible but complex to implement

## Decision
Use **YAML files** with **Pydantic validation** for strategy definitions.

Example strategy:
```yaml
strategy:
  name: "RSI Momentum with Flow Confirmation"
  version: "1.0.0"
  description: "Buy oversold stocks with bullish flow"

indicators:
  - name: "rsi_14"
    type: "RSI"
    params:
      period: 14
      source: "close"

entry:
  conditions:
    - type: "indicator_threshold"
      indicator: "rsi_14"
      operator: "lt"
      value: 35
    - type: "flow_signal"
      direction: "bullish"
      min_premium: 100000
  logic: "all"  # all conditions must be true

exit:
  take_profit:
    type: "percentage"
    value: 5.0
  stop_loss:
    type: "atr_multiple"
    value: 2.0

risk:
  profile: "aggressive"
```

## Supported Components

**Indicator Types**: RSI, SMA, EMA, ATR, MACD, BOLLINGER, VWAP, VOLUME_SMA

**Condition Operators**: lt, le, gt, ge, eq, ne, cross_above, cross_below

**Exit Types**: percentage, atr_multiple, fixed_price, trailing_stop

**Risk Profiles**: conservative, moderate, aggressive

## Consequences

### Positive
- **Human readable**: Easy to write, review, and understand
- **Version controllable**: Text files work well with git
- **Validated**: Pydantic catches errors before execution
- **Extensible**: Easy to add new indicator types or conditions

### Negative
- **Limited expressiveness**: Complex logic requires multiple conditions
- **No code execution**: Can't express arbitrary Python logic
- **Schema coupling**: Changes to schema may break existing strategies
- **Learning curve**: Users must learn the YAML schema

### Neutral
- Strategies stored in `strategies/` directory by default
- LLM can convert natural language to this format (ADR-006)

## Alternatives Considered

1. **Python DSL**: More powerful but security concerns with code execution
2. **JSON**: Valid but YAML is more readable for humans
3. **GUI builder**: Would be nice but high implementation effort
4. **Database storage**: Loses version control benefits

## References
- Schema: `src/ib_daily_picker/analysis/strategy_schema.py`
- Loader: `src/ib_daily_picker/analysis/strategy_loader.py`
- Example: `strategies/example_rsi_flow.yaml`

# ADR-006: LLM Integration (Anthropic + Ollama)

## Status
Accepted

## Context
Writing YAML strategy files requires understanding the schema. To lower the barrier to entry, we want users to describe strategies in plain English and have them converted to valid YAML.

Requirements:
- Convert natural language to structured YAML
- Support cloud LLM (high quality) and local LLM (privacy, cost)
- Reliable structured output (not free-form text)
- Configurable backend

Options evaluated:
- **Direct API calls**: Full control but complex structured output handling
- **LangChain**: Popular but heavy dependency, overkill for this use case
- **Instructor**: Lightweight, Pydantic-based structured output
- **Outlines**: Good for local models, less cloud support

## Decision
Use **Instructor** library with support for **Anthropic Claude** (cloud) and **Ollama** (local).

**Instructor** chosen because:
- Pydantic models define output structure
- Works with multiple LLM backends
- Lightweight dependency
- Automatic retries and validation

**Dual backend** approach:
- **Anthropic Claude**: High-quality results, pay-per-use
- **Ollama**: Free, private, runs locally, good for iteration

## Implementation

```python
# Natural language input
"Buy when RSI is below 30 with bullish options flow,
 take profit at 5%, stop loss at 2 ATR"

# Converted to valid YAML strategy
strategy:
  name: "RSI Oversold with Flow"
  ...
indicators:
  - name: "rsi_14"
    type: "RSI"
    params: {period: 14}
entry:
  conditions:
    - type: "indicator_threshold"
      indicator: "rsi_14"
      operator: "lt"
      value: 30
    - type: "flow_signal"
      direction: "bullish"
...
```

## Configuration

```python
# Environment variables
LLM_PROVIDER=anthropic  # or "ollama"
ANTHROPIC_API_KEY=sk-...
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# Or via config
llm_provider: str = "anthropic"
anthropic_model: str = "claude-sonnet-4-20250514"
ollama_model: str = "llama2"
```

## Consequences

### Positive
- **Accessibility**: Users don't need to learn YAML schema
- **Flexibility**: Switch between cloud/local as needed
- **Validation**: Output is validated against Pydantic models
- **Iteration speed**: Quick to try strategy ideas

### Negative
- **Cost**: Anthropic API calls cost money
- **Latency**: LLM calls add seconds to strategy creation
- **Quality variance**: Local models may produce lower quality output
- **Dependency**: Adds instructor, anthropic, ollama dependencies

### Neutral
- Conversion is optional - users can still write YAML manually
- Invalid LLM output falls back to sensible defaults with warnings
- Temperature set low (0.3) for consistent output

## Alternatives Considered

1. **No LLM**: Users write YAML manually - higher barrier to entry
2. **LangChain**: Too heavy for this single use case
3. **Fine-tuned model**: Would need training data, maintenance burden
4. **Template system**: Less flexible than natural language

## References
- Instructor documentation: https://instructor-ai.github.io/instructor/
- Implementation: `src/ib_daily_picker/llm/client.py`
- Converter: `src/ib_daily_picker/llm/strategy_converter.py`
- Pydantic models: `src/ib_daily_picker/llm/strategy_converter.py` (LLMStrategySpec)

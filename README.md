# IB Daily Picker

A Python CLI tool that identifies promising stock trading opportunities by correlating market price data with options flow signals from Unusual Whales, applying configurable trading strategies, and maintaining a journal for backtesting.

## Features

- **Stock Data Fetching**: Pulls OHLCV data from yfinance (primary) with Finnhub fallback
- **Flow Data Integration**: Fetches options flow alerts from Unusual Whales API
- **Technical Indicators**: RSI, SMA, EMA, ATR, MACD, Bollinger Bands, VWAP
- **YAML Strategy Definitions**: Define trading strategies in human-readable YAML
- **Natural Language Strategies**: Use LLM (Claude or Ollama) to convert English descriptions to YAML
- **Trade Journal**: Track recommendations, executions, and outcomes
- **Backtesting Engine**: Evaluate strategies against historical data with walk-forward validation
- **Risk Profiles**: Conservative, moderate, and aggressive position sizing

## Installation

```bash
# Clone the repository
git clone https://github.com/noodlefrenzy/ib-daily-picker.git
cd ib-daily-picker

# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
ib-picker --help
```

## Quick Start

```bash
# 1. Initialize configuration
ib-picker config init

# 2. Fetch stock data for some tickers
ib-picker fetch stocks --tickers AAPL,MSFT,GOOGL,NVDA

# 3. Validate the example strategy
ib-picker strategy validate strategies/example_rsi_flow.yaml

# 4. View available strategies
ib-picker strategy list

# 5. Run a backtest
ib-picker backtest run example_rsi_flow --from 2024-01-01 --to 2024-12-31
```

## Configuration

Configuration is stored in `~/.ib-picker/config.toml` or via environment variables.

### Environment Variables

```bash
# Stock Data (optional - yfinance works without keys)
FINNHUB_API_KEY=your_finnhub_key

# Flow Data (required for flow features)
UNUSUAL_WHALES_API_KEY=your_uw_key

# LLM (optional - for natural language strategy conversion)
LLM_PROVIDER=anthropic  # or "ollama"
ANTHROPIC_API_KEY=your_anthropic_key
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2

# Database (optional - defaults shown)
IB_PICKER_DATA_DIR=~/.ib-picker/data
```

### View Current Configuration

```bash
ib-picker config show
```

## CLI Commands

### Data Fetching

```bash
# Fetch stock price data
ib-picker fetch stocks --tickers AAPL,MSFT,GOOGL
ib-picker fetch stocks --sector Technology --limit 50

# Fetch flow alerts (requires Unusual Whales API key)
ib-picker fetch flows --tickers AAPL,MSFT
ib-picker fetch flows --min-premium 100000

# Check data coverage
ib-picker fetch status
```

### Strategy Management

```bash
# List available strategies
ib-picker strategy list

# Validate a strategy file
ib-picker strategy validate strategies/my_strategy.yaml

# Show strategy details
ib-picker strategy show example_rsi_flow

# Create strategy from natural language (requires LLM)
ib-picker strategy create my_strategy --from-english "Buy when RSI below 30 with bullish flow, 5% take profit, 2 ATR stop loss"
```

### Analysis

```bash
# Run analysis with a strategy
ib-picker analyze --strategy example_rsi_flow --tickers AAPL,MSFT

# View recent signals
ib-picker signals --limit 20
```

### Trade Journal

```bash
# List journal entries
ib-picker journal list
ib-picker journal list --status open

# Open a new trade
ib-picker journal open AAPL --entry-price 150.00 --direction long

# Execute a recommendation
ib-picker journal execute <recommendation-id> --price 150.00

# Close a trade
ib-picker journal close <trade-id> --exit-price 157.50

# Add notes to a trade
ib-picker journal note <trade-id> "Closed early due to earnings"

# View performance metrics
ib-picker journal metrics

# Export trades
ib-picker journal export --format csv --output trades.csv
```

### Backtesting

```bash
# Run backtest
ib-picker backtest run example_rsi_flow --from 2024-01-01 --to 2024-12-31

# Compare strategies
ib-picker backtest compare strategy1,strategy2 --from 2024-01-01 --to 2024-12-31

# Custom parameters
ib-picker backtest run my_strategy \
  --from 2023-01-01 \
  --to 2024-12-31 \
  --initial-capital 100000 \
  --position-size 0.1 \
  --output results.json
```

### Database

```bash
# Show database status
ib-picker db status

# Export data
ib-picker db export --format csv --output data_export/
```

## Strategy Format

Strategies are defined in YAML files. See `strategies/example_rsi_flow.yaml` for a complete example.

```yaml
strategy:
  name: "RSI Momentum with Flow Confirmation"
  version: "1.0.0"
  description: "Buy oversold stocks with bullish options flow"

indicators:
  - name: "rsi_14"
    type: "RSI"
    params:
      period: 14
      source: "close"
  - name: "sma_50"
    type: "SMA"
    params:
      period: 50

entry:
  conditions:
    - type: "indicator_threshold"
      indicator: "rsi_14"
      operator: "lt"
      value: 35
    - type: "flow_signal"
      direction: "bullish"
      min_premium: 100000
  logic: "all"  # "all" = AND, "any" = OR

exit:
  take_profit:
    type: "percentage"
    value: 5.0
  stop_loss:
    type: "atr_multiple"
    value: 2.0
  trailing_stop:
    type: "percentage"
    value: 3.0

risk:
  profile: "aggressive"  # conservative, moderate, aggressive
```

### Supported Indicators

| Type | Description | Parameters |
|------|-------------|------------|
| `RSI` | Relative Strength Index | `period`, `source` |
| `SMA` | Simple Moving Average | `period`, `source` |
| `EMA` | Exponential Moving Average | `period`, `source` |
| `ATR` | Average True Range | `period` |
| `MACD` | Moving Average Convergence Divergence | `fast`, `slow`, `signal` |
| `BOLLINGER` | Bollinger Bands | `period`, `std_dev` |
| `VWAP` | Volume Weighted Average Price | - |
| `VOLUME_SMA` | Volume Simple Moving Average | `period` |

### Condition Operators

| Operator | Description |
|----------|-------------|
| `lt` | Less than |
| `le` | Less than or equal |
| `gt` | Greater than |
| `ge` | Greater than or equal |
| `eq` | Equal |
| `ne` | Not equal |
| `cross_above` | Crosses above |
| `cross_below` | Crosses below |

### Risk Profiles

| Profile | Risk per Trade | Min R:R | Max Positions |
|---------|---------------|---------|---------------|
| `conservative` | 0.5% | 3.0 | 5 |
| `moderate` | 1.0% | 2.0 | 8 |
| `aggressive` | 2.0% | 1.5 | 10 |

## Architecture

```
ib-daily-picker/
├── src/ib_daily_picker/
│   ├── cli.py              # Typer CLI entry points
│   ├── config.py           # pydantic-settings configuration
│   ├── analysis/           # Strategy evaluation, indicators, signals
│   ├── backtest/           # Backtesting engine and metrics
│   ├── fetchers/           # Data fetchers (yfinance, Finnhub, UW)
│   ├── journal/            # Trade journal management
│   ├── llm/                # LLM strategy conversion
│   ├── models/             # Domain models (Stock, Flow, Trade)
│   └── store/              # Database layer (DuckDB + SQLite)
├── strategies/             # YAML strategy definitions
├── tests/                  # Test suite (111 tests)
└── docs/adr/               # Architecture Decision Records
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| CLI | Typer + Rich |
| Config | pydantic-settings |
| Stock Data | yfinance (primary) + Finnhub (fallback) |
| Flow Data | Unusual Whales API |
| Database | DuckDB (analytics) + SQLite (state) |
| Validation | Pydantic v2 |
| LLM | Instructor (Anthropic + Ollama) |
| Testing | pytest |

See [docs/adr/](docs/adr/) for detailed architecture decisions.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov

# Type checking
mypy src/

# Linting
ruff check .

# Formatting
ruff format .
```

## Data Storage

Data is stored in `~/.ib-picker/data/` by default:

- `analytics.duckdb` - OHLCV prices, flow alerts, recommendations (DuckDB)
- `state.sqlite` - Sync tracking, configuration (SQLite)

The dual-database architecture optimizes for:
- **DuckDB**: Columnar storage for fast analytical queries on time-series data
- **SQLite**: ACID guarantees for application state

## API Keys

### Finnhub (Optional)
- Free tier: 60 requests/minute
- Register at: https://finnhub.io/
- Used as fallback when yfinance fails

### Unusual Whales (Required for flow features)
- Subscription required for API access
- Register at: https://unusualwhales.com/
- Rate limit: 120 requests/minute

### Anthropic (Optional, for LLM features)
- Pay-per-use API
- Register at: https://console.anthropic.com/
- Used for natural language to strategy conversion

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite: `pytest`
5. Submit a pull request

See [CLAUDE.md](CLAUDE.md) for development guidelines and conventions.

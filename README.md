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
- **Web Interface**: Browser-based UI with dashboard, trade forms, and REST API

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
# Fetch stock price data by ticker
ib-picker fetch stocks --tickers AAPL,MSFT,GOOGL

# Fetch by sector name
ib-picker fetch stocks --sector Technology --limit 20

# Fetch stocks in the same sector as a reference ticker
ib-picker fetch stocks --same-sector-as NVDA --limit 10

# Fetch flow alerts (requires Unusual Whales API key)
ib-picker fetch flows --tickers AAPL,MSFT
ib-picker fetch flows --min-premium 100000

# Check data coverage
ib-picker fetch status
```

**Available sectors:** Technology, Consumer Cyclical, Healthcare, Financial, Communication Services, Consumer Defensive, Energy, Industrials, Basic Materials, Real Estate, Utilities

**Fetch status meanings:**
- `success` (green) - New data fetched and stored
- `up_to_date` (yellow) - Data already current, no new data available yet
- `not_found` (red) - Ticker is invalid or not found

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

### Watchlist Management

```bash
# Add symbols to watchlist
ib-picker watchlist add AAPL,MSFT,GOOGL
ib-picker watchlist add NVDA --notes "GPU play" --tags "ai,semiconductor"

# List watchlist
ib-picker watchlist list

# Remove from watchlist
ib-picker watchlist remove AAPL

# Clear entire watchlist
ib-picker watchlist clear --force
```

### Earnings Calendar

```bash
# Check earnings for specific symbols
ib-picker earnings check AAPL,MSFT,GOOGL --days 30

# Check upcoming earnings from watchlist
ib-picker earnings upcoming --days 14

# Useful for avoiding trades around earnings
ib-picker earnings check --days 7  # Uses watchlist if no symbols specified
```

### Scanning for Opportunities

```bash
# Scan watchlist with default strategy
ib-picker scan

# Scan specific tickers
ib-picker scan --tickers AAPL,MSFT,GOOGL

# Scan a sector
ib-picker scan --sector Technology

# Skip stocks with earnings within N days
ib-picker scan --skip-earnings-within 7

# Use a specific strategy
ib-picker scan --strategy momentum

# Output formats for automation
ib-picker scan --output json >> ~/scan-results.jsonl  # JSONL for log aggregation
ib-picker scan --output log                            # Simple log format for cron
```

**Scheduling scans with cron:**
```bash
# Add to crontab (crontab -e):
# Run scan every weekday at 9:30 AM EST
30 9 * * 1-5 /path/to/ib-picker scan --output log >> ~/ib-picker-scans.log 2>&1
```

## Web Interface

The application includes a web UI for visual interaction with all features.

### Starting the Web Server

```bash
# Start web server (default: http://127.0.0.1:8000)
ib-picker serve

# Custom host/port
ib-picker serve --host 0.0.0.0 --port 8080

# Development mode with auto-reload
ib-picker serve --reload
```

### Web Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Overview with recent signals, watchlist, market status |
| Stocks | `/stocks` | Browse stocks with prices and indicators |
| Stock Detail | `/stocks/{symbol}` | Detailed view with candlestick chart, volume, indicators, flow alerts |
| Compare | `/charts/compare` | Multi-symbol normalized price comparison with Plotly.js |
| Portfolio | `/charts/portfolio` | Portfolio analytics: equity curve, returns distribution, drawdown |
| Correlations | `/charts/correlations` | Correlation heatmap between stocks |
| Journal | `/journal` | Trade journal with open/close/execute forms |
| Analysis | `/analysis` | Run strategies and view signals |
| Backtest | `/backtest` | Configure and run backtests |
| Strategies | `/strategies` | Browse and view strategy definitions |

### REST API

The web server exposes a REST API at `/api/*` for programmatic access:

```bash
# List stocks
curl http://localhost:8000/api/stocks

# Get stock detail
curl http://localhost:8000/api/stocks/AAPL

# List signals
curl http://localhost:8000/api/signals

# Run analysis
curl -X POST http://localhost:8000/api/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"strategy": "example_rsi_flow", "symbols": ["AAPL", "MSFT"]}'

# Compare stocks (normalized returns)
curl "http://localhost:8000/api/charts/compare?symbols=AAPL,MSFT,NVDA&range=3M"

# Get indicators for a stock
curl "http://localhost:8000/api/charts/indicators/AAPL?indicators=sma_50,sma_200,rsi"

# Get correlation matrix
curl "http://localhost:8000/api/charts/correlation?symbols=AAPL,MSFT,GOOGL,NVDA&days=90"
```

### API Documentation

Interactive API documentation is available when the server is running:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "ib-daily-picker"}
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
│   ├── store/              # Database layer (DuckDB + SQLite)
│   └── web/                # FastAPI web application
│       ├── main.py         # App factory
│       ├── routes/api/     # REST API endpoints
│       ├── routes/pages/   # Server-rendered pages
│       ├── templates/      # Jinja2 templates
│       └── static/         # CSS, JS assets
├── strategies/             # YAML strategy definitions
├── tests/                  # Test suite
└── docs/adr/               # Architecture Decision Records
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| CLI | Typer + Rich |
| Web | FastAPI + Jinja2 + uvicorn |
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

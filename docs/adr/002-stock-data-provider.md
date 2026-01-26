# ADR-002: Stock Data Provider (yfinance + Finnhub)

## Status
Accepted

## Context
The application needs historical and current stock price data (OHLCV) for:
- Technical indicator calculation (RSI, SMA, ATR, etc.)
- Backtesting strategies against historical data
- Real-time analysis of current market conditions

Requirements:
- Free or low-cost (this is a personal trading tool)
- Reliable data quality
- Historical data going back at least 5 years
- Sector/industry classification for basket filtering

Options evaluated:
- **yfinance**: Free, unlimited, excellent historical depth, good sector data
- **Finnhub**: Free tier (60 req/min), reliable, 1 year per API call
- **Alpha Vantage**: Free tier limited (5 req/min), good data quality
- **Polygon.io**: Free tier very limited, excellent for real-time
- **IEX Cloud**: Pay-per-use, high quality

## Decision
Use **yfinance as the primary provider** with **Finnhub as fallback**:

1. **yfinance** (primary):
   - Unlimited free access via Yahoo Finance
   - Full historical data since IPO
   - Excellent sector/industry classification
   - Good for batch fetching multiple tickers

2. **Finnhub** (fallback):
   - Used when yfinance fails or returns incomplete data
   - 60 requests/minute free tier
   - More reliable API with proper error codes
   - Better for real-time quotes

The fetcher automatically falls back to Finnhub if yfinance returns no data or errors.

## Consequences

### Positive
- **Zero cost**: Both providers have free tiers sufficient for personal use
- **Reliability**: Fallback ensures data availability even if one provider fails
- **Historical depth**: yfinance provides decades of data for backtesting
- **No API key required**: yfinance works without authentication

### Negative
- **yfinance instability**: Yahoo Finance occasionally changes their API, breaking yfinance
- **Rate limiting**: Must implement request throttling for Finnhub
- **Data quality variance**: Free providers may have occasional data gaps or delays
- **No real-time**: Neither free tier provides true real-time data (15-20 min delay)

### Neutral
- Finnhub requires an API key (free registration)
- Data is cached locally after first fetch to minimize API calls

## Alternatives Considered

1. **Alpha Vantage only**: Too rate-limited for batch operations (5 req/min)
2. **Paid providers**: Unnecessary cost for personal use case
3. **IB TWS data**: Requires active IB connection, complex setup

## References
- yfinance documentation: https://github.com/ranaroussi/yfinance
- Finnhub documentation: https://finnhub.io/docs/api
- Implementation: `src/ib_daily_picker/fetchers/yfinance_fetcher.py`
- Implementation: `src/ib_daily_picker/fetchers/finnhub_fetcher.py`
- Orchestrator: `src/ib_daily_picker/fetchers/stock_fetcher.py`

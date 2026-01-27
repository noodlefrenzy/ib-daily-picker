# ADR-003: Flow Data Provider (Unusual Whales)

## Status
Accepted

## Context
The core hypothesis of this tool is that options flow data reveals "smart money" positioning before price moves. We need a source of flow alerts that indicates unusual options activity.

Requirements:
- Flow alerts with premium, volume, and sentiment data
- Historical flow data for backtesting
- API access (not just web dashboard)

Options evaluated:
- **Unusual Whales**: Dedicated flow data platform, good API, subscription-based
- **Tradier**: Options data available, less flow-focused
- **CBOE**: Institutional-grade, expensive

## Decision
Use **Unusual Whales API** as the primary flow data source.

Key factors:
- Purpose-built for retail traders analyzing flow
- Clean API with flow alerts endpoint
- Monthly subscription model (not per-call)
- Python SDK available (`unusualwhales-python`)
- Historical data access for backtesting

Implementation includes:
- Rate limiting (120 req/min per API docs)
- Caching with 15-30 minute TTL (flow alerts are time-sensitive but not real-time critical)
- Premium filtering to focus on significant trades

## Consequences

### Positive
- **High-quality flow data**: Unusual Whales specializes in this exact use case
- **Clean API**: Well-documented, reliable endpoints
- **Flow alerts**: Pre-filtered unusual activity, not raw options data
- **Python SDK**: Reduces integration effort

### Negative
- **Subscription cost**: Requires paid Unusual Whales subscription
- **Vendor lock-in**: Flow alert format is UW-specific
- **Rate limits**: 120 requests/minute
- **Data lag**: Alerts are near-real-time but not instant

### Neutral
- API key stored in environment variable (`UNUSUAL_WHALES_API_KEY`)
- Alerts cached to reduce repeated fetches

## Alternatives Considered

1. **Scraping free sources**: Unreliable, ToS violations, no historical data
2. **Building from raw options data**: Requires expensive data feeds and complex analysis

## References
- Unusual Whales API: https://docs.unusualwhales.com/
- Implementation: `src/ib_daily_picker/fetchers/unusual_whales.py`
- Configuration: `src/ib_daily_picker/config.py` (unusual_whales_api_key)

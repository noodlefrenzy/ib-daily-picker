# ADR-001: Dual Database Architecture (DuckDB + SQLite)

## Status
Accepted

## Context
The application needs to store two fundamentally different types of data:

1. **Analytical data** - Large volumes of time-series data (OHLCV prices, flow alerts, recommendations) that will be queried with aggregations, joins, and filters across date ranges
2. **Application state** - Small amounts of configuration and sync tracking data that needs simple CRUD operations

Traditional approaches would use either:
- A single relational database (PostgreSQL/SQLite) for everything
- A time-series database for analytics + relational for state
- A single embedded database for simplicity

## Decision
Use a **dual-database architecture**:

- **DuckDB** (`analytics.duckdb`) for analytical workloads:
  - OHLCV price data
  - Flow alerts from Unusual Whales
  - Trade recommendations
  - Backtest results

- **SQLite** (`state.sqlite`) for application state:
  - Sync tracking (what data has been fetched)
  - Configuration persistence
  - Session state

Both databases are embedded (no server required) and stored in `~/.ib-picker/data/` by default.

## Consequences

### Positive
- **Optimal query performance**: DuckDB's columnar storage excels at analytical queries (aggregations, date range filters) that are core to backtesting and analysis
- **Simple deployment**: Both databases are embedded files, no database server needed
- **Clear separation**: Analytics vs state have different access patterns and this makes that explicit
- **DuckDB advantages**: Vectorized execution, efficient compression, excellent pandas integration

### Negative
- **Two connection managers**: Code must manage connections to both databases
- **No cross-database joins**: Cannot join analytics data with state data in a single query
- **Learning curve**: Developers need to understand when to use which database
- **Migration complexity**: Schema changes require coordinating two databases

### Neutral
- Both databases support SQL, so query syntax is familiar
- DuckDB files can be inspected with the DuckDB CLI tool
- SQLite files can be inspected with any SQLite browser

## Alternatives Considered

1. **SQLite only**: Simpler but poor performance for analytical queries on large datasets
2. **PostgreSQL**: Better for multi-user but requires server setup, overkill for single-user CLI
3. **DuckDB only**: Could work but DuckDB's ACID guarantees are weaker for high-frequency state updates

## References
- DuckDB documentation: https://duckdb.org/docs/
- Implementation: `src/ib_daily_picker/store/database.py`
- Configuration: `src/ib_daily_picker/config.py` (DatabaseSettings)

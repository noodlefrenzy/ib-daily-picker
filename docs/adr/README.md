# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the IB Daily Picker project.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](001-database-architecture.md) | Dual Database Architecture (DuckDB + SQLite) | Accepted | 2026-01-26 |
| [ADR-002](002-stock-data-provider.md) | Stock Data Provider (yfinance + Finnhub) | Accepted | 2026-01-26 |
| [ADR-003](003-flow-data-provider.md) | Flow Data Provider (Unusual Whales) | Accepted | 2026-01-26 |
| [ADR-004](004-cli-framework.md) | CLI Framework (Typer + Rich) | Accepted | 2026-01-26 |
| [ADR-005](005-strategy-format.md) | Strategy Definition Format (YAML) | Accepted | 2026-01-26 |
| [ADR-006](006-llm-integration.md) | LLM Integration (Anthropic + Ollama) | Accepted | 2026-01-26 |
| [ADR-007](007-web-framework.md) | Web Framework (FastAPI + Jinja2) | Accepted | 2026-01-28 |
| [ADR-008](008-discord-bot.md) | Discord Bot Interface (discord.py) | Accepted | 2026-01-30 |
| [ADR-009](009-azure-hosting.md) | Azure Hosting (Container Apps + Blob Storage) | Accepted | 2026-01-30 |

## ADR Process

When making significant architectural decisions:

1. Create a new ADR using the template below
2. Assign the next sequential number
3. Update this index
4. Get team review before marking as Accepted

## Template

```markdown
# ADR-XXX: Title

## Status
[DRAFT | ACCEPTED | SUPERSEDED by ADR-XXX | DEPRECATED]

## Context
[Why is this decision needed? What problem are we solving?]

## Decision
[What did we decide?]

## Consequences
### Positive
- [Benefit 1]

### Negative
- [Tradeoff 1]

### Neutral
- [Observation 1]

## References
- [Related ADRs, external docs, discussions]
```

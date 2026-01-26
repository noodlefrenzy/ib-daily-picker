# ADR-004: CLI Framework (Typer + Rich)

## Status
Accepted

## Context
The application is a command-line tool requiring:
- Multiple subcommands (fetch, analyze, backtest, journal, etc.)
- Rich output formatting (tables, colors, progress bars)
- Good developer experience (type hints, auto-completion)
- Help text generation

Options evaluated:
- **Click**: Mature, widely used, decorator-based
- **Typer**: Built on Click, type hint-based, modern
- **argparse**: Standard library, verbose, limited formatting
- **Fire**: Auto-generates CLI from functions, less control

## Decision
Use **Typer** for CLI framework with **Rich** for output formatting.

**Typer** chosen because:
- Type hints define arguments (no decorators needed)
- Built on Click (proven, stable)
- Excellent auto-completion support
- Modern Python feel

**Rich** chosen because:
- Beautiful terminal output (tables, panels, syntax highlighting)
- Progress bars for long operations
- Color support with graceful fallback
- Integrates well with Typer

## Consequences

### Positive
- **Developer experience**: Type hints provide IDE support and validation
- **User experience**: Rich output makes data easy to read
- **Maintainability**: Less boilerplate than Click decorators
- **Auto-completion**: Shell completion scripts generated automatically

### Negative
- **Dependency**: Two additional dependencies (typer, rich)
- **Learning curve**: Team must learn Typer patterns
- **Output coupling**: Rich formatting code mixed with business logic

### Neutral
- CLI structure uses command groups (app.add_typer pattern)
- JSON output available via `--json` flag for machine consumption

## CLI Structure

```
ib-picker
├── config      # Configuration management
│   ├── show
│   ├── set
│   └── init
├── fetch       # Data fetching
│   ├── stocks
│   ├── flows
│   └── status
├── strategy    # Strategy management
│   ├── list
│   ├── validate
│   ├── show
│   └── create
├── analyze     # Run analysis
├── signals     # View signals
├── journal     # Trade journal
│   ├── list
│   ├── open
│   ├── execute
│   ├── close
│   ├── note
│   ├── metrics
│   └── export
├── backtest    # Backtesting
│   ├── run
│   └── compare
└── db          # Database operations
    ├── status
    └── export
```

## Alternatives Considered

1. **Click only**: More verbose, Rich integration requires more code
2. **argparse + Rich**: Standard library but very verbose for complex CLIs
3. **Fire**: Too magical, less control over help text and validation

## References
- Typer documentation: https://typer.tiangolo.com/
- Rich documentation: https://rich.readthedocs.io/
- Implementation: `src/ib_daily_picker/cli.py`

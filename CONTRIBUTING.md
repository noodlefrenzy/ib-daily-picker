# Contributing to IB Daily Picker

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Be respectful and constructive in all interactions. We're here to build something useful together.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/ib-daily-picker.git
   cd ib-daily-picker
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```
5. Verify your setup:
   ```bash
   pytest
   ```

The pre-commit hooks will automatically run `ruff` (linting + formatting) on every commit, catching issues before they reach CI.

## Development Workflow

### Before Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make sure tests pass before you start:
   ```bash
   pytest
   ```

### Making Changes

1. Write tests first (TDD) when adding new features
2. Follow existing code patterns and style
3. Use type hints for all function signatures
4. Use `Decimal` for all monetary values, never `float`

### Code Quality

Run these checks before committing:

```bash
# Format code
ruff format .

# Lint
ruff check .

# Type checking
mypy src/

# Run tests
pytest

# Run tests with coverage
pytest --cov
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding/updating tests
- `refactor`: Code change that neither fixes nor adds
- `chore`: Maintenance tasks

**Examples:**
```
feat(backtest): add walk-forward validation command
fix(fetcher): handle API timeout gracefully
docs(readme): add installation instructions
test(analysis): add edge cases for RSI calculation
```

## Pull Request Process

1. Update documentation if you're changing behavior
2. Add tests for new functionality
3. Ensure all checks pass (ruff, mypy, pytest)
4. Update the README if adding new commands or features
5. Submit a PR with a clear description of changes

### PR Description Template

```markdown
## Summary
Brief description of what this PR does.

## Changes
- Change 1
- Change 2

## Testing
How was this tested?

## Checklist
- [ ] Tests pass locally
- [ ] Code is formatted with ruff
- [ ] Type hints added for new code
- [ ] Documentation updated if needed
```

## Project Structure

```
ib-daily-picker/
├── src/ib_daily_picker/
│   ├── cli.py              # CLI commands (Typer)
│   ├── config.py           # Configuration (pydantic-settings)
│   ├── analysis/           # Strategy evaluation, signals
│   ├── backtest/           # Backtesting engine
│   ├── fetchers/           # Data fetchers (yfinance, UW)
│   ├── journal/            # Trade journal
│   ├── models/             # Domain models
│   ├── store/              # Database layer
│   └── web/                # FastAPI web interface
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # Test data
├── strategies/             # YAML strategy definitions
└── docs/adr/               # Architecture Decision Records
```

## Testing Guidelines

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use pytest fixtures for shared test setup
- Mock external APIs (yfinance, Unusual Whales, Finnhub)
- Test edge cases: empty data, API errors, invalid inputs

## Adding New Features

### New CLI Command

1. Add command in `src/ib_daily_picker/cli.py`
2. Add tests in `tests/unit/test_cli.py` or appropriate module
3. Update README with usage examples
4. Update help text with clear descriptions

### New Strategy Indicator

1. Add indicator in `src/ib_daily_picker/analysis/indicators.py`
2. Add to strategy schema in `src/ib_daily_picker/analysis/strategy_schema.py`
3. Add tests for the indicator calculation
4. Document in README's indicator table

### New Data Fetcher

1. Create fetcher in `src/ib_daily_picker/fetchers/`
2. Implement the fetcher interface pattern
3. Add comprehensive error handling
4. Create recorded API response fixtures for tests
5. Document API key requirements

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Questions about the codebase

We appreciate all contributions!

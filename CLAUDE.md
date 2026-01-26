---
# CLAUDE.md Template Configuration
version: "1.0.0"
project_type: "cli"  # web-app | cli | backend | library | monorepo
testing_philosophy: "tdd"  # tdd | tad | bdd | lightweight | manual | hybrid
bootstrap_source: null  # Set by /plan-0-constitution when bootstrapping
last_updated: "2026-01-26"
---

<!-- SECTION: QUICK_START -->
<!-- REQUIRED -->
# IB Daily Picker

## Project Overview

<!-- USER CONTENT START: overview -->
A Python CLI tool that identifies promising stock opportunities by correlating market flow data with price action.

**Core Workflow:**
1. Fetch and store financial data for a configurable basket of stocks (free API)
2. Query Interactive Brokers API for flow/flow alerts (cost-conscious, parsimonious usage)
3. Analyze flows against stock data to surface potential buys
4. Store all data (stocks, flows, alerts) to enable backtesting and strategy iteration

**Key Constraints:**
- IB API calls are metered/costly - minimize requests, cache aggressively
- Historical data storage enables counterfactual analysis without re-fetching
- Strategies should be pluggable for backtesting against historical data
<!-- USER CONTENT END: overview -->

## Development Commands

```bash
# Essential commands
pip install -e ".[dev]"       # Install with dev dependencies
python -m ib_daily_picker     # Run CLI (or use entry point after install)
pytest                        # Run test suite
pytest --cov                  # Run tests with coverage
ruff check .                  # Lint
ruff format .                 # Format code
mypy src/                     # Type checking
```

## Current Status

<!-- USER CONTENT START: status -->
**Focus:** Initial planning and architecture design

**Recent Changes:**
- Project scaffolding created
- CLAUDE.md customized for project requirements

**Known Issues:**
- Spec incomplete - using /plan commands to elaborate requirements
- API selection (free stock data) TBD
- Database choice TBD
- IB API authentication/setup not yet documented
<!-- USER CONTENT END: status -->

---

<!-- SECTION: CORE_GUIDANCE -->
<!-- REQUIRED -->
## Core Guidance

### Code Style Principles

**General:**
- Functional, immutable patterns preferred where practical
- async/await for I/O operations (httpx, database, IB API)
- Strict type hints throughout - no `Any` without justification
- Use `dataclasses` or `pydantic` for data structures
- Underscore prefix (`_var`) for intentionally unused variables
- Python 3.11+ features acceptable (match statements, etc.)

**Error Handling:**
- Validate at boundaries (user input, external APIs)
- Fail fast with clear error messages
- Don't swallow errors silently

**Dependencies:**
- Explicit over implicit
- No circular dependencies
- Clear dependency direction (apps -> packages -> external)

<!-- USER CONTENT START: code_style_additions -->
**Python/Financial Domain Specifics:**
- Use `Decimal` for money/prices, never `float`
- Dates: `datetime.date` for calendar dates, `datetime.datetime` with timezone for timestamps
- All timestamps stored as UTC; convert to local only for display
- API responses should be validated with Pydantic before use
- Database models separate from API models (clean boundaries)
- Use context managers for DB connections and API sessions
- Log all external API calls with timing for cost tracking
<!-- USER CONTENT END: code_style_additions -->

### File Operations Checklist

**When renaming, moving, or deleting files:**

1. Search for references to the old path:
   ```bash
   grep -r "old-filename" --include="*.md" --include="*.py" --include="*.toml"
   ```
2. Check for README.md or index files in the same/parent directory
3. Check any ADR index if touching ADRs
4. Update any documentation, imports, or links that reference changed files
5. Verify links still work after changes

### Testing Philosophy

<!-- CONDITIONAL: testing_philosophy != manual -->
**Test Documentation Block Format:**

For TAD/TDD workflows, every test file should include a Test Doc block:

```python
"""
TEST DOC: [Feature/Component Name]

WHAT: [What behavior is being tested]
WHY: [Why this test exists - what bug/requirement it covers]
HOW: [Brief description of test approach]

CASES:
- [Case 1]: [Expected behavior]
- [Case 2]: [Expected behavior]

EDGE CASES:
- [Edge case]: [How it's handled]
"""
```
<!-- END CONDITIONAL -->

**Testing Approach:**
| Philosophy | When to Use | Key Principle |
|------------|-------------|---------------|
| TDD | New features with clear specs | Write test first, then implementation |
| TAD | Exploratory development | Tests document discoveries |
| BDD | User-facing features | Describe behavior from user perspective |
| Lightweight | Simple utilities | Focus on edge cases and contracts |
| Manual | UI-heavy features | Supplement with manual verification |
| Hybrid | Complex projects | Mix approaches per component |

<!-- USER CONTENT START: testing_specifics -->
**TDD for Financial Data:**
- Write tests first - they define the contract before implementation
- Mock all external APIs (stock data, IB) with realistic fixtures
- Use `pytest-recording` or VCR.py to capture real API responses for fixtures
- Test edge cases: market holidays, after-hours, missing data, API errors
- Decimal precision tests: verify no floating-point drift in calculations
- Time-sensitive tests: use `freezegun` to control datetime.now()

**Test Organization:**
```
tests/
  unit/           # Pure function tests, no I/O
  integration/    # DB operations, mocked external APIs
  fixtures/       # Shared test data, recorded API responses
  conftest.py     # Shared fixtures (db sessions, mock clients)
```

**Critical Test Scenarios:**
- API rate limiting / backoff behavior
- Partial data scenarios (some stocks missing)
- Strategy backtesting determinism (same inputs = same outputs)
- Data storage and retrieval round-trips
<!-- USER CONTENT END: testing_specifics -->

### Verification Philosophy

**Multi-layer verification catches different bugs:**

| Layer | What It Catches | What It Misses |
|-------|-----------------|----------------|
| Type checking | Import/export mismatches, type errors | Runtime behavior, UI interactions |
| Linting | Style issues, common mistakes | Logic errors, integration issues |
| Unit tests | Function-level logic | Integration, UI flow |
| Integration tests | Component interactions | UI polish, UX issues |
| Manual testing | UI interactions, user flows | Edge cases without explicit testing |

**Do not skip layers.** Each catches issues the others miss.

**Pre-Commit Verification:**
```bash
# Run all verification layers before committing
mypy src/                 # Type checking
ruff check .              # Linting
ruff format --check .     # Format verification
pytest                    # Tests
```

---

<!-- SECTION: DOCUMENTATION_REQUIREMENTS -->
<!-- REQUIRED -->
## Documentation Requirements

### Exit Criteria (REQUIRED)

**Before considering any task complete, verify documentation is in sync:**

1. **Architecture Decision Records (ADRs):**
   - [ ] Does this change diverge from any existing ADR? -> Update or supersede it
   - [ ] Does this introduce a significant architectural decision? -> Create a new ADR
   - [ ] Are any ADRs now outdated due to this change? -> Update status

2. **README Files:**
   - [ ] Does the relevant README reflect current behavior?
   - [ ] Are setup instructions still accurate?
   - [ ] Are any documented features now changed or removed?

3. **Plan/Spec Status:**
   - [ ] If implementing a plan, is the status updated (DRAFT -> ACCEPTED -> SUPERSEDED)?
   - [ ] Are related plans cross-referenced if they overlap?

4. **Project Instructions:**
   - [ ] Does this change affect conventions documented in CLAUDE.md?
   - [ ] Is the project status section still accurate?
   - [ ] Are any architecture descriptions now outdated?

**Why this matters:** Documentation drift causes confusion, wasted investigation time, and bugs when developers follow outdated guidance.

### README Synchronization

**Triggers - Update README when:**
- Adding/removing commands or scripts
- Changing setup or installation steps
- Adding/removing features
- Changing environment requirements
- Modifying API endpoints or interfaces

**README Checklist:**
```
[ ] Project description accurate
[ ] Installation steps work on fresh clone
[ ] All documented commands are valid
[ ] Environment variables documented
[ ] Dependencies listed with versions
[ ] Examples reflect current API
```

### ADR Management

**ADR Triggers (create a new ADR when):**
- Choosing between multiple viable approaches (document why this one)
- Deviating from established patterns (document the exception)
- Making technology choices (document alternatives considered)
- Changing how components/packages interact (document the architecture)

**ADR Format:**
```markdown
# ADR-[NUMBER]: [TITLE]

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

**ADR Maintenance:**
- Review ADRs quarterly or when major changes occur
- Mark superseded ADRs clearly with pointer to replacement
- Keep ADR index updated (docs/adr/README.md or similar)

### Micro-Context Standards

**File Headers (for complex files):**
```python
"""
[FILENAME]

PURPOSE: [What this file does]
OWNER: [Team or person responsible]
DEPENDENCIES: [Key external dependencies]

ARCHITECTURE NOTES:
[Any non-obvious design decisions or patterns]
"""
```

**Front-Matter (for documentation files):**
```yaml
---
title: [Document Title]
status: [draft | review | final]
last_updated: [YYYY-MM-DD]
related:
  - [path/to/related/doc.md]
---
```

**Contextual Comments:**
- Use `# WHY:` for non-obvious decisions
- Use `# TODO:` with ticket/issue reference
- Use `# HACK:` with explanation and remediation plan
- Use `# PERF:` for performance-critical sections
- Use `# COST:` for IB API calls to track metered usage

---

<!-- SECTION: PROJECT_SPECIFIC -->
<!-- OPTIONAL -->
## Project Architecture

<!-- USER CONTENT START: architecture -->
### Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Stock API  │     │   IB API    │     │  Database   │
│   (free)    │     │  (metered)  │     │  (local)    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └─────────┬─────────┴─────────┬─────────┘
                 │                   │
           ┌─────▼─────┐       ┌─────▼─────┐
           │  Fetchers │       │   Store   │
           └─────┬─────┘       └─────┬─────┘
                 │                   │
           ┌─────▼───────────────────▼─────┐
           │         Analysis Engine       │
           │  (strategies, flow matching)  │
           └─────────────┬─────────────────┘
                         │
                   ┌─────▼─────┐
                   │    CLI    │
                   │ (commands)│
                   └───────────┘
```

**Data Flow:**
1. CLI triggers fetch → Fetchers pull data → Store persists
2. CLI triggers analysis → Engine loads from Store → Strategies evaluate → Results output
3. Backtest mode → Engine replays historical data → Strategy evaluated → Metrics reported

### Directory Structure

```
ib-daily-picker/
  src/
    ib_daily_picker/
      __init__.py
      cli.py              # Click/Typer CLI entry points
      config.py           # Settings, environment, basket definitions
      fetchers/           # Stock API client, IB API client
      store/              # Database models, repositories
      analysis/           # Strategy implementations, flow matching
      models/             # Domain models (Stock, Flow, Alert, etc.)
  tests/
    unit/                 # Pure logic tests
    integration/          # DB and mocked API tests
    fixtures/             # Test data, recorded API responses
    conftest.py
  docs/
    adr/                  # Architecture Decision Records
  pyproject.toml
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| CLI | Click or Typer | Command-line interface (TBD during planning) |
| HTTP | httpx | Async HTTP client for APIs |
| Database | SQLite or PostgreSQL | Local storage (TBD - SQLite for simplicity, PG for scale) |
| ORM | SQLAlchemy 2.0 | Database abstraction with async support |
| Validation | Pydantic v2 | API response validation, config |
| IB Client | ib_insync or native | Interactive Brokers API access |
| Testing | pytest | Test framework |

### Domain Concepts

| Concept | Definition | Where Used |
|---------|------------|------------|
| **Basket** | Configured set of stock symbols to track | config, fetchers, analysis |
| **Stock Data** | OHLCV + metadata for a symbol on a date | fetchers, store, analysis |
| **Flow** | Order flow data from IB (volume, direction, timing) | fetchers, store, analysis |
| **Flow Alert** | IB-defined unusual activity signal | fetchers, store, analysis |
| **Strategy** | Pluggable analysis logic that scores opportunities | analysis, backtesting |
| **Signal** | Strategy output: buy/sell recommendation with confidence | analysis, CLI output |
| **Backtest** | Historical replay of strategy against stored data | analysis |

### Integration Points

| External System | Purpose | Interface |
|-----------------|---------|-----------|
| Free Stock API (TBD) | Daily OHLCV data, fundamentals | REST API (candidates: Alpha Vantage, Yahoo Finance, Polygon free tier) |
| Interactive Brokers | Flow data, flow alerts | IB API via ib_insync or native TWS API |
| Local Database | Persistence for all entities | SQLAlchemy async |

### Cost Management (IB API)

**Principles:**
- Batch requests where possible
- Cache aggressively - never re-fetch data we have
- Log every IB API call with timestamp for auditing
- Implement request budgets per run (configurable max calls)
- Prefer "pull what we need" over "sync everything"

**Request Budget Pattern:**
```python
# COST: IB API call - counts against daily budget
with api_budget.track("flow_alerts"):
    alerts = await ib_client.get_flow_alerts(symbols)
```
<!-- USER CONTENT END: architecture -->

---

<!-- SECTION: WORKFLOWS -->
<!-- CONDITIONAL: project_type = web-app OR project_type = mobile -->
## Manual UI Testing (CRITICAL)

**TypeScript/compilation passing is NOT sufficient.** Before committing any UI changes:

1. **Start the app(s)** and manually test every feature you touched
2. **Click every button** - verify handlers are actually connected
3. **Test complete user flows** - Create -> Read -> Update -> Delete
4. **Test affected platforms** if changes touch shared code

**UI Testing Checklist:**
```
For each new/modified feature:
[ ] Started the app(s)
[ ] Clicked through the UI - buttons, forms, modals
[ ] Verified data persists - created item appears in list
[ ] Verified actions work - edit updates, delete removes
[ ] Checked console for errors - no red errors in DevTools
[ ] Tested on affected platforms
```

**Common issues this catches:**
- Event handlers not connected (button does nothing)
- Navigation missing required parameters
- Drag-and-drop listeners blocking click handlers
- Missing CSS/styles for new components
- State not updating after mutations

**Root cause of missed bugs:** Assuming "code compiles" means "feature works."
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: workflows -->
### CLI Command Structure (Planned)

```bash
# Data fetching
ib-picker fetch stocks              # Fetch stock data for basket
ib-picker fetch flows               # Fetch IB flow data (COST: uses API budget)
ib-picker fetch alerts              # Fetch IB flow alerts (COST: uses API budget)

# Analysis
ib-picker analyze                   # Run current strategy, output signals
ib-picker analyze --strategy=NAME   # Run specific strategy

# Backtesting
ib-picker backtest --strategy=NAME --from=DATE --to=DATE
ib-picker backtest --compare=STRAT1,STRAT2  # Compare strategies

# Data management
ib-picker db status                 # Show data coverage
ib-picker db export                 # Export for analysis
ib-picker config show               # Show current configuration
ib-picker config set KEY VALUE      # Update configuration
```

### Development Workflow

1. **TDD Cycle:**
   - Write failing test for new behavior
   - Implement minimum code to pass
   - Refactor with tests green
   - Commit with descriptive message

2. **Adding a New Strategy:**
   - Create test file: `tests/unit/analysis/test_strategy_name.py`
   - Define expected behavior with test cases
   - Implement in `src/ib_daily_picker/analysis/strategies/`
   - Add to strategy registry
   - Run backtest to validate

3. **Adding New Data Source:**
   - ADR required: document API choice and alternatives
   - Create fetcher with interface matching existing pattern
   - Add comprehensive mocks/fixtures
   - Integration test with recorded responses

### Environment Configuration

```bash
# .env (not committed)
IB_GATEWAY_HOST=127.0.0.1
IB_GATEWAY_PORT=4001
IB_CLIENT_ID=1
STOCK_API_KEY=xxx              # If API requires key
DATABASE_URL=sqlite:///data/picker.db
IB_API_BUDGET_DAILY=100        # Max IB API calls per day
LOG_LEVEL=INFO
```
<!-- USER CONTENT END: workflows -->

---

<!-- SECTION: LEARNING_REFLECTION -->
<!-- REQUIRED -->
## Learning & Reflection

### Recent Learnings

<!--
After completing each phase or significant task, capture learnings here.
This section is prompted by /plan-6-implement-phase completion.

Entry Format:
## [DATE] - [TOPIC TITLE]

**Context:** [What were you working on?]

**Discovery:** [What did you learn? What surprised you?]

**Impact:** [How does this affect future work?]

**References:** [Related files, PRs, ADRs]

**Tags:** #gotcha | #pattern | #antipattern | #performance | #security | #ux
-->

<!-- USER CONTENT START: learnings -->
<!-- Learnings will be captured here as the project develops -->
<!-- Example format preserved for reference:

### [YYYY-MM-DD] - IB API Rate Limiting Discovery

**Context:** Implementing flow alert fetching

**Discovery:** IB API has undocumented throttling beyond the documented rate limits.
Rapid sequential calls trigger temporary blocks.

**Impact:** Implement request spacing (min 100ms between calls) and exponential backoff.

**References:**
- `src/ib_daily_picker/fetchers/ib_client.py:XX`
- ADR-XXX

**Tags:** #gotcha #api #cost
-->
<!-- USER CONTENT END: learnings -->

### Known Issues & Technical Debt

<!-- USER CONTENT START: tech_debt -->
| Issue | Severity | Context | Remediation |
|-------|----------|---------|-------------|
| Free API selection | Med | Need to evaluate options during planning | ADR after /plan-1a-explore |
| DB choice (SQLite vs PG) | Low | Start simple, may need scale | ADR if migrating |
| IB API auth complexity | Med | TWS/Gateway setup is manual | Document in README |
<!-- USER CONTENT END: tech_debt -->

### Post-Implementation Notes

<!-- USER CONTENT START: post_impl -->
### 2026-01-26 - Project Initialization

- CLAUDE.md customized for Python CLI with TDD
- Architecture is planned but not validated - run /plan commands to refine
- Key decisions deferred to ADRs: stock API choice, database choice, strategy interface
<!-- USER CONTENT END: post_impl -->

---

<!-- SECTION: APPENDICES -->
## Appendices

### Appendix A: Commit Format Standards

```
<type>(<scope>): <description>

[optional body]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes nor adds |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |

**Scope:** Use the most specific relevant area (component, package, feature)

**Examples:**
```
feat(fetcher): add Alpha Vantage stock data client
feat(analysis): implement momentum crossover strategy
fix(ib-client): handle connection timeout gracefully
refactor(store): extract repository pattern for stocks
test(backtest): add edge cases for market holidays
docs(readme): document IB Gateway setup
```

**Scopes for this project:**
`cli`, `fetcher`, `store`, `analysis`, `backtest`, `ib-client`, `config`, `models`

### Appendix B: Complexity Scoring Reference

Use CS 1-5 instead of time estimates:

| Score | Scope | Risk | Examples |
|-------|-------|------|----------|
| **CS-1** | Single file, isolated change | Minimal | Fix typo, update constant, add log |
| **CS-2** | Few files, minimal integration | Low | Add simple endpoint, new utility function |
| **CS-3** | Multiple components, moderate complexity | Some | New feature with tests, refactor module |
| **CS-4** | Cross-cutting concerns, significant integration | Notable | Authentication system, major refactor |
| **CS-5** | System-wide impact, high uncertainty | Significant | Architecture change, new core abstraction |

**Usage in Plans:**
```markdown
## Tasks
- [ ] Add user endpoint (CS-2)
- [ ] Implement caching layer (CS-4)
- [ ] Update config constant (CS-1)
```

### Appendix C: Extension Points by Project Type

<!-- CONDITIONAL: project_type = web-app -->
**Web App Extensions:**
- Component library documentation
- State management patterns
- API client conventions
- Styling/theming approach
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = cli -->
**CLI Extensions:**
- Command structure and naming
- Flag conventions
- Output formatting (human vs machine)
- Configuration file handling
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = backend -->
**Backend Extensions:**
- API versioning strategy
- Database migration approach
- Authentication/authorization patterns
- Logging and monitoring conventions
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = library -->
**Library Extensions:**
- Public API design principles
- Versioning and changelog conventions
- Documentation generation
- Example maintenance
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: extensions -->
**CLI Output Conventions:**
- Human-readable by default, `--json` flag for machine output
- Progress indicators for long operations (fetching, backtesting)
- Color-coded signals: green=buy, red=avoid, yellow=watch
- Verbose mode (`-v`) shows API call details and timing

**Configuration Hierarchy:**
1. CLI flags (highest priority)
2. Environment variables
3. Config file (`~/.ib-picker/config.toml` or project `.env`)
4. Defaults (lowest priority)

**Financial Data Conventions:**
- Always display prices with 2 decimal places
- Percentages with 2 decimal places and % suffix
- Dates in ISO format (YYYY-MM-DD) in output
- Timestamps include timezone indicator
<!-- USER CONTENT END: extensions -->

---

<!-- SECTION: META -->
## Template Maintenance

This template follows progressive disclosure:
- **Lines 1-50:** Quick Start - essential info for immediate productivity
- **Lines 51-150:** Core Guidance - universal principles for all projects
- **Lines 151-250:** Documentation Requirements - keeping docs in sync
- **Lines 251-350:** Project-Specific - customizable architecture details
- **Lines 351-450:** Workflows - conditional by project type
- **Lines 451+:** Learning & Appendices - reference material

**Bootstrap:** Run `/plan-0-constitution` to customize this template for your project type.

**User Content:** Sections between `<!-- USER CONTENT START -->` and `<!-- USER CONTENT END -->` are preserved during template updates.

**Conditional Sections:** Sections marked with `<!-- CONDITIONAL: ... -->` are shown/hidden based on project configuration.

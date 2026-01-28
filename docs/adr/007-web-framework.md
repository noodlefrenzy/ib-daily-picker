# ADR-007: Web Framework (FastAPI + Jinja2)

## Status
Accepted

## Context
While the CLI provides full functionality, a web interface offers advantages:
- Visual dashboards for at-a-glance market overview
- Easier navigation between stocks, journal, and analysis
- Form-based trade management (open/close/execute)
- Mobile-friendly access without terminal

Requirements:
- REST API for programmatic access and frontend flexibility
- Server-side rendering for fast initial page loads
- OpenAPI documentation for API consumers
- Async support for non-blocking I/O
- Integration with existing database and analysis layers

Options evaluated:
- **FastAPI**: Modern, async-native, automatic OpenAPI docs
- **Flask**: Mature, simple, but sync by default
- **Django**: Full-featured, but heavyweight for this use case
- **Starlette**: Lower-level than FastAPI, same ASGI foundation

For templating:
- **Jinja2**: Industry standard, FastAPI native support
- **Mako**: Fast, but less ecosystem support
- **React/Vue SPA**: More complex, requires separate build pipeline

## Decision
Use **FastAPI** for the web framework with **Jinja2** for server-side rendering and **uvicorn** as the ASGI server.

**FastAPI** chosen because:
- Native async/await support matches existing httpx usage
- Automatic OpenAPI/Swagger documentation at `/api/docs`
- Pydantic integration (already used for validation)
- Excellent performance characteristics
- Type hints drive request/response validation

**Jinja2** chosen because:
- Server-side rendering for fast initial loads
- No JavaScript build pipeline required
- Progressive enhancement possible (add JS where needed)
- Simpler deployment (no separate frontend build)

**uvicorn** chosen because:
- Reference ASGI server for FastAPI
- Production-ready with `--reload` for development
- Included as optional dependency

## Consequences

### Positive
- **API-first**: REST endpoints enable future SPA or mobile apps
- **Documentation**: OpenAPI docs auto-generated at `/api/docs`
- **Consistency**: Pydantic models shared between CLI and web
- **Performance**: Async handlers don't block on I/O
- **Simplicity**: Single `ib-picker serve` command starts everything

### Negative
- **Additional dependencies**: fastapi, uvicorn, jinja2 added to requirements
- **Two interfaces**: CLI and web must stay in sync feature-wise
- **Template maintenance**: HTML templates require separate styling effort
- **No real-time**: WebSockets not implemented (polling for updates)

### Neutral
- Web server is optional - CLI remains fully functional
- Templates use HTMX-style patterns (server returns HTML fragments)
- Static files served from `web/static/` directory

## Architecture

```
src/ib_daily_picker/web/
├── main.py              # FastAPI app factory
├── dependencies.py      # Shared dependencies (db, templates)
├── routes/
│   ├── api/             # REST API endpoints
│   │   ├── stocks.py    # GET /api/stocks, /api/stocks/{symbol}
│   │   ├── flows.py     # GET /api/flows
│   │   ├── signals.py   # GET /api/signals
│   │   ├── journal.py   # CRUD /api/journal/*
│   │   ├── watchlist.py # CRUD /api/watchlist/*
│   │   ├── strategies.py# GET /api/strategies
│   │   ├── analysis.py  # POST /api/analysis/run
│   │   └── backtest.py  # POST /api/backtest/run
│   └── pages/           # Server-rendered HTML pages
│       ├── dashboard.py # GET / (home dashboard)
│       ├── stocks.py    # GET /stocks, /stocks/{symbol}
│       ├── journal.py   # GET /journal
│       ├── analysis.py  # GET /analysis
│       └── backtest.py  # GET /backtest
├── templates/           # Jinja2 templates
│   ├── base.html        # Base layout
│   ├── pages/           # Page templates
│   └── components/      # Reusable components
└── static/              # CSS, JS, images
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stocks` | List stocks with prices |
| GET | `/api/stocks/{symbol}` | Stock detail with indicators |
| GET | `/api/flows` | List flow alerts |
| GET | `/api/signals` | List trading signals |
| GET | `/api/journal` | List journal entries |
| POST | `/api/journal/open` | Open new trade |
| POST | `/api/journal/close/{id}` | Close trade |
| GET | `/api/watchlist` | List watchlist |
| POST | `/api/watchlist` | Add to watchlist |
| GET | `/api/strategies` | List strategies |
| POST | `/api/analysis/run` | Run analysis |
| POST | `/api/backtest/run` | Run backtest |

## Alternatives Considered

1. **Flask + Blueprints**: Simpler but sync-only, manual OpenAPI
2. **Django REST Framework**: Powerful but heavy, ORM conflicts with DuckDB
3. **Separate React SPA**: Better UX but complex build, CORS, deployment
4. **Streamlit**: Quick dashboards but limited customization, not REST

## References
- FastAPI documentation: https://fastapi.tiangolo.com/
- Jinja2 documentation: https://jinja.palletsprojects.com/
- Implementation: `src/ib_daily_picker/web/`
- CLI integration: `src/ib_daily_picker/cli.py` (serve command)

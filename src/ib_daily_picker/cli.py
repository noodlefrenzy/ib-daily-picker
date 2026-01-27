"""
CLI entry point using Typer and Rich.

PURPOSE: Command-line interface for all IB Daily Picker operations
DEPENDENCIES: typer, rich

ARCHITECTURE NOTES:
- Uses Typer for CLI structure with automatic help generation
- Rich console for formatted output (tables, colors, progress)
- Command groups: config, fetch, analyze, journal, backtest, strategy
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from ib_daily_picker import __version__
from ib_daily_picker.config import get_settings, reset_settings

# Rich console for formatted output
console = Console()
err_console = Console(stderr=True)

# Main application
app = typer.Typer(
    name="ib-picker",
    help="Stock opportunity identification using flow data and price action.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"ib-picker version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output.",
        ),
    ] = False,
) -> None:
    """IB Daily Picker - Stock opportunity identification tool."""
    # Store verbose flag in context for subcommands
    ctx = typer.Context
    if verbose:
        # Will be used by subcommands
        pass


# =============================================================================
# Config Commands
# =============================================================================
config_app = typer.Typer(
    name="config",
    help="Configuration management commands.",
    no_args_is_help=True,
)
app.add_typer(config_app)


@config_app.command("show")
def config_show(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show current configuration."""
    settings = get_settings()

    if json_output:
        import json

        console.print(settings.model_dump_json(indent=2))
        return

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Database settings
    table.add_row("DuckDB Path", str(settings.database.duckdb_path))
    table.add_row("SQLite Path", str(settings.database.sqlite_path))

    # API settings
    table.add_row(
        "Finnhub API Key",
        "***configured***" if settings.api.finnhub_api_key else "[red]not set[/red]",
    )
    table.add_row(
        "UW API Key",
        "***configured***"
        if settings.api.unusual_whales_api_key
        else "[red]not set[/red]",
    )
    table.add_row("LLM Provider", settings.api.llm_provider)
    table.add_row("LLM Model", settings.api.llm_model)

    # Cost settings
    table.add_row("UW Daily Budget", str(settings.cost.uw_daily_budget))
    table.add_row("Flow Cache TTL", f"{settings.cost.flow_cache_ttl_minutes} min")

    # Risk settings
    table.add_row("Risk Profile", settings.risk.name)
    table.add_row("Risk Per Trade", f"{settings.risk.risk_per_trade * 100}%")
    table.add_row("Max Positions", str(settings.risk.max_positions))

    # Basket settings
    table.add_row("Default Tickers", ", ".join(settings.basket.default_tickers[:5]) + "...")

    console.print(table)


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Configuration key to set")],
    value: Annotated[str, typer.Argument(help="Value to set")],
) -> None:
    """Set a configuration value.

    Supported keys: default_tickers, risk_profile, uw_daily_budget
    """
    import tomli_w

    settings = get_settings()
    config_path = settings.config_dir / "config.toml"

    # Load existing config or create new
    config: dict[str, Any] = {}
    if config_path.exists():
        import tomli
        with open(config_path, "rb") as f:
            config = tomli.load(f)

    # Map keys to config structure
    key_map = {
        "default_tickers": ("basket", "default_tickers", lambda v: v.split(",")),
        "risk_profile": ("risk", "profile", str),
        "uw_daily_budget": ("uw_daily_budget", None, int),
    }

    if key not in key_map:
        console.print(f"[red]Unknown key: {key}[/red]")
        console.print(f"[dim]Supported keys: {', '.join(key_map.keys())}[/dim]")
        raise typer.Exit(1)

    section, subkey, converter = key_map[key]
    try:
        converted_value = converter(value)
    except Exception as e:
        console.print(f"[red]Invalid value for {key}: {e}[/red]")
        raise typer.Exit(1)

    # Update config
    if subkey:
        if section not in config:
            config[section] = {}
        config[section][subkey] = converted_value
    else:
        config[section] = converted_value

    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    console.print(f"[green]Set {key} = {value}[/green]")
    console.print(f"[dim]Config saved to {config_path}[/dim]")


@config_app.command("init")
def config_init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing config"),
    ] = False,
) -> None:
    """Initialize configuration file and directories."""
    settings = get_settings()
    config_path = settings.config_dir / "config.toml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    settings.ensure_directories()
    settings.save_toml()

    console.print(f"[green]Configuration initialized at {config_path}[/green]")
    console.print(f"Data directory: {settings.database.duckdb_path.parent}")


# =============================================================================
# Fetch Commands
# =============================================================================
fetch_app = typer.Typer(
    name="fetch",
    help="Data fetching commands.",
    no_args_is_help=True,
)
app.add_typer(fetch_app)


def _get_sector_tickers(sector: str, limit: int = 20) -> list[str]:
    """Get tickers for a given sector using yfinance screener.

    Args:
        sector: Sector name (e.g., "Technology", "Consumer Cyclical")
        limit: Maximum number of tickers to return

    Returns:
        List of ticker symbols in that sector
    """
    import yfinance as yf

    # Common tickers by sector for reliable lookup
    # yfinance doesn't have a direct sector screener, so we use a curated list
    # and filter by sector
    sector_seeds: dict[str, list[str]] = {
        "Technology": [
            "AAPL", "MSFT", "GOOGL", "NVDA", "META", "AVGO", "ORCL", "CRM",
            "ADBE", "AMD", "INTC", "QCOM", "TXN", "IBM", "NOW", "INTU",
            "AMAT", "MU", "LRCX", "ADI", "SNPS", "CDNS", "KLAC", "MCHP",
        ],
        "Consumer Cyclical": [
            "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX",
            "BKNG", "CMG", "ORLY", "AZO", "ROST", "DHI", "LEN", "GM",
            "F", "MAR", "HLT", "YUM", "DPZ", "DECK", "ULTA", "LULU",
        ],
        "Healthcare": [
            "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT",
            "DHR", "BMY", "AMGN", "MDT", "ISRG", "SYK", "GILD", "VRTX",
            "REGN", "ZTS", "BDX", "CVS", "CI", "HUM", "ELV", "MCK",
        ],
        "Financial": [
            "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
            "SPGI", "BLK", "C", "AXP", "SCHW", "CB", "MMC", "PGR",
            "ICE", "CME", "AON", "MET", "AIG", "TRV", "ALL", "AFL",
        ],
        "Communication Services": [
            "GOOG", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS",
            "CHTR", "EA", "TTWO", "WBD", "PARA", "OMC", "IPG", "LYV",
        ],
        "Consumer Defensive": [
            "WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "MDLZ",
            "CL", "GIS", "K", "KMB", "SYY", "HSY", "KR", "TGT",
            "DG", "DLTR", "EL", "STZ", "KDP", "MKC", "CHD", "CLX",
        ],
        "Energy": [
            "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PXD", "PSX",
            "VLO", "OXY", "WMB", "KMI", "HAL", "DVN", "HES", "BKR",
        ],
        "Industrials": [
            "CAT", "UNP", "RTX", "HON", "UPS", "BA", "DE", "LMT",
            "GE", "MMM", "ADP", "CSX", "NSC", "FDX", "EMR", "ITW",
            "ETN", "PH", "PCAR", "WM", "RSG", "JCI", "CARR", "GD",
        ],
        "Basic Materials": [
            "LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DD",
            "DOW", "PPG", "VMC", "MLM", "ALB", "CTVA", "CF", "MOS",
        ],
        "Real Estate": [
            "PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL",
            "DLR", "AVB", "EQR", "VTR", "ARE", "MAA", "UDR", "ESS",
        ],
        "Utilities": [
            "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL",
            "PCG", "WEC", "ED", "ES", "AWK", "DTE", "FE", "PPL",
        ],
    }

    # Normalize sector name (case-insensitive matching)
    sector_lower = sector.lower()
    matched_sector = None
    for s in sector_seeds:
        if s.lower() == sector_lower or sector_lower in s.lower():
            matched_sector = s
            break

    if not matched_sector:
        # Try to find tickers by checking a sample ticker's sector
        console.print(f"[yellow]Unknown sector '{sector}', trying to discover...[/yellow]")
        return []

    seed_tickers = sector_seeds[matched_sector]

    # Verify tickers are in the right sector and get additional info
    valid_tickers = []
    for ticker in seed_tickers[:limit]:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if info.get("sector", "").lower() == matched_sector.lower():
                valid_tickers.append(ticker)
        except Exception:
            # Skip tickers that fail lookup
            continue

        if len(valid_tickers) >= limit:
            break

    return valid_tickers


@fetch_app.command("stocks")
def fetch_stocks(
    tickers: Annotated[
        Optional[str],
        typer.Option(
            "--tickers",
            "-t",
            help="Comma-separated list of tickers (default: use basket)",
        ),
    ] = None,
    sector: Annotated[
        Optional[str],
        typer.Option(
            "--sector",
            "-S",
            help="Fetch stocks from a sector (e.g., 'Technology', 'Consumer Cyclical')",
        ),
    ] = None,
    start_date: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Start date (YYYY-MM-DD)",
        ),
    ] = None,
    end_date: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="End date (YYYY-MM-DD)",
        ),
    ] = None,
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            help="Fetch full history (ignore existing data)",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Max tickers when using --sector",
        ),
    ] = 20,
) -> None:
    """Fetch stock OHLCV data."""
    import asyncio
    from datetime import date as date_type

    from rich.progress import Progress, SpinnerColumn, TextColumn

    from ib_daily_picker.fetchers import get_stock_fetcher

    settings = get_settings()

    # Determine ticker list based on options
    if sector:
        console.print(f"[cyan]Looking up tickers in sector: {sector}[/cyan]")
        ticker_list = _get_sector_tickers(sector, limit=limit)
        if not ticker_list:
            err_console.print(f"[red]No tickers found for sector: {sector}[/red]")
            err_console.print("[dim]Available sectors: Technology, Consumer Cyclical, Healthcare, Financial, Communication Services, Consumer Defensive, Energy, Industrials, Basic Materials, Real Estate, Utilities[/dim]")
            raise typer.Exit(1)
        console.print(f"[green]Found {len(ticker_list)} tickers: {', '.join(ticker_list[:10])}{'...' if len(ticker_list) > 10 else ''}[/green]")
    elif tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
    else:
        ticker_list = settings.basket.default_tickers

    # Parse dates
    start = date_type.fromisoformat(start_date) if start_date else None
    end = date_type.fromisoformat(end_date) if end_date else None

    console.print(f"[cyan]Fetching stock data for {len(ticker_list)} tickers[/cyan]")

    fetcher = get_stock_fetcher()

    async def run_fetch() -> dict:
        results = {}
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching...", total=len(ticker_list))

            for symbol in ticker_list:
                progress.update(task, description=f"Fetching {symbol}...")
                result = await fetcher.fetch_and_store(
                    symbol, start, end, incremental=not full
                )
                results[symbol] = result
                progress.advance(task)

        return results

    results = asyncio.run(run_fetch())

    # Import status enum for comparison
    from ib_daily_picker.fetchers.base import FetchStatus

    # Summary table
    table = Table(title="Fetch Results")
    table.add_column("Symbol", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Records")
    table.add_column("Source")

    success_count = 0
    up_to_date_count = 0
    for symbol, result in results.items():
        # Color code: green=success, yellow=up_to_date, red=error
        if result.status == FetchStatus.UP_TO_DATE:
            status_style = "yellow"
            up_to_date_count += 1
        elif result.is_success:
            status_style = "green"
            success_count += 1
        else:
            status_style = "red"

        record_count = len(result.data) if result.data else 0
        table.add_row(
            symbol,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            str(record_count),
            result.source,
        )

    console.print(table)

    # Summary message
    total_ok = success_count + up_to_date_count
    if up_to_date_count > 0:
        console.print(
            f"\n[green]Fetched {success_count} new[/green], "
            f"[yellow]{up_to_date_count} already up to date[/yellow] "
            f"(total: {total_ok}/{len(ticker_list)} tickers)"
        )
    else:
        console.print(
            f"\n[green]Successfully fetched {success_count}/{len(ticker_list)} tickers[/green]"
        )


@fetch_app.command("flows")
def fetch_flows(
    tickers: Annotated[
        Optional[str],
        typer.Option(
            "--tickers",
            "-t",
            help="Comma-separated list of tickers",
        ),
    ] = None,
    min_premium: Annotated[
        Optional[float],
        typer.Option(
            "--min-premium",
            help="Minimum premium filter",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of alerts",
        ),
    ] = 100,
) -> None:
    """Fetch flow alerts from Unusual Whales.

    [yellow]COST: Uses API budget[/yellow]
    """
    import asyncio
    from decimal import Decimal as Dec

    from ib_daily_picker.fetchers import get_unusual_whales_fetcher
    from ib_daily_picker.store import FlowRepository, get_db_manager

    settings = get_settings()

    if not settings.api.unusual_whales_api_key:
        err_console.print(
            "[red]Error: Unusual Whales API key not configured.[/red]"
        )
        err_console.print("Set IB_PICKER_UNUSUAL_WHALES_API_KEY environment variable.")
        raise typer.Exit(1)

    symbols = [t.strip().upper() for t in tickers.split(",")] if tickers else None

    console.print("[cyan]Fetching flow alerts from Unusual Whales...[/cyan]")
    if symbols:
        console.print(f"  Symbols: {', '.join(symbols)}")
    console.print("[yellow]This will use your Unusual Whales API budget.[/yellow]")

    fetcher = get_unusual_whales_fetcher()

    async def run_fetch():
        premium = Dec(str(min_premium)) if min_premium else None
        return await fetcher.fetch_flow_alerts(
            symbols=symbols,
            min_premium=premium,
            limit=limit,
        )

    result = asyncio.run(run_fetch())

    if not result.is_success:
        err_console.print(f"[red]Error: {', '.join(result.errors)}[/red]")
        raise typer.Exit(1)

    if not result.data or not result.data.alerts:
        console.print("[yellow]No flow alerts found.[/yellow]")
        return

    # Store alerts in database
    db = get_db_manager()
    repo = FlowRepository(db)
    count = repo.save_batch(result.data.alerts)

    # Display results
    table = Table(title=f"Flow Alerts ({len(result.data.alerts)} found, {count} stored)")
    table.add_column("Symbol", style="cyan")
    table.add_column("Type")
    table.add_column("Direction")
    table.add_column("Premium", style="green")
    table.add_column("Strike")
    table.add_column("Exp")
    table.add_column("Time", style="dim")

    for alert in result.data.alerts[:20]:  # Show first 20
        direction_style = "green" if alert.is_bullish else "red" if alert.is_bearish else "white"
        premium_str = f"${alert.premium:,.0f}" if alert.premium else "-"
        strike_str = f"${alert.strike:.2f}" if alert.strike else "-"
        exp_str = alert.expiration.strftime("%m/%d") if alert.expiration else "-"
        time_str = alert.alert_time.strftime("%H:%M")

        table.add_row(
            alert.symbol,
            alert.alert_type.value,
            f"[{direction_style}]{alert.direction.value}[/{direction_style}]",
            premium_str,
            strike_str,
            exp_str,
            time_str,
        )

    console.print(table)

    if len(result.data.alerts) > 20:
        console.print(f"[dim]... and {len(result.data.alerts) - 20} more[/dim]")


@fetch_app.command("status")
def fetch_status() -> None:
    """Show data coverage and sync status."""
    from ib_daily_picker.store.database import get_db_manager

    db = get_db_manager()

    table = Table(title="Data Coverage")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Date Range", style="yellow")
    table.add_column("Last Sync", style="dim")

    with db.duckdb() as conn:
        # OHLCV stats
        result = conn.execute("""
            SELECT
                COUNT(DISTINCT symbol) as symbols,
                COUNT(*) as rows,
                MIN(date) as min_date,
                MAX(date) as max_date
            FROM ohlcv
        """).fetchone()

        if result and result[1] > 0:
            table.add_row(
                "OHLCV",
                f"{result[0]} symbols, {result[1]} rows",
                f"{result[2]} to {result[3]}",
                "-",
            )
        else:
            table.add_row("OHLCV", "0", "-", "-")

        # Flow alerts stats
        result = conn.execute("""
            SELECT
                COUNT(*) as count,
                MIN(alert_time) as min_time,
                MAX(alert_time) as max_time
            FROM flow_alerts
        """).fetchone()

        if result and result[0] > 0:
            table.add_row(
                "Flow Alerts",
                str(result[0]),
                f"{result[1][:10]} to {result[2][:10]}",
                "-",
            )
        else:
            table.add_row("Flow Alerts", "0", "-", "-")

    console.print(table)


# =============================================================================
# Strategy Commands
# =============================================================================
strategy_app = typer.Typer(
    name="strategy",
    help="Strategy management commands.",
    no_args_is_help=True,
)
app.add_typer(strategy_app)


@strategy_app.command("list")
def strategy_list() -> None:
    """List available strategies."""
    from ib_daily_picker.analysis import get_strategy_loader

    loader = get_strategy_loader()
    strategies = loader.list_strategies()

    if not strategies:
        settings = get_settings()
        console.print("[yellow]No strategy files found.[/yellow]")
        console.print(f"Add YAML files to: {settings.strategies_dir}")
        return

    table = Table(title="Available Strategies")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("File", style="dim")
    table.add_column("Description")

    for s in strategies:
        table.add_row(s["name"], s["version"], s["file"], s["description"][:50] + "..." if len(s.get("description", "")) > 50 else s.get("description", ""))

    console.print(table)


@strategy_app.command("validate")
def strategy_validate(
    strategy_file: Annotated[
        Path,
        typer.Argument(help="Path to strategy YAML file"),
    ],
) -> None:
    """Validate a strategy YAML file."""
    from ib_daily_picker.analysis import StrategyValidationError, get_strategy_loader

    if not strategy_file.exists():
        err_console.print(f"[red]File not found: {strategy_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Validating: {strategy_file}[/cyan]")

    loader = get_strategy_loader()

    try:
        strategy = loader.load(str(strategy_file))
        console.print(f"[green]Valid strategy: {strategy.name} v{strategy.version}[/green]")

        # Show strategy details
        console.print(f"\n[bold]Indicators:[/bold]")
        for ind in strategy.indicators:
            console.print(f"  - {ind.name}: {ind.type.value} (params: {ind.params})")

        console.print(f"\n[bold]Entry Conditions:[/bold] (logic: {strategy.entry.logic.value})")
        for cond in strategy.entry.conditions:
            if hasattr(cond, "indicator"):
                console.print(f"  - {cond.indicator} {cond.operator.value} {cond.value}")
            elif hasattr(cond, "direction"):
                console.print(f"  - flow: {cond.direction} (min premium: ${cond.min_premium or 0:,.0f})")

        if strategy.exit.take_profit:
            console.print(f"\n[bold]Take Profit:[/bold] {strategy.exit.take_profit.type.value} @ {strategy.exit.take_profit.value}")
        if strategy.exit.stop_loss:
            console.print(f"[bold]Stop Loss:[/bold] {strategy.exit.stop_loss.type.value} @ {strategy.exit.stop_loss.value}")

        console.print(f"\n[bold]Risk Profile:[/bold] {strategy.risk.profile.value}")

    except StrategyValidationError as e:
        err_console.print(f"[red]Validation failed:[/red]\n{e}")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@strategy_app.command("show")
def strategy_show(
    name: Annotated[str, typer.Argument(help="Strategy name")],
) -> None:
    """Show details of a strategy."""
    from ib_daily_picker.analysis import get_strategy_loader

    loader = get_strategy_loader()

    try:
        strategy = loader.load(name)
        console.print(f"[bold cyan]{strategy.name}[/bold cyan] v{strategy.version}")
        if strategy.strategy.description:
            console.print(f"[dim]{strategy.strategy.description}[/dim]")
        console.print()

        # Indicators
        table = Table(title="Indicators")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Parameters")
        for ind in strategy.indicators:
            table.add_row(ind.name, ind.type.value, str(ind.params))
        console.print(table)

        # Entry conditions
        console.print(f"\n[bold]Entry Logic:[/bold] {strategy.entry.logic.value.upper()}")
        for i, cond in enumerate(strategy.entry.conditions, 1):
            if hasattr(cond, "indicator"):
                console.print(f"  {i}. {cond.indicator} {cond.operator.value} {cond.value}")
            elif hasattr(cond, "direction"):
                console.print(f"  {i}. Flow: {cond.direction} (min ${cond.min_premium or 0:,.0f})")

        # Exit rules
        console.print("\n[bold]Exit Rules:[/bold]")
        if strategy.exit.take_profit:
            console.print(f"  Take Profit: {strategy.exit.take_profit.type.value} @ {strategy.exit.take_profit.value}")
        if strategy.exit.stop_loss:
            console.print(f"  Stop Loss: {strategy.exit.stop_loss.type.value} @ {strategy.exit.stop_loss.value}")
        if strategy.exit.trailing_stop:
            console.print(f"  Trailing Stop: {strategy.exit.trailing_stop.type.value} @ {strategy.exit.trailing_stop.value}")

        # Risk profile
        console.print(f"\n[bold]Risk Profile:[/bold] {strategy.risk.profile.value}")
        if strategy.risk.min_risk_reward:
            console.print(f"  Min R:R: {strategy.risk.min_risk_reward}")

    except FileNotFoundError:
        err_console.print(f"[red]Strategy not found: {name}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@strategy_app.command("create")
def strategy_create(
    name: Annotated[str, typer.Argument(help="Strategy name")],
    from_english: Annotated[
        Optional[str],
        typer.Option(
            "--from-english",
            help="Natural language description to convert",
        ),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
) -> None:
    """Create a new strategy."""
    settings = get_settings()

    if from_english:
        console.print(f"[cyan]Converting to YAML: {from_english}[/cyan]")

        try:
            from ib_daily_picker.llm import StrategyConverter

            converter = StrategyConverter()

            with console.status("[bold green]Generating strategy with LLM..."):
                yaml_str = converter.convert_to_yaml(from_english)

            # Determine output path
            output_path = output or (settings.strategies_dir / f"{name}.yaml")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(yaml_str)

            console.print(f"[green]Strategy created: {output_path}[/green]")
            console.print("\n[bold]Generated YAML:[/bold]")
            console.print(yaml_str)

        except ImportError as e:
            err_console.print(f"[red]LLM dependencies not installed: {e}[/red]")
            err_console.print("Install with: pip install anthropic instructor")
            raise typer.Exit(1)
        except ValueError as e:
            err_console.print(f"[red]Conversion failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Create a template strategy
        template = '''# Strategy: {name}
# Created with ib-picker strategy create

strategy:
  name: "{name}"
  version: "1.0.0"
  description: "TODO: Add description"
  author: "TODO: Add author"
  tags: []

indicators:
  - name: "rsi_14"
    type: "RSI"
    params:
      period: 14
      source: "close"

entry:
  conditions:
    - type: "indicator_threshold"
      indicator: "rsi_14"
      operator: "lt"
      value: 30

  logic: "all"

exit:
  take_profit:
    type: "percentage"
    value: 5.0

  stop_loss:
    type: "percentage"
    value: 3.0

risk:
  profile: "moderate"
  min_risk_reward: 2.0
'''
        yaml_content = template.format(name=name)

        output_path = output or (settings.strategies_dir / f"{name}.yaml")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml_content)

        console.print(f"[green]Strategy template created: {output_path}[/green]")
        console.print("[dim]Edit the file to customize your strategy.[/dim]")


# =============================================================================
# Analyze Commands
# =============================================================================
@app.command("analyze")
def analyze(
    strategy: Annotated[
        Optional[str],
        typer.Option(
            "--strategy",
            "-s",
            help="Strategy name to use",
        ),
    ] = None,
    tickers: Annotated[
        Optional[str],
        typer.Option(
            "--tickers",
            "-t",
            help="Comma-separated list of tickers",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Run analysis and generate signals."""
    import json

    from ib_daily_picker.analysis import SignalGenerator, StrategyEvaluator, load_strategy
    from ib_daily_picker.store.database import get_db_manager
    from ib_daily_picker.store.repositories import RecommendationRepository, StockRepository

    settings = get_settings()

    # Load strategy
    if not strategy:
        console.print("[red]Please specify a strategy with --strategy[/red]")
        raise typer.Exit(1)

    try:
        strat = load_strategy(strategy)
    except Exception as e:
        console.print(f"[red]Failed to load strategy: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Running analysis with strategy: {strat.name}[/cyan]")

    # Get tickers
    ticker_list = tickers.split(",") if tickers else settings.basket.default_tickers[:10]
    console.print(f"  Analyzing: {', '.join(ticker_list)}")

    # Initialize components
    db = get_db_manager()
    stock_repo = StockRepository(db)
    rec_repo = RecommendationRepository(db)

    evaluator = StrategyEvaluator(strat, stock_repo)
    generator = SignalGenerator(strat)

    # Evaluate each ticker
    results = []
    with console.status("[bold green]Evaluating...") as status:
        for ticker in ticker_list:
            status.update(f"[bold green]Evaluating {ticker}...")
            try:
                eval_result = evaluator.evaluate(ticker)
                if eval_result.signal_triggered:
                    results.append(eval_result)
            except Exception as e:
                console.print(f"[yellow]  {ticker}: {e}[/yellow]")

    if not results:
        console.print("[yellow]No signals triggered.[/yellow]")
        return

    # Generate and save recommendations
    signal_result = generator.generate_signals(results)
    for rec in signal_result.recommendations:
        rec_repo.save(rec)

    if json_output:
        data = [
            {
                "symbol": r.symbol,
                "signal_type": r.signal_type.value,
                "entry_price": str(r.entry_price) if r.entry_price else None,
                "stop_loss": str(r.stop_loss) if r.stop_loss else None,
                "take_profit": str(r.take_profit) if r.take_profit else None,
                "confidence": float(r.confidence),
            }
            for r in signal_result.recommendations
        ]
        console.print(json.dumps(data, indent=2))
        return

    # Display results
    console.print(f"\n[green]Generated {len(signal_result.recommendations)} signal(s):[/green]")
    table = Table(title="Signals")
    table.add_column("Symbol", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Entry", justify="right")
    table.add_column("Stop", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Confidence", justify="right")

    for rec in signal_result.recommendations:
        table.add_row(
            rec.symbol,
            rec.signal_type.value,
            f"${rec.entry_price:.2f}" if rec.entry_price else "-",
            f"${rec.stop_loss:.2f}" if rec.stop_loss else "-",
            f"${rec.take_profit:.2f}" if rec.take_profit else "-",
            f"{float(rec.confidence):.0%}",
        )

    console.print(table)


@app.command("signals")
def signals(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of signals to show"),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show recent trading signals."""
    import json

    from ib_daily_picker.store.database import get_db_manager
    from ib_daily_picker.store.repositories import RecommendationRepository

    db = get_db_manager()
    rec_repo = RecommendationRepository(db)

    # Get pending recommendations
    recommendations = rec_repo.get_pending(limit=limit)

    if not recommendations:
        console.print("[yellow]No pending signals found.[/yellow]")
        return

    if json_output:
        data = [
            {
                "id": r.id,
                "symbol": r.symbol,
                "signal_type": r.signal_type.value,
                "entry_price": str(r.entry_price) if r.entry_price else None,
                "stop_loss": str(r.stop_loss) if r.stop_loss else None,
                "take_profit": str(r.take_profit) if r.take_profit else None,
                "confidence": float(r.confidence),
                "generated_at": r.generated_at.isoformat(),
            }
            for r in recommendations
        ]
        console.print(json.dumps(data, indent=2))
        return

    console.print(f"[cyan]Recent signals ({len(recommendations)}):[/cyan]")
    table = Table()
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Symbol", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Entry", justify="right")
    table.add_column("Stop", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Generated", style="dim")

    for rec in recommendations:
        table.add_row(
            rec.id[:8],
            rec.symbol,
            rec.signal_type.value,
            f"${rec.entry_price:.2f}" if rec.entry_price else "-",
            f"${rec.stop_loss:.2f}" if rec.stop_loss else "-",
            f"${rec.take_profit:.2f}" if rec.take_profit else "-",
            f"{float(rec.confidence):.0%}",
            rec.generated_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# =============================================================================
# Journal Commands
# =============================================================================
journal_app = typer.Typer(
    name="journal",
    help="Trade journal commands.",
    no_args_is_help=True,
)
app.add_typer(journal_app)


@journal_app.command("list")
def journal_list(
    status: Annotated[
        Optional[str],
        typer.Option("--status", help="Filter by status: open, closed, all"),
    ] = "all",
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of trades to show"),
    ] = 20,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List trades in journal."""
    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    trades = []
    if status in ("open", "all"):
        trades.extend(manager.get_open_trades())
    if status in ("closed", "all"):
        trades.extend(manager.get_closed_trades(limit=limit))

    if json_output:
        import json

        data = [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction.value,
                "entry_price": str(t.entry_price),
                "exit_price": str(t.exit_price) if t.exit_price else None,
                "pnl": str(t.pnl) if t.pnl else None,
                "status": t.status.value,
            }
            for t in trades[:limit]
        ]
        console.print(json.dumps(data, indent=2))
        return

    if not trades:
        console.print("[yellow]No trades found.[/yellow]")
        return

    table = Table(title=f"Trade Journal ({len(trades)} trades)")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Symbol", style="cyan")
    table.add_column("Dir")
    table.add_column("Entry", style="green")
    table.add_column("Exit")
    table.add_column("PnL")
    table.add_column("R", style="dim")
    table.add_column("Status")

    for trade in trades[:limit]:
        dir_style = "green" if trade.direction.value == "long" else "red"
        pnl_str = ""
        if trade.pnl is not None:
            pnl_style = "green" if trade.pnl > 0 else "red"
            pnl_str = f"[{pnl_style}]${trade.pnl:,.2f}[/{pnl_style}]"

        r_str = f"{trade.r_multiple:.1f}R" if trade.r_multiple else "-"

        table.add_row(
            trade.id[:8],
            trade.symbol,
            f"[{dir_style}]{trade.direction.value}[/{dir_style}]",
            f"${trade.entry_price:.2f}",
            f"${trade.exit_price:.2f}" if trade.exit_price else "-",
            pnl_str,
            r_str,
            trade.status.value,
        )

    console.print(table)


@journal_app.command("open")
def journal_open(
    symbol: Annotated[str, typer.Argument(help="Stock ticker symbol")],
    entry_price: Annotated[
        float,
        typer.Option("--price", "-p", help="Entry price"),
    ],
    size: Annotated[
        float,
        typer.Option("--size", "-s", help="Position size (shares)"),
    ],
    direction: Annotated[
        str,
        typer.Option("--direction", "-d", help="Trade direction: long or short"),
    ] = "long",
    stop_loss: Annotated[
        Optional[float],
        typer.Option("--stop", help="Stop loss price"),
    ] = None,
    take_profit: Annotated[
        Optional[float],
        typer.Option("--target", help="Take profit target"),
    ] = None,
    tags: Annotated[
        Optional[str],
        typer.Option("--tags", help="Comma-separated tags"),
    ] = None,
) -> None:
    """Open a new trade."""
    from decimal import Decimal

    from ib_daily_picker.journal import get_journal_manager
    from ib_daily_picker.models import TradeDirection

    manager = get_journal_manager()

    trade_dir = TradeDirection.LONG if direction.lower() == "long" else TradeDirection.SHORT
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    trade = manager.open_trade(
        symbol=symbol.upper(),
        direction=trade_dir,
        entry_price=Decimal(str(entry_price)),
        position_size=Decimal(str(size)),
        stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
        take_profit=Decimal(str(take_profit)) if take_profit else None,
        tags=tag_list,
    )

    console.print(f"[green]Opened trade {trade.id[:8]}[/green]")
    console.print(f"  Symbol: {trade.symbol}")
    console.print(f"  Direction: {trade.direction.value}")
    console.print(f"  Entry: ${trade.entry_price:.2f}")
    console.print(f"  Size: {trade.position_size} shares")
    if trade.stop_loss:
        console.print(f"  Stop Loss: ${trade.stop_loss:.2f}")
    if trade.take_profit:
        console.print(f"  Take Profit: ${trade.take_profit:.2f}")


@journal_app.command("execute")
def journal_execute(
    recommendation_id: Annotated[
        str,
        typer.Argument(help="Recommendation ID to execute"),
    ],
    entry_price: Annotated[
        float,
        typer.Option("--price", "-p", help="Actual entry price"),
    ],
    size: Annotated[
        float,
        typer.Option("--size", "-s", help="Position size (shares)"),
    ],
) -> None:
    """Record trade execution from a recommendation."""
    from decimal import Decimal

    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    try:
        trade = manager.execute_recommendation(
            recommendation_id=recommendation_id,
            entry_price=Decimal(str(entry_price)),
            position_size=Decimal(str(size)),
        )
        console.print(f"[green]Executed recommendation as trade {trade.id[:8]}[/green]")
        console.print(f"  Symbol: {trade.symbol}")
        console.print(f"  Entry: ${trade.entry_price:.2f}")
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@journal_app.command("close")
def journal_close(
    trade_id: Annotated[
        str,
        typer.Argument(help="Trade ID to close"),
    ],
    exit_price: Annotated[
        float,
        typer.Option("--price", "-p", help="Exit price"),
    ],
    notes: Annotated[
        Optional[str],
        typer.Option("--notes", "-n", help="Trade notes"),
    ] = None,
) -> None:
    """Close a trade."""
    from decimal import Decimal

    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    try:
        trade = manager.close_trade(
            trade_id=trade_id,
            exit_price=Decimal(str(exit_price)),
            notes=notes,
        )
        pnl_style = "green" if trade.pnl and trade.pnl > 0 else "red"
        console.print(f"[green]Closed trade {trade.id[:8]}[/green]")
        console.print(f"  Symbol: {trade.symbol}")
        console.print(f"  Exit: ${trade.exit_price:.2f}")
        if trade.pnl:
            console.print(f"  PnL: [{pnl_style}]${trade.pnl:,.2f}[/{pnl_style}]")
        if trade.r_multiple:
            console.print(f"  R-Multiple: {trade.r_multiple:.2f}")
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@journal_app.command("note")
def journal_note(
    trade_id: Annotated[
        str,
        typer.Argument(help="Trade ID"),
    ],
    note: Annotated[
        str,
        typer.Argument(help="Note to add"),
    ],
) -> None:
    """Add a note to a trade."""
    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    try:
        trade = manager.add_note(trade_id, note)
        console.print(f"[green]Note added to trade {trade.id[:8]}[/green]")
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@journal_app.command("metrics")
def journal_metrics(
    start_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Start date (YYYY-MM-DD)"),
    ] = None,
    end_date: Annotated[
        Optional[str],
        typer.Option("--to", help="End date (YYYY-MM-DD)"),
    ] = None,
    extended: Annotated[
        bool,
        typer.Option("--extended", "-e", help="Show extended metrics"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show trade performance metrics."""
    from datetime import date as date_type

    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    start = date_type.fromisoformat(start_date) if start_date else None
    end = date_type.fromisoformat(end_date) if end_date else None

    if extended:
        metrics = manager.get_extended_metrics(start_date=start, end_date=end)

        if json_output:
            import json

            data = {
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "total_pnl": str(metrics.total_pnl),
                "win_rate": str(metrics.win_rate),
                "profit_factor": str(metrics.profit_factor) if metrics.profit_factor else None,
                "expectancy": str(metrics.expectancy),
                "avg_r_multiple": str(metrics.avg_r_multiple) if metrics.avg_r_multiple else None,
            }
            console.print(json.dumps(data, indent=2))
            return

        table = Table(title="Extended Trade Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Trades", str(metrics.total_trades))
        table.add_row("Winning Trades", str(metrics.winning_trades))
        table.add_row("Losing Trades", str(metrics.losing_trades))
        table.add_row("Win Rate", f"{float(metrics.win_rate) * 100:.1f}%")
        table.add_row("Total PnL", f"${metrics.total_pnl:,.2f}")
        table.add_row("Avg Winner", f"${metrics.avg_winner:,.2f}")
        table.add_row("Avg Loser", f"${metrics.avg_loser:,.2f}")
        table.add_row("Expectancy", f"${metrics.expectancy:,.2f}")

        if metrics.profit_factor:
            table.add_row("Profit Factor", f"{metrics.profit_factor:.2f}")
        if metrics.avg_r_multiple:
            table.add_row("Avg R-Multiple", f"{metrics.avg_r_multiple:.2f}")

        table.add_row("Largest Winner", f"${metrics.largest_winner:,.2f}")
        table.add_row("Largest Loser", f"${metrics.largest_loser:,.2f}")

        # Streak info
        table.add_row("Current Streak", f"{metrics.streak.current_streak} ({metrics.streak.current_streak_type})")
        table.add_row("Max Win Streak", str(metrics.streak.max_win_streak))
        table.add_row("Max Loss Streak", str(metrics.streak.max_loss_streak))

        # Drawdown
        table.add_row("Current Drawdown", f"${metrics.drawdown.current_drawdown:,.2f}")
        table.add_row("Max Drawdown", f"${metrics.drawdown.max_drawdown:,.2f}")

        console.print(table)

    else:
        metrics = manager.get_metrics(start_date=start, end_date=end)

        if json_output:
            import json

            data = {
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "total_pnl": str(metrics.total_pnl),
                "win_rate": str(metrics.win_rate),
            }
            console.print(json.dumps(data, indent=2))
            return

        table = Table(title="Trade Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Trades", str(metrics.total_trades))
        table.add_row("Winning Trades", str(metrics.winning_trades))
        table.add_row("Losing Trades", str(metrics.losing_trades))
        table.add_row("Win Rate", f"{float(metrics.win_rate) * 100:.1f}%")
        table.add_row("Total PnL", f"${metrics.total_pnl:,.2f}")
        table.add_row("Avg Winner", f"${metrics.avg_winner:,.2f}")
        table.add_row("Avg Loser", f"${metrics.avg_loser:,.2f}")

        if metrics.profit_factor:
            table.add_row("Profit Factor", f"{metrics.profit_factor:.2f}")

        console.print(table)


@journal_app.command("export")
def journal_export(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path"),
    ] = Path("trades.csv"),
    format_type: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: csv or json"),
    ] = "csv",
    start_date: Annotated[
        Optional[str],
        typer.Option("--from", help="Start date (YYYY-MM-DD)"),
    ] = None,
    end_date: Annotated[
        Optional[str],
        typer.Option("--to", help="End date (YYYY-MM-DD)"),
    ] = None,
) -> None:
    """Export trades to file."""
    from datetime import date as date_type

    from ib_daily_picker.journal import get_journal_manager

    manager = get_journal_manager()

    start = date_type.fromisoformat(start_date) if start_date else None
    end = date_type.fromisoformat(end_date) if end_date else None

    if format_type.lower() == "json":
        content = manager.export_trades_json(start, end)
        output = output.with_suffix(".json")
    else:
        content = manager.export_trades_csv(start, end)
        output = output.with_suffix(".csv")

    output.write_text(content)
    console.print(f"[green]Exported trades to {output}[/green]")


# =============================================================================
# Backtest Commands
# =============================================================================
backtest_app = typer.Typer(
    name="backtest",
    help="Backtesting commands.",
    no_args_is_help=True,
)
app.add_typer(backtest_app)


@backtest_app.command("run")
def backtest_run(
    strategy_name: Annotated[
        str,
        typer.Argument(help="Strategy name to backtest"),
    ],
    start_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)"),
    ],
    end_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)"),
    ],
    tickers: Annotated[
        Optional[str],
        typer.Option("--tickers", "-t", help="Comma-separated tickers"),
    ] = None,
    initial_capital: Annotated[
        float,
        typer.Option("--capital", help="Initial capital"),
    ] = 100000.0,
    position_size: Annotated[
        float,
        typer.Option("--position-size", help="Position size as decimal (0.10 = 10%)"),
    ] = 0.10,
    max_positions: Annotated[
        int,
        typer.Option("--max-positions", help="Maximum concurrent positions"),
    ] = 5,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Run backtest for a strategy."""
    from datetime import date as date_type
    from decimal import Decimal

    from ib_daily_picker.analysis import get_strategy_loader
    from ib_daily_picker.backtest import (
        BacktestConfig,
        BacktestRunner,
        format_console_report,
        format_json_report,
    )
    from ib_daily_picker.store.database import get_db_manager

    settings = get_settings()

    # Load strategy
    loader = get_strategy_loader()
    try:
        strategy = loader.load(strategy_name)
    except FileNotFoundError:
        err_console.print(f"[red]Strategy not found: {strategy_name}[/red]")
        raise typer.Exit(1)

    # Get ticker list
    ticker_list = [
        t.strip().upper()
        for t in (tickers.split(",") if tickers else settings.basket.default_tickers)
    ]

    console.print(f"[cyan]Backtesting: {strategy.name}[/cyan]")
    console.print(f"  Period: {start_date} to {end_date}")
    console.print(f"  Tickers: {', '.join(ticker_list[:5])}{'...' if len(ticker_list) > 5 else ''}")
    console.print(f"  Initial Capital: ${initial_capital:,.2f}")

    config = BacktestConfig(
        start_date=date_type.fromisoformat(start_date),
        end_date=date_type.fromisoformat(end_date),
        initial_capital=Decimal(str(initial_capital)),
        position_size_pct=Decimal(str(position_size)),
        max_positions=max_positions,
    )

    db = get_db_manager()
    runner = BacktestRunner(db)

    with console.status("[bold green]Running backtest..."):
        result = runner.run(strategy, ticker_list, config)

    if not result.metrics:
        err_console.print("[red]Backtest failed - no metrics generated[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print(format_json_report(result))
    else:
        console.print(format_console_report(result))


@backtest_app.command("compare")
def backtest_compare(
    strategies: Annotated[
        str,
        typer.Option("--strategies", "-s", help="Comma-separated strategy names"),
    ],
    start_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)"),
    ],
    end_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)"),
    ],
    tickers: Annotated[
        Optional[str],
        typer.Option("--tickers", "-t", help="Comma-separated tickers"),
    ] = None,
    initial_capital: Annotated[
        float,
        typer.Option("--capital", help="Initial capital"),
    ] = 100000.0,
) -> None:
    """Compare multiple strategies."""
    from datetime import date as date_type
    from decimal import Decimal

    from ib_daily_picker.analysis import get_strategy_loader
    from ib_daily_picker.backtest import (
        BacktestConfig,
        BacktestRunner,
        format_comparison_table,
    )
    from ib_daily_picker.store.database import get_db_manager

    settings = get_settings()
    strategy_names = [s.strip() for s in strategies.split(",")]

    ticker_list = [
        t.strip().upper()
        for t in (tickers.split(",") if tickers else settings.basket.default_tickers)
    ]

    console.print(f"[cyan]Comparing strategies: {', '.join(strategy_names)}[/cyan]")
    console.print(f"  Period: {start_date} to {end_date}")

    loader = get_strategy_loader()
    db = get_db_manager()
    runner = BacktestRunner(db)

    config = BacktestConfig(
        start_date=date_type.fromisoformat(start_date),
        end_date=date_type.fromisoformat(end_date),
        initial_capital=Decimal(str(initial_capital)),
    )

    results = []
    for name in strategy_names:
        try:
            strategy = loader.load(name)
            with console.status(f"[bold green]Running {name}..."):
                result = runner.run(strategy, ticker_list, config)
                results.append(result)
        except FileNotFoundError:
            err_console.print(f"[yellow]Strategy not found: {name}[/yellow]")

    if not results:
        err_console.print("[red]No strategies successfully backtested[/red]")
        raise typer.Exit(1)

    console.print("\n" + format_comparison_table(results))


# =============================================================================
# Database Commands
# =============================================================================
db_app = typer.Typer(
    name="db",
    help="Database management commands.",
    no_args_is_help=True,
)
app.add_typer(db_app)


@db_app.command("status")
def db_status() -> None:
    """Show database status and statistics."""
    # Alias for fetch status
    fetch_status()


@db_app.command("export")
def db_export(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output file path"),
    ] = Path("export.csv"),
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table to export (ohlcv, flow_alerts, recommendations, trades)"),
    ] = "ohlcv",
) -> None:
    """Export data to CSV."""
    from ib_daily_picker.store.database import get_db_manager

    valid_tables = ["ohlcv", "flow_alerts", "recommendations", "trades"]
    if table not in valid_tables:
        console.print(f"[red]Invalid table: {table}[/red]")
        console.print(f"[dim]Valid tables: {', '.join(valid_tables)}[/dim]")
        raise typer.Exit(1)

    console.print(f"[cyan]Exporting {table} to {output}...[/cyan]")

    db = get_db_manager()
    with db.duckdb() as conn:
        # Get data
        result = conn.execute(f"SELECT * FROM {table}").fetchall()
        if not result:
            console.print(f"[yellow]No data in {table} table.[/yellow]")
            return

        # Get column names
        columns = [desc[0] for desc in conn.description]

        # Write CSV
        import csv
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(result)

    console.print(f"[green]Exported {len(result)} rows to {output}[/green]")


if __name__ == "__main__":
    app()

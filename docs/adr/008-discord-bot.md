# ADR-008: Discord Bot Interface (discord.py)

## Status
Accepted

## Context
While the CLI and web interface provide comprehensive access to IB Daily Picker functionality, users requested a Discord bot interface for:
- Receiving automated daily stock analysis in Discord channels
- Running ad-hoc analysis from mobile devices without terminal access
- Team collaboration with shared signal notifications
- Real-time alerts in existing Discord trading communities

Requirements:
- Slash commands for interactive analysis
- Scheduled daily analysis posts
- Rich embeds for readable signal presentation
- Integration with existing analysis and data layers
- Minimal additional infrastructure

Options evaluated:
- **discord.py**: Mature, async-native, official Discord library
- **Pycord**: Fork with additional features, less stable
- **hikari**: Modern but smaller ecosystem
- **Red-DiscordBot**: Framework-based, too opinionated

For scheduling:
- **discord.ext.tasks**: Built into discord.py, simple loops
- **APScheduler**: More powerful but additional dependency
- **Celery**: Overkill for single daily task

## Decision
Use **discord.py** for the Discord bot with **discord.ext.tasks** for scheduled daily analysis.

**discord.py** chosen because:
- Most mature and widely-used Discord library for Python
- Native async/await support matches existing codebase
- Built-in slash command support via `app_commands`
- Excellent documentation and community support
- Cog system for modular command organization

**discord.ext.tasks** chosen because:
- Zero additional dependencies (built into discord.py)
- Simple decorator-based loop definition
- Automatic reconnection handling
- Sufficient for daily scheduling needs

## Consequences

### Positive
- **Accessibility**: Run analysis from any Discord client (mobile, desktop, web)
- **Automation**: Daily signals posted without manual intervention
- **Collaboration**: Teams can share a bot and discuss signals in context
- **Low latency**: Slash commands respond within seconds
- **Modularity**: Cog-based architecture keeps commands organized

### Negative
- **Single-instance constraint**: Discord bots should only run one instance per token
- **Gateway dependency**: Bot requires persistent WebSocket connection
- **Rate limits**: Discord API has rate limits on message posting
- **No offline access**: Requires Discord client to interact

### Neutral
- Bot commands mirror CLI functionality (no new features, just new interface)
- Rich embeds provide similar information density to CLI tables
- Scheduling uses Eastern Time to align with US market hours

## Architecture

```
src/ib_daily_picker/discord/
├── __init__.py           # Exports IBPickerBot, run_bot
├── bot.py                # Main bot class, cog loading
├── embeds.py             # Rich embed formatters
├── scheduler.py          # Daily analysis task loop
├── storage.py            # Azure Blob Storage sync (for cloud deployment)
└── cogs/
    ├── __init__.py
    ├── core.py           # /ping, /help, /about
    ├── analysis.py       # /analyze, /signals, /strategies
    ├── data.py           # /fetch, /status, /watchlist
    ├── journal.py        # /metrics, /trades
    └── admin.py          # /schedule status, /schedule run
```

## Discord Commands

| Command | Description |
|---------|-------------|
| `/ping` | Check bot latency |
| `/help` | Show available commands |
| `/about` | Bot information and links |
| `/analyze` | Run strategy analysis |
| `/signals` | Show recent recommendations |
| `/strategies` | List available strategies |
| `/fetch stocks` | Fetch stock data |
| `/fetch flows` | Fetch flow alerts |
| `/status` | Show data coverage |
| `/watchlist` | List watched symbols |
| `/metrics` | Show trading performance |
| `/trades` | Show recent trades |
| `/schedule status` | Check daily schedule |
| `/schedule run` | Manually trigger daily analysis |

## Configuration

```bash
# Required
DISCORD_TOKEN=your_bot_token

# Optional (for faster slash command sync during development)
DISCORD_GUILD_ID=your_server_id

# Daily schedule configuration
DISCORD_DAILY_CHANNEL_ID=channel_id
DISCORD_DAILY_TIME=09:30           # Eastern Time
DISCORD_DAILY_STRATEGY=example_rsi_flow
DISCORD_DAILY_ENABLED=true
```

## Alternatives Considered

1. **Telegram Bot**: Similar reach but less common in trading communities
2. **Slack Bot**: More enterprise-focused, less retail trader adoption
3. **Matrix Bot**: Open protocol but fragmented client ecosystem
4. **Custom WebSocket server**: Maximum control but significant infrastructure overhead

## References
- discord.py documentation: https://discordpy.readthedocs.io/
- Discord API documentation: https://discord.com/developers/docs
- Implementation: `src/ib_daily_picker/discord/`
- CLI integration: `src/ib_daily_picker/cli.py` (bot command)
- Related: [ADR-009](009-azure-hosting.md) for deployment

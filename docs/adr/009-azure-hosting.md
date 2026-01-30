# ADR-009: Azure Hosting (Container Apps + Blob Storage)

## Status
Accepted

## Context
The Discord bot requires persistent hosting to maintain its WebSocket connection to Discord Gateway. Requirements:
- Always-on service (bot must stay connected)
- Persistent database storage (DuckDB + SQLite files)
- Secure secret management
- CI/CD pipeline for automated deployments
- Cost-effective for a single low-traffic bot

Hosting options evaluated:
- **Azure Container Apps**: Serverless containers, WebSocket support, scale-to-zero
- **Azure App Service**: PaaS, but more expensive for always-on
- **Azure Container Instances**: Simple but no scale-to-zero, no secrets integration
- **Azure Kubernetes Service**: Overkill complexity for single container
- **AWS Fargate/ECS**: Similar to Container Apps but different ecosystem
- **DigitalOcean App Platform**: Simpler but less Azure integration

Storage options for databases:
- **Azure Blob Storage**: Object storage with SDK, sync on startup/shutdown
- **Azure Files**: SMB mount, but has SQLite locking issues
- **Azure Managed Disks**: Block storage, persistent but complex
- **CosmosDB**: Managed DB, but would require rewriting storage layer

## Decision
Use **Azure Container Apps** for hosting with **Azure Blob Storage** for database persistence, **Azure Key Vault** for secrets, and **Azure Container Registry** for images.

**Azure Container Apps** chosen because:
- WebSocket support (required for Discord Gateway)
- Managed environment (no Kubernetes expertise required)
- Built-in HTTPS and identity support
- Cost-effective with consumption-based pricing
- GitHub Actions integration for CI/CD

**Azure Blob Storage** chosen because:
- Simple upload/download API for database files
- Works around SQLite/DuckDB file locking limitations
- Sync pattern: download on startup, upload on shutdown
- Cost-effective for small files
- Managed Identity authentication (no connection strings in code)

**Azure Key Vault** chosen because:
- Secure secret storage (Discord token, API keys)
- RBAC-based access control
- Managed Identity integration
- Audit logging for compliance

## Consequences

### Positive
- **Simplicity**: No Kubernetes cluster to manage
- **Cost**: Pay only for actual compute usage
- **Security**: Managed Identity eliminates credential management
- **CI/CD**: GitHub Actions deploys on manual trigger (workflow_dispatch)
- **Observability**: Log Analytics integration for debugging

### Negative
- **Single-replica constraint**: Discord bots must run single instance
- **Cold start**: May have startup delay after scale-to-zero
- **Storage sync**: Must handle sync failures gracefully
- **Azure lock-in**: Infrastructure code is Azure-specific

### Neutral
- Database sync happens at startup and periodic intervals
- Bicep templates define all infrastructure as code
- Environment-based deployment (dev, staging, prod)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Azure Container Apps                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Discord Bot Container               │   │
│  │  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │   │
│  │  │  Cogs   │  │Scheduler │  │ Blob Storage  │  │   │
│  │  │(commands)│  │ (daily)  │  │    Sync       │  │   │
│  │  └────┬────┘  └────┬─────┘  └───────┬───────┘  │   │
│  │       │            │                │          │   │
│  │       └────────────┴────────────────┘          │   │
│  │                    │                           │   │
│  │         ┌──────────▼──────────┐               │   │
│  │         │  Existing Services  │               │   │
│  │         │ (fetchers, analysis,│               │   │
│  │         │  store, journal)    │               │   │
│  │         └─────────────────────┘               │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│              ┌──────────▼──────────┐                   │
│              │  Azure Blob Storage │                   │
│              │  (DuckDB + SQLite)  │                   │
│              └─────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────▼─────────┐   ┌────────▼────────┐
    │   Azure Key Vault │   │  Azure Container│
    │     (secrets)     │   │    Registry     │
    └───────────────────┘   └─────────────────┘
```

## Infrastructure Components

| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Container Apps Environment | Managed environment | Log Analytics integration |
| Container App | Bot container | Single replica, 0.25 vCPU, 0.5 GB |
| Container Registry | Docker images | Basic SKU |
| Storage Account | Database files | Standard LRS, Hot tier |
| Key Vault | Secrets | Standard SKU, RBAC auth |
| Log Analytics | Logging | 30-day retention |
| Managed Identity | Auth | User-assigned |

## CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]      # Triggers build job only
  pull_request:
    branches: [main]      # Triggers build job only
  workflow_dispatch:      # Manual trigger for full deploy

jobs:
  build:     # Lint + test (runs on all triggers)
  docker:    # Build and push to ACR (manual trigger only)
  deploy:    # Deploy Bicep + update Container App (manual trigger only)
  notify:    # Report deployment status (manual trigger only)
```

**Note:** The docker, deploy, and notify jobs only run on manual trigger (workflow_dispatch)
until Azure infrastructure is set up and `AZURE_CREDENTIALS` secret is configured.

## Database Sync Strategy

```python
class BlobStorageManager:
    async def download_file(blob_name, local_path):
        """Download database file from blob storage on startup"""

    async def upload_file(local_path, blob_name):
        """Upload database file to blob storage on shutdown/interval"""

    async def sync_databases():
        """Sync both analytics.duckdb and state.sqlite"""
```

Sync triggers:
- **Startup**: Download latest from blob storage
- **Shutdown**: Upload current state
- **Periodic**: Upload every N minutes (configurable)

## Secret Management

Secrets stored in Key Vault:
- `discord-token` - Discord bot token
- `uw-api-key` - Unusual Whales API key
- `anthropic-api-key` - Anthropic API key (optional)
- `finnhub-api-key` - Finnhub API key (optional)

Access via Managed Identity (no secrets in environment variables or code).

## Environments

| Environment | Branch | Container App Name | Key Vault |
|-------------|--------|-------------------|-----------|
| dev | feature/* | ibpicker-bot-dev | ibpicker-kv-dev |
| staging | staging | ibpicker-bot-staging | ibpicker-kv-staging |
| prod | main | ibpicker-bot | ibpicker-kv |

## Alternatives Considered

1. **Azure App Service**: More expensive, overkill features
2. **Azure Functions**: No WebSocket support
3. **VM + Docker**: More control but more maintenance
4. **Railway/Fly.io**: Simpler but less Azure ecosystem integration
5. **Self-hosted**: Maximum control but requires infrastructure expertise

## References
- Azure Container Apps: https://learn.microsoft.com/en-us/azure/container-apps/
- Azure Blob Storage Python SDK: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
- Bicep documentation: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/
- Implementation: `infra/main.bicep`, `.github/workflows/deploy.yml`
- Related: [ADR-008](008-discord-bot.md) for Discord bot design

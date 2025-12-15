# Scripts Module

> [Home](../CLAUDE.md) > Scripts

## Overview

Deployment, management, and utility scripts.

## Key Scripts

| Script | Description |
|--------|-------------|
| `start_api.sh` | Start API server |
| `start_qdrant.sh` | Start Qdrant Docker container |
| `graceful-restart.sh` | Zero-downtime restart |
| `quick-deploy-new.sh` | Full deploy (commit + push + restart) |
| `deploy.sh` | Production deployment |
| `deploy-admin.sh` | Deploy with admin frontend build |
| `index_project.sh` | Run indexer |
| `logs.sh` | View server logs |
| `config.sh` | Shared configuration |
| `start-mcp-server.sh` | Start MCP server |

## Migration Scripts

| Script | Description |
|--------|-------------|
| `migrate_multi_user.py` | Multi-user migration |
| `restore_knowledge.py` | Restore knowledge from backup |
| `migrations/` | SQL migration files |

## Usage Examples

### Start Development

```bash
# Start Qdrant
./scripts/start_qdrant.sh

# Start API
./scripts/start_api.sh
```

### Deploy Changes

```bash
# Quick deploy with commit message
./scripts/quick-deploy-new.sh "feat: new feature"

# Graceful restart (no commit)
./scripts/graceful-restart.sh
```

### View Logs

```bash
./scripts/logs.sh
# or
tail -f logs/rag.log
```

### Index Project

```bash
./scripts/index_project.sh
# or
python -m indexer.index_all --incremental
```

## Graceful Restart (`graceful-restart.sh`)

Zero-downtime restart process:

1. Find existing uvicorn process
2. Start new process on same port
3. Wait for health check
4. Kill old process

## Quick Deploy (`quick-deploy-new.sh`)

Full deployment flow:

1. Detect frontend changes
2. Build frontend if needed
3. Git commit and push
4. SSH to server
5. Git pull
6. Upload frontend dist (if changed)
7. Graceful restart

## Configuration (`config.sh`)

Shared variables:
- `REMOTE_USER`
- `REMOTE_HOST`
- `REMOTE_DIR`
- `API_PORT`

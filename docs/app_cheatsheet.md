# App Cheatsheet

**<PROJECT_NAME> — Quick Reference**

## URLs & Endpoints

### Local Development

| URL | Description |
|-----|-------------|
| `http://localhost:<FRONTEND_PORT>` | Frontend (dev server, proxies API to backend) |
| `http://localhost:<BACKEND_PORT>` | Backend API root |
| `http://localhost:<BACKEND_PORT>/health` | Health check |
| `http://localhost:<BACKEND_PORT>/docs` | Swagger/OpenAPI docs |
| `http://localhost:<BACKEND_PORT>/redoc` | ReDoc API docs |

### Dev Login Credentials

Seeded by `bash scripts/db_seed.sh`. Password for all accounts: `<!-- TODO: fill in -->`

| Email | Role | Notes |
|-------|------|-------|
| `admin@test.com` | admin | <!-- TODO: fill in --> |
| `user@test.com` | user | <!-- TODO: fill in --> |

> **TODO:** Implement sign-up flows so accounts can be created without seeding.

### Monitoring Dashboard

| URL | Description |
|-----|-------------|
| `http://localhost:<BACKEND_PORT>/dashboard` | Overview dashboard |
| `http://localhost:<BACKEND_PORT>/dashboard/logs` | Log Viewer |
| `http://localhost:<BACKEND_PORT>/dashboard/metrics` | Metrics Explorer |

### Dashboard API Endpoints (prefix: `/api/v1/dashboard`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health-overview` | Status, uptime, counters |
| `GET` | `/performance` | Latency percentiles, model metrics |
| `GET` | `/safety` | Safety pass rate, violations |
| `GET` | `/alerts` | Active alerts with runbook URLs |
| `GET` | `/logs?level=&search=&limit=200` | Filtered log records |
| `GET` | `/time-series?metric=&bucket=60` | Time-bucketed metric data |
| `GET` | `/request-stats` | API call counts, errors, latency by path |

### API Endpoints (prefix: `/api/v1`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sources/upload` | Upload and ingest a file (PDF, DOCX, TXT, MD) |
| `POST` | `/sources/url` | Ingest content from a URL |
| `POST` | `/sources/text` | Ingest raw text content |
| `POST` | `/sources/folder` | Ingest all supported files from a local folder |
| `GET` | `/sources` | List sources with optional filters |
| `GET` | `/sources/{id}` | Get full source detail |
| `PUT` | `/sources/{id}` | Update source metadata (title, tags, description) |
| `DELETE` | `/sources/{id}` | Delete source, vectors, and stored files |
| `POST` | `/sources/{id}/reindex` | Re-index a source from its stored original |
| `GET` | `/sources/{id}/original` | Download the original source file |
| `GET` | `/sources/{id}/view` | View the source inline |
| `POST` | `/chat` | Send a chat message, get RAG-powered response |
| `GET` | `/chat/sessions` | List all chat sessions |
| `GET` | `/chat/sessions/{id}` | Get chat session with message history |
| `POST` | `/summarize` | Summarize by source IDs or topic |
| `POST` | `/qna/generate` | Generate Q&A pairs from topic or sources |
| `GET` | `/qna/{id}` | Retrieve a generated Q&A set |
| `POST` | `/qna/{id}/export` | Export Q&A set as JSON or Markdown |
| `POST` | `/interview/start` | Start an interview preparation session |
| `POST` | `/interview/{id}/answer` | Submit answer, get feedback + next question |
| `GET` | `/interview/{id}/summary` | Get interview summary with scores |

## Commands

```bash
# Start development server
uv run uvicorn main:app --reload --host 0.0.0.0 --port <BACKEND_PORT>

# Run all tests
uv run pytest tests/ -x -q

# Run by category
uv run pytest tests/unit/          # Unit tests
uv run pytest tests/integration/   # Integration tests
uv run pytest tests/evaluation/    # Model evaluation
uv run pytest tests/safety/        # Safety & compliance

# Lint and type check
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy src/ --ignore-missing-imports

# Coverage report
uv run pytest tests/ --cov=src --cov-report=html
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `APP_ENV` | `dev` | Environment: dev, staging, production, test |
| `APP_DEBUG` | `true` | Debug mode |
| `MODEL_BACKEND` | `mock` | Model backend: `mock`, `local`, `cloud` |
| `SECRET_KEY` | (required in prod) | Application secret key |
| `DATABASE__URL` | — | Database connection string |
| <!-- TODO: add project-specific env vars --> | | |

## Monitoring

| Dashboard | Description | Runbook |
|-----------|-------------|---------|
| Prediction Metrics | Confidence, latency, model distribution | `docs/runbook/low_confidence.md` |
| Latency | p50/p95/p99 for all components | `docs/runbook/high_latency.md` |
| Safety Compliance | Policy violations | — |
| <!-- TODO: add project-specific dashboards --> | | |

## Key Files

| Path | Description |
|------|-------------|
| `main.py` | Application entry point |
| `src/api/` | HTTP endpoint definitions |
| `src/pipelines/` | Core pipeline logic |
| `src/models/` | ML model wrappers |
| `src/observability/` | Metrics, alerts, audit |
| `configs/dev.yaml` | Development configuration |
| <!-- TODO: add project-specific key files --> | |

## Scripts

All operational scripts live in `scripts/`. Every manual step required to run the application has a corresponding script (REQ-RUN-001).

### First-Time Setup

```bash
# Full developer environment setup (installs deps, copies .env, installs pre-commit, runs tests)
bash scripts/setup.sh

# Or manual setup:
uv sync --extra dev
cp .env.example .env          # edit with your settings
uv run pre-commit install
```

### Database Management

```bash
# Create database user + database (idempotent, needs sudo)
sudo bash scripts/db_setup.sh

# Apply all pending migrations
bash scripts/db_migrate.sh upgrade

# Generate a new migration after model changes
bash scripts/db_migrate.sh generate "add column X to table Y"

# Roll back one migration
bash scripts/db_migrate.sh downgrade -1

# Show migration status (current revision, pending)
bash scripts/db_migrate.sh status

# Seed development data
bash scripts/db_seed.sh

# Seed with reset (truncate all tables first)
bash scripts/db_seed.sh --reset

# Full database health check
bash scripts/db_status.sh

# Back up database
bash scripts/db_backup.sh

# Restore from backup
bash scripts/db_restore.sh backups/<filename>

# Nuclear reset: drop all, re-migrate, re-seed (blocked in production)
bash scripts/db_reset.sh
```

**Database configuration** is read from `.env` — see the `DATABASE__*` variables. All destructive scripts require typing "yes" to confirm and are blocked when `APP_ENV=production`.

### Starting the Application

```bash
# Backend — development server (with hot reload)
bash scripts/start_server.sh

# Backend — staging (2 workers)
bash scripts/start_server.sh staging

# Backend — production (4 workers)
bash scripts/start_server.sh production

# Frontend — dev server (proxies /api to backend)
bash frontend/scripts/start.sh

# Frontend — production build
bash frontend/scripts/start.sh build

# Frontend — stop
bash frontend/scripts/stop.sh
```

**Typical dev workflow:** Start the backend first (`bash scripts/start_server.sh`), then in a second terminal start the frontend (`bash frontend/scripts/start.sh`). The frontend dev server proxies API calls to the backend.

### Data & Models

```bash
# Download model weights (may require auth for gated models)
bash scripts/download_models.sh

# Initialize data directory structure
bash scripts/init_data.sh

# Initialize with mock data for development
bash scripts/init_data.sh --mock

# Index embeddings into the vector store
bash scripts/index_embeddings.sh
```

### Git Workflow

```bash
# Quick commit and push
./scripts/git_push.sh "your commit message" --all

# Commit with tests
./scripts/git_push.sh "your commit message" --all --test

# Just check status
./scripts/git_push.sh --status
```

### Requirements Sync

Syncs `docs/requirements/*_controller.json` from the corresponding `*_requirements.md` files. Preserves any `implement`/`enable` flags already set to `"Y"`.

```bash
# Preview changes (no files written)
./scripts/sync_requirements.sh --dry-run

# Apply changes (syncs both common + documentation)
./scripts/sync_requirements.sh

# Sync only one file
./scripts/sync_requirements.sh --file common
./scripts/sync_requirements.sh --file documentation
```

## Running in Local Mode (Complete Checklist)

```bash
# 1. Setup environment
bash scripts/setup.sh

# 2. Set MODEL_BACKEND=local in .env
#    (setup.sh creates .env from .env.example — edit the MODEL_BACKEND line)

# 3. Install ML + optional dependencies
uv sync --extra dev --extra ml

# 4. Setup database
sudo bash scripts/db_setup.sh        # Create user + database
bash scripts/db_migrate.sh upgrade   # Apply migrations
bash scripts/db_seed.sh              # Seed development data

# 5. Download model weights
bash scripts/download_models.sh

# 6. Start the server
bash scripts/start_server.sh

# 7. Verify with integration tests
MODEL_BACKEND=local uv run pytest tests/integration/ -v
```

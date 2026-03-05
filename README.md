# Portman

**The port authority for homelabs and dev clusters.**

Portman discovers, tracks, and allocates TCP/UDP ports across everything running on your machine — K3s services, Docker containers, systemd daemons, and project configs — so you never hit `EADDRINUSE` again.

```
$ portman list
PORT   PROTO  SERVICE            CATEGORY   STATUS  SOURCE
22     tcp    sshd               system     active  systemd:sshd.service
5432   tcp    postgresql         database   active  systemd:postgresql.service
6333   tcp    qdrant             database   active  docker:qdrant
6444   tcp    k3s-api            system     active  k8s:kubernetes
7474   tcp    neo4j-http         database   active  docker:neo4j
8000   tcp    my-api             http       active  project:~/projects/backend/.env
9100   tcp    node-exporter      monitoring active  systemd:node-exporter.service
9800   tcp    portman-daemon     system     active  daemon:self
```

---

## Why Portman?

If you run a homelab or local dev cluster, you have ports claimed by five different systems and no unified view:

- **K3s** owns some ports (6443, 10250, NodePorts)
- **Docker** publishes others (Neo4j on 7474, Qdrant on 6333)
- **systemd** runs bare-metal services (sshd on 22, postgres on 5432)
- **Your projects** hardcode ports in `.env` and `docker-compose.yml`
- **Dev servers** grab whatever they want (`npm run dev` on 3000)

Conflicts are discovered at startup. The fix is always "pick another number." Nobody tracks the whole picture.

### Existing tools don't solve this

| Tool | What it does | The gap |
|------|-------------|---------|
| [Port Keeper](https://portkeeper.net/) | Reserve ports, detect conflicts, team sharing | You manually register everything. No scanning. No daemon. |
| [Port-Kill](https://www.blog.brightcoding.dev/2026/02/06/port-kill-the-essential-dev-tool-for-port-management) | Kill processes blocking ports | Reactive — fixes symptoms, not causes. No registry. |
| [Portree](https://github.com/fairy-pitta/portree) | Hash-based port allocation for git worktrees | One trick for one workflow. No system awareness. |
| [devports](https://dev.to/bendechrai/stop-manually-tracking-development-ports-i-built-an-automated-solution-44k0) | Automatic allocation across worktrees | Worktree-specific. No system inventory. |

Every one of these assumes you already know what's in use. **None of them go find out for you.**

---

## What Portman Does

### Discovers ports from every source

One command builds a complete inventory:

```bash
portman init ~/projects/
```

Portman scans three layers:

**Project configs** — reads your source files directly:
- `docker-compose.yml` port mappings
- `.env` files with `*PORT*` variables
- `package.json` scripts with `--port` flags
- Python files with uvicorn/gunicorn port args
- `nginx.conf` / `httpd.conf` listen directives
- YAML/TOML configs with port keys

**Installed system software** — reads what's configured, not just running:
- systemd unit files (`ListenStream=`, `ExecStart=` port args)
- Service configs in `/etc/` (sshd, postgres, redis, nginx, mysql)
- Docker container port mappings
- K3s/Kubernetes service ports

**Live processes** — probes what's actually listening and cross-references against the registry to find rogue and stale ports.

### Allocates ports at runtime

Services request ports from Portman instead of hardcoding them:

```bash
# Shell — in any service's start script
PORT=$(portman alloc my-service --type http --format plain)
uvicorn main:app --port $PORT
```

```python
# Python
from portman import allocate_port
port = allocate_port("my-service", category="http")
```

```bash
# Any language — via the daemon's HTTP API
PORT=$(curl -s http://127.0.0.1:9800/api/v1/ports/allocate \
  -d '{"service":"my-go-svc","category":"http"}' | jq -r '.port')
```

The daemon guarantees no duplicates, even when multiple services start simultaneously.

### Prevents conflicts before they happen

1. **At scan time** — `portman init` highlights conflicts before committing to the registry
2. **At allocation time** — checks both the registry and live system state
3. **At runtime** — periodic health checks catch rogue processes on registered ports

When a conflict is found, Portman suggests the nearest available alternative in the same category.

### Knows what common ports are

Built-in knowledge base of hundreds of well-known services. Port 5432 isn't "unknown TCP" — it's "PostgreSQL (database)." Port 9100 is "Prometheus Node Exporter." Port 6444 is "K3s API."

---

## Features

- **Multi-source scanner** — project configs, systemd, Docker, K3s, live processes
- **System daemon** (`portmand`) — runs as a systemd user service, handles concurrent allocations
- **CLI** (`portman`) — init, scan, alloc, release, list, search, conflicts, check, gc, export, import
- **Web dashboard** — sortable table, conflict highlighting, port map visualization, live status
- **REST API** — language-agnostic allocation at `http://127.0.0.1:9800/api/v1/`
- **Python SDK** — `from portman import allocate_port`
- **Category-based range policies** — HTTP in 8000-8999, databases in 5400-5499, customizable
- **Well-known port knowledge base** — auto-identifies hundreds of common services
- **SQLite registry** — zero-config, WAL mode for concurrent access
- **Rich CLI output** — color-coded tables, conflict highlighting

---

## Quick Start

### Install

```bash
# From source (requires Python 3.12+ and uv)
git clone https://github.com/yourusername/cluster-port-manager.git
cd cluster-port-manager
uv sync
```

### Scan your machine

```bash
# Scan projects and system software, build the registry
portman init ~/projects/

# Or scan just projects
portman init ~/projects/ --projects-only

# Or scan just system services
portman init --system-only
```

### Allocate ports

```bash
# Next available HTTP port (from 8000-8999)
portman alloc my-service --type http

# Specific port
portman alloc redis-cache --port 6380 --type database

# Multiple ports from a manifest
portman alloc --manifest .portman.yaml
```

### Query the registry

```bash
# List everything
portman list

# Filter by category
portman list --category database

# Filter by source
portman list --source-type docker

# Check for conflicts
portman conflicts

# Validate live state (find stale/rogue ports)
portman check
```

### Start the daemon

```bash
# Run in foreground
portman daemon start

# Or install as a systemd user service (auto-starts on login)
portman daemon install
systemctl --user enable portmand

# Check status
portman daemon status
```

### Web dashboard

```bash
portman serve
# Dashboard at http://127.0.0.1:9999
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `portman init [dirs...]` | Scan directories + system, initialize registry |
| `portman scan [dirs...]` | Incremental re-scan, show diff |
| `portman alloc <service>` | Allocate a port (`--type`, `--port`, `--range`, `--count`, `--format`) |
| `portman release <service\|--port N>` | Release port(s) |
| `portman reserve <port>` | Reserve a port (`--for <service>`, `--until <date>`) |
| `portman list` | List ports (`--service`, `--range`, `--category`, `--status`, `--source-type`) |
| `portman info <port>` | Detailed port info |
| `portman search <query>` | Fuzzy search across services, paths, descriptions |
| `portman conflicts` | Report all current conflicts |
| `portman check` | Validate registry vs live state (stale + rogue) |
| `portman gc` | Interactive cleanup of stale allocations |
| `portman env <service>` | Generate `.env` file with allocated ports |
| `portman export` | Export registry (`--format json\|csv\|yaml`) |
| `portman import <file>` | Import allocations from file |
| `portman config` | View/edit configuration |
| `portman daemon start\|stop\|status` | Manage the daemon |
| `portman daemon install\|uninstall` | Manage systemd service |
| `portman serve` | Start web dashboard |

Global flags: `--verbose` / `-v`, `--quiet` / `-q`, `--yes` / `-y` (skip confirmations).

---

## Default Port Ranges

| Category | Range | Examples |
|----------|-------|---------|
| `http` | 8000-8999 | API backends, web servers |
| `frontend` | 3000-3999 | React, Next.js, Vue dev servers |
| `database` | 5400-5499 | PostgreSQL, MySQL, Redis |
| `grpc` | 50000-50099 | gRPC services |
| `messaging` | 5600-5699 | RabbitMQ, Kafka |
| `debug` | 9200-9299 | Debug/profiling ports |
| `custom` | 10000-10999 | Everything else |
| `system` | 0-1023 | Reserved, never allocated |

Customizable in `~/.portman/config.yaml`. Per-project overrides in `.portman.yaml`.

---

## Service Integration

### .portman.yaml manifest

Declare a service's port needs:

```yaml
service: my-app
ports:
  - name: http
    type: http
    env_var: APP_PORT
  - name: debug
    type: debug
    env_var: DEBUG_PORT
```

```bash
portman alloc --manifest .portman.yaml
# Allocated port 8013 (tcp/http) for my-app [APP_PORT]
# Allocated port 9205 (tcp/debug) for my-app [DEBUG_PORT]

portman env my-app > .env.ports
# APP_PORT=8013
# DEBUG_PORT=9205
```

### REST API

When the daemon is running, any language can allocate ports:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/ports` | List all ports (query filters supported) |
| `POST` | `/api/v1/ports/allocate` | Allocate a port |
| `DELETE` | `/api/v1/ports/{port}` | Release a port |
| `GET` | `/api/v1/services` | List all services |
| `GET` | `/api/v1/conflicts` | Current conflicts |
| `GET` | `/api/v1/status` | Live port status |
| `GET` | `/api/v1/stats` | Allocation statistics |

---

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌────────────────┐
│   CLI (portman)  │---->│                  │---->│  Port Registry │
└──────────────────┘     │   Core Engine    │     │  (SQLite, WAL) │
                         │                  │     └────────────────┘
┌──────────────────┐     │  - Scanner       │
│  Web Dashboard   │---->│  - Allocator     │
│  (FastAPI+Jinja) │     │  - Validator     │
└──────────────────┘     │  - Policy Engine │
                         │  - Known Ports   │
┌──────────────────┐     │                  │
│  System Daemon   │---->│                  │
│  (portmand)      │     └──────────────────┘
│  - Unix socket   │            ^
│  - HTTP API      │            |
└──────────────────┘     ┌──────────────────┐
                         │     Parsers       │
┌──────────────────┐     │  - docker-compose │
│  Service Clients │     │  - .env / YAML    │
│  (Python SDK,    │---->│  - nginx / Python │
│   curl, scripts) │     │  - systemd units  │
└──────────────────┘     │  - docker inspect │
                         │  - kubectl get svc│
                         │  - live processes  │
                         └──────────────────┘
```

---

## Who Should Use This

Portman is for **mixed-orchestration environments** where multiple tools share the same host ports.

**Good fit:**
- Homelab with K3s + Docker + systemd + dev projects on one machine
- Developer laptop running 10+ services with different tools
- Bare-metal cluster with services that can't all be containerized
- Small startup with a shared dev/staging server

**Not the right tool:**
- Fully managed cloud Kubernetes (EKS/GKE/AKS) — use Ingress + service mesh instead
- Everything containerized on an overlay network — no port conflicts possible
- Enterprise with CMDB and platform engineering — different solutions exist

For the architecturally correct way to eliminate port conflicts permanently (full containerization with overlay networking), see the [Full Containerization Guide](docs/FULL_CONTAINERIZATION_GUIDE.md). Portman is for environments where that isn't practical yet.

---

## How It Compares

| Capability | Port Keeper | Port-Kill | devports | Portree | **Portman** |
|-----------|:-----------:|:---------:|:--------:|:-------:|:-----------:|
| Manual port registration | Yes | - | - | - | Yes |
| Kill port-hogging processes | - | Yes | - | - | - |
| Worktree-aware allocation | - | - | Yes | Yes | - |
| Project config file scanning | - | - | - | - | **Yes** |
| System software scanning | - | - | - | - | **Yes** |
| Live process detection | Yes | Yes | - | - | **Yes** |
| Conflict prevention | - | - | - | - | **Yes** |
| Runtime daemon | - | - | - | - | **Yes** |
| Concurrent-safe allocation | - | - | - | - | **Yes** |
| Well-known port knowledge base | - | - | - | - | **Yes** |
| systemd integration | - | - | - | - | **Yes** |
| Docker/K8s port discovery | - | - | - | - | **Yes** |
| Web dashboard | - | - | - | - | **Yes** |
| REST API | - | - | - | - | **Yes** |
| Category-based range policies | Yes | - | - | - | **Yes** |

---

## Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.12+ |
| CLI | Typer + Rich |
| Web | FastAPI + Jinja2 |
| Database | SQLite (aiosqlite, WAL mode) |
| Scanning | Custom parsers + psutil |
| Daemon | Unix socket + uvicorn |
| Config | Pydantic Settings |

---

## Development

```bash
# Setup
uv sync --extra dev
uv run pre-commit install

# Run tests
uv run pytest tests/ -x -q

# Lint + typecheck
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy src/ --ignore-missing-imports

# Full quality check
bash scripts/check_all.sh
```

---

## Roadmap

- [x] Requirements and architecture
- [ ] Core engine (registry, allocator, validator, policy)
- [ ] File parsers (docker-compose, .env, nginx, Python, YAML)
- [ ] System parsers (systemd, Docker, K3s)
- [ ] CLI commands
- [ ] System daemon
- [ ] Web dashboard
- [ ] Python SDK
- [ ] Publish to PyPI

### Future (v2+)

- Watch mode — monitor for new port bindings in real-time
- Config rewriting — update `.env` and `docker-compose.yml` with allocated ports
- Multi-host support — central server + agent architecture
- Port dependency graph — service A depends on service B's port
- Slack/webhook notifications on conflicts

---

## Contributing

Contributions welcome. Please open an issue first to discuss what you'd like to change.

---

## License

MIT

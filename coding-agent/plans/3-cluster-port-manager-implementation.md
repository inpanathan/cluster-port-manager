# Plan 3: Cluster Port Manager — Full Implementation

**Status**: AWAITING APPROVAL
**Branch**: TBD (suggest: `feat/portman-core`)
**Requirements**: `docs/requirements/project_requirements_v1.md` (99 reqs), `common_requirements.md` (203 reqs), `documentation_requirements.md` (51 reqs)

---

## Overview

Build `portman` — a CLI + system daemon + web dashboard for centralized port management across development cluster services. SQLite-backed registry, file/process/system scanning, conflict detection, daemon-based runtime allocation, and a FastAPI web dashboard.

---

## Phase 1: Project Setup & Foundation

### 1.1 Dependencies & Project Config
- [ ] Add new dependencies to `pyproject.toml`: `typer`, `rich`, `aiosqlite`, `psutil`, `jinja2`
- [ ] Add `[project.scripts]` entry: `portman = "src.cli.app:main"`
- [ ] Run `uv sync --extra dev`
- **Reqs**: REQ-CLI-001, REQ-CLI-003, REQ-NFR-013

### 1.2 Directory Structure
- [ ] Create source directories: `src/cli/`, `src/cli/commands/`, `src/core/`, `src/parsers/`, `src/db/`, `src/daemon/`, `src/web/`, `src/web/templates/`, `src/web/static/`
- [ ] Create test directories: `tests/unit/test_parsers/`, `tests/fixtures/sample_projects/`, `tests/fixtures/sample_configs/`, `tests/fixtures/sample_system/`
- [ ] Add `__init__.py` files

### 1.3 Configuration
- [ ] Add portman-specific settings to `src/utils/config.py`: registry path (`~/.portman/registry.db`), config path (`~/.portman/config.yaml`), daemon socket path, daemon HTTP port (9800), health check interval, default port ranges
- [ ] Create `configs/default_ranges.yaml` with default category ranges from requirements section 8
- [ ] Add `.portman.yaml` schema support (Pydantic model for per-project manifests)
- **Reqs**: REQ-POL-001, REQ-REG-001, REQ-CFG-001 through REQ-CFG-003

### 1.4 Error Handling
- [ ] Add portman-specific error codes to `src/utils/errors.py`: `PORT_CONFLICT`, `PORT_IN_USE`, `PORT_NOT_FOUND`, `INVALID_RANGE`, `REGISTRY_ERROR`, `SCAN_ERROR`, `POLICY_VIOLATION`, `DAEMON_UNAVAILABLE`, `DAEMON_ALREADY_RUNNING`
- **Reqs**: REQ-ERR-001, REQ-NFR-008

---

## Phase 2: Database Layer

### 2.1 Models
- [ ] Create `src/db/models.py` — Pydantic models for: `PortAllocation`, `PortRangePolicy`, `ScanHistory`
- [ ] Define enums: `PortCategory` (http, frontend, database, grpc, messaging, debug, custom), `PortStatus` (active, stale, reserved, conflict), `Protocol` (tcp, udp), `SourceType` (project_config, process, systemd, docker, k8s, system_config, manual)
- **Reqs**: REQ-ALLOC-006, REQ-SCAN-004, REQ-SCAN-005, REQ-SCAN-010

### 2.2 Connection Management
- [ ] Create `src/db/connection.py` — SQLite connection factory with WAL mode, user-only permissions (0600)
- [ ] Support both sync (CLI) and async (daemon/web) access patterns
- [ ] Create database and `~/.portman/` directory on first use
- **Reqs**: REQ-REG-001, REQ-NFR-004, REQ-NFR-005, REQ-NFR-011

### 2.3 Schema & Migrations
- [ ] Create `src/db/migrations.py` — schema creation for `port_allocations`, `port_range_policies`, `scan_history` tables
- [ ] Add `source_type` column to `port_allocations`
- [ ] Unique constraint on `(port, protocol)`
- [ ] Seed default port range policies from `configs/default_ranges.yaml`
- **Reqs**: REQ-NFR-005

---

## Phase 3: Core Engine

### 3.1 Well-Known Ports Knowledge Base
- [ ] Create `src/core/known_ports.py` — dictionary mapping port numbers to service metadata:
  - sshd=22, dns=53, http=80, https=443, cups=631, mysql=3306, postgres=5432, redis=6379, neo4j-http=7474, neo4j-bolt=7687, qdrant=6333, rabbitmq=5672, kafka=9092, node-exporter=9100, k3s-api=6443/6444, etc.
  - Each entry: port, default protocol, service name, category, description
  - `resolve(port) -> ServiceInfo | None` — lookup by port number
- **Reqs**: REQ-SCAN-012

### 3.2 Registry (CRUD)
- [ ] Create `src/core/registry.py` — `PortRegistry` class
  - `add(allocation)` — insert with conflict check
  - `remove(port, protocol)` — delete by port
  - `remove_by_service(service_name)` — delete all for a service
  - `get(port, protocol)` — single lookup
  - `list(filters)` — filtered list with sorting
  - `search(query)` — fuzzy text search across service names, descriptions, paths
  - `export(format)` — JSON/CSV/YAML export
  - `import_file(path)` — import from file
  - `update_status(port, protocol, status)` — update status field
- **Reqs**: REQ-REG-001 through REQ-REG-010

### 3.3 Policy Engine
- [ ] Create `src/core/policy.py` — `PolicyEngine` class
  - `get_range(category)` — return configured range for category
  - `validate_allocation(port, category)` — check port falls within category range
  - `get_blacklisted_ranges()` — return reserved/never-allocate ranges
  - `load_project_overrides(path)` — load `.portman.yaml` overrides
  - `suggest_alternative(port, category)` — find nearest available in same range
- **Reqs**: REQ-POL-001 through REQ-POL-004, REQ-CONF-005

### 3.4 Validator
- [ ] Create `src/core/validator.py` — `PortValidator` class
  - `check_registry_conflict(port, protocol)` — check if port+protocol exists in registry
  - `check_live_port(port, protocol)` — probe if port is currently bound (socket connect)
  - `find_conflicts()` — full scan: registry dupes, registry vs live, cross-project
  - `check_health()` — validate registry against live state (stale + rogue detection)
- **Reqs**: REQ-CONF-001 through REQ-CONF-004, REQ-ALLOC-007, REQ-LIFE-004

### 3.5 Allocator
- [ ] Create `src/core/allocator.py` — `PortAllocator` class
  - `allocate(service, category, port, range, count, force)` — main allocation logic
    - If specific port: validate + allocate
    - If range: find lowest available in range
    - If category: use policy engine to get range, find lowest available
    - If none: find next available across all non-reserved ranges
  - `release(service, port)` — release by service or specific port
  - `reserve(port, service, until)` — create reservation
  - `garbage_collect()` — find stale allocations, return for interactive cleanup
  - Uses registry, validator, and policy engine internally
  - Thread/async safe for concurrent daemon requests
- **Reqs**: REQ-ALLOC-001 through REQ-ALLOC-008, REQ-LIFE-001 through REQ-LIFE-005, REQ-DMN-010

---

## Phase 4: Parsers (Port Scanner)

### 4.1 Parser Interface
- [ ] Create `src/parsers/base.py` — abstract `BaseParser` with `parse(file_path) -> list[DiscoveredPort]`
- [ ] Define `DiscoveredPort` dataclass: port, protocol, service_name, source_file, source_line, category, source_type

### 4.2 Project File Parsers
- [ ] `src/parsers/docker_compose.py` — parse `ports:` mappings (host:container format)
- [ ] `src/parsers/dotenv.py` — parse variables with `PORT` in name
- [ ] `src/parsers/package_json.py` — parse `--port` args in scripts section
- [ ] `src/parsers/python_files.py` — parse uvicorn/gunicorn port args, FastAPI/Flask configs
- [ ] `src/parsers/nginx.py` — parse `listen` directives
- [ ] `src/parsers/procfile.py` — parse port arguments in commands
- [ ] `src/parsers/yaml_generic.py` — parse keys matching `*port*` patterns in YAML/TOML
- **Reqs**: REQ-SCAN-002

### 4.3 System Parsers
- [ ] `src/parsers/systemd_units.py` — parse `ListenStream=`, `ListenDatagram=`, `ExecStart=` port args from `/etc/systemd/system/` and `/usr/lib/systemd/system/`
- [ ] `src/parsers/system_configs.py` — parse well-known config files in `/etc/` (sshd_config, postgresql.conf, redis.conf, nginx default site, apache ports.conf, mysql my.cnf)
- [ ] `src/parsers/docker_inspect.py` — run `docker ps --format json` and `docker inspect` to get published port mappings from running containers
- [ ] `src/parsers/k8s_services.py` — run `kubectl get svc -o json` to get NodePort/LoadBalancer/ClusterIP ports (gracefully skip if kubectl unavailable)
- **Reqs**: REQ-SCAN-009, REQ-SCAN-010

### 4.4 Process Scanner
- [ ] `src/parsers/process_scanner.py` — detect listening ports from running processes using `psutil` (cross-platform alternative to ss/lsof)
- [ ] Enrich with known_ports knowledge base for service name resolution
- **Reqs**: REQ-SCAN-003, REQ-SCAN-012

### 4.5 Scanner Orchestrator
- [ ] Create `src/core/scanner.py` — `PortScanner` class
  - `scan(directories, exclude_patterns, projects_only, system_only)` — recursive scan with all parsers
  - `scan_projects(directories, exclude_patterns)` — project file parsers only
  - `scan_system()` — system parsers only (systemd, docker, k8s, /etc/)
  - `scan_processes()` — live process scan
  - `incremental_scan(directories)` — detect new/changed/removed vs registry, return diff
  - `classify_port(port_number)` — auto-categorize based on well-known ranges + knowledge base
  - Handle permission errors gracefully (skip + warn)
  - Record scan history to database
- **Reqs**: REQ-SCAN-001, REQ-SCAN-004 through REQ-SCAN-012, REQ-CONF-004, REQ-NFR-001, REQ-NFR-006

---

## Phase 5: System Daemon

### 5.1 Daemon Server
- [ ] Create `src/daemon/server.py` — `PortmanDaemon` class
  - Async FastAPI/uvicorn app bound to both Unix socket (`~/.portman/portmand.sock`) and HTTP (`127.0.0.1:9800`)
  - Mirrors `/api/v1/` REST endpoints from the web dashboard
  - Handles concurrent allocation requests with async locking (no duplicate ports)
  - Periodic health check task (configurable interval, default 60s) that probes all registered ports
  - On startup: check if registry empty, run initial full scan if so
  - PID file at `~/.portman/portmand.pid` for status checks
  - Graceful shutdown on SIGTERM/SIGINT
- **Reqs**: REQ-DMN-001 through REQ-DMN-005, REQ-DMN-009, REQ-DMN-010

### 5.2 Daemon Client
- [ ] Create `src/daemon/client.py` — `DaemonClient` class
  - `is_running()` — check if daemon is alive (probe socket)
  - `allocate(service, category, port)` — send allocation request via Unix socket
  - `release(service, port)` — send release request
  - `list(filters)` — query ports
  - `status()` — get daemon uptime, port count, last health check
  - Falls back to direct database access if daemon unavailable
  - Used by CLI commands and Python SDK
- **Reqs**: REQ-DMN-002, REQ-DMN-003, REQ-DMN-004

### 5.3 Daemon Logging
- [ ] Structured log output to `~/.portman/portmand.log`
- [ ] Log rotation: max 10MB, 3 backup files
- [ ] Log events: allocation, release, conflict, health_check, scan, startup, shutdown
- **Reqs**: REQ-DMN-006

### 5.4 systemd Integration
- [ ] Create `src/daemon/systemd.py` — generate and install systemd user service file
  - `install()` — write `~/.config/systemd/user/portmand.service`, run `systemctl --user daemon-reload`
  - `uninstall()` — stop + disable + remove service file
  - `enable()` / `disable()` — auto-start on login
  - Service file: `Type=exec`, `ExecStart=portman daemon start`, restart on failure
- **Reqs**: REQ-DMN-001, REQ-DMN-007, REQ-DMN-008

---

## Phase 6: CLI

### 6.1 CLI App Shell
- [ ] Create `src/cli/app.py` — Typer app with global `--verbose`, `--quiet` callbacks
- [ ] Set up Rich console for formatted output
- [ ] All commands check for daemon and use `DaemonClient` when available
- **Reqs**: REQ-CLI-001, REQ-CLI-003 through REQ-CLI-005, REQ-CLI-007, REQ-NFR-007

### 6.2 Init & Scan Commands
- [ ] `src/cli/commands/init.py` — `portman init [dirs]`: scan projects + system, present summary, confirm, commit to registry. Flags: `--projects-only`, `--system-only`
- [ ] `src/cli/commands/scan.py` — `portman scan [dirs]`: incremental re-scan, show diff, update registry
- **Reqs**: REQ-SCAN-001, REQ-SCAN-006, REQ-SCAN-007, REQ-SCAN-008, REQ-SCAN-011, REQ-CLI-006

### 6.3 Allocation Commands
- [ ] `src/cli/commands/alloc.py` — `portman alloc <service>` with `--port`, `--range`, `--count`, `--type`, `--format`, `--force`, `--manifest`
- [ ] `src/cli/commands/release.py` — `portman release <service|--port N>` with confirmation
- [ ] `src/cli/commands/reserve.py` — `portman reserve <port> --for <service> --until <date>`
- **Reqs**: REQ-ALLOC-001 through REQ-ALLOC-008, REQ-LIFE-001 through REQ-LIFE-003, REQ-INT-004, REQ-CLI-006

### 6.4 Query Commands
- [ ] `src/cli/commands/list_cmd.py` — `portman list` with `--service`, `--range`, `--category`, `--status`, `--sort`, `--source-type`
- [ ] `src/cli/commands/info.py` — `portman info <port>`
- [ ] `src/cli/commands/search.py` — `portman search <query>`
- **Reqs**: REQ-REG-002 through REQ-REG-008

### 6.5 Validation & Maintenance Commands
- [ ] `src/cli/commands/conflicts.py` — `portman conflicts`
- [ ] `src/cli/commands/check.py` — `portman check`
- [ ] `src/cli/commands/gc.py` — `portman gc` (interactive stale cleanup)
- **Reqs**: REQ-CONF-003, REQ-LIFE-004, REQ-LIFE-005, REQ-CLI-006

### 6.6 Daemon Commands
- [ ] `src/cli/commands/daemon.py` — subcommands:
  - `portman daemon start` — launch daemon in foreground
  - `portman daemon stop` — graceful shutdown
  - `portman daemon status` — show running state, uptime, port count
  - `portman daemon install` — install systemd user service
  - `portman daemon uninstall` — remove systemd service
- **Reqs**: REQ-DMN-001, REQ-DMN-007, REQ-DMN-008

### 6.7 Utility Commands
- [ ] `src/cli/commands/export.py` — `portman export --format json|csv|yaml`
- [ ] `src/cli/commands/import_cmd.py` — `portman import <file>`
- [ ] `src/cli/commands/config.py` — `portman config` (view/edit)
- [ ] `src/cli/commands/env.py` — `portman env <service>` (.env generation)
- [ ] `src/cli/commands/serve.py` — `portman serve` (start web dashboard)
- **Reqs**: REQ-REG-009, REQ-REG-010, REQ-INT-003, REQ-WEB-001, REQ-WEB-002

---

## Phase 7: Web Dashboard

### 7.1 REST API
- [ ] Refactor `src/api/routes.py` to expose portman operations at `/api/v1/`:
  - `GET /ports` — list with query filters (including `source_type`)
  - `GET /ports/{port}` — port detail
  - `POST /ports/allocate` — allocate
  - `DELETE /ports/{port}` — release
  - `POST /ports/reserve` — reserve
  - `GET /services` — list services
  - `GET /services/{name}` — service detail
  - `GET /conflicts` — current conflicts
  - `GET /status` — live port status check
  - `POST /scan` — trigger scan
  - `GET /ranges` — configured ranges
  - `GET /stats` — allocation statistics (including breakdown by source_type)
  - `GET /daemon/status` — daemon health
- **Reqs**: REQ-WEB-010, REQ-INT-005

### 7.2 HTML Templates
- [ ] `src/web/templates/base.html` — base layout with nav, CSS
- [ ] `src/web/templates/dashboard.html` — home: stats summary, allocation table (with source type icons), conflict highlights, range utilization bars
- [ ] `src/web/templates/portmap.html` — port map heatmap/grid visualization
- [ ] `src/web/templates/service_detail.html` — service view with all ports, sources, history
- [ ] `src/web/templates/status.html` — live status page with color-coded port health
- [ ] `src/web/templates/allocate.html` — allocation form
- **Reqs**: REQ-WEB-003 through REQ-WEB-009

### 7.3 Static Assets
- [ ] `src/web/static/style.css` — minimal CSS for tables, charts, status colors
- [ ] `src/web/static/dashboard.js` — optional JS for sorting, filtering, live status polling (progressive enhancement)
- **Reqs**: REQ-NFR-009

### 7.4 Dashboard Server Integration
- [ ] Update `main.py` — mount Jinja2 templates, serve static files, add HTML routes
- [ ] Auto-register dashboard port in registry on startup
- [ ] Default port selection logic (highest HTTP + 1 or 9999)
- [ ] Bind to `127.0.0.1` by default, `--host` flag for external
- **Reqs**: REQ-WEB-001, REQ-WEB-002, REQ-WEB-008, REQ-WEB-009, REQ-NFR-010

---

## Phase 8: Service Integration

### 8.1 Python SDK
- [ ] Create `src/sdk.py` — `allocate_port(service, category)`, `release_port(service)`, `get_port(service)`
- [ ] SDK uses `DaemonClient` when daemon running, falls back to direct DB
- **Reqs**: REQ-INT-002

### 8.2 Shell Helper
- [ ] Create `scripts/portman-helper.sh` — shell function wrapping `portman alloc --format plain`
- **Reqs**: REQ-INT-001

### 8.3 Manifest Support
- [ ] `.portman.yaml` manifest parsing and bulk allocation (covered in Phase 6.3)
- [ ] Add `.env` file writing after manifest allocation
- **Reqs**: REQ-INT-003, REQ-INT-004

### 8.4 HTTP Allocation for Non-Python Services
- [ ] Document curl-based allocation via daemon HTTP API
- [ ] Example scripts for bash, Go, Node.js service startup integration
- **Reqs**: REQ-INT-005

---

## Phase 9: Testing

### 9.1 Test Fixtures
- [ ] Create `tests/fixtures/sample_projects/` with mock directories:
  - `backend/` — docker-compose.yml, .env, Python files with uvicorn
  - `frontend/` — package.json with port scripts
  - `infra/` — nginx.conf, Procfile
- [ ] Create `tests/fixtures/sample_system/` with mock system files:
  - `systemd/` — mock .service files with ListenStream directives
  - `etc/` — mock sshd_config, postgresql.conf, redis.conf
  - `docker_output/` — mock `docker ps` and `docker inspect` JSON output
  - `k8s_output/` — mock `kubectl get svc` JSON output
- [ ] Create `tests/conftest.py` — temp-dir SQLite fixture, isolated config, mock registry, temporary daemon socket
- **Reqs**: REQ-TST-PM-006, REQ-TST-PM-007, REQ-TST-051, REQ-TST-052

### 9.2 Unit Tests — Parsers (Project)
- [ ] `tests/unit/test_parsers/test_docker_compose.py`
- [ ] `tests/unit/test_parsers/test_dotenv.py`
- [ ] `tests/unit/test_parsers/test_package_json.py`
- [ ] `tests/unit/test_parsers/test_python_files.py`
- [ ] `tests/unit/test_parsers/test_nginx.py`
- [ ] `tests/unit/test_parsers/test_procfile.py`
- [ ] `tests/unit/test_parsers/test_yaml_generic.py`
- **Reqs**: REQ-TST-PM-001

### 9.3 Unit Tests — Parsers (System)
- [ ] `tests/unit/test_parsers/test_systemd_units.py`
- [ ] `tests/unit/test_parsers/test_system_configs.py`
- [ ] `tests/unit/test_parsers/test_docker_inspect.py`
- [ ] `tests/unit/test_parsers/test_k8s_services.py`
- **Reqs**: REQ-TST-PM-008

### 9.4 Unit Tests — Core
- [ ] `tests/unit/test_allocator.py` — sequential, specific port, range, count, conflict rejection, concurrent safety
- [ ] `tests/unit/test_validator.py` — registry conflicts, live port mock, stale detection
- [ ] `tests/unit/test_policy.py` — range lookup, validation, blacklist, overrides
- [ ] `tests/unit/test_registry.py` — CRUD, search, filtering, export
- [ ] `tests/unit/test_scanner.py` — orchestrator with mock parsers, projects-only, system-only
- [ ] `tests/unit/test_known_ports.py` — port-to-service resolution, unknown ports
- **Reqs**: REQ-TST-PM-002, REQ-TST-PM-003, REQ-TST-PM-010

### 9.5 Integration Tests
- [ ] `tests/integration/test_cli.py` — all CLI commands via `CliRunner` (including daemon subcommands)
- [ ] `tests/integration/test_api.py` — all REST API endpoints via `TestClient`
- [ ] `tests/integration/test_daemon.py` — daemon lifecycle: start, allocate via socket, concurrent allocations, health check, stop
- **Reqs**: REQ-TST-PM-004, REQ-TST-PM-005, REQ-TST-PM-009

---

## Phase 10: Documentation & Polish

### 10.1 README
- [ ] Create `README.md` from template with project-specific content: overview, installation, quick start, CLI reference, daemon setup, architecture diagram
- **Reqs**: REQ-AGT-001, REQ-DOC-002

### 10.2 Operational Docs
- [ ] Update `docs/app_cheatsheet.md` with all portman CLI commands, daemon commands, URLs, config vars
- [ ] Create `docs/runbook/port_conflict.md` — conflict resolution runbook
- [ ] Create `docs/runbook/stale_ports.md` — stale port cleanup runbook
- [ ] Create `docs/runbook/daemon_issues.md` — daemon troubleshooting runbook
- **Reqs**: REQ-RUN-002, REQ-RUN-003, REQ-DOC-003

### 10.3 Final Cleanup
- [ ] Update `pyproject.toml` project name/description to "cluster-port-manager"
- [ ] Update `main.py` FastAPI title/description
- [ ] Ensure `scripts/check_all.sh` passes (lint + format + typecheck + tests)
- [ ] Remove unused template boilerplate (src/data/, src/models/, src/features/, src/pipelines/, src/evaluation/)

---

## Implementation Order & Dependencies

```
Phase 1 (Foundation) ──> Phase 2 (Database) ──> Phase 3 (Core Engine)
                                                       │
                              ┌────────────────────────┼────────────────┐
                              v                        v                v
                     Phase 4 (Parsers)        Phase 5 (Daemon)   Phase 6 (CLI)
                              │                        │                │
                              └────────────┬───────────┘                │
                                           v                            v
                                  Phase 7 (Web Dashboard) ◄────────────┘
                                           v
                                  Phase 8 (Integration)
                                           v
                                  Phase 9 (Testing)
                                           v
                                  Phase 10 (Docs & Polish)
```

- Phases 4 (Parsers) and 5 (Daemon) can be built in parallel since both depend on Phase 3
- Phase 6 (CLI) depends on Phase 5 (Daemon) for the daemon commands and client fallback
- Phase 7 (Web) depends on Phase 5 (Daemon) for daemon status endpoint

---

## Estimated Requirement Coverage

| Source | Total | Covered |
|--------|-------|---------|
| Project reqs (SCAN/ALLOC/LIFE/REG/CONF/POL/CLI/WEB/INT/DMN/NFR/TST-PM) | 99 | 99 |
| Common reqs (applicable subset: AGT, CFG, ERR, LOG, SEC, TST, RUN, DOC) | ~40 | ~40 |
| Documentation reqs (applicable subset) | ~10 | ~10 |

---

## Acceptance Criteria

1. `portman init ~/projects/` scans projects AND system software, populates the registry
2. `portman list --source-type systemd` shows ports discovered from systemd services
3. `portman list --source-type docker` shows ports from running Docker containers
4. `portman alloc my-service --type http` returns a port in 8000-8999
5. `portman daemon start` launches daemon, `portman daemon status` confirms running
6. `curl http://127.0.0.1:9800/api/v1/ports/allocate -d '{"service":"test","category":"http"}'` returns allocated port
7. Two concurrent allocation requests to the daemon never return the same port
8. `portman daemon install` creates a working systemd user service
9. `portman conflicts` detects and reports duplicate port assignments
10. `portman serve` launches a web dashboard showing all allocations grouped by source type
11. All tests pass: `uv run pytest tests/ -x -q`
12. Lint + typecheck clean: `bash scripts/check_all.sh`

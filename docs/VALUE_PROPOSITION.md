# Portman: Why Another Port Manager?

## The Problem

Every developer who runs more than a handful of services locally has hit this:

```
Error: listen EADDRINUSE: address already in use :::8080
```

You stop what you're doing. You run `lsof -i :8080`. You find a zombie process from three hours ago. You kill it. You restart. Ten minutes later it happens on port 3000.

This gets worse with scale. A typical homelab or development cluster runs dozens of services — databases, message brokers, monitoring stacks, API backends, frontend dev servers, Kubernetes services, Docker containers. Each picks its own port. Nobody coordinates. Conflicts are discovered at startup time, and the "fix" is always the same: pick a different number and hope nobody else picked it too.

Existing tools address fragments of this problem. None solve the whole thing.

## What Exists Today

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| **Port Keeper** | Reserve ports, detect conflicts, team sharing | No config scanning. No system awareness. No daemon. You manually register everything. |
| **Port-Kill** | Kill processes hogging ports, restart services | Reactive, not proactive. No registry. Solves the symptom, not the cause. |
| **Portree** | Hash-based port allocation for git worktrees | Narrow scope. One trick for one workflow. |
| **devports** | Automatic port allocation across worktrees | Same — worktree-specific. No system inventory. |
| **Manual spreadsheets / wiki pages** | "Port 8080 is for the auth service" | Stale the moment someone forgets to update it. No enforcement. |

Every one of these tools assumes you already know which ports are in use. None of them go find out for you.

## What Portman Does Differently

Portman is a **port authority** — it doesn't just track ports you tell it about. It discovers every port assignment on your machine, from every source, and becomes the single place services go to get a port.

### 1. Deep Discovery Across Every Source

Portman scans **three layers** that no other tool combines:

**Project configs** — It reads your actual source files:
- `docker-compose.yml` port mappings
- `.env` files with `*PORT*` variables
- `package.json` scripts with `--port` flags
- Python files with uvicorn/gunicorn port arguments
- `nginx.conf` listen directives
- YAML/TOML configs with port keys

**Installed system software** — It reads what's *configured*, not just what's running:
- systemd unit files (`ListenStream=`, `ExecStart=` port args)
- Service configs in `/etc/` (sshd, postgres, redis, nginx, mysql, apache)
- Docker container port mappings (`docker inspect`)
- K3s/Kubernetes service ports (`kubectl get svc`)

**Live processes** — It probes what's actually listening right now, and cross-references against the registry to find rogue ports that nobody registered and stale entries for services that stopped.

The result: after `portman init ~/projects/`, you have a complete inventory of every port on your machine — where it's defined, what service owns it, whether it's currently active, and whether anything conflicts.

### 2. Daemon-Based Runtime Allocation

This is the fundamental shift. Other tools are passive registries. Portman is an **active allocator**.

When the daemon (`portmand`) is running, services request ports at startup instead of hardcoding them:

```bash
# In any service's start script
PORT=$(portman alloc my-service --type http --format plain)
uvicorn main:app --port $PORT
```

```python
# In Python code
from portman import allocate_port
port = allocate_port("my-service", category="http")
```

```bash
# From any language via HTTP
PORT=$(curl -s http://127.0.0.1:9800/api/v1/ports/allocate \
  -d '{"service":"my-go-svc","category":"http"}' | jq -r '.port')
```

The daemon guarantees:
- **No duplicates** — concurrent requests from multiple services starting simultaneously never get the same port
- **Policy enforcement** — HTTP services get ports in 8000-8999, databases in 5400-5499, etc.
- **Live validation** — the port is probed before allocation to ensure nothing rogue is sitting on it
- **Automatic tracking** — every allocation is recorded with who requested it and when

This works as a systemd user service that starts on login, so it's always available. The CLI and SDK fall back to direct database access if the daemon isn't running — no hard dependency.

### 3. A Knowledge Base, Not Just a Database

Portman ships with a built-in knowledge base of well-known service ports. When it discovers port 5432 in use, it doesn't just say "port 5432, TCP, listening." It says "PostgreSQL (database), port 5432, TCP, from systemd:postgresql.service, currently active."

This means the initial scan produces a human-readable inventory, not a wall of numbers. It knows that 6379 is Redis, 7474 is Neo4j HTTP, 9100 is Prometheus Node Exporter, 6444 is K3s API — hundreds of common services mapped out of the box.

### 4. Conflict Detection That Actually Prevents Conflicts

Other tools tell you about conflicts after they happen. Portman prevents them at three levels:

1. **At scan time** — `portman init` highlights every conflict found across your projects and system before anything is committed to the registry
2. **At allocation time** — every `portman alloc` checks both the registry and live system state before returning a port
3. **At runtime** — the daemon's periodic health checks catch new conflicts (rogue processes binding registered ports) and flag them

When a conflict is detected, Portman doesn't just say "conflict." It suggests the nearest available alternative in the same category range.

## Who Is This For?

- **Homelab operators** running 20+ services across Docker, K3s, bare metal — tired of maintaining port spreadsheets
- **Backend developers** working on microservice architectures locally — tired of `EADDRINUSE` every morning
- **DevOps engineers** managing dev/staging clusters — need a source of truth for port assignments
- **Teams** where multiple people develop against the same set of services — need coordination without a wiki page that's always outdated

## How It Compares

| Capability | Port Keeper | Port-Kill | devports | **Portman** |
|-----------|:-----------:|:---------:|:--------:|:-----------:|
| Manual port registration | Yes | - | - | Yes |
| Kill port-hogging processes | - | Yes | - | - |
| Worktree-aware allocation | - | - | Yes | - |
| Project config scanning | - | - | - | **Yes** |
| System software scanning | - | - | - | **Yes** |
| Live process detection | Yes | Yes | - | **Yes** |
| Conflict prevention (not just detection) | - | - | - | **Yes** |
| Runtime daemon for allocation | - | - | - | **Yes** |
| Concurrent-safe allocation | - | - | - | **Yes** |
| Well-known port knowledge base | - | - | - | **Yes** |
| systemd integration | - | - | - | **Yes** |
| Docker/K8s port discovery | - | - | - | **Yes** |
| Web dashboard | - | - | - | **Yes** |
| REST API for any language | - | - | - | **Yes** |
| Category-based range policies | Yes | - | - | **Yes** |

## The Vision

Port management shouldn't be a manual process. Your machine already knows every port assignment — it's scattered across config files, systemd units, Docker metadata, and Kubernetes manifests. Portman collects all of it into one place and then becomes the authority that services consult when they need a port.

The end state: you never hardcode a port number again. You never hit `EADDRINUSE` again. You always know exactly what's running where.

```bash
$ portman list
PORT   PROTO  SERVICE            CATEGORY   STATUS  SOURCE
22     tcp    sshd               system     active  systemd:sshd.service
5432   tcp    postgresql         database   active  systemd:postgresql.service
6333   tcp    qdrant             database   active  docker:qdrant
6444   tcp    k3s-api            system     active  k8s:kubernetes
7474   tcp    neo4j-http         database   active  docker:neo4j
7687   tcp    neo4j-bolt         database   active  docker:neo4j
8000   tcp    my-api             http       active  project:~/projects/backend/.env
8001   tcp    auth-service       http       active  daemon:alloc
8080   tcp    apache             http       active  systemd:apache2.service
9100   tcp    node-exporter      monitoring active  systemd:node-exporter.service
9800   tcp    portman-daemon     system     active  daemon:self
9999   tcp    portman-dashboard  http       active  daemon:self
```

That's the inventory of your entire machine, built automatically, kept current by a daemon, and available to any service that asks.

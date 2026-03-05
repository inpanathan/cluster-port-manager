# Portman and Kubernetes: Where It Fits

## How Enterprises Handle Port Management Today

Inside Kubernetes, port management is largely a solved problem with three layers:

| Layer | How ports work | Who manages it |
|-------|---------------|----------------|
| **ClusterIP** (default) | K8s assigns virtual IPs internally. Pods talk by service name, not port. Ports are namespaced — 10 services can all use port 80 internally. | Kubernetes automatically |
| **NodePort** (30000-32767) | K8s allocates from a reserved range. Since 1.27, it splits into static (30000-30085) and dynamic (30086-32767) bands to [avoid collisions](https://kubernetes.io/blog/2023/05/11/nodeport-dynamic-and-static-allocation/). | Kubernetes automatically |
| **LoadBalancer / Ingress** | External traffic enters on 80/443 and gets routed by hostname/path. Individual service ports are invisible to the outside. | Ingress controller (Traefik, nginx, etc.) |
| **Service Mesh** (Consul, Istio, Linkerd) | Sidecar proxies handle all networking. Services don't even know their own ports — Envoy manages connections, mTLS, routing. | Mesh control plane |

Enterprise tools in this space: [Consul](https://developer.hashicorp.com/consul/docs/use-case/service-mesh) for service mesh and discovery, Istio for mesh networking, cloud-native load balancers (ALB, NLB, GKE L7), and [Kubernetes itself](https://kubernetes.io/docs/concepts/services-networking/).

**The key insight: inside a fully managed K8s cluster, you don't need portman.** Kubernetes is the port authority.

---

## Where the Gap Is

The problem isn't inside Kubernetes. It's **everything around it**.

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR MACHINE                          │
│                                                         │
│  ┌──────────────┐  Port management?  ┌───────────────┐  │
│  │   K3s / K8s  │  ← Solved inside → │  K8s handles  │  │
│  │   cluster    │       here          │  ClusterIP,   │  │
│  │              │                     │  NodePort,    │  │
│  └──────┬───────┘                     │  Ingress      │  │
│         │                             └───────────────┘  │
│         │ NodePorts land on host ports                    │
│         ▼                                                │
│  ┌──────────────────────────────────────────────────┐    │
│  │              HOST PORT SPACE                      │    │
│  │                                                   │    │
│  │  sshd:22  postgres:5432  redis:6379               │    │
│  │  neo4j:7474,7687 (Docker)                         │    │
│  │  qdrant:6333 (Docker)                             │    │
│  │  k3s-api:6444  node-exporter:9100                 │    │
│  │  apache:8081  iperf3:5201                         │    │
│  │  tailscale:41641,50154                            │    │
│  │  your-api:8000  your-frontend:3000                │    │
│  │  k8s NodePorts: 30000-32767                       │    │
│  │                                                   │    │  ← WHO MANAGES
│  │  ??? nobody tracks these as a whole ???           │    │     ALL OF THIS?
│  └──────────────────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ ~/projects/  │  │  Docker      │  │  System      │  │
│  │ backend/     │  │  containers  │  │  services    │  │
│  │ frontend/    │  │  (non-K8s)   │  │  (systemd)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The **host port space** is a free-for-all. A typical homelab/dev machine has ports claimed by:

- **K3s internals** (6444, 10248-10256)
- **Docker-published containers** outside K8s (Neo4j, Qdrant)
- **Bare-metal system services** (sshd, postgres, apache, CUPS)
- **Tailscale networking** (41641, 50154)
- **Development servers** from your project directories
- **Kubernetes NodePorts** (30000-32767 range)

Nobody coordinates these. An enterprise K8s cluster doesn't know that your Docker Compose Neo4j is on 7474, or that your dev API is hardcoded to 8000 in `.env`, or that apache already has 8081.

---

## Where Portman Fits

Portman doesn't compete with Kubernetes. It fills the layer **below** it:

| Scope | Enterprise solution | Portman |
|-------|-------------------|---------|
| Inter-service routing inside K8s | Service mesh (Consul/Istio) | Not in scope |
| Pod-to-pod networking | K8s CNI (Flannel/Calico) | Not in scope |
| External traffic routing | Ingress controller + LB | Not in scope |
| **Host-level port inventory** | Nothing. Spreadsheets. Tribal knowledge. | **This is portman.** |
| **Dev environment port coordination** | Nothing. `EADDRINUSE`. | **This is portman.** |
| **Cross-tool visibility** (K8s + Docker + systemd + projects) | Nothing unified exists. | **This is portman.** |

---

## Concrete Scenarios Portman Solves That K8s Doesn't

### 1. "I want to run a new Docker container on port 8080"

Is anything already there? K8s doesn't know about your bare-metal services. Portman does — it scanned systemd units, Docker containers, and project configs. It can tell you port 8080 is already used by your dev server, and suggest 8081 instead.

### 2. "K3s NodePort landed on 30080 but my monitoring stack needs that"

K8s allocated from its range, unaware that you have a convention for that port. Portman's blacklist/reservation system can reserve specific NodePort ranges or individual ports, and its conflict detection catches the overlap.

### 3. "New developer joins the team — what's running where?"

`portman list` gives a full inventory across K8s services, Docker containers, systemd services, and project configs in one table. No wiki to maintain, no tribal knowledge required.

```
$ portman list
PORT   PROTO  SERVICE            CATEGORY   STATUS  SOURCE
22     tcp    sshd               system     active  systemd:sshd.service
5432   tcp    postgresql         database   active  systemd:postgresql.service
6333   tcp    qdrant             database   active  docker:qdrant
6444   tcp    k3s-api            system     active  k8s:kubernetes
7474   tcp    neo4j-http         database   active  docker:neo4j
7687   tcp    neo4j-bolt         database   active  docker:neo4j
8000   tcp    my-api             http       active  project:~/projects/backend/.env
8080   tcp    apache             http       active  systemd:apache2.service
9100   tcp    node-exporter      monitoring active  systemd:node-exporter.service
9800   tcp    portman-daemon     system     active  daemon:self
```

### 4. "My dev API conflicts with the staging proxy that's also on this box"

Different tools, different configs, same port. Portman's cross-source scanning catches this before you hit the error. It scans your project's `.env` file, the nginx config in `/etc/`, and the Docker container ports — all in one pass — and flags the conflict immediately.

### 5. "I'm adding a new microservice to my homelab — what port should it use?"

```bash
$ portman alloc my-new-svc --type http
Allocated port 8013 (tcp/http) for my-new-svc
```

It gives you the next available port that doesn't conflict with anything on the machine — not just what K8s knows about, but everything.

### 6. "Which ports are actually in use vs just configured?"

```bash
$ portman check
STALE (allocated but not listening):
  8005  tcp  old-service    http    project:~/projects/old/.env    Last seen: 3 days ago

ROGUE (listening but not registered):
  4567  tcp  unknown        custom  process:ruby (pid 28341)
```

Portman cross-references the registry against live system state. K8s can tell you about its own pods, but not about the Ruby process someone forgot about.

---

## Kubernetes Integration: What Portman Reads, Not Manages

Portman treats Kubernetes as a **data source**, not a system it controls:

| What portman does | What portman does NOT do |
|-------------------|--------------------------|
| `kubectl get svc -o json` to read NodePort/LoadBalancer ports | Create or modify K8s Services |
| Add K8s service ports to the unified registry with `source_type: k8s` | Deploy pods or manage workloads |
| Flag conflicts between K8s ports and other host services | Act as an ingress controller |
| Show K8s ports alongside Docker/systemd/project ports in one view | Replace kube-proxy or service mesh |

This is read-only integration. Portman enriches its inventory with K8s data but never writes back to the cluster.

---

## The Enterprise Stack vs The Homelab Stack

### Enterprise (managed cloud K8s)

```
Internet → Cloud LB → Ingress Controller → Service Mesh → Pods
                                                            ↑
                                              K8s manages all ports
                                              No host port conflicts
                                              (pods are on overlay network)
```

In a fully managed cloud cluster (EKS, GKE, AKS), pods run on an overlay network. They never bind host ports. Service discovery is handled by DNS. Traffic routing is handled by the mesh. **There is no host port problem to solve.**

### Homelab / Dev Machine (bare metal K3s + mixed workloads)

```
┌─ Host ──────────────────────────────────────────────┐
│                                                      │
│  K3s cluster (NodePorts on host: 30000-32767)        │
│  Docker containers (published ports: 5432, 6333...) │
│  systemd services (sshd:22, apache:8081...)          │
│  Dev servers (backend:8000, frontend:3000...)         │
│  Tailscale, monitoring, ad-hoc tools                 │
│                                                      │
│  ALL sharing the same host port space                │
│  NO unified management                               │
│                                                      │
│  ← THIS is where portman lives                       │
└──────────────────────────────────────────────────────┘
```

On a homelab node or dev machine, services from five different orchestration systems all compete for the same 65535 ports. K8s manages its own slice. Docker manages its own slice. systemd manages its own slice. Your project `.env` files manage their own slice. Nobody manages the whole picture.

---

## Honest Positioning Summary

| If you have... | You need... | Portman's role |
|----------------|-------------|---------------|
| A fully managed cloud K8s cluster (EKS/GKE/AKS) | Ingress + service mesh | **Portman adds no value here** |
| A single-node homelab with K3s + Docker + bare metal | Something to track it all | **Primary use case** |
| A multi-service dev environment on your laptop | Port coordination | **Primary use case** |
| A bare-metal cluster with K3s + non-K8s services | Unified port visibility | **Strong use case** |
| An on-prem staging cluster with mixed workloads | Host-level port governance | **Strong use case** |

Portman is not a service mesh, not an ingress controller, not a replacement for K8s networking. It's the **host-level port authority** that sits underneath all of those tools and gives you a single source of truth for "what's using which port on this machine, and how do I avoid conflicts."

---

## References

- [Kubernetes Services, Load Balancing, and Networking](https://kubernetes.io/docs/concepts/services-networking/)
- [Kubernetes 1.27: Avoid Collisions Assigning Ports to NodePort Services](https://kubernetes.io/blog/2023/05/11/nodeport-dynamic-and-static-allocation/)
- [Kubernetes NodePorts - Static and Dynamic Assignments](https://layer5.io/blog/kubernetes/kubernetes-nodeports-static-and-dynamic-assignments/)
- [HashiCorp Consul Service Mesh](https://developer.hashicorp.com/consul/docs/use-case/service-mesh)
- [ClusterIP vs NodePort vs LoadBalancer vs Ingress (2026)](https://acecloud.ai/blog/clusterip-nodeport-loadbalancer-ingress/)
- [Why Kubernetes NodePort Stops at 32767](https://polyedre.github.io/posts/why-2767-nodeports/)

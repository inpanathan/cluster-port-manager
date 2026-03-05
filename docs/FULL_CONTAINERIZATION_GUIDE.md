# What It Takes to Fully Containerize On-Prem

A practical guide for eliminating host port conflicts by moving everything into Kubernetes with overlay networking. This is the "fix the architecture" path — the alternative to needing a port manager.

---

## The Goal

```
BEFORE (port conflict hell):                AFTER (zero conflicts):

  Host port space:                            Host port space:
  sshd:22                                     sshd:22 (only thing left)
  postgres:5432                               K3s internals (6443, 10250)
  redis:6379                                  MetalLB: 192.168.1.200
  neo4j:7474, 7687                              → Traefik: 80, 443
  qdrant:6333                                     → routes everything by hostname
  apache:8081
  node-exporter:9100                          Everything else: overlay network
  my-api:8000                                 No host port bindings
  frontend:3000                               No conflicts possible
  k3s NodePorts: 30XXX
  CONFLICTS EVERYWHERE
```

---

## The Stack You Need

| Layer | Component | Purpose | Replaces |
|-------|-----------|---------|----------|
| **OS** | Ubuntu/Debian or Talos Linux | Host OS | Same |
| **K8s Distribution** | K3s | Lightweight Kubernetes | Docker Compose, systemd services |
| **CNI (Networking)** | Flannel (bundled with K3s) or Calico | Overlay network for pods | Host port bindings |
| **Load Balancer** | MetalLB | Gives K8s services real LAN IPs | NodePort, host ports |
| **Ingress** | Traefik (bundled with K3s) or nginx-ingress | Routes HTTP by hostname/path | Per-service port exposure |
| **TLS** | cert-manager + Let's Encrypt | Automatic HTTPS | Manual certs |
| **Storage** | Longhorn (easy) or OpenEBS Mayastor (fast) or Rook-Ceph (enterprise) | Persistent volumes for databases | Local disk mounts |
| **DNS** | CoreDNS (bundled) + external (Pi-hole/AdGuard) | Service discovery + LAN DNS | /etc/hosts, manual DNS |
| **GitOps** | Flux or ArgoCD | Declarative deployments from git | Manual kubectl apply |
| **Secrets** | Sealed Secrets or External Secrets | Secret management | .env files |

---

## Migration: Service by Service

### Layer 1: Networking Foundation (Do This First)

#### 1a. Install MetalLB

MetalLB gives your bare-metal K3s cluster the ability to assign real LAN IP addresses to LoadBalancer services — the same thing cloud providers do automatically.

```yaml
# metallb-pool.yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
    - 192.168.1.200-192.168.1.250   # Reserve a range on your LAN
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
```

**What this gives you**: K8s services of type `LoadBalancer` get a real IP on your network. No more NodePorts.

#### 1b. Configure Traefik Ingress

K3s bundles Traefik. Configure it to use MetalLB:

```yaml
# traefik-config.yaml (HelmChartConfig)
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    service:
      spec:
        loadBalancerIP: 192.168.1.200
    ports:
      web:
        port: 80
      websecure:
        port: 443
```

**What this gives you**: One IP (192.168.1.200) handles ALL HTTP traffic. Services are routed by hostname. No per-service port exposure.

#### 1c. LAN DNS

Point `*.dev.local` (or your domain) to the MetalLB IP:

```
# Pi-hole / AdGuard / /etc/dnsmasq.conf
address=/dev.local/192.168.1.200
```

Now `grafana.dev.local`, `api.dev.local`, `neo4j.dev.local` all resolve to Traefik, which routes by hostname.

---

### Layer 2: Stateless Services (Easy Wins)

These are the simplest to containerize — no persistent data, no special requirements.

| Service | Before | After |
|---------|--------|-------|
| Your API backend | `uvicorn main:app --port 8000` | K8s Deployment + Service + IngressRoute |
| Frontend dev server | `npm run dev -- --port 3000` | K8s Deployment + IngressRoute |
| Apache/nginx static sites | `systemd: apache2.service` on port 8081 | K8s Deployment + IngressRoute |
| Node exporter | `systemd: node-exporter.service` on port 9100 | K8s DaemonSet (hostNetwork only for this) |

Example — migrating your API backend:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-api
  template:
    metadata:
      labels:
        app: my-api
    spec:
      containers:
        - name: my-api
          image: my-api:latest
          ports:
            - containerPort: 8000    # Internal only. No host port.
---
apiVersion: v1
kind: Service
metadata:
  name: my-api
spec:
  selector:
    app: my-api
  ports:
    - port: 80              # Other services call my-api:80
      targetPort: 8000       # Routes to container's 8000
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-api
spec:
  entryPoints: [websecure]
  routes:
    - match: Host(`api.dev.local`)
      kind: Rule
      services:
        - name: my-api
          port: 80
```

**Port 8000 never touches the host.** It's internal to the pod. External access is through `https://api.dev.local` on Traefik's port 443.

---

### Layer 3: Databases (The Hard Part)

This is where most people get stuck. Databases need:
- **Persistent storage** that survives pod restarts
- **Predictable performance** (disk I/O matters)
- **Backup/restore** capability
- **Sometimes host networking** for wire-protocol performance

#### Storage: Pick One

| Solution | Best for | Complexity | Performance |
|----------|----------|------------|-------------|
| **Longhorn** | Homelabs, small clusters | Low — install via Helm, web UI | Good — replicated block storage |
| **OpenEBS Mayastor** | Performance-critical workloads | Medium — needs NVMe, hugepages | [Excellent](https://cwiggs.com/posts/2024-12-26-openebs-vs-longhorn/) — NVMe-over-TCP |
| **Rook-Ceph** | Multi-node production | High — CRUSH maps, OSD lifecycle | Excellent — battle-tested |
| **Local Path** (K3s default) | Single-node, dev/test only | None — built into K3s | Native disk speed, no replication |

For a single-node homelab: **Longhorn** or **Local Path Provisioner** (already in K3s).
For multi-node: **Longhorn** (easy) or **Rook-Ceph** (robust).

#### PostgreSQL on K8s

Use a Kubernetes operator instead of managing it yourself:

| Operator | Maturity | Features |
|----------|----------|----------|
| [CloudNativePG](https://cloudnative-pg.io/) | Production-grade, CNCF | Automated failover, backups to S3, declarative config |
| [Crunchy PGO](https://www.crunchydata.com/products/crunchy-postgresql-for-kubernetes/bare-metal) | Enterprise, bare-metal optimized | HA, monitoring, backup/restore |
| [Zalando Postgres Operator](https://github.com/zalando/postgres-operator) | Production-grade | Patroni-based HA, connection pooling |

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres
spec:
  instances: 1                    # 3 for HA
  storage:
    size: 10Gi
    storageClass: longhorn
  postgresql:
    parameters:
      shared_buffers: "256MB"
      max_connections: "100"
```

**Port 5432 is internal to the cluster.** Your API connects via `postgres.default.svc.cluster.local:5432`. No host port.

#### Redis on K8s

```yaml
# Simple single-node Redis (no operator needed)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: redis-data
```

For production Redis: use the [Redis Operator](https://github.com/OT-CONTAINER-KIT/redis-operator) for sentinel/cluster mode.

#### Neo4j, Qdrant, and Other Databases

Most databases now ship official Helm charts:

```bash
# Neo4j
helm install neo4j neo4j/neo4j --set volumes.data.mode=defaultStorageClass

# Qdrant
helm install qdrant qdrant/qdrant --set persistence.size=10Gi
```

All internal to the cluster. Expose via IngressRoute if you need browser access (Neo4j Browser, Qdrant dashboard).

---

### Layer 4: Monitoring Stack

| Service | Before | After |
|---------|--------|-------|
| Prometheus | Manual install, port 9090 | kube-prometheus-stack Helm chart |
| Grafana | Docker container, port 3000 | Part of kube-prometheus-stack |
| Node exporter | systemd service, port 9100 | DaemonSet (part of kube-prometheus-stack) |
| Alertmanager | Manual, port 9093 | Part of kube-prometheus-stack |

```bash
helm install monitoring prometheus-community/kube-prometheus-stack \
  --set grafana.ingress.enabled=true \
  --set grafana.ingress.hosts[0]=grafana.dev.local
```

One command. All ports internal. Grafana accessible at `https://grafana.dev.local`.

**Note**: Node exporter is the one exception that legitimately needs `hostNetwork: true` because it needs to read host-level metrics. This is fine — it's a read-only monitoring agent.

---

### Layer 5: Docker Compose Migrations

If you have Docker Compose stacks, convert them to K8s manifests:

| Tool | What it does |
|------|-------------|
| [Kompose](https://kompose.io/) | Converts docker-compose.yml to K8s manifests automatically |
| Manual rewrite | More control, better results |

```bash
# Automatic conversion (good starting point)
kompose convert -f docker-compose.yml

# Then edit the output to:
# - Remove hostPort mappings
# - Add IngressRoute for HTTP services
# - Add PVC for persistent data
# - Use K8s service DNS instead of Docker network names
```

---

## The Exceptions: What Still Needs Host Ports

Even in a fully containerized setup, a few things legitimately bind host ports:

| Service | Why it needs host access | Port |
|---------|--------------------------|------|
| **sshd** | You need to get into the machine | 22 |
| **K3s API server** | Cluster management | 6443 |
| **kubelet** | K8s node agent | 10250 |
| **MetalLB** | L2 ARP for LAN IP assignment | (no port, ARP protocol) |
| **Tailscale/WireGuard** | VPN overlay | 41641 (UDP) |
| **Node exporter** | Reads host metrics | 9100 (hostNetwork) |

That's 4-5 host ports total, all well-known, all non-conflicting. Everything else is on the overlay network.

---

## The Full Cost: What You're Taking On

Fully containerizing isn't free. Here's what it costs:

### Complexity You're Adding

| Area | What you need to learn/manage |
|------|-------------------------------|
| **Kubernetes itself** | Deployments, Services, Ingress, ConfigMaps, Secrets, RBAC |
| **Storage** | PV/PVC, StorageClass, Longhorn/Ceph operations |
| **Networking** | CNI, MetalLB, Traefik IngressRoutes, DNS |
| **Database operators** | CloudNativePG, Redis Operator lifecycle |
| **GitOps** | Flux/ArgoCD for declarative config |
| **Debugging** | `kubectl logs`, `kubectl exec`, `kubectl describe` instead of `journalctl` and `systemctl` |
| **Upgrades** | K3s upgrades, operator upgrades, Helm chart version management |

### Resource Overhead

| Component | RAM overhead | CPU overhead |
|-----------|-------------|-------------|
| K3s server | ~512MB | Minimal |
| K3s agent | ~256MB | Minimal |
| Flannel CNI | ~50MB per node | Minimal |
| MetalLB | ~50MB | Minimal |
| Traefik | ~100MB | Minimal |
| Longhorn | ~500MB-1GB | Moderate (replication I/O) |
| Per-pod overhead | ~5-10MB (pause container + cgroups) | <1% |
| **Total platform tax** | **~1.5-2.5GB** | **Moderate** |

On a 32GB machine: negligible. On a Raspberry Pi 4 with 4GB: significant.

### Performance Impact

| Workload | Overhead vs bare metal |
|----------|----------------------|
| Stateless HTTP services | [<1% — negligible](https://thenewstack.io/bare-metal-kubernetes-the-performance-advantage-is-almost-gone/) |
| CPU-bound computation | <1% (cgroups overhead) |
| Network-heavy (overlay vs host) | 2-5% (VXLAN encapsulation) |
| Disk I/O (Longhorn replicated) | 10-30% (replication + network) |
| Disk I/O (Local Path, no replication) | <1% |
| GPU workloads | 0% (device passthrough) |

**Bottom line**: Stateless is free. Storage-heavy workloads (databases) pay the biggest tax, especially with replicated storage. Use Local Path Provisioner for single-node setups to avoid this.

---

## Migration Order (Recommended)

```
Phase 1: Networking foundation          (1-2 hours)
├── Install MetalLB
├── Configure Traefik
└── Set up LAN DNS

Phase 2: Stateless services             (1 hour per service)
├── API backends
├── Frontend dev servers
└── Static sites

Phase 3: Monitoring                     (1 hour)
└── kube-prometheus-stack (Prometheus + Grafana + exporters)

Phase 4: Databases                      (2-4 hours per database)
├── Choose storage solution (Longhorn recommended to start)
├── PostgreSQL via CloudNativePG operator
├── Redis (simple Deployment or operator)
└── Other DBs (Neo4j, Qdrant via Helm charts)

Phase 5: Docker Compose migrations      (1-2 hours per stack)
├── Convert with Kompose
├── Remove host port bindings
└── Add IngressRoutes

Phase 6: Decommission bare-metal services  (cleanup)
├── Stop and disable systemd services replaced by K8s
├── Remove Docker Compose stacks replaced by K8s
└── Verify everything works through Ingress
```

**Total for a typical homelab (10-15 services)**: 2-4 weekends of focused work.

---

## Decision Framework

| Question | If yes... | If no... |
|----------|-----------|----------|
| Do you have <8GB RAM on the machine? | K8s overhead may be too much. Stay with Docker Compose + portman. | K8s overhead is fine. |
| Are you comfortable with K8s concepts? | Go ahead and migrate. | Budget learning time (1-2 weeks to be productive). |
| Do you need replicated storage (multi-node)? | Use Longhorn or Rook-Ceph. | Use Local Path Provisioner (zero overhead). |
| Are you running GPU workloads? | Use K8s with NVIDIA device plugin. Works great. | N/A. |
| Do you need services accessible from LAN without VPN? | MetalLB + Traefik is essential. | K3s ServiceLB may be enough. |
| Are you mid-migration and can't containerize everything now? | **Use portman** for the transition period. | Full containerization eliminates the need. |

---

## Summary

| Aspect | Cost |
|--------|------|
| **Learning curve** | Moderate — K8s, storage, networking, operators |
| **Time investment** | 2-4 weekends for a typical homelab |
| **RAM overhead** | ~1.5-2.5GB for the platform |
| **Performance cost** | <1% for stateless, 10-30% for replicated storage |
| **Operational complexity** | Higher than Docker Compose, but GitOps makes it manageable |
| **Reward** | Zero port conflicts, service discovery by name, rolling updates, self-healing, declarative config |

Full containerization is the architecturally correct solution. It eliminates port conflicts permanently. But it's not free — it's a meaningful infrastructure investment. Portman exists for the environments where that investment hasn't been made yet, or where mixed workloads make full containerization impractical.

---

## References

- [MetalLB — bare metal load-balancer for Kubernetes](https://metallb.universe.tf/)
- [Kubernetes Ingress on Bare Metal: MetalLB, Traefik, and Cloudflare](https://www.thedougie.com/2025/06/05/kubernetes-ingress-metallb-traefik-cloudflare/)
- [How to Use MetalLB with Traefik Ingress](https://oneuptime.com/blog/post/2026-01-07-metallb-traefik-ingress/view)
- [Longhorn vs OpenEBS vs Rook-Ceph on K3s in 2025](https://onidel.com/blog/longhorn-vs-openebs-rook-ceph-2025)
- [Bare-Metal Kubernetes: The Performance Advantage Is Almost Gone](https://thenewstack.io/bare-metal-kubernetes-the-performance-advantage-is-almost-gone/)
- [Crunchy PostgreSQL for Kubernetes on Bare Metal](https://www.crunchydata.com/products/crunchy-postgresql-for-kubernetes/bare-metal)
- [Redis Operator for Kubernetes](https://github.com/OT-CONTAINER-KIT/redis-operator)
- [Enterprise Infrastructure in 2025: Moving Beyond VMware to Kubernetes](https://www.vcluster.com/blog/what-does-your-infrastructure-look-like-in-2025-and-beyond)
- [Replacing ServiceLB by MetalLB in K3s](https://blog.kevingomez.fr/2025/08/21/replacing-servicelb-by-metallb-in-k3s/)
- [Bare-metal considerations — ingress-nginx](https://kubernetes.github.io/ingress-nginx/deploy/baremetal/)

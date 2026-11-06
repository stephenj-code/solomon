# project-solomon

Self-hosted 3-node Kubernetes cluster on NVIDIA Jetson hardware. Runs FastAPI microservices,
LangGraph agents, and UI applications with a full GitOps workflow and local AI inference.

Managed by **Solomon** — a Claude Code skill that knows the cluster, builds services
consistently, and handles day-to-day operations.

> **Implementation detail** — for per-namespace object inventory, ingress patterns, auth flows,
> and cross-namespace flows see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Node topology

| Node             | Role                | RAM   | IP            |
|------------------|---------------------|-------|---------------|
| agx-orin-prod-1  | control-plane + GPU | 61 GB | 192.168.1.49  |
| orin-nano-prod-1 | worker              | 7 GB  | 192.168.1.175 |
| orin-nano-dev-1  | worker              | 7 GB  | 192.168.1.139 |

All nodes: NVIDIA Jetson ARM64. LLM inference and ARC runners pin to agx-orin-prod-1
(61 GB RAM, 1 TB SSD, GPU).

---

## Tech stack

### Foundation

| Component | Purpose |
|-----------|---------|
| Cilium | CNI — eBPF NetworkPolicy, Istio-compatible (`kubeProxyReplacement=false`) |
| NVIDIA device plugin | GPU RuntimeClass `nvidia` for Jetson nodes |
| local-path provisioner | Dynamic PVCs on 1 TB SSD (agx-orin-prod-1) |
| cert-manager | Wildcard TLS — `*.project-solomon.ai` via Let's Encrypt DNS-01/Cloudflare |
| Sealed Secrets | Git-safe secrets — SealedSecret CRDs, encrypted with cluster public key |

### Networking

| Component | Purpose |
|-----------|---------|
| Istio ambient mode | Service mesh — ztunnel DaemonSet, no sidecars, transparent mTLS |
| Istio IngressGateway | Cluster ingress — hostPort :443 (LAN) + ClusterIP :80 (Cloudflare tunnel) |
| Kubernetes Gateway API | `HTTPRoute` + `Gateway` — no Istio VirtualService |
| Cloudflare Tunnel | External HTTPS → IngressGateway |
| dnsmasq | Split DNS on agx-orin-prod-1 — `*.project-solomon.ai` → 192.168.1.49 for LAN clients |

### Auth

| Component | Purpose |
|-----------|---------|
| Keycloak | Identity provider — SSO for all services |
| oauth2-proxy | Browser OIDC flow for UI apps — per-app instances provisioned automatically |
| Istio JWT RequestAuthentication | Validates Keycloak JWTs at the IngressGateway, cluster-wide |
| Istio AuthorizationPolicy | Deny-by-default on `ai`, `auth`, `mcp-servers`; SPIFFE-based allow rules |

### Data

| Component | Purpose |
|-----------|---------|
| CloudNativePG | Postgres operator — shared cluster, one `Database` CRD per service |
| MinIO | Object storage on 1 TB SSD — Velero backup target |
| Velero | Scheduled cluster backups → MinIO |

### AI

Local inference — NVIDIA Jetson AGX Orin. Only [Jetson AI Lab](https://www.jetson-ai-lab.com/models/) official containers.

| Component | Engine | Model | Notes |
|-----------|--------|-------|-------|
| llama-server | llama.cpp | Muse Glimmer 30B | GGUF, 131K ctx, vision, ~25 tok/s |
| vllm | vLLM | Nemotron3 Nano 30B-A3B | MoE, ~3B active params, fast tier |

Both models stay hot simultaneously (~25 GB of 61 GB unified memory). Models pull from
HuggingFace on first start (HuggingFace token stored as SealedSecret in `ai` namespace).

External providers (via LiteLLM, pay-as-you-go):

| Provider | Models |
|----------|--------|
| Together AI | GLM-5.2, GLM-5.3, Kimi K3 |
| Anthropic | Claude Sonnet (`external` alias) |

**LiteLLM proxy** — single AI gateway for all agents. Per-service virtual keys, model aliases,
usage logging, automatic fallback routing.

| Alias | Model | Use for |
|-------|-------|---------|
| `smart` | Muse Glimmer 30B (local) | Reasoning, planning, vision, long context |
| `fast` | Nemotron3 Nano (local) | High-frequency, routing, classification |
| `glm` | GLM-5.2 (Together AI) | GLM-family tasks |
| `kimi` | Kimi K3 (Together AI) | Kimi-specific workflows |
| `external` | Claude Sonnet (Anthropic) | Quality ceiling, complex reasoning |

### Observability

| Component | Purpose |
|-----------|---------|
| Prometheus + Alertmanager | Metrics and alerting (kube-prometheus-stack) |
| Grafana | Dashboards — Prometheus + Loki + Jaeger |
| Loki + Promtail | Log aggregation — 30d retention |
| Kiali | Istio mesh topology |
| Jaeger | Distributed tracing |

### Security

| Component | Purpose |
|-----------|---------|
| Trivy Operator | Continuous pod scanning → `VulnerabilityReport` CRDs → Prometheus metrics |
| Trivy CLI (CI) | Image scan on build — fails on CRITICAL CVEs |
| Bandit + Semgrep | Python SAST on every push |
| Cilium NetworkPolicy | L4 kernel enforcement — API server access, cross-namespace, internet egress |
| Pod Security Standards | `restricted` on `auth`, `baseline` everywhere else |

### CI/CD

| Component | Purpose |
|-----------|---------|
| GitHub Actions (ARC) | Self-hosted ARM64 ephemeral runners on agx-orin-prod-1 |
| GHCR | Container registry — image tagged by git SHA (immutable) + `latest` |
| Docker layer cache | 100 GB PVC — cold build 4–6 min → warm 15–30 s |
| ArgoCD | GitOps — watches `k8s/` in each app repo, syncs SHA tag to cluster |

---

## How the layers fit together

Every pod that runs in this cluster passes through four distinct layers. Each has one job and hands off to the next.

```
You write YAML → ArgoCD applies it → kube-apiserver stores it in etcd
                                              │
                              kube-scheduler picks a node
                                              │
                              kubelet on that node receives the order
                                    │                │
                               containerd          Cilium (CNI)
                           runs the container    wires the network
                                    │                │
                              Linux kernel ←─────────┘
                          namespaces + cgroups + eBPF
```

### What each component is responsible for

**Kubernetes** — the orchestrator. Decides *what* runs *where* and keeps it that way. Its world is Pods, Services, Deployments, Namespaces. It knows nothing about mTLS, JWT auth, or HTTP routing — those are added by Istio on top.

**containerd** — the executor. Receives an order from kubelet and actually starts the container. Pulls the image, then calls the Linux kernel: `clone()` to create isolated namespaces (each container gets its own network, process tree, filesystem view), and writes to `/sys/fs/cgroup` to enforce CPU/RAM limits. For GPU pods, the NVIDIA runtime maps the GPU in first.

**Cilium** — the network layer. Called by kubelet (via the CNI interface) every time a pod starts. Creates a virtual ethernet pair for the pod, assigns it an IP, then loads eBPF programs into the Linux kernel that enforce NetworkPolicy — allowing or dropping packets before they ever reach the pod. When a NetworkPolicy YAML changes, Cilium updates the kernel programs live.

**eBPF** — a Linux kernel feature that lets you run custom code *inside* the kernel at specific hooks (packet arrival, syscall, connection open) without modifying the kernel itself. Cilium uses it to intercept every packet at the lowest possible level — faster and more precise than iptables.

**Istio (ambient mode)** — a service mesh that runs invisibly alongside pods. Kubernetes sees it as just another DaemonSet (`ztunnel`). It transparently encrypts all pod-to-pod traffic (mTLS) and enforces JWT auth at the gateway. Kubernetes does not know it exists.

**Linux kernel** — does the actual work for all of the above: creates namespace isolation, enforces cgroup resource limits, and runs eBPF programs for packet filtering.

### Pod startup in one flow

```
1. YAML committed → ArgoCD applies → stored in etcd
2. kube-scheduler assigns pod to a node
3. kubelet sees the assignment, calls containerd
4. containerd pulls image, calls kernel:
     clone() → isolated namespaces
     cgroup  → CPU/RAM limits enforced
5. kubelet calls Cilium (CNI):
     Cilium creates veth pair, assigns IP
     bpf() syscall → eBPF program loaded into kernel
     NetworkPolicy now enforced at kernel level
6. Pod is live. Istio ztunnel transparently encrypts its traffic.
```

### Observability — three different views of traffic

| Tool | Level | Answers |
|------|-------|---------|
| Hubble | L3/L4 raw packets (eBPF) | Did NetworkPolicy block that? What IPs are connecting? |
| Kiali | L7 HTTP via Istio mesh | Are my services healthy? What's the error rate? |
| Jaeger | L7 distributed traces | Why was this request slow? What path did it take? |

---

## App templates

Every app starts from one of four templates, each built around the same five concepts:

| Concept | What it is | `api` | `agent` | `react` | `rust` | `job`/`cronjob` |
|---------|-----------|-------|---------|---------|--------|-----------------|
| **Structure** | How the app is wired | `routes.py` | `graph.py` | `routes.tsx` | `router.rs` | `app/job.py` |
| **Logic** | What happens per request/node/step | `handlers.py` | `nodes.py` | `pages/` | `handlers.rs` | `app/steps.py` |
| **Data** | Shapes flowing through | `models.py` | `state.py` | `types.ts` | `models.rs` | `app/models.py` |
| **Capabilities** | External calls and tools | `services.py` | `tools.py` | `api.ts` | `services.rs` | `app/services.py` |
| **Config** | Settings and instructions | `config.py` | `prompts.py` | `config.ts` | `config.rs` | `app/config.py` |

Understanding these five concepts means understanding every app type in the cluster.
Each template's `CLAUDE.md` explains the add-new-X workflow for that language.

### Build pipeline by template

| Template | SAST | Test |
|----------|------|------|
| `api` | Bandit + Semgrep (python) | — |
| `agent` | Bandit + Semgrep (python) | — |
| `react` | Semgrep (javascript) | TypeScript errors caught by `npm run build` in Dockerfile |
| `rust` | cargo clippy | cargo test |

All four: Docker build → Trivy image scan (fail on CRITICAL) → push to GHCR → patch `k8s/deployment.yaml` SHA.

### Create a new app

```bash
scripts/new-app.sh <name> [agent|api|react|rust] [namespace]

# Examples
scripts/new-app.sh frigate-agent            # LangGraph agent (default)
scripts/new-app.sh results-api api          # FastAPI service
scripts/new-app.sh geometry-ui react        # Vite + React UI
scripts/new-app.sh compute-core rust        # Axum Rust service
```

Creates a private GitHub repo under `stephenj-code/<name>`, copies the template, substitutes
placeholders, pushes to main. `provision.yaml` runs automatically and bootstraps:
Cloudflare CNAME, Keycloak client (SealedSecret), LiteLLM virtual key (SealedSecret),
ArgoCD Application in platform repo.
Optional: CloudNativePG database (`needs.database: true`), oauth2-proxy + Keycloak browser
client (`needs.ui: true`).

---

## Solomon

Solomon is Claude Code configured as a cluster manager via `CLAUDE.md` and `.claude/commands/solomon.md`.

No runtime services — invoked directly in a Claude Code session on agx-orin-prod-1 or over SSH.
MCP tools (kubernetes, prometheus, filesystem) bridge via `scripts/mcp-proxy.py` to in-cluster pods.

```bash
# Start a Solomon session
cd /path/to/solomon && claude  # then run /solomon
```

Use `claude --model opus` for any session making cluster or infrastructure changes.

---

## Bootstrap

Day-0 sequence (new cluster):

```bash
# 1. Workers join the control-plane (kubeadm, done manually)

# 2. Run bootstrap script on agx-orin-prod-1
bash scripts/bootstrap.sh
# Installs: Helm, Cilium, Sealed Secrets controller, ArgoCD

# 3. Apply root ArgoCD Application — it manages everything else
kubectl apply -f argocd-apps/_root.yaml

# 4. Monitor sync
kubectl -n argocd get applications -w

# 5. After Keycloak is up — import realm, seal runtime secrets (see MIGRATION.md)
```

See `MIGRATION.md` for the full phased migration checklist including all RUNTIME tasks.

---

## Branching and releases

Branch names and commit type prefixes (`feat:`, `fix:`, `chore:`) are independent.
A `v0.1` milestone branch holds commits of every type. `feat/*` branches are short-lived
topic branches, not tied to commit type.

**Pre-launch** (manifests being built, no live cluster yet):
```
main    ArgoCD target.
v0.1    All milestone work accumulates here.
feat/*  Short-lived, branches from v0.1 for large risky sub-tasks.
─────────────────────────────────────────
Phase 13 done + cluster healthy → merge v0.1 → main → tag v0.1
```

**Post-launch** (live cluster, Phase 13+):
```
main    ArgoCD target. Direct commits for safe changes.
feat/*  Short-lived. Risky changes only — branch from main, merge after verify.
fix/*   Short-lived. Complex hotfixes only — same lifecycle.
─────────────────────────────────────────
Milestones tagged on main: v0.2, v1.0, etc.
```

Tags represent **verified cluster states** — only ever on `main`.

All commits follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `ci:`. Breaking changes: append `!`.

Changelogs generated with [git-cliff](https://git-cliff.org/) — see `cliff.toml`.

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

## New app

```bash
scripts/new-app.sh <name> [namespace]
```

Creates a GitHub repo from `templates/app-template/`, pushes initial commit.
`provision.yaml` runs automatically and bootstraps: Cloudflare CNAME, Keycloak client
(SealedSecret), LiteLLM virtual key (SealedSecret), ArgoCD Application in platform repo.
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

## Branching

```
main     ArgoCD target. Stable, always deployable. Direct commits for small safe changes.
v0.1     Current: initial cluster build. Merges to main when bootstrapped and healthy.
feat/*   Short-lived. Risky infra changes (CNI upgrade, Istio upgrade, new operator).
fix/*    Short-lived. Hotfixes.
```

All commits follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `ci:`. Breaking changes: append `!`.

Changelogs generated with [git-cliff](https://git-cliff.org/) — see `cliff.toml`.

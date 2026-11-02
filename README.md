# project-solomon

Self-hosted 3-node Kubernetes cluster on NVIDIA Jetson hardware. Built for running FastAPI microservices, LangGraph agents, and UI applications with a full GitOps workflow and local AI inference.

Managed by **Solomon** — a Claude Code skill that knows the cluster, builds services consistently, and handles operations.

---

## Node topology

| Node | Role | RAM | IP |
|------|------|-----|----|
| agx-orin-prod-1 | control-plane + GPU workloads | 61 GB | 192.168.1.49 |
| orin-nano-prod-1 | worker | 7 GB | 192.168.1.175 |
| orin-nano-dev-1 | worker | 7 GB | 192.168.1.139 |

All nodes: NVIDIA Jetson ARM64. LLM inference and ARC runners pin to agx-orin-prod-1 (61 GB RAM, 1 TB SSD, GPU).

---

## Tech stack

### Foundation

| Component | Purpose |
|-----------|---------|
| Cilium | CNI — Istio-compatible (`kubeProxyReplacement=false`) |
| NVIDIA operator | GPU runtime class for Jetson nodes |
| local-path provisioner | Dynamic PVCs on 1 TB SSD (agx-orin-prod-1) |
| cert-manager | Wildcard TLS — `*.project-solomon.ai` via Let's Encrypt DNS-01/Cloudflare |
| Sealed Secrets | Git-safe secret management — encrypted SealedSecret CRDs |

### Networking

| Component | Purpose |
|-----------|---------|
| Istio ambient mode | Service mesh — ztunnel DaemonSet (~50 MB/node), no per-pod sidecars |
| Istio IngressGateway | Cluster ingress — hostPort 443 (LAN) + ClusterIP 80 (Cloudflare) |
| Kubernetes Gateway API | HTTPRoute, Gateway, GatewayClass — standard over Istio VirtualService |
| Cloudflare Tunnel | External access → Istio IngressGateway |
| dnsmasq | Split DNS on agx-orin-prod-1 — LAN clients resolve `*.project-solomon.ai` → 192.168.1.49 directly |

### Auth

| Component | Purpose |
|-----------|---------|
| Keycloak | SSO — identity provider for all services |
| oauth2-proxy | Browser SSO for UI apps — handles OIDC redirect to Keycloak |
| Istio JWT auth policy | API / agent protection — validates Keycloak JWTs at IngressGateway (cluster-wide) |

Every application gets a Keycloak **resource server** client (audience validation). UI apps additionally get a browser client + oauth2-proxy. Agents making outbound M2M calls get a service account client (Client Credentials flow).

### Data

| Component | Purpose |
|-----------|---------|
| CloudNativePG | Postgres operator — shared cluster, one `Database` CRD per service |
| LangGraph AsyncPostgresSaver | Per-thread agent checkpointing in postgres |
| LangGraph AsyncPostgresStore | Cross-thread agent memory in postgres |
| MinIO | Object storage on 1 TB SSD — Velero backup target, agent artifacts |

### AI

**Local inference** (NVIDIA Jetson AGX Orin — only [Jetson AI Lab](https://www.jetson-ai-lab.com/models/) official containers):

| Component | Engine | Model | Notes |
|-----------|--------|-------|-------|
| llama-server | llama.cpp | Muse Glimmer 30B | GGUF, 131K ctx, ~25 tok/s, vision |
| vllm | vLLM | Nemotron3 Nano 30B-A3B | MoE, ~3B active params, fast tier |

Total loaded: ~25 GB of 61 GB unified memory. Both stay hot simultaneously.

- Muse Glimmer auto-downloads 3 artifacts on first start (17 GB model + vision encoder + DFlash decoder). Needs HuggingFace token (SealedSecret).
- Nemotron3 Nano auto-downloads from HuggingFace when vLLM starts (~15–20 GB). First startup is slow — subsequent restarts use the cached PVC.

**External providers** (accessed via LiteLLM, pay-as-you-go, no subscription):

| Provider | Models | Pricing |
|----------|--------|---------|
| [Together AI](https://www.together.ai/pricing) | GLM-5.2, GLM-5.3, Kimi K3, GLM-5.3 Flash | GLM-5.2: $1.40/$4.40 · Kimi K3: $3.00/$15.00 per 1M |
| [Fireworks AI](https://fireworks.ai/pricing) | Muse Glimmer 30B (cloud), GLM-5.3 Flash | MG30B: $1.96/$4.88 · Flash: $0.225/$0.75 per 1M |
| Anthropic | Claude Sonnet | Pay-per-token |

No OpenRouter — LiteLLM is the gateway. Adding OpenRouter would just insert a middleman with a markup between LiteLLM and the providers. Together AI and Fireworks connect directly.

**LiteLLM proxy** — the single AI gateway for all agents and services:
- Per-service virtual keys with spend limits
- Model aliases (agents code against these — never raw model names or provider URLs)
- Automatic fallback routing
- Full usage logging

| Alias | Primary | Fallback | Use for |
|-------|---------|---------|---------|
| `smart` | Muse Glimmer 30B (local) | Muse Glimmer 30B (Fireworks) | Reasoning, planning, tool chains, vision, long context |
| `fast` | Nemotron3 Nano (local) | GLM-5.3 Flash (Together AI) | High-frequency calls, routing, classification |
| `glm` | GLM-5.2 (Together AI) | GLM-5.3 (Together AI) | GLM-family tasks |
| `kimi` | Kimi K3 (Together AI) | — | Kimi-specific workflows |
| `external` | Claude Sonnet (Anthropic) | — | Quality ceiling, complex reasoning |

### CI/CD

| Component | Purpose |
|-----------|---------|
| GitHub Actions | Build image → push GHCR → patch image tag in git → ArgoCD syncs |
| GHCR | Container registry — free, automatic `GITHUB_TOKEN` auth |
| ARC | Actions Runner Controller — self-hosted ARM64 ephemeral runners, plain YAML manifests |
| Docker layer cache | 100 GB PVC on 1 TB SSD — cold build 4–6 min → warm 15–30 s |
| ArgoCD | GitOps — watches `k8s/` in each app repo, syncs to cluster |

**Image tagging:** every push to `main` produces `:<sha>` (immutable, used in `deployment.yaml`) and `:latest`. Release tags additionally produce `:v1.2.3`. ArgoCD always tracks the SHA tag — deployment history is fully traceable.

### MCP / Tools

| Tier | Location | Purpose |
|------|----------|---------|
| Cluster tools | `infrastructure/mcp-servers/` | kubernetes, prometheus, database — shared by all agents |
| Agent tools | App repo sidecar container | Agent-specific business logic tools |
| Third-party tools | `mcp-external` namespace or remote endpoint | External APIs registered in LiteLLM |

LiteLLM acts as the **MCP gateway** — all MCP servers register with it. Agents discover and call tools through a single endpoint. Tool calls are logged and tracked alongside LLM usage.

### Observability

| Component | Purpose |
|-----------|---------|
| Prometheus | Metrics collection and alerting |
| Grafana | Dashboards — Prometheus metrics + Loki logs + Jaeger traces |
| Loki | Log aggregation and storage |
| Promtail | DaemonSet — ships pod logs from all nodes to Loki |
| Kiali | Istio service mesh topology and traffic visualization |
| Jaeger | Distributed tracing |

### Backup

| Component | Purpose |
|-----------|---------|
| Velero | Scheduled cluster backups |
| MinIO | Backup target on local 1 TB SSD |

---

## Architecture

### Networking and ingress

Traffic enters the cluster from two paths:

```
External user
  browser/client → Cloudflare DNS (*.project-solomon.ai)
  → Cloudflare Tunnel → Istio IngressGateway (ClusterIP :80)
  → HTTPRoute → target service

LAN user (device DNS set to 192.168.1.49)
  browser/client → dnsmasq on agx-orin-prod-1
  → resolves *.project-solomon.ai → 192.168.1.49
  → Istio IngressGateway (hostPort :443, wildcard TLS)
  → HTTPRoute → target service
```

LAN path bypasses Cloudflare entirely — ~65 ms TTFB vs ~375 ms via tunnel.

Istio IngressGateway is the single entry point. Every inbound request passes through Istio JWT auth policy before reaching the service.

### Auth flows

**Browser / UI app:**
```
User hits https://myapp.project-solomon.ai
→ oauth2-proxy intercepts (no session cookie)
→ redirect to Keycloak login
→ user authenticates
→ Keycloak issues JWT → oauth2-proxy stores session
→ oauth2-proxy proxies request to app with user identity headers
```

**API / programmatic client:**
```
Client already holds a JWT (obtained from Keycloak)
→ calls https://myapi.project-solomon.ai with Bearer token
→ Istio JWT auth policy validates signature against Keycloak JWKS
→ checks audience claim matches the API's resource server client ID
→ request reaches service
```

**In-cluster service-to-service:**
```
Service A → Service B (internal DNS)
→ Istio ztunnel provides mTLS automatically
→ no tokens required for in-cluster calls
```

**Agent M2M (calling external OAuth2 APIs):**
```
Agent → POST /token (client_id + client_secret) → Keycloak
→ receive access_token (Client Credentials flow)
→ call external API with Bearer token
```

### Database isolation

Each service gets its own postgres database via a `Database` CRD:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: my-agent-db
spec:
  name: my_agent_db
  owner: my_agent
  cluster:
    name: shared-postgres
```

CloudNativePG automatically provisions the database, user, and a credentials Secret in the target namespace. Services never share credentials.

### CI/CD pipeline

```
Developer pushes to main (app repo)
  │
  ├─ build.yaml (GitHub Actions on self-hosted ARM64 runner)
  │    build Docker image (with layer cache from 1TB SSD PVC)
  │    push to GHCR:
  │      ghcr.io/stephenj-code/<service>:<7-char-sha>   ← immutable
  │      ghcr.io/stephenj-code/<service>:latest
  │    patch k8s/deployment.yaml with SHA tag
  │    commit + push to main
  │
  └─ ArgoCD detects k8s/ change
       sync to cluster → rolling update
```

On git release tag: additionally pushes `ghcr.io/stephenj-code/<service>:v1.2.3`.

Provisioning (first deploy only) runs separately via `provision.yaml` — calls Cloudflare API, Keycloak admin API, LiteLLM admin API. No cluster credentials in GitHub; all changes land via git commits that ArgoCD applies.

### Agent communication protocols

**AG-UI** (agent ↔ browser UI): SSE streaming over standard HTTPS. No special infrastructure — Istio IngressGateway supports SSE natively. Agents expose `/agui` SSE endpoint alongside their REST API.

**A2A** (agent ↔ agent): HTTP over in-cluster DNS. Istio mTLS handles auth automatically. Agents register with LiteLLM as model endpoints — other agents call them through the LiteLLM gateway for unified routing and logging. Agents expose `/.well-known/agent.json` (Agent Card) for A2A discovery.

---

## Building a new service

Every service, agent, and app starts from the **`solomon-app-template`** GitHub template repository. It provides a consistent structure, CI/CD workflows, and provisioning scripts.

```bash
gh repo create my-agent --template stephenj-code/solomon-app-template --private
```

### App types

| Type | Auth | DB | MCP sidecar | Protocol |
|------|------|----|-------------|---------|
| `api` | Istio JWT | optional | optional | REST |
| `agent` | Istio JWT | yes (checkpointer) | likely | REST + A2A |
| `ui` | oauth2-proxy + Keycloak client | optional | no | REST + AG-UI |

### `app.yaml` — the contract

```yaml
name: research-agent
type: agent                       # api | agent | ui
subdomain: research               # research.project-solomon.ai
namespace: research-agent

needs:
  database: true                  # CloudNativePG Database CRD
  litellm_key: true               # per-service LiteLLM virtual key
  mcp_server: false               # agent-specific MCP sidecar
  keycloak_client: false          # browser SSO (UI apps only)
  keycloak_service_account: false # M2M outbound calls (Client Credentials)

# keycloak_audience: true is always provisioned for all app types
# (resource server client for JWT audience validation)
```

### What provisioning creates

Every app (all types):
- Cloudflare CNAME: `<subdomain>.project-solomon.ai` → tunnel
- Keycloak resource server client (audience validation)
- LiteLLM virtual key → sealed and committed to `k8s/sealed-secrets/`
- Namespace, ServiceAccount, Deployment, Service, HTTPRoute
- Istio JWT auth policy (checks audience claim for this app)
- ArgoCD Application committed to `argocd-apps/` in this repo

Additionally for `type: ui` or `keycloak_client: true`:
- Keycloak browser client with redirect URIs
- oauth2-proxy Deployment + Service in the app namespace

Additionally for `keycloak_service_account: true`:
- Keycloak confidential client (Client Credentials grant)
- Client secret → sealed and committed to `k8s/sealed-secrets/`

Additionally for `needs.database: true`:
- CloudNativePG `Database` CRD committed to `infrastructure/database/databases/`

### App repo structure

```
my-service/
├── app.yaml                      # declares what this app needs
├── app/
│   ├── main.py                   # FastAPI app
│   ├── routers/
│   │   ├── api.py                # REST endpoints
│   │   ├── agui.py               # AG-UI SSE stream (agents/UI apps)
│   │   └── a2a.py                # A2A agent card + task endpoints (agents)
│   ├── requirements.txt
│   └── Dockerfile
├── mcp-server/                   # only if needs.mcp_server: true
│   ├── server.py
│   └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── serviceaccount.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── httproute.yaml
│   ├── auth-policy.yaml          # Istio JWT policy (api/agent) or oauth2-proxy (ui)
│   └── sealed-secrets/           # CI-generated, safe to commit
├── .github/
│   └── workflows/
│       ├── build.yaml            # runs on every push to main
│       └── provision.yaml        # runs once (app.yaml changes or manual trigger)
└── CLAUDE.md                     # app-specific context for Solomon
```

### Provisioning GitHub secrets (org-level)

| Secret | Used for |
|--------|---------|
| `CF_API_TOKEN` | Cloudflare DNS CNAME creation |
| `CF_ZONE_ID` | Cloudflare zone |
| `KEYCLOAK_ADMIN_URL` | Keycloak admin API |
| `KEYCLOAK_ADMIN_PASS` | Keycloak admin credentials |
| `LITELLM_ADMIN_KEY` | LiteLLM virtual key creation |
| `KUBESEAL_CERT` | Sealed Secrets public key (offline sealing in CI) |
| `PLATFORM_REPO_TOKEN` | PAT to commit Database CRD + ArgoCD Application back to this repo |

---

## Repo structure

```
solomon/
├── CLAUDE.md                     # Solomon instructions and cluster knowledge
├── README.md                     # this file
├── .mcp.json                     # MCP server bridge config for Solomon
│
├── infrastructure/               # All cluster manifests — ArgoCD syncs these
│   ├── namespaces/
│   │   └── namespaces.yaml
│   ├── foundation/
│   │   ├── cilium/
│   │   ├── cert-manager/
│   │   ├── storage/
│   │   ├── sealed-secrets/
│   │   └── nvidia/
│   ├── networking/
│   │   ├── istio/
│   │   └── cloudflared/
│   ├── auth/
│   │   ├── keycloak/
│   │   └── oauth2-proxy/
│   ├── database/
│   │   ├── cloudnativepg/        # operator + shared cluster
│   │   └── databases/            # per-app Database CRDs (added by provisioning)
│   ├── ai/
│   │   ├── llama-server/         # llama.cpp container — Muse Glimmer 30B (GGUF)
│   │   ├── vllm/                 # vLLM container — Nemotron3 Nano 30B-A3B (MoE)
│   │   └── litellm/
│   ├── backup/
│   │   ├── minio/
│   │   └── velero/
│   ├── observability/
│   │   ├── prometheus/
│   │   ├── grafana/
│   │   ├── loki/
│   │   ├── promtail/
│   │   ├── kiali/
│   │   └── jaeger/
│   ├── gitops/
│   │   └── argocd/
│   ├── ci-cd/
│   │   └── arc/
│   │       ├── controller/       # rendered from helm template, plain YAML
│   │       └── runners/
│   │           └── build-runner/
│   ├── mcp-servers/
│   │   ├── kubernetes/
│   │   ├── prometheus/
│   │   └── database/
│   └── security/
│
├── argocd-apps/                  # App-of-apps: one Application CR per component
│   ├── _root.yaml                # root app — ArgoCD watches this directory
│   ├── foundation.yaml
│   ├── networking.yaml
│   ├── auth.yaml
│   ├── database.yaml
│   ├── ai.yaml
│   ├── backup.yaml
│   ├── observability.yaml
│   ├── gitops.yaml
│   ├── ci-cd.yaml
│   └── mcp-servers.yaml
│   # per-app Application CRs added here by provisioning workflow
│
└── scripts/
    ├── bootstrap.sh              # Day-0: install ArgoCD + apply root app
    ├── mcp-proxy.py              # MCP bridge (proxies to in-cluster MCP servers)
    └── sealed-secrets.pem        # Cluster public key for offline sealing (gitignored if sensitive)
```

---

## Solomon

Solomon is Claude Code configured as a cluster manager via this repo's `CLAUDE.md` and the `/solomon` skill in `.claude/solomon.md`.

There are no runtime services for Solomon (no API, no UI, no background agent). Solomon is invoked directly in a Claude Code session. It has full cluster access via MCP tools bridged through `scripts/mcp-proxy.py`.

**Modes:**
- **OPS** — diagnose and remediate cluster issues
- **BUILD** — add/modify infrastructure or services (always use `claude --model opus`)
- **DESIGN** — plan architecture, new services, migrations

**Session start:** run `/solomon` in the Claude Code CLI from this repo's directory.

---

## Bootstrap

Day-0 sequence (new cluster from scratch):

```bash
# 1. Install ArgoCD manually (only thing kubectl apply'd directly)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. Apply the root ArgoCD Application — it manages everything else
kubectl apply -f argocd-apps/_root.yaml

# 3. ArgoCD takes over — syncs all components from this repo
# Monitor: kubectl -n argocd get applications

# 4. Install Sealed Secrets controller (chicken-and-egg: needed before secrets can be applied)
# Included in infrastructure/foundation/sealed-secrets/ — apply manually first
kubectl apply -f infrastructure/foundation/sealed-secrets/

# 5. Seal and commit all required secrets (Keycloak, Cloudflare token, etc.)
# Then let ArgoCD sync them
```

See `scripts/bootstrap.sh` for the full annotated sequence.

---

## Branching and releases

### Commit conventions

All commits — in this repo and every app repo — follow **Conventional Commits**:

```
<type>: <short description>

feat: add cloudnativepg operator
fix: correct istio httproute for oauth2-proxy callback
chore: bump litellm to 1.52.0
refactor: consolidate mcp-server deployments
docs: update bootstrap sequence
ci: add release-please workflow
feat!: replace traefik with istio ingressgateway   ← breaking change
```

| Type | When |
|------|------|
| `feat` | New capability |
| `fix` | Corrects broken behaviour |
| `refactor` | Restructures without changing behaviour |
| `chore` | Maintenance, version bumps, cleanup |
| `docs` | Documentation only |
| `ci` | CI/CD workflow changes |

This discipline keeps `git log` readable and enables automated changelog generation.

### Platform repo branching

```
main          ArgoCD target. Stable, always deployable.
v0.1          Current working branch — initial cluster build. Merges to main when healthy.
feat/<name>   Short-lived — risky infra changes (CNI upgrade, new operator, Istio upgrade).
fix/<name>    Short-lived — hotfixes.
```

Small safe changes (config tweaks, namespace additions, image bumps) go directly to `main`.
Anything that could destabilize the cluster goes on a feature branch — review the diff before merging.

**Milestone tagging:**
```bash
git tag v0.1    # initial cluster bootstrapped and healthy
git tag v0.2    # first app deployed end-to-end
git push origin --tags
```

**Changelog generation** (git-cliff reads conventional commits):
```bash
git-cliff v0.1..v0.2 --output CHANGELOG.md
```

### App repo branching

```
main          ArgoCD target. Push to main = deploy to cluster.
feat/<name>   Non-trivial features, dependency changes, graph changes.
fix/<name>    Bug fixes (small ones can go direct to main).
```

**Automated releases via release-please:**

A GitHub Actions workflow watches `main` for conventional commits and automatically opens a Release PR with version bump + CHANGELOG.md. Merge when ready to cut a release → creates git tag + GitHub Release.

```yaml
# .github/workflows/release.yaml  (included in _template/)
- uses: googleapis/release-please-action@v4
  with:
    release-type: python
```

ArgoCD targets `main` for continuous deploy on most app repos. Point at the latest release tag for anything that needs explicit promotion before deploying.

### Changelog

`cliff.toml` at the repo root configures git-cliff for platform changelog generation. Run:

```bash
# Since last tag
git-cliff --output CHANGELOG.md

# Between specific tags
git-cliff v0.1..v0.2 --output CHANGELOG.md

# Preview without writing
git-cliff --unreleased
```

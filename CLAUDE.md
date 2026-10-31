# CLAUDE.md — project-solomon

This is the platform repo for **project-solomon**: a self-hosted 3-node Kubernetes cluster on NVIDIA Jetson hardware managed by Solomon (Claude Code).

## Repo structure

- `infrastructure/` — All cluster manifests, synced by ArgoCD
- `argocd-apps/` — ArgoCD Application CRs (app-of-apps pattern)
- `scripts/` — Bootstrap scripts and MCP proxy bridges
- `_template/` — Cookiecutter template for new services, agents, and apps
- `.claude/` — Solomon skill files

## Quick start

Run `/solomon` or say **"become solomon"** to initialize a session.

## When "become solomon" is said

Execute in order:

1. **Read this file** — internalize topology, rules, tool inventory
2. **Check node health**: `mcp__solomon-kubernetes__list_nodes` — surface any NotReady nodes
3. **Check degraded workloads**: `mcp__solomon-kubernetes__list_deployments` across all namespaces — flag anything not fully available
4. **Check active alerts**: `mcp__solomon-prometheus__prometheus_get_alerts` — surface firing alerts
5. **Output session brief** — health score, any issues, mode, available tools
6. **Await instructions**

Session brief format:

```
SOLOMON // SESSION START — {date}
MODE: OPS | BUILD | DESIGN  (set when first task is clear)

Cluster Health
  Nodes: X/3 ready
  Deployments: X degraded (list them)
  Alerts: X firing (list them)

Tool Inventory
  kubernetes / prometheus / filesystem

Awaiting instructions.
```

---

## Operating modes

### OPS — Investigation and remediation
- Diagnose cluster issues using MCP tools
- Remediate safely; design Work Orders for anything destructive
- Do not modify application code or manifests directly unless it is a hotfix

### BUILD — Cluster and infrastructure changes
- All changes via git → ArgoCD (commit to `main`, ArgoCD syncs)
- Only use `kubectl apply` for emergency hotfixes — document why
- **Always start BUILD sessions with `claude --model opus`**

### DESIGN — Architecture and strategy
- No cluster changes
- Plan new services, infrastructure, migrations, and cookiecutter usage

---

## Key rules

- **Git is the source of truth** — never make persistent cluster changes outside of git
- **ArgoCD syncs `main`** — commit, push, ArgoCD picks it up
- **Never schedule Ollama/LLM inference on orin-nano nodes** — 7 GB RAM, insufficient
- **Never modify** kube-system, kube-public, kube-node-lease namespaces
- **Never store secrets in plaintext** — always Sealed Secrets (`kubeseal`)
- **Every new service** must be provisioned via the cookiecutter workflow (see `_template/`)
- **After any infra change** — check `argocd-apps/` for stale or missing Application CRs

---

## Destructive actions — always require explicit Steve approval

Stop and confirm before executing any of these, regardless of context:

- **Node reboot** (`sudo reboot`, `shutdown -r`) — takes down control-plane and all workloads
- **Node drain** (`kubectl drain`) — evicts all pods from a node
- **Node delete** (`kubectl delete node`)
- **Kernel / firmware changes** requiring reboot (e.g. `nvpmodel`, `jetson_clocks`)
- **etcd deletion or restore**
- **Velero restore** — overwrites live cluster state

When designing a plan that includes any of these: stop, describe what and why, wait for explicit approval.

---

## Node topology

| Node | Role | RAM | IP |
|------|------|-----|----|
| agx-orin-prod-1 | control-plane + GPU workloads | 61 GB | 192.168.1.49 |
| orin-nano-prod-1 | worker | 7 GB | 192.168.1.175 |
| orin-nano-dev-1 | worker | 7 GB | 192.168.1.139 |

**agx-orin-prod-1** hosts: Ollama (local LLMs), ARC self-hosted runners, Docker layer cache (1 TB SSD), dnsmasq (LAN DNS), control-plane components.

**orin-nano nodes** — workers only. Never schedule LLM inference here.

---

## Namespace inventory

| Namespace | Contents |
|-----------|----------|
| `arc-systems` | ARC controller |
| `arc-runners` | Ephemeral GitHub Actions runner pods |
| `argocd` | ArgoCD |
| `auth` | Keycloak, oauth2-proxy |
| `ai` | Ollama, LiteLLM proxy |
| `backup` | Velero, MinIO |
| `database` | CloudNativePG operator + shared postgres cluster |
| `mcp-servers` | Cluster-level MCP servers (kubernetes, prometheus, database) |
| `mcp-external` | Third-party MCP servers (network-isolated) |
| `observability` | Prometheus, Grafana, Loki, Promtail, Kiali, Jaeger |
| `agents` | LangGraph agents (each agent gets its own namespace when isolated) |

Each application, agent, and UI gets its own namespace provisioned via the cookiecutter workflow.

---

## MCP tool inventory

Tools are available via MCP bridges configured in `.mcp.json`. Bridges proxy through `scripts/mcp-proxy.py` into in-cluster MCP server pods.

**solomon-kubernetes/**
`list_pods`, `list_deployments`, `list_nodes`, `get_pod_logs`, `get_events`, `list_services`, `list_namespaces`, `get_deployment`, `restart_deployment`, `list_ingress`

**solomon-prometheus/**
`prometheus_query`, `prometheus_query_range`, `prometheus_get_alerts`, `prometheus_get_targets`

**solomon-filesystem/**
`read_file`, `write_file`, `patch_file`, `list_dir`, `run_shell`, `node_exec` (targets: agx-orin-prod-1, orin-nano-prod-1, orin-nano-dev-1)

MCP servers are deployed in `infrastructure/mcp-servers/` and run in the `mcp-servers` namespace.

---

## Cookiecutter workflow

Every new service, agent, or app starts from `_template/`. See `_template/README.md` for full usage.

**Provision a new app (one-time):**
```bash
# Trigger the provision workflow manually in GitHub Actions
# OR let it auto-run when app.yaml is first committed to main
```

**What provisioning creates automatically** (driven by `app.yaml`):
- Cloudflare CNAME (`<subdomain>.project-solomon.ai` → tunnel)
- LiteLLM virtual key (sealed → committed to `k8s/sealed-secrets/`)
- Keycloak resource server client (audience validation, all apps)
- Keycloak browser client + oauth2-proxy config (UI apps only)
- Keycloak service account client (M2M apps only)
- CloudNativePG Database CRD committed to platform repo (if `needs.database: true`)
- ArgoCD Application committed to `argocd-apps/` in this repo
- Namespace, ServiceAccount, HTTPRoute, Istio JWT auth policy

---

## Ingress architecture

```
External user
  DNS: <subdomain>.project-solomon.ai → Cloudflare
  Cloudflare Tunnel → Istio IngressGateway (ClusterIP :80)

LAN user (DNS set to 192.168.1.49)
  DNS: <subdomain>.project-solomon.ai → 192.168.1.49 (dnsmasq)
  Direct → Istio IngressGateway (hostPort :443, wildcard TLS via cert-manager)

Istio IngressGateway
  HTTPRoute → service in target namespace
  Istio JWT auth policy → validates Keycloak JWT on every request
  (UI apps: oauth2-proxy sits in front, handles browser SSO redirect)
```

---

## Secrets

All secrets managed via **Sealed Secrets**. Never commit raw Kubernetes Secrets.

```bash
# Seal a secret (safe to commit)
kubectl create secret generic my-secret \
  --from-literal=key=value \
  --dry-run=client -o yaml | \
  kubeseal --cert scripts/sealed-secrets.pem --format yaml \
  > k8s/sealed-secrets/my-secret.yaml
```

The Sealed Secrets controller lives in `infrastructure/sealed-secrets/`. Its public key is cached at `scripts/sealed-secrets.pem` for offline sealing.

---

## CI/CD flow

```
Push to main (app repo)
  → GitHub Actions: build Docker image on self-hosted ARM64 runner
  → Push to GHCR (ghcr.io/stephenj-code/<service>:<sha>)
  → Patch k8s/deployment.yaml with new image tag
  → Commit + push to main
  → ArgoCD detects change → syncs to cluster
```

Self-hosted runners: ARC on agx-orin-prod-1, ARM64, ephemeral pods, DinD sidecar, 100 GB Docker layer cache PVC on 1 TB SSD.

---

## Commit conventions

All commits in this repo and every app repo follow **Conventional Commits**:

```
<type>: <short description>

# Examples
feat: add cloudnativepg operator
fix: correct istio httproute for oauth2-proxy callback
chore: bump litellm to 1.52.0
refactor: consolidate mcp-server deployments into single namespace
docs: update bootstrap sequence in README
ci: add release-please workflow
```

**Types:**

| Type | When to use |
|------|------------|
| `feat` | New capability — new infra component, new API endpoint, new agent feature |
| `fix` | Corrects broken behaviour |
| `refactor` | Restructures without changing behaviour |
| `chore` | Maintenance — version bumps, cleanup, dependency updates |
| `docs` | Documentation only |
| `ci` | CI/CD workflow changes |
| `test` | Test additions or fixes |

**Breaking changes:** append `!` to the type or add a `BREAKING CHANGE:` footer:

```
feat!: replace traefik with istio ingressgateway

BREAKING CHANGE: all HTTPRoute resources must be updated to Gateway API spec
```

Solomon writes commits in this format by default. Never write vague messages like `update config` or `fix stuff`.

---

## Branching strategy

### Platform repo (this repo)

```
main        ArgoCD watches this. Stable, always deployable. Direct commits for small safe changes.
v0.1        Current: initial cluster build. Merge to main when cluster is bootstrapped and healthy.
feat/<name> Short-lived. Big or risky infra changes (CNI upgrade, new operator, Istio upgrade).
fix/<name>  Short-lived. Hotfixes.
```

**When to use a feature branch:** anything that could destabilize the cluster if it goes wrong. Small config changes, adding namespaces, bumping image tags → direct to `main`.

**Tagging milestones manually:**

```bash
git tag v0.1    # initial cluster healthy
git tag v0.2    # first app deployed end-to-end
git push origin --tags
```

**Generating a changelog between tags:**

```bash
git-cliff v0.1..v0.2 --output CHANGELOG.md
git add CHANGELOG.md && git commit -m "docs: update changelog for v0.2"
```

### App repos (per service/agent/api)

```
main        ArgoCD watches this. Push to main = deploy to cluster.
feat/<name> Non-trivial features, dependency changes, agent graph changes.
fix/<name>  Bug fixes (small ones can go direct to main).
```

**Releases via release-please:** a GitHub Action watches `main` for conventional commits and opens a Release PR automatically. Merge it when ready to cut a release. On merge: git tag + GitHub Release + CHANGELOG.md generated automatically.

ArgoCD for most app repos tracks `main` (continuous deploy). For stable/production-critical apps, point ArgoCD at the latest release tag instead.

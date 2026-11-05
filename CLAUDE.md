# CLAUDE.md — project-solomon

This is the platform repo for **project-solomon**: a self-hosted 3-node Kubernetes cluster on NVIDIA Jetson hardware managed by Solomon (Claude Code).

## Repo structure

- `infrastructure/` — All cluster manifests, synced by ArgoCD
- `argocd-apps/` — ArgoCD Application CRs (app-of-apps pattern)
- `scripts/` — Bootstrap scripts and MCP proxy bridges
- `.claude/commands/` — Solomon slash commands (`/solomon` session init)
- `MIGRATION.md` — Cluster build/migration task checklist
- `ARCHITECTURE.md` — Per-namespace object inventory, ingress patterns, cross-namespace flows. **Read before writing or modifying any manifest, HTTPRoute, Istio policy, or ArgoCD Application.**

## Quick start

Run `/solomon` or say **"become solomon"** to initialize a session.

---

## Key rules

- **Git is the source of truth** — never make persistent cluster changes outside of git
- **ArgoCD syncs `main`** — commit, push, ArgoCD picks it up
- **Use `claude --model opus`** for any session making cluster or infrastructure changes
- **Never schedule LLM inference on orin-nano nodes** — 7 GB RAM, insufficient; llama-server and vllm pin to agx-orin-prod-1
- **AI model policy** — only models listed on [jetson-ai-lab.com/models](https://www.jetson-ai-lab.com/models/) are deployed; check there first before adding any model
- **HuggingFace token required** — llama-server and vllm pull models from HuggingFace on first start; token stored as SealedSecret in `ai` namespace
- **Never modify** kube-system, kube-public, kube-node-lease namespaces
- **Never store secrets in plaintext** — always Sealed Secrets (`kubeseal`); exception: Frigate RTSP creds live in `/data/frigate/.env` (chmod 600) on the host
- **Every new service** must be provisioned via `scripts/new-app.sh <name>` (uses `templates/app-template/` in this repo)
- **After any infra change** — check `argocd-apps/` for stale or missing Application CRs
- **Agent co-location** — agents live in their tool's namespace (see namespace inventory); `agents` namespace is catch-all only
- **All agents registered in LiteLLM agent registry** — provisioning workflow handles this automatically
- **Never use Istio VirtualService** — always use Kubernetes Gateway API `HTTPRoute`
- **Deny-by-default AuthorizationPolicy** is active on `ai`, `auth`, `mcp-servers` — explicit allow rules required for new in-cluster consumers

---

## Documentation discipline

**Every infrastructure change must update the relevant docs in the same commit.**

| Changed | Update |
|---------|--------|
| Namespace added / removed | `ARCHITECTURE.md` namespace inventory + `CLAUDE.md` namespace table |
| App port, hostname, or auth mode changed | `ARCHITECTURE.md` namespace entry |
| New cross-namespace flow | `ARCHITECTURE.md` cross-namespace flows section |
| Deny-by-default added / removed from a namespace | `ARCHITECTURE.md` + `CLAUDE.md` security posture |
| ArgoCD Application path changed | `ARCHITECTURE.md` namespace entry + `CLAUDE.md` namespace table |
| New tech stack component | `README.md` tech stack table |
| Node topology change | `README.md` + `CLAUDE.md` + `ARCHITECTURE.md` node tables |
| Migration task completed | `MIGRATION.md` — check the box; advance `Current active phase:` when all non-RUNTIME tasks in the phase are done |
| New hard rule or constraint | `CLAUDE.md` key rules |

Run `scripts/validate-docs.sh` before committing to catch namespace drift between
`infrastructure/`, `ARCHITECTURE.md`, and `namespaces.yaml`.

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

**agx-orin-prod-1** hosts: llama-server (Muse Glimmer 30B, llama.cpp), vllm (Nemotron3 Nano 30B-A3B), ARC self-hosted runners, Docker layer cache (1 TB SSD), dnsmasq (LAN DNS), Frigate NVR (Docker, not k8s), control-plane components.

**orin-nano nodes** — workers only. Never schedule LLM inference here.

---

## Namespace inventory

| Namespace | Contents |
|-----------|----------|
| `arc-systems` | ARC controller |
| `arc-runners` | Ephemeral GitHub Actions runner pods |
| `argocd` | ArgoCD |
| `auth` | Keycloak, oauth2-proxy, **keycloak-agent** |
| `ai` | llama-server (Muse Glimmer 30B), vllm (Nemotron3 Nano), LiteLLM proxy, **litellm-agent** |
| `backup` | Velero, MinIO, **backup-agent** |
| `database` | CloudNativePG operator + shared postgres cluster, **database-agent** |
| `mcp-servers` | solomon-kubernetes, solomon-prometheus, solomon-filesystem — Solomon tools only |
| `mcp-external` | Third-party MCP servers (network-isolated) |
| `nvr` | **frigate-agent** only — Frigate itself runs as Docker on agx-orin-prod-1 host |
| `observability` | Prometheus, Grafana, Loki, Promtail, Kiali, Jaeger, **grafana-agent**, **loki-agent** |
| `security` | Trivy Operator, **security-agent** |
| `agents` | Cross-cutting agents with no natural home namespace |

**Frigate note:** Frigate NVR runs as a Docker container on agx-orin-prod-1 (`--network=host`, `--privileged`, nvidia runtime). It is intentionally NOT in Kubernetes — host networking + GPU passthrough + single-instance bring no benefit from k8s orchestration. Exposed to the cluster via Istio `ServiceEntry` → `HTTPRoute` → `frigate.project-solomon.ai`. The frigate-agent calls `http://192.168.1.49:5000` directly.

---

## Ingress architecture

```
External user
  DNS: <subdomain>.project-solomon.ai → Cloudflare
  Cloudflare Tunnel → cloudflared pod → Istio IngressGateway (ClusterIP :80)

LAN user (DNS set to 192.168.1.49)
  DNS: <subdomain>.project-solomon.ai → dnsmasq → 192.168.1.49
  Direct → Istio IngressGateway (hostPort :443, wildcard TLS via cert-manager)

Istio IngressGateway
  Istio JWT auth policy → validates Keycloak JWT on every request
  HTTPRoute → service in target namespace
  (UI apps: oauth2-proxy sits in front, handles browser SSO redirect)
  (API apps: JWT passed directly, audience claim checked)
```

**Service types:** all internal services use ClusterIP. No NodePort. IngressGateway uses hostPort :443 (not NodePort — binds directly to node NIC via nodeSelector on agx-orin-prod-1).

**External services (e.g. Frigate):** Istio `ServiceEntry` registers host endpoints into the mesh. `HTTPRoute` routes the subdomain to the ServiceEntry.

---

## Security posture

**mTLS:** Istio ambient mode — ztunnel DaemonSet transparently encrypts all pod-to-pod traffic. Every pod has a SPIFFE identity. No sidecars required.

**Deny-by-default:** `AuthorizationPolicy` (empty spec = deny-all) is applied to `ai`, `auth`, `mcp-servers`. Explicit allow rules use SPIFFE principals (`cluster.local/ns/<ns>/sa/<sa>`).

**L4 NetworkPolicy:** Cilium NetworkPolicy enforced at kernel via eBPF (independent of mesh). Key rules: block pods from reaching kube-apiserver (except argocd, arc-runners, mcp-servers), block cross-namespace by default, block internet egress (except ai, arc-runners, argocd).

**Vulnerability scanning:** Trivy Operator continuously scans all running pods → `VulnerabilityReport` CRDs → Prometheus metrics. Trivy also runs in CI (image scan + IaC scan). security-agent queries these CRDs and escalates CVEs.

---

## MCP tool inventory

Tools are available via MCP bridges configured in `.mcp.json`. Bridges proxy through `scripts/mcp-proxy.py` into in-cluster MCP server pods.

**solomon-kubernetes/**
`list_pods`, `list_deployments`, `list_nodes`, `get_pod_logs`, `get_events`, `list_services`, `list_namespaces`, `get_deployment`, `restart_deployment`, `list_ingress`

**solomon-prometheus/**
`prometheus_query`, `prometheus_query_range`, `prometheus_get_alerts`, `prometheus_get_targets`

**solomon-filesystem/**
`read_file`, `write_file`, `patch_file`, `list_dir`, `run_shell`, `node_exec` (targets: agx-orin-prod-1, orin-nano-prod-1, orin-nano-dev-1)

MCP servers are deployed in `infrastructure/mcp-servers/` and run in the `mcp-servers` namespace. These are Solomon's tools only. Individual agents use native LangGraph `@tool` functions against their primary service — not MCP.

---

## New service workflow

Every new service, agent, or app starts from `templates/app-template/` in this repo.
The template lives here so it stays in sync with cluster design — no separate repo to drift.

```bash
scripts/new-app.sh my-agent
```

This creates the GitHub repo, copies the template, substitutes the app name, and pushes.
Edit `app.yaml` to describe what the app needs, then commit to `main`. The `provision.yaml` workflow runs automatically on first push and bootstraps all external dependencies.

**What provisioning creates automatically** (driven by `app.yaml`):
- Cloudflare CNAME (`<subdomain>.project-solomon.ai` → tunnel)
- LiteLLM virtual key (sealed → committed to `k8s/sealed-secrets/`)
- LiteLLM agent registry entry (all apps registered as agents by default)
- Keycloak resource server client (audience validation, all apps)
- Keycloak browser client + oauth2-proxy config (UI apps only)
- Keycloak service account client (M2M apps only)
- CloudNativePG Database CRD committed to platform repo (if `needs.database: true`)
- ArgoCD Application committed to `argocd-apps/` in this repo
- Namespace, ServiceAccount, HTTPRoute, Istio JWT auth policy

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

The Sealed Secrets controller lives in `infrastructure/foundation/sealed-secrets/`. Its public key is cached at `scripts/sealed-secrets.pem` for offline sealing.

**Exception — Frigate RTSP credentials:** stored in `/data/frigate/.env` (chmod 600) on agx-orin-prod-1 host. Docker reads them at startup via `--env-file`. Never in a k8s Secret.

---

## CI/CD flow

```
Push to main (app repo)
  → GitHub Actions: build Docker image on self-hosted ARM64 runner
  → Trivy image scan (fail on CRITICAL CVEs)
  → Bandit / Semgrep SAST scan
  → Push to GHCR:
      ghcr.io/stephenj-code/<service>:<7-char-sha>   ← immutable, used in deployment.yaml
      ghcr.io/stephenj-code/<service>:latest
  → On git tag (release): also push ghcr.io/stephenj-code/<service>:v1.2.3
  → Patch k8s/deployment.yaml with SHA tag
  → Commit + push to main
  → ArgoCD detects change → syncs to cluster
```

ArgoCD always tracks the SHA tag in `deployment.yaml`. Self-hosted runners: ARC on agx-orin-prod-1, ARM64, ephemeral pods, DinD sidecar, 100 GB Docker layer cache PVC.

---

## Commit conventions

All commits in this repo and every app repo follow **Conventional Commits**:

```
<type>: <short description>

feat: add cloudnativepg operator
fix: correct istio httproute for oauth2-proxy callback
chore: bump litellm to 1.52.0
refactor: consolidate mcp-server deployments into single namespace
docs: update bootstrap sequence in README
ci: add trivy image scanning to build workflow
```

| Type | When to use |
|------|------------|
| `feat` | New capability |
| `fix` | Corrects broken behaviour |
| `refactor` | Restructures without changing behaviour |
| `chore` | Maintenance — version bumps, cleanup, dependency updates |
| `docs` | Documentation only |
| `ci` | CI/CD workflow changes |
| `test` | Test additions or fixes |

**Breaking changes:** append `!` or add `BREAKING CHANGE:` footer.

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

**Generating a changelog:**

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

**Releases via release-please:** a GitHub Action watches `main` for conventional commits and opens a Release PR automatically. Merge to cut a release → git tag + GitHub Release + CHANGELOG.md generated automatically.

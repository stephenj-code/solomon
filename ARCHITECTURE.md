# project-solomon — cluster architecture reference

> Machine-readable reference for Solomon. Read this before writing or modifying any
> infrastructure manifest, ArgoCD Application, Istio policy, or HTTPRoute.
> Update this file whenever a namespace, app, port, hostname, or auth rule changes.

---

## Conventions (apply everywhere — do not repeat per app)

**GitOps:** git commit to `main` → ArgoCD detects → cluster converges. Never `kubectl apply` manually.

**ArgoCD root:** `argocd-apps/_root.yaml` watches `argocd-apps/` → spawns all child Applications.
Every child Application points at a path in `infrastructure/` with `directory.recurse: true`.

**Ingress — two paths into the cluster:**
- LAN: `dnsmasq` resolves `*.project-solomon.ai` → `192.168.1.49` → IngressGateway `:443` (TLS terminated, `wildcard-tls` cert from cert-manager, Cloudflare DNS-01).
- WAN: Cloudflare DNS → Cloudflare tunnel → `cloudflared` pod → IngressGateway `:80` (plain HTTP; Cloudflare terminates TLS externally).

**HTTPRoute pattern:** every app defines an `HTTPRoute` in its own namespace.
```yaml
parentRefs:
  - name: main
    namespace: istio-system
    sectionName: https
  - name: main
    namespace: istio-system
    sectionName: http
hostnames: [<app>.project-solomon.ai]
backendRefs: [{name: <service>, port: <port>}]
```
Gateway `allowedRoutes.namespaces.from: All` — no ReferenceGrant needed.

**JWT auth — two layers at the IngressGateway:**
1. `RequestAuthentication` `jwt-keycloak` (istio-system, targets Gateway `main`): validates Bearer tokens against Keycloak JWKS. Invalid token → 401. No token → passes through (browsers need to reach oauth2-proxy unauthenticated to start SSO).
2. `AuthorizationPolicy` per namespace: deny-all or explicit allow rules enforce who can reach what.

**Deny-by-default namespaces:** `ai`, `auth`, `mcp-servers` have `AuthorizationPolicy spec:{}` (deny-all).
Every new consumer of these namespaces needs an explicit ALLOW policy naming its SPIFFE principal:
`cluster.local/ns/<namespace>/sa/<serviceaccount>`

**All other namespaces** (observability, database, backup, security, nvr, arc-runners, etc.) have no Istio deny-all. Cilium NetworkPolicy provides L4 isolation.

**mTLS:** Istio ambient mode. ztunnel DaemonSet encrypts all pod-to-pod traffic transparently.
No sidecars. SPIFFE identity: `cluster.local/ns/<ns>/sa/<sa>` — used in all AuthorizationPolicy rules.

**Service type:** always ClusterIP. No NodePort. No LoadBalancer.
IngressGateway uses `hostPort: 443` + `externalIPs: [192.168.1.49]` on agx-orin-prod-1.

**Secrets:** always SealedSecrets (`kubeseal --cert scripts/sealed-secrets.pem`). Never commit raw `Secret` objects. Exception: Frigate RTSP creds in `/data/frigate/.env` (chmod 600) on agx-orin-prod-1 host.

**New app:** `scripts/new-app.sh <name> [agent|api|react|rust] [namespace]` → copies the chosen template, creates GitHub repo, pushes. `provision.yaml` auto-runs and commits: Cloudflare CNAME, Keycloak client (SealedSecret), LiteLLM virtual key (SealedSecret), ArgoCD Application to `argocd-apps/`, LiteLLM allow policy to `infrastructure/ai/istio/`. Optional: CloudNativePG DB CR (`needs.database: true`), oauth2-proxy manifest + Keycloak browser client (`needs.ui: true`). See README.md for the five-concept file model common to all template types.

---

## Cluster nodes

| Node             | Role                | RAM   | IP            |
|------------------|---------------------|-------|---------------|
| agx-orin-prod-1  | control-plane + GPU | 61 GB | 192.168.1.49  |
| orin-nano-prod-1 | worker              | 7 GB  | 192.168.1.175 |
| orin-nano-dev-1  | worker              | 7 GB  | 192.168.1.139 |

GPU workloads pin to agx-orin-prod-1 via `nodeSelector`. Never schedule LLM inference on orin-nano nodes.

---

## ArgoCD sync waves

| Wave | What syncs |
|------|------------|
| 0 | Istio base CRDs |
| 1 | istiod |
| 2 | istio-cni, ztunnel |
| 3 | ingressgateway |
| 4 | networking (Gateway, cloudflared, NetworkPolicies) |
| 5 | kube-prometheus-stack Helm, ARC controller Helm |
| 6 | auth, ai, database, backup, observability, security, ci-cd, mcp-servers, nvr, app namespaces |
| 7 | security (Trivy Operator — after Prometheus CRDs from wave 5) |

---

## Namespace inventory

---

### foundation — `kube-system` / `cert-manager` / `local-path-storage`

ArgoCD: `argocd-apps/foundation.yaml` → `infrastructure/foundation/` wave:0
Objects: Cilium (CNI, eBPF NetworkPolicy enforcement), Sealed Secrets controller (decrypts SealedSecrets cluster-wide), NVIDIA device plugin + RuntimeClass `nvidia` (pinned to agx-orin-prod-1), local-path provisioner (default StorageClass), cert-manager + ClusterIssuer (Cloudflare DNS-01) + Certificate `wildcard-tls` → Secret `wildcard-tls` in `istio-system`.
Ingress: none. Auth: none.

---

### `istio-system`

ArgoCD: `argocd-apps/istio-*.yaml` (5 Applications, waves 0–4) → Helm charts.
Objects: GatewayClass `istio`, Gateway `main` (https:443 TLS-terminate, http:80 plaintext, `allowedRoutes.from: All`), `RequestAuthentication` `jwt-keycloak` (targets Gateway `main`, validates Keycloak JWTs, `forwardOriginalToken: true`), IngressGateway Deployment (ClusterIP + `externalIPs:[192.168.1.49]`, `hostPort:443`, pinned agx-orin-prod-1).
Ingress: none (this IS the ingress layer). Auth: n/a.

---

### `argocd`

ArgoCD: `argocd-apps/gitops.yaml` → `infrastructure/gitops/argocd/` wave:6.
ArgoCD server, repo-server, application-set controller, dex, redis, notifications controller.
Ingress: `argocd.project-solomon.ai` → HTTPRoute → Service `argocd-server:80`.
Auth: ArgoCD's own OIDC integration with Keycloak (`argocd-cm` configures OIDC). No deny-all on argocd namespace.

---

### Sealed Secrets storage — `infrastructure/sealed-secrets/`

Not a namespace. Cross-cutting directory of committed SealedSecret manifests organised by target namespace:
`ai/`, `auth/`, `backup/`, `cert-manager/`, `ci-cd/`, `networking/`, `observability/`.
ArgoCD apps for each namespace pick these up via `directory.recurse: true`.
Never contains raw `Secret` objects — always `SealedSecret` kind.

---

### `networking`

ArgoCD: `argocd-apps/networking.yaml` → `infrastructure/networking/` wave:4.
Objects: `cloudflared` Deployment (2 replicas, `tunnel-token` SealedSecret), Cilium NetworkPolicies (allow-api-server, allow-observability-scraping, internet-egress restrictions).
Key NetworkPolicy rules: pods blocked from kube-apiserver (exceptions: argocd, arc-runners, mcp-servers); cross-namespace blocked by default; internet egress blocked (exceptions: ai, arc-runners, argocd, cert-manager).
Ingress: none. Auth: none.

---

### `auth`

ArgoCD: `argocd-apps/auth.yaml` → `infrastructure/auth/` wave:6.
deny-by-default: **YES** — allow rules in `infrastructure/auth/istio/allow-keycloak.yaml`.

**keycloak**
Objects: SA `keycloak`, Deployment `:8080`, Service `:8080`, PVC, postgres backend (`keycloak-postgres` Deployment in same namespace), `keycloak-admin` SealedSecret, `keycloak-postgres` SealedSecret.
Ingress: `keycloak.project-solomon.ai` → HTTPRoute → Service `keycloak:8080`.
Auth: `allow-keycloak-ingress` (IngressGateway SPIFFE → keycloak).

**oauth2-proxy** (shared)
Objects: SA `oauth2-proxy`, Deployment `:4180`, Service `:4180`, `oauth2-proxy-secrets` SealedSecret.
Args: `--upstream=static://202` (validates auth only; does NOT proxy), `--redirect-url=https://oauth2.project-solomon.ai/oauth2/callback`, `--cookie-domain=.project-solomon.ai`.
Ingress: `oauth2.project-solomon.ai` → HTTPRoute → Service `oauth2-proxy:4180`.
Auth: `allow-oauth2-proxy-ingress` (IngressGateway → oauth2-proxy), `allow-keycloak-internal` (oauth2-proxy SA → keycloak).
Note: per-app oauth2-proxy instances (for `needs.ui: true` apps) are written by `provision.yaml` into each app's `k8s/` with `--upstream=http://<app>:80` and a dedicated Keycloak browser client `<app>-ui`.

---

### `ai`

ArgoCD: `argocd-apps/ai.yaml` → `infrastructure/ai/` wave:6.
deny-by-default: **YES** — allow rules in `infrastructure/ai/istio/allow-ai.yaml` + per-agent `allow-<agent>.yaml` files committed by `provision.yaml`.

**litellm**
Objects: SA `litellm`, Deployment `:4000`, Service `:4000`, `litellm-secrets` SealedSecret (LITELLM_MASTER_KEY, TOGETHER_API_KEY), `litellm-db` SealedSecret (DATABASE_URL → shared-rw.database:5432/litellm), CloudNativePG Database CR at `infrastructure/database/databases/litellm.yaml`.
Ingress: `litellm.project-solomon.ai` → HTTPRoute → Service `litellm:4000`.
Auth: `allow-litellm-ingress` (IngressGateway → litellm). Per-agent access via `allow-<agent>-to-litellm` policies (SPIFFE `cluster.local/ns/<ns>/sa/<agent>`).
Model aliases: `smart` → vllm/Nemotron3-Nano-30B-A3B, `fast` → llama-server/Muse-Glimmer-30B, `glm` → Together AI GLM-5, `kimi` → Together AI Kimi K3, `external` → Together AI fallback.

**llama-server** (Muse Glimmer 30B, llama.cpp)
Objects: SA `llama-server`, Deployment (GPU, `runtimeClassName: nvidia`, `nodeSelector: agx-orin-prod-1`), Service `:8080`, `huggingface-token` SealedSecret. Model pulled from HuggingFace on first start.
Ingress: none (internal only — litellm routes to it).
Auth: `allow-llama-server-internal` (litellm SA only → llama-server).

**vllm** (Nemotron3 Nano 30B-A3B)
Objects: SA `vllm`, Deployment (GPU, `runtimeClassName: nvidia`, `nodeSelector: agx-orin-prod-1`), Service `:8000`, `huggingface-token` SealedSecret.
Ingress: none (internal only — litellm routes to it).
Auth: `allow-vllm-internal` (litellm SA only → vllm).

---

### `database`

ArgoCD: `argocd-apps/database.yaml` + `argocd-apps/cloudnativepg.yaml` → `infrastructure/database/` wave:6.
Objects: CloudNativePG operator (Helm), Cluster `shared` (PostgreSQL 16, pgvector included), Database CRs in `infrastructure/database/databases/<app>.yaml` (one per app that needs a DB).
Endpoints: `shared-rw.database.svc.cluster.local:5432` (read-write), `shared-r.database.svc.cluster.local:5432` (read-only).
Pattern: CNPG creates Secret `<app>-app` in `database` namespace. Manually extract, seal into app's namespace as `<app>-db` SealedSecret. `provision.yaml` handles this automatically for new apps.
pgvector: available on every database — enable with `CREATE EXTENSION vector;`. Use for agent semantic memory, embeddings, and computation history search.
Ingress: none. Auth: Cilium NetworkPolicy (no Istio deny-all on database ns).

---

### `backup`

ArgoCD: `argocd-apps/backup.yaml` → `infrastructure/backup/` wave:6.

**minio**
Objects: Deployment, Service `:9000` (S3 API) + `:9001` (console), 800Gi PVC on agx-orin-prod-1, `minio-root` SealedSecret.
Ingress: none (internal only — Velero S3 target).

**velero**
Objects: Helm app (`argocd-apps/velero.yaml`), BackupSchedule (daily), `velero-minio` SealedSecret (S3 credentials).
Ingress: none. Restore requires explicit Steve approval (destructive — overwrites live cluster state).

---

### `observability`

ArgoCD: `argocd-apps/prometheus.yaml` (Helm, wave:5) + `argocd-apps/observability.yaml` → `infrastructure/observability/` wave:6.
deny-by-default: **NO**. No oauth2-proxy on any observability app — JWT at gateway is sufficient for this threat model.

**grafana** — managed by kube-prometheus-stack Helm. Service `:80`. HTTPRoute → `grafana.project-solomon.ai`.
**prometheus** — kube-prometheus-stack. Service `:9090`. No ingress (scrapes cluster internally).
**alertmanager** — kube-prometheus-stack. No external ingress.
**loki** — Deployment `:3100`, 20Gi PVC, 30d retention. No ingress. Promtail ships logs to `loki.observability:3100`.
**promtail** — DaemonSet (all 3 nodes), ships to Loki.
**kiali** — Deployment `:20001`, ClusterRole (read-only across all namespaces for topology). HTTPRoute → `kiali.project-solomon.ai`. Config: `auth.strategy: anonymous` (Kiali's own auth disabled; relies on JWT at gateway).
**jaeger** — Deployment `:16686`, all-in-one in-memory. HTTPRoute → `jaeger.project-solomon.ai`.

---

### `security`

ArgoCD: `argocd-apps/security.yaml` + `argocd-apps/trivy-operator.yaml` → `infrastructure/security/` wave:7.

**trivy-operator**
Objects: Helm app, ServiceMonitor, PrometheusRule (CVE metrics → Prometheus).
Behaviour: continuously scans all running pods → writes `VulnerabilityReport` CRDs. CI also runs Trivy (image scan + IaC scan) on every push via `build.yaml`.
Ingress: none. Auth: Cilium NetworkPolicy only.

---

### `arc-systems` / `arc-runners`

ArgoCD: `argocd-apps/arc-controller.yaml` (wave:5) + `argocd-apps/arc-runners.yaml` (wave:6) + `argocd-apps/ci-cd.yaml` → `infrastructure/ci-cd/`.
Objects: ARC controller (Helm, arc-systems), Runner scale set (Helm, arc-runners, label:`arc-solomon`, ephemeral ARM64 pods, DinD sidecar, 0→5 scale), 100Gi Docker layer cache PVC on agx-orin-prod-1, `arc-github-app` SealedSecret.
Ingress: none (runners pull jobs from GitHub). Auth: GitHub App `solomon-arc` credentials in SealedSecret.

---

### `mcp-external`

ArgoCD: none yet (placeholder namespace).
Network-isolated namespace for third-party MCP servers that need internet access but must be
isolated from the internal mesh. No workloads deployed yet. Cilium NetworkPolicy will allow
internet egress from this namespace only.
Ingress: none. Auth: none yet.

---

### `agents`

ArgoCD: none yet (placeholder namespace).
Catch-all for cross-cutting agents that span multiple tool namespaces and have no natural home.
Prefer co-locating agents in their primary tool's namespace (see CLAUDE.md agent co-location rule).
Only use this namespace when an agent genuinely belongs nowhere else.
Ingress: per-agent HTTPRoute when deployed. Auth: per-agent AuthorizationPolicy.

---

### `mcp-servers`

ArgoCD: `argocd-apps/mcp-servers.yaml` → `infrastructure/mcp-servers/` wave:6.
deny-by-default: **YES**. Access pattern: `kubectl exec` only (bypasses ztunnel — exec traffic routes kube-apiserver → kubelet → container, not through the pod network). No HTTP ingress.

**solomon-kubernetes**
Objects: SA `solomon-kubernetes`, ClusterRole (get/list/watch pods/nodes/services/namespaces/events/httproutes + patch deployments), ClusterRoleBinding, ConfigMap `solomon-kubernetes-server` (server.py), Deployment (`sleep infinity`, mounts server.py), Service `:80`.
Tools: `list_pods`, `list_deployments`, `list_nodes`, `get_pod_logs`, `get_events`, `list_services`, `list_namespaces`, `get_deployment`, `restart_deployment`, `list_ingress`.

**solomon-prometheus**
Objects: SA `solomon-prometheus`, Deployment (`sleep infinity`), Service `:80`.
Tools: `prometheus_query`, `prometheus_query_range`, `prometheus_get_alerts`, `prometheus_get_targets`.
Queries: `http://prometheus-operated.observability.svc.cluster.local:9090`.

**solomon-filesystem**
Objects: SA `solomon-filesystem`, Deployment (`sleep infinity`), `filesystem-ssh-key` SealedSecret (RUNTIME: generate + distribute pubkey to all 3 nodes first).
Tools: `read_file`, `write_file`, `patch_file`, `list_dir`, `run_shell`, `node_exec` (SSH to agx-orin-prod-1, orin-nano-prod-1, orin-nano-dev-1).

MCP bridge: `scripts/mcp-proxy.py` + `.mcp.json` — Solomon invokes via `kubectl exec` into the appropriate pod.

---

### `nvr`

ArgoCD: `argocd-apps/nvr.yaml` → `infrastructure/nvr/` wave:6.
deny-by-default: **NO**. Frigate itself runs as Docker on agx-orin-prod-1 host (`--network=host`, `--privileged`, port 5000). NOT in Kubernetes.

**ServiceEntry** `frigate` — registers `frigate.external.local → 192.168.1.49:5000` in Istio mesh (MESH_EXTERNAL, STATIC). Allows mesh-enrolled pods to call Frigate with traffic classification.
**oauth2-proxy-frigate** — SA, Deployment `:4180`, Service `:4180`, `oauth2-proxy-frigate-secrets` SealedSecret (RUNTIME).
Args: `--upstream=http://frigate.external.local:5000` (full reverse proxy, not static://202), `--client-id=frigate-ui`, `--cookie-name=_oauth2_proxy_frigate`.
Ingress: `frigate.project-solomon.ai` → HTTPRoute → Service `oauth2-proxy-frigate:4180`.
Auth: Keycloak browser client `frigate-ui` (standardFlowEnabled). SealedSecret must be created after Keycloak is up (RUNTIME).

---

## Cross-namespace flows

**Browser → any UI app**
```
Browser → DNS → IngressGateway
  RequestAuthentication: no token yet → passes through
  HTTPRoute → oauth2-proxy (app ns, port 4180)
  oauth2-proxy: no cookie → 302 redirect → keycloak.project-solomon.ai/realms/solomon
  User authenticates → Keycloak issues JWT → redirect back to /oauth2/callback
  oauth2-proxy sets session cookie, forwards request with Authorization: Bearer <jwt>
  IngressGateway RequestAuthentication: validates JWT
  oauth2-proxy proxies → app Service :80
```

**API caller → any app**
```
Client sends Authorization: Bearer <jwt>
IngressGateway RequestAuthentication validates token
HTTPRoute → app Service directly (no oauth2-proxy)
```

**Agent → LiteLLM**
```
Agent pod (ns: X, sa: X) → ai ns (deny-all active)
Requires: allow-X-to-litellm AuthorizationPolicy in ai ns
  selector: app:litellm, source principal: cluster.local/ns/X/sa/X
Agent authenticates to LiteLLM with LITELLM_API_KEY (virtual key, sealed per agent)
provision.yaml writes this allow policy automatically for needs.llm:true apps
```

**Solomon → MCP tools**
```
scripts/mcp-proxy.py → kubectl exec <pod> -n mcp-servers -- python3 /app/server.py
Exec path: kube-apiserver → kubelet → container (bypasses ztunnel, bypasses deny-all)
MCP server runs stdio transport, exits when session ends
```

**ArgoCD → app repos**
```
provision.yaml (GitHub Actions, arc-solomon runner) writes to platform repo:
  argocd-apps/<app>.yaml  → ArgoCD root picks up → starts syncing app k8s/
  infrastructure/ai/istio/allow-<app>.yaml → ArgoCD ai app picks up → allows agent→litellm
ArgoCD uses PLATFORM_REPO_TOKEN (GitHub PAT, stored as GH Actions secret)
```

---

## Adding a new app — what gets created and where

| Step | Who does it | Where it lands |
|------|-------------|----------------|
| `scripts/new-app.sh <name>` | Solomon / Steve | Creates GitHub repo `stephenj-code/<name>` |
| `provision.yaml` auto-runs | GitHub Actions (arc-solomon) | Commits to both app repo and platform repo |
| Cloudflare CNAME | provision.yaml | Cloudflare DNS |
| Keycloak service account client | provision.yaml | Keycloak realm solomon |
| `keycloak-client` SealedSecret | provision.yaml | `<app-repo>/k8s/sealed-secrets/` |
| LiteLLM virtual key | provision.yaml (if `needs.llm:true`) | LiteLLM proxy |
| `litellm-api-key` SealedSecret | provision.yaml | `<app-repo>/k8s/sealed-secrets/` |
| `allow-<app>-to-litellm` policy | provision.yaml | `infrastructure/ai/istio/` (platform repo) |
| ArgoCD Application CR | provision.yaml | `argocd-apps/<app>.yaml` (platform repo) |
| CloudNativePG Database CR | provision.yaml (if `needs.database:true`) | `infrastructure/database/databases/<app>.yaml` |
| Keycloak browser client + oauth2-proxy | provision.yaml (if `needs.ui:true`) | Keycloak + `<app-repo>/k8s/oauth2-proxy.yaml` |
| `oauth2-proxy-secrets` SealedSecret | provision.yaml (if `needs.ui:true`) | `<app-repo>/k8s/sealed-secrets/` |

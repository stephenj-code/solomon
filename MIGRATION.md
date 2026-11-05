# Migration Checklist — project-solomon

Track progress of the fresh cluster build. Check off items as completed.
Solomon reads this file on session start to surface the current phase and open tasks.

**Current active phase: Phase 11 — Agents**

---

## Phase 1 — Foundation manifests ✓

- [x] Write Cilium manifests (`infrastructure/foundation/cilium/`) — `values.yaml` for Helm; bootstrap.sh installs via `helm install`
- [x] Write Sealed Secrets manifests (`infrastructure/foundation/sealed-secrets/controller.yaml`) — upstream v0.27.0 plain YAML
- [x] Write NVIDIA manifests (`infrastructure/foundation/nvidia/`) — `runtimeclass.yaml` + `device-plugin.yaml` (pinned to agx-orin-prod-1)
- [x] Write local-path provisioner manifests (`infrastructure/foundation/storage/`) — upstream v0.0.26 + default StorageClass
- [x] Write cert-manager manifests (`infrastructure/foundation/cert-manager/`) — upstream v1.15.0 + ClusterIssuer (Cloudflare DNS-01) + wildcard Certificate
- [x] Update `scripts/bootstrap.sh` — installs Helm, Cilium, Sealed Secrets, then ArgoCD; full annotated sequence

---

## Phase 2 — Networking ✓

- [x] Write Istio ArgoCD Helm apps with sync waves 0-4 (`argocd-apps/istio-*.yaml`) — base, istiod, cni, ztunnel, ingressgateway
- [x] Write GatewayClass + Gateway (`infrastructure/networking/istio/`) — wildcard listener :443 HTTPS + :80 HTTP for cloudflared
- [x] IngressGateway — ClusterIP + externalIPs: [192.168.1.49], pinned to agx-orin-prod-1, tolerates control-plane taint
- [x] Write cloudflared Deployment (`infrastructure/networking/cloudflared/`) — 2 replicas, token from SealedSecret
- [x] Write dnsmasq config (`scripts/dnsmasq-project-solomon.conf`) — split DNS, *.project-solomon.ai → 192.168.1.49
- [x] Write Cilium NetworkPolicy manifests — API server access, observability scraping, internet egress restrictions
- [ ] **RUNTIME**: Install dnsmasq on agx-orin-prod-1 and copy config (run during migration execution, Phase 13)
- [ ] **RUNTIME**: Seal cloudflare-tunnel-token → `infrastructure/networking/cloudflared/tunnel-token-sealed.yaml`

---

## Phase 3 — Auth

- [x] Write Keycloak manifests (`infrastructure/auth/keycloak/`) — Deployment, Service, HTTPRoute, PVC
- [x] Write oauth2-proxy manifests (`infrastructure/auth/oauth2-proxy/`)
- [x] Write Istio JWT AuthPolicy (cluster-wide, validates Keycloak JWKS)
- [x] Write deny-by-default AuthorizationPolicy for `ai`, `auth`, `mcp-servers` namespaces
- [ ] Import Keycloak realm export (run after Keycloak is up)
- [ ] **RUNTIME**: Seal keycloak-admin → `infrastructure/auth/keycloak/sealed-secrets/keycloak-admin-sealed.yaml`
- [ ] **RUNTIME**: Seal keycloak-postgres → `infrastructure/auth/keycloak/sealed-secrets/keycloak-postgres-sealed.yaml`
- [ ] **RUNTIME**: Seal oauth2-proxy-secrets → `infrastructure/auth/oauth2-proxy/sealed-secrets/oauth2-proxy-secrets-sealed.yaml`

---

## Phase 4 — Data

- [x] Write CloudNativePG operator manifests (`argocd-apps/cloudnativepg.yaml` — Helm, wave 6)
- [x] Write shared postgres cluster manifest (`infrastructure/database/cluster.yaml`)
- [x] Write MinIO manifests (`infrastructure/backup/minio/`) — StatefulSet, 800Gi PVC, setup Job
- [x] Write Velero manifests (`argocd-apps/velero.yaml` — Helm, wave 6; schedule in `infrastructure/backup/velero/`)
- [ ] **RUNTIME**: Seal minio-root → `infrastructure/backup/minio/sealed-secrets/minio-root-sealed.yaml`
- [ ] **RUNTIME**: Seal velero-minio → `infrastructure/backup/velero/sealed-secrets/velero-minio-sealed.yaml`

---

## Phase 5 — AI stack

- [x] Write llama-server Deployment (`infrastructure/ai/llama-server/`) — Muse Glimmer 30B, pinned to agx-orin-prod-1
- [x] Write vllm Deployment (`infrastructure/ai/vllm/`) — Nemotron3 Nano 30B-A3B, pinned to agx-orin-prod-1
- [x] Write LiteLLM Deployment + config (`infrastructure/ai/litellm/`) — model aliases, virtual key config, agent registry
- [x] Configure LiteLLM model aliases: `smart`, `fast`, `glm`, `kimi`, `external`
- [x] Register Together AI (GLM-5.2 / GLM-5.3, Kimi K3) in LiteLLM config
- ~~Register Fireworks AI (Muse Glimmer cloud fallback) in LiteLLM config~~ — removed, not needed
- [x] Write model pull Job for Muse Glimmer (first-start artifact download)
- [x] Write Istio allow rules for ai namespace (`infrastructure/ai/istio/allow-ai.yaml`)
- [x] Write CloudNativePG Database CR for LiteLLM (`infrastructure/database/databases/litellm.yaml`)
- [ ] **RUNTIME**: Confirm Muse Glimmer HF repo ID + GGUF filename (update model-pull/job.yaml placeholders)
- [ ] **RUNTIME**: Seal huggingface-token → `infrastructure/ai/sealed-secrets/huggingface-token-sealed.yaml`
- [ ] **RUNTIME**: Seal litellm-secrets (LITELLM_MASTER_KEY, TOGETHER_API_KEY) → `infrastructure/ai/sealed-secrets/litellm-secrets-sealed.yaml`
- [ ] **RUNTIME**: Seal litellm-db (DATABASE_URL, after CNPG creates litellm database) → `infrastructure/ai/sealed-secrets/litellm-db-sealed.yaml`
- [ ] **RUNTIME**: Verify Together AI model slugs (glm, kimi) in `infrastructure/ai/litellm/config.yaml`

---

## Phase 6 — Observability

- [x] Write Prometheus manifests — kube-prometheus-stack Helm app (`argocd-apps/prometheus.yaml`); includes Prometheus, Grafana, AlertManager, node-exporter, kube-state-metrics
- [x] Write Grafana manifests — managed by kube-prometheus-stack; HTTPRoute at `infrastructure/observability/grafana/httproute.yaml`
- [x] Write Loki manifests (`infrastructure/observability/loki/deployment.yaml`) — single-binary, 30d retention, 20Gi PVC
- [x] Write Promtail DaemonSet (`infrastructure/observability/promtail/daemonset.yaml`) — all nodes, ships to Loki
- [x] Write Kiali manifests (`infrastructure/observability/kiali/deployment.yaml`) — standalone, HTTPRoute
- [x] Write Jaeger manifests (`infrastructure/observability/jaeger/deployment.yaml`) — all-in-one, in-memory, HTTPRoute
- [ ] **RUNTIME**: Seal grafana-admin → `infrastructure/observability/grafana/grafana-admin-sealed.yaml`

---

## Phase 7 — Security

- [x] Write Trivy Operator manifests — Helm app `argocd-apps/trivy-operator.yaml` (wave 6); ServiceMonitor + PrometheusRule in `infrastructure/security/trivy-operator/`
- [x] Write Pod Security Standards admission config — PSA labels on all namespaces in `infrastructure/namespaces/namespaces.yaml`; `restricted` on `auth`, `baseline` everywhere else (`ai` kept at baseline — GPU workloads incompatible with restricted)
- [x] Configure etcd encryption at rest — `scripts/enable-etcd-encryption.sh`; run on agx-orin-prod-1 during Phase 13 after cluster is healthy; save generated AES key to KeePass
- [x] Update `argocd-apps/security.yaml` — wave 7, updated comment
- [x] Add Trivy image scan step to `templates/app-template/.github/workflows/` (Phase 11)
- [x] Add Bandit + Semgrep SAST step to `templates/app-template/.github/workflows/` (Phase 11)
- [ ] **EXTERNAL**: Set up Renovate Bot on GitHub org (`stephenj-code`) — configure via `renovate.json` in each app repo or org-level config

---

## Phase 8 — CI/CD

- [x] Write ARC controller Helm app (`argocd-apps/arc-controller.yaml`, wave 5)
- [x] Write ARC runner scale set Helm app (`argocd-apps/arc-runners.yaml`, wave 6) — ephemeral ARM64 runners, DinD sidecar, 0→5 scale, label: `arc-solomon`
- [x] Provision Docker layer cache PVC (`infrastructure/ci-cd/arc/runners/build-runner/pvc.yaml`) — 100Gi on agx-orin-prod-1
- [x] Update `argocd-apps/ci-cd.yaml` — directory app for PVC + secrets, wave 6
- [ ] **RUNTIME**: Create GitHub App `solomon-arc` on stephenj-code org (see `infrastructure/ci-cd/arc/sealed-secrets/.gitkeep` for instructions)
- [ ] **RUNTIME**: Seal arc-github-app → `infrastructure/ci-cd/arc/sealed-secrets/arc-github-app-sealed.yaml`

---

## Phase 9 — MCP servers

- [x] Write solomon-kubernetes MCP server manifests (`infrastructure/mcp-servers/kubernetes/`)
- [x] Write solomon-prometheus MCP server manifests (`infrastructure/mcp-servers/prometheus/`)
- [x] Write solomon-filesystem MCP server manifests (`infrastructure/mcp-servers/filesystem/`)
- [x] Create `.mcp.json` in solomon repo root (bridge config pointing to in-cluster servers)
- [ ] **RUNTIME**: Generate SSH keypair for solomon-filesystem node_exec; distribute pubkey to all 3 nodes; seal privkey → `infrastructure/mcp-servers/filesystem/sealed-secrets/filesystem-ssh-key-sealed.yaml`
- [ ] Test MCP bridges via `scripts/mcp-proxy.py` (run after Phase 13 migration)

---

## Phase 10 — NVR (Frigate)

- [ ] **RUNTIME**: Move Frigate RTSP credentials from Docker env vars to `/data/frigate/.env` (chmod 600)
- [x] Write Istio ServiceEntry for Frigate (`infrastructure/nvr/serviceentry.yaml`)
- [x] Write HTTPRoute for `frigate.project-solomon.ai` (`infrastructure/nvr/httproute.yaml`)
- [x] Write oauth2-proxy for Frigate UI access (`infrastructure/nvr/oauth2-proxy.yaml`)
- [x] Add `argocd-apps/nvr.yaml` ArgoCD Application
- [ ] **RUNTIME**: Create Keycloak `frigate` OIDC client; seal `oauth2-proxy-frigate-secrets` → `infrastructure/nvr/sealed-secrets/oauth2-proxy-frigate-secrets-sealed.yaml`
- [ ] Create frigate-agent repo: `scripts/new-app.sh frigate-agent`
- [ ] Implement frigate-agent LangGraph tools (events, snapshots, config, stats)
- [ ] Test Muse Glimmer vision on Frigate snapshots (end-to-end agent query)

---

## Phase 11 — Agents

- [x] Write `templates/app-template/` — canonical app scaffold in this repo (see Phase 11 for full structure)
- [x] Write `scripts/new-app.sh` — creates GitHub repo from template, substitutes app name, pushes
- [x] Implement `templates/app-template/.github/workflows/provision.yaml` (Cloudflare, Keycloak, LiteLLM, ArgoCD, database, UI oauth2-proxy)
- [x] Add Trivy image scan + Bandit/Semgrep to `templates/app-template/.github/workflows/build.yaml`
- [ ] **RUNTIME**: Create security-agent repo: `scripts/new-app.sh security-agent`
- [ ] **RUNTIME**: Implement security-agent tools in created repo (Trivy CLI, VulnerabilityReport CRDs, Bandit, CVE lookup)

---

## Phase 12 — Platform tooling

### On agx-orin-prod-1
- [ ] Install k9s (`curl -sS https://webinstall.dev/k9s | bash`)
- [ ] Install stern for multi-pod log tailing (`curl -sS https://webinstall.dev/stern | bash`)
- [ ] Set up tmux default session for Solomon

### SSH key auth (prerequisite for remote access)
- [ ] Set up SSH key auth from Windows laptop to agx-orin-prod-1
- [ ] Set up SSH key auth from Mac laptop to agx-orin-prod-1

### Cloudflare Gateway DNS — LAN-wide threat blocking (free, ~5 min)
- Protects every LAN device (nodes, laptops, phones) — blocks malware C2, phishing, ransomware download domains
- Simple option (no Zero Trust account needed): set router DNS to `1.1.1.2` / `1.0.0.2` (Cloudflare for Families — malware blocking)
- Advanced option (custom policies + query logs): Zero Trust dashboard → Gateway → DNS Locations → create location → use assigned org-specific IPs
- [ ] Set router primary DNS: `1.1.1.2`, secondary DNS: `1.0.0.2`
- [ ] Set Jetson nodes DNS to `1.1.1.2` in `/etc/resolv.conf` (covers OS/package updates, image pulls)
- [ ] Verify: query a known malware domain from any LAN device → should return REFUSED

### Cloudflare WARP (Cloudflare One Client) — laptop security + remote cluster access
- Protects laptops on any network (Gateway DNS follows the laptop off-LAN via WARP)
- Provides remote kubectl/SSH access via private network routing through Cloudflare Tunnel
- One client, two benefits — no VPN server needed, no open ports
- [ ] Zero Trust dashboard → Settings → WARP Client → configure enrollment (email or one-time PIN)
- [ ] Zero Trust dashboard → Networks → Tunnels → your tunnel → Private Networks:
      add `192.168.1.49/32` as a private network route
- [ ] Zero Trust dashboard → Settings → WARP Client → Device settings → Split Tunnels:
      mode = "Include IPs and domains", add `192.168.1.49/32`
- [ ] Install Cloudflare One Client on Windows laptop (`winget install Cloudflare.WARP`)
- [ ] Install Cloudflare One Client on Mac laptop (`brew install --cask cloudflare-warp`)
- [ ] Enroll both laptops: open WARP client → Login with Cloudflare Access → authenticate
- [ ] Install kubectl on Windows laptop (`winget install Kubernetes.kubectl`)
- [ ] Install kubectl on Mac laptop (`brew install kubectl`)
- [ ] Copy kubeconfig from agx-orin to both laptops (`~/.kube/config`, server: `https://192.168.1.49:6443`)
- [ ] Test from outside LAN: WARP on → `kubectl get nodes` → should work
- [ ] Test from outside LAN: WARP on → `ssh stephen@192.168.1.49` → should work

### VS Code Remote SSH
- [ ] Verify VS Code Remote SSH works from both laptops (uses SSH key auth above)
- [ ] (Optional) Install Lens on both laptops for GUI cluster browsing

### Access patterns reference
- **Pattern 1 (primary):** SSH into agx-orin → run `claude` there. kubectl native, MCP tools live. Best for infra changes.
- **Pattern 2a (LAN):** WARP optional — kubeconfig `192.168.1.49:6443` works directly.
- **Pattern 2b (remote):** WARP on → same kubeconfig — traffic routes through Cloudflare tunnel automatically.

---

## Phase 13 — Migration execution

> All manifests must be complete and committed before starting this phase.

- [ ] Take Velero snapshot of existing cluster (backup before reset)
- [ ] Verify `/data/frigate` data is intact and Frigate `.env` file is in place
- [ ] Reset existing cluster: `kubeadm reset` on all 3 nodes
- [ ] Wipe CNI state: `rm -rf /etc/cni /var/lib/cni` on all nodes
- [ ] Run `scripts/bootstrap.sh` on agx-orin-prod-1 (Cilium → workers join → ArgoCD → Sealed Secrets)
- [ ] Apply root ArgoCD Application: `kubectl apply -f argocd-apps/_root.yaml`
- [ ] Monitor ArgoCD sync: `kubectl -n argocd get applications -w`
- [ ] Verify all nodes Ready
- [ ] Verify all namespaces healthy
- [ ] Verify Keycloak up → import realm
- [ ] Verify LiteLLM up → test model aliases
- [ ] Verify Frigate accessible at `frigate.project-solomon.ai`
- [ ] Verify MCP bridges working (run `/solomon`, check tool responses)
- [ ] Tag milestone: `git tag v0.1 && git push origin --tags`

---

## Completed

_(items move here when done)_

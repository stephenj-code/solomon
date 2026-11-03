# Migration Checklist — project-solomon

Track progress of the fresh cluster build. Check off items as completed.
Solomon reads this file on session start to surface the current phase and open tasks.

**Current active phase: Phase 6 — Observability**

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

- [ ] Write Trivy Operator manifests (`infrastructure/security/trivy-operator/`)
- [ ] Add Trivy image scan step to `solomon-app-template` CI workflow
- [ ] Add Bandit + Semgrep SAST step to `solomon-app-template` CI workflow
- [ ] Write Pod Security Standards admission config (baseline cluster-wide, restricted on `ai` + `auth`)
- [ ] Configure etcd encryption at rest (`EncryptionConfiguration` in kubeadm)
- [ ] Set up Renovate Bot on GitHub org (`stephenj-code`)
- [ ] Add `argocd-apps/security.yaml` ArgoCD Application

---

## Phase 8 — CI/CD

- [ ] Render ARC controller manifests from Helm (`infrastructure/ci-cd/arc/controller/`)
- [ ] Write ARC runner set manifests (`infrastructure/ci-cd/arc/runners/build-runner/`)
- [ ] Create GitHub App for ARC (replace PAT)
- [ ] Seal GitHub App private key + app ID + installation ID
- [ ] Provision Docker layer cache PVC (100 GB on agx-orin-prod-1)
- [ ] Add `argocd-apps/ci-cd.yaml` ArgoCD Application

---

## Phase 9 — MCP servers

- [ ] Write solomon-kubernetes MCP server manifests (`infrastructure/mcp-servers/kubernetes/`)
- [ ] Write solomon-prometheus MCP server manifests (`infrastructure/mcp-servers/prometheus/`)
- [ ] Write solomon-filesystem MCP server manifests (`infrastructure/mcp-servers/filesystem/`)
- [ ] Create `.mcp.json` in solomon repo root (bridge config pointing to in-cluster servers)
- [ ] Test MCP bridges via `scripts/mcp-proxy.py`

---

## Phase 10 — NVR (Frigate)

- [ ] Move Frigate RTSP credentials from Docker env vars to `/data/frigate/.env` (chmod 600)
- [ ] Write Istio ServiceEntry for Frigate (`infrastructure/nvr/serviceentry.yaml`)
- [ ] Write HTTPRoute for `frigate.project-solomon.ai` (`infrastructure/nvr/httproute.yaml`)
- [ ] Write Keycloak client + oauth2-proxy for Frigate UI access
- [ ] Add `argocd-apps/nvr.yaml` ArgoCD Application
- [ ] Create frigate-agent repo from `solomon-app-template`
- [ ] Implement frigate-agent LangGraph tools (events, snapshots, config, stats)
- [ ] Test Muse Glimmer vision on Frigate snapshots (end-to-end agent query)

---

## Phase 11 — Agents

- [ ] Create `solomon-app-template` GitHub template repo (`stephenj-code/solomon-app-template`)
- [ ] Implement `provision.yaml` workflow (Cloudflare, Keycloak, LiteLLM, ArgoCD, LiteLLM agent registry)
- [ ] Create `security-agent` repo from template
- [ ] Implement security-agent tools (Trivy CLI, VulnerabilityReport CRDs, Bandit, CVE lookup)

---

## Phase 12 — Platform tooling

- [ ] Install k9s on agx-orin-prod-1 (`curl -sS https://webinstall.dev/k9s | bash`)
- [ ] Set up SSH key auth from Windows laptop to agx-orin-prod-1
- [ ] Set up SSH key auth from Mac laptop to agx-orin-prod-1
- [ ] Verify VS Code Remote SSH from both laptops
- [ ] Set up tmux default session for Solomon on agx-orin-prod-1

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

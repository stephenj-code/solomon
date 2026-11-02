# Migration Checklist — project-solomon

Track progress of the fresh cluster build. Check off items as completed.
Solomon reads this file on session start to surface the current phase and open tasks.

**Current active phase: Phase 1 — Foundation manifests**

---

## Phase 1 — Foundation manifests

Write all `infrastructure/foundation/` manifests. These must be applied manually before ArgoCD takes over (chicken-and-egg).

- [ ] Write Cilium manifests (`infrastructure/foundation/cilium/`) — CNI, `kubeProxyReplacement=false`
- [ ] Write Sealed Secrets manifests (`infrastructure/foundation/sealed-secrets/`) — controller install
- [ ] Write NVIDIA GPU operator manifests (`infrastructure/foundation/nvidia/`) — Jetson runtime class
- [ ] Write local-path provisioner manifests (`infrastructure/foundation/storage/`) — dynamic PVCs on 1TB SSD
- [ ] Write cert-manager manifests (`infrastructure/foundation/cert-manager/`) — wildcard TLS via Cloudflare DNS-01
- [ ] Verify `scripts/bootstrap.sh` sequence matches new repo structure

---

## Phase 2 — Networking

- [ ] Write Istio ambient mode manifests (`infrastructure/networking/istio/`) — ztunnel, IngressGateway, GatewayClass
- [ ] Write Gateway + wildcard Gateway manifest (`infrastructure/networking/istio/gateway.yaml`)
- [ ] Write cloudflared deployment (`infrastructure/networking/cloudflared/`)
- [ ] Configure dnsmasq on agx-orin-prod-1 (split DNS — `*.project-solomon.ai` → 192.168.1.49)
- [ ] Write Cilium NetworkPolicy manifests — API server access, cross-namespace, egress rules

---

## Phase 3 — Auth

- [ ] Write Keycloak manifests (`infrastructure/auth/keycloak/`) — Deployment, Service, HTTPRoute, PVC
- [ ] Write oauth2-proxy manifests (`infrastructure/auth/oauth2-proxy/`)
- [ ] Write Istio JWT AuthPolicy (cluster-wide, validates Keycloak JWKS)
- [ ] Write deny-by-default AuthorizationPolicy for `ai`, `auth`, `mcp-servers` namespaces
- [ ] Import Keycloak realm export (run after Keycloak is up)
- [ ] Seal Keycloak admin password → `infrastructure/auth/keycloak/sealed-secrets/`

---

## Phase 4 — Data

- [ ] Write CloudNativePG operator manifests (`infrastructure/database/cloudnativepg/`)
- [ ] Write shared postgres cluster manifest (`infrastructure/database/cluster.yaml`)
- [ ] Write MinIO manifests (`infrastructure/backup/minio/`) — object storage on 1TB SSD
- [ ] Write Velero manifests (`infrastructure/backup/velero/`) — scheduled backups to MinIO
- [ ] Seal MinIO root credentials
- [ ] Seal Velero MinIO credentials

---

## Phase 5 — AI stack

- [ ] Write llama-server Deployment (`infrastructure/ai/llama-server/`) — Muse Glimmer 30B, pinned to agx-orin-prod-1
- [ ] Write vllm Deployment (`infrastructure/ai/vllm/`) — Nemotron3 Nano 30B-A3B, pinned to agx-orin-prod-1
- [ ] Write LiteLLM Deployment + config (`infrastructure/ai/litellm/`) — model aliases, virtual key config, agent registry
- [ ] Seal HuggingFace token → `infrastructure/ai/sealed-secrets/`
- [ ] Seal LiteLLM master key + Anthropic API key
- [ ] Configure LiteLLM model aliases: `smart`, `fast`, `glm`, `kimi`, `external`
- [ ] Register Together AI (GLM-5.2, GLM-5.3, Kimi K3) in LiteLLM config
- [ ] Register Fireworks AI (Muse Glimmer cloud fallback) in LiteLLM config
- [ ] Write model pull Job for Muse Glimmer (first-start artifact download)

---

## Phase 6 — Observability

- [ ] Write Prometheus manifests (`infrastructure/observability/prometheus/`)
- [ ] Write Grafana manifests (`infrastructure/observability/grafana/`)
- [ ] Write Loki manifests (`infrastructure/observability/loki/`)
- [ ] Write Promtail DaemonSet (`infrastructure/observability/promtail/`)
- [ ] Write Kiali manifests (`infrastructure/observability/kiali/`)
- [ ] Write Jaeger manifests (`infrastructure/observability/jaeger/`)

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

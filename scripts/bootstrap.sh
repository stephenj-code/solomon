#!/usr/bin/env bash
# bootstrap.sh — Day-0 cluster bootstrap for project-solomon
#
# Run this on agx-orin-prod-1 after a fresh kubeadm init.
# Steps marked [MANUAL] require human input and cannot be automated.
#
# Usage:
#   chmod +x scripts/bootstrap.sh
#   ./scripts/bootstrap.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_URL="https://github.com/stephenj-code/solomon"
ARGOCD_VERSION="v2.13.0"
SEALED_SECRETS_VERSION="v0.27.0"
CILIUM_VERSION="1.16.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()   { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn()   { echo -e "${YELLOW}[warn]${NC} $*"; }
manual() { echo -e "${RED}[MANUAL]${NC} $*"; }

# ---------------------------------------------------------------------------
# STEP 0: Pre-flight
# ---------------------------------------------------------------------------
info "Pre-flight checks..."

command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found"; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "git not found"; exit 1; }
command -v kubeseal>/dev/null 2>&1 || warn "kubeseal not found — install before sealing secrets"

kubectl cluster-info >/dev/null 2>&1 || { echo "No cluster reachable. Run kubeadm init first."; exit 1; }
info "Cluster reachable."

# ---------------------------------------------------------------------------
# STEP 1: Helm (required for Cilium)
# ---------------------------------------------------------------------------
if ! command -v helm &>/dev/null; then
  info "Installing Helm..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
else
  info "Helm already installed: $(helm version --short)"
fi

# ---------------------------------------------------------------------------
# STEP 2: Cilium CNI
# ---------------------------------------------------------------------------
# Must be applied before workers join — nodes will not reach Ready without CNI.
# kubeadm init must have been run with: --pod-network-cidr=10.244.0.0/16
# kubeProxyReplacement=false (see values.yaml) keeps kube-proxy for Istio
# ambient compatibility.
info "Installing Cilium ${CILIUM_VERSION}..."
helm repo add cilium https://helm.cilium.io/ --force-update
helm repo update

helm upgrade --install cilium cilium/cilium \
  --version "${CILIUM_VERSION}" \
  --namespace kube-system \
  --values "${REPO_ROOT}/infrastructure/foundation/cilium/values.yaml" \
  --wait --timeout 120s

info "Cilium installed. Waiting for DaemonSet to be ready..."
kubectl -n kube-system rollout status daemonset/cilium --timeout=120s

# ---------------------------------------------------------------------------
# STEP 3: Join worker nodes
# ---------------------------------------------------------------------------
manual "Join worker nodes now. On this node run:"
manual "  kubeadm token create --print-join-command"
manual "Then run the printed command on orin-nano-prod-1 (192.168.1.175)"
manual "  and orin-nano-dev-1 (192.168.1.139)."
manual "Press Enter when both workers show Ready..."
read -r

kubectl get nodes
manual "Verify all 3 nodes are Ready before continuing."
manual "Press Enter to continue..."
read -r

# ---------------------------------------------------------------------------
# STEP 4: Sealed Secrets controller
# ---------------------------------------------------------------------------
# Must be installed before ArgoCD tries to sync SealedSecret resources.
# Applied directly from the committed plain YAML manifest.
info "Installing Sealed Secrets controller ${SEALED_SECRETS_VERSION}..."
kubectl apply -f "${REPO_ROOT}/infrastructure/foundation/sealed-secrets/controller.yaml" \
  --server-side

info "Waiting for Sealed Secrets controller..."
kubectl -n kube-system rollout status deployment/sealed-secrets --timeout=120s

info "Fetching Sealed Secrets public key for offline sealing..."
# Wait for controller to generate its keypair
sleep 10
kubeseal --fetch-cert \
  --controller-name=sealed-secrets \
  --controller-namespace=kube-system \
  > "${REPO_ROOT}/scripts/sealed-secrets.pem"
info "Public key cached at scripts/sealed-secrets.pem (gitignored — do not commit)"

# ---------------------------------------------------------------------------
# STEP 5: Seal required secrets
# ---------------------------------------------------------------------------
manual "Seal the following secrets before applying the root ArgoCD app."
manual "Use: kubectl create secret generic <name> --from-literal=key=val"
manual "     --dry-run=client -o yaml |"
manual "     kubeseal --cert scripts/sealed-secrets.pem --format yaml"
manual "     > path/to/sealed.yaml"
manual ""
manual "Required secrets (seal and git commit each before continuing):"
manual "  cert-manager/cloudflare-api-token  — CF token for DNS-01 (Zone/DNS/Edit)"
manual "  auth/keycloak-admin                — Keycloak admin + postgres passwords"
manual "  ai/litellm                         — master key, Anthropic key"
manual "  ai/huggingface                     — HF token for model downloads"
manual "  networking/cloudflared             — Cloudflare Tunnel token"
manual "  backup/minio                       — MinIO root user + password"
manual "  backup/velero                      — Velero MinIO credentials"
manual "  ci-cd/arc                          — GitHub App private key, app ID, install ID"
manual ""
manual "Commit sealed secrets and push to main before continuing."
manual "Press Enter when all secrets are sealed and committed..."
read -r

# ---------------------------------------------------------------------------
# STEP 6: ArgoCD
# ---------------------------------------------------------------------------
info "Installing ArgoCD ${ARGOCD_VERSION}..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" \
  --server-side

info "Waiting for ArgoCD server..."
kubectl -n argocd rollout status deploy/argocd-server --timeout=180s

# ---------------------------------------------------------------------------
# STEP 7: Apply root ArgoCD Application
# ---------------------------------------------------------------------------
info "Applying root ArgoCD Application..."
kubectl apply -f "${REPO_ROOT}/argocd-apps/_root.yaml"

info "ArgoCD is now syncing all components from ${REPO_URL}."
info ""
info "Monitor progress:"
info "  kubectl -n argocd get applications -w"
info ""
info "ArgoCD UI (port-forward):"
info "  kubectl -n argocd port-forward svc/argocd-server 8080:443"
info "  Password: kubectl -n argocd get secret argocd-initial-admin-secret \\"
info "            -o jsonpath='{.data.password}' | base64 -d"
info ""
info "Once Keycloak is up:"
info "  Import realm: kubectl cp keycloak-realm-export.json \\"
info "    auth/<keycloak-pod>:/tmp/ then import via UI"
info ""
info "Once LiteLLM is up:"
info "  Verify model aliases: curl http://litellm.ai.svc/v1/models"
info ""
info "Verify Frigate .env credentials:"
info "  cat /data/frigate/.env  (should be chmod 600, FRIGATE_RTSP_USER + PASSWORD)"
info ""
info "Bootstrap complete. Check MIGRATION.md for remaining phases."

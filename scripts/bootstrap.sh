#!/usr/bin/env bash
# bootstrap.sh — Day-0 cluster bootstrap for project-solomon
#
# Run this on agx-orin-prod-1 after a fresh kubeadm init.
# Steps marked MANUAL require human input and cannot be automated.
#
# Usage:
#   chmod +x scripts/bootstrap.sh
#   ./scripts/bootstrap.sh

set -euo pipefail

REPO_URL="https://github.com/stephenj-code/solomon"
ARGOCD_VERSION="v2.13.0"
SEALED_SECRETS_VERSION="v0.27.0"
CILIUM_VERSION="v1.16.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC} $*"; }
manual()  { echo -e "${RED}[MANUAL]${NC} $*"; }

# ---------------------------------------------------------------------------
# STEP 0: Pre-flight
# ---------------------------------------------------------------------------
info "Pre-flight checks..."

command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found"; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "git not found"; exit 1; }
command -v helm    >/dev/null 2>&1 || { echo "helm not found (needed for ARC render)"; exit 1; }
command -v kubeseal>/dev/null 2>&1 || warn "kubeseal not found — install before sealing secrets"

kubectl cluster-info >/dev/null 2>&1 || { echo "No cluster reachable. Run kubeadm init first."; exit 1; }
info "Cluster reachable."

# ---------------------------------------------------------------------------
# STEP 1: Cilium CNI
# ---------------------------------------------------------------------------
# MANUAL: kubeadm init should have been run WITHOUT kube-proxy skipped
# (kubeProxyReplacement=false for Istio ambient compatibility).
# kubeadm init --pod-network-cidr=10.244.0.0/16

info "Installing Cilium ${CILIUM_VERSION}..."
# Cilium manifests live in infrastructure/foundation/cilium/
# Applied directly here (before ArgoCD) because the cluster needs CNI to schedule pods.
kubectl apply -f infrastructure/foundation/cilium/ --server-side

info "Waiting for Cilium pods to be ready..."
kubectl -n kube-system rollout status daemonset/cilium --timeout=120s

# ---------------------------------------------------------------------------
# STEP 2: Worker nodes
# ---------------------------------------------------------------------------
manual "Join worker nodes now. On agx-orin-prod-1, run:"
manual "  kubeadm token create --print-join-command"
manual "Then run the printed command on orin-nano-prod-1 and orin-nano-dev-1."
manual "Press Enter when both workers have joined..."
read -r

kubectl get nodes
info "Verify all 3 nodes are Ready before continuing."
manual "Press Enter when all nodes show Ready..."
read -r

# ---------------------------------------------------------------------------
# STEP 3: ArgoCD
# ---------------------------------------------------------------------------
info "Installing ArgoCD ${ARGOCD_VERSION}..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" \
  --server-side

info "Waiting for ArgoCD server to be ready..."
kubectl -n argocd rollout status deploy/argocd-server --timeout=180s

# ---------------------------------------------------------------------------
# STEP 4: Sealed Secrets controller
# ---------------------------------------------------------------------------
# Must be installed before ArgoCD tries to sync SealedSecret resources.
info "Installing Sealed Secrets controller ${SEALED_SECRETS_VERSION}..."
# Manifests live in infrastructure/foundation/sealed-secrets/
# Applied directly (before root app) to break the chicken-and-egg dependency.
kubectl apply -f infrastructure/foundation/sealed-secrets/ --server-side

info "Caching Sealed Secrets public key for offline sealing..."
# Wait for controller to generate its key
sleep 15
kubeseal --fetch-cert \
  --controller-name=sealed-secrets \
  --controller-namespace=kube-system \
  > scripts/sealed-secrets.pem
info "Public key cached at scripts/sealed-secrets.pem (gitignored — do not commit)"

# ---------------------------------------------------------------------------
# STEP 5: Seal required secrets
# ---------------------------------------------------------------------------
manual "Seal the following secrets before applying the root ArgoCD app."
manual "Use: kubectl create secret generic <name> --from-literal=key=val --dry-run=client -o yaml | kubeseal --cert scripts/sealed-secrets.pem --format yaml > path/to/sealed.yaml"
manual ""
manual "Required secrets:"
manual "  auth/keycloak          — admin password, postgres password"
manual "  ai/litellm             — anthropic API key, admin key"
manual "  networking/cloudflared — tunnel token"
manual "  backup/minio           — root user + password"
manual "  backup/velero          — MinIO credentials"
manual "  ci-cd/arc              — GitHub App private key, app ID, installation ID"
manual ""
manual "Commit sealed secrets to the repo before continuing."
manual "Press Enter when all secrets are sealed and committed to main..."
read -r

# ---------------------------------------------------------------------------
# STEP 6: Apply root ArgoCD Application
# ---------------------------------------------------------------------------
info "Applying root ArgoCD Application..."
kubectl apply -f argocd-apps/_root.yaml

info "ArgoCD will now sync all components from ${REPO_URL}."
info "Monitor progress:"
info "  kubectl -n argocd get applications -w"
info "  kubectl -n argocd get app root -o yaml"

# ---------------------------------------------------------------------------
# STEP 7: Post-bootstrap
# ---------------------------------------------------------------------------
info ""
info "Bootstrap complete. What to do next:"
info "  1. Watch ArgoCD sync:  kubectl -n argocd get applications -w"
info "  2. Check namespaces:   kubectl get ns"
info "  3. ArgoCD UI:          kubectl -n argocd port-forward svc/argocd-server 8080:443"
info "     Password:           kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
info "  4. Once Keycloak is up: import realm from keycloak-realm-export.json"
info "  5. Pull Muse Glimmer:  kubectl apply -f infrastructure/ai/llama-server/model-pull-job.yaml"

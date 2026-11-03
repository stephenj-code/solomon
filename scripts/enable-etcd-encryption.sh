#!/usr/bin/env bash
# enable-etcd-encryption.sh
#
# Enables etcd encryption at rest for Secrets on agx-orin-prod-1.
# Run this during Phase 13 AFTER the cluster is healthy and all workloads
# are running. Do NOT run during initial bootstrap.
#
# What this does:
#   1. Generates a random 32-byte AES key
#   2. Writes /etc/kubernetes/encryption-config.yaml on agx-orin-prod-1
#   3. Patches the kube-apiserver static pod manifest to load the config
#   4. Waits for the API server to restart
#   5. Force-rewrites all existing Secrets so they are encrypted on disk
#
# IMPORTANT: Back up the key to KeePass immediately after this script runs.
# The key is printed at the end. If you lose it and the cluster needs to be
# restored from disk, Secrets will be unreadable.
#
# Run from agx-orin-prod-1 as root (or sudo):
#   sudo bash scripts/enable-etcd-encryption.sh
#
# Verify encryption is active afterwards:
#   ETCDCTL_API=3 etcdctl \
#     --cacert /etc/kubernetes/pki/etcd/ca.crt \
#     --cert   /etc/kubernetes/pki/etcd/server.crt \
#     --key    /etc/kubernetes/pki/etcd/server.key \
#     get /registry/secrets/default/test-secret | hexdump -C | head
#   # Should show "k8s:enc:aescbc:v1:key1:" prefix — not plaintext.

set -euo pipefail

ENCRYPTION_CONFIG=/etc/kubernetes/encryption-config.yaml
APISERVER_MANIFEST=/etc/kubernetes/manifests/kube-apiserver.yaml

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root" >&2
  exit 1
fi

if [ -f "$ENCRYPTION_CONFIG" ]; then
  echo "ERROR: $ENCRYPTION_CONFIG already exists — encryption may already be enabled." >&2
  echo "       Delete it manually if you want to regenerate." >&2
  exit 1
fi

# Generate a cryptographically random 32-byte key (AES-256).
AES_KEY=$(head -c 32 /dev/urandom | base64)

cat > "$ENCRYPTION_CONFIG" <<EOF
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: ${AES_KEY}
      # identity provider last — allows reading unencrypted Secrets written
      # before encryption was enabled. Remove after force-rewrite below.
      - identity: {}
EOF

chmod 600 "$ENCRYPTION_CONFIG"
echo "Wrote $ENCRYPTION_CONFIG"

# Patch kube-apiserver static pod manifest to load the config.
# kubeadm-managed clusters store the manifest at the path above.
if grep -q "encryption-provider-config" "$APISERVER_MANIFEST"; then
  echo "WARNING: --encryption-provider-config already present in apiserver manifest."
  echo "         Review $APISERVER_MANIFEST manually."
else
  # Insert the flag after the existing --etcd-* flags block.
  sed -i '/- --etcd-servers=/a\    - --encryption-provider-config='"$ENCRYPTION_CONFIG" \
    "$APISERVER_MANIFEST"

  # Mount the config file into the apiserver container (static pod).
  # kubeadm manifests use hostPath volumes for /etc/kubernetes.
  # The /etc/kubernetes directory is already mounted — no extra volume needed.
  echo "Patched $APISERVER_MANIFEST"
fi

# kubelet detects the manifest change and restarts the apiserver pod.
echo "Waiting for kube-apiserver to restart (up to 60s)..."
sleep 10
for i in $(seq 1 10); do
  if kubectl --kubeconfig /etc/kubernetes/admin.conf get nodes &>/dev/null; then
    echo "API server is back up."
    break
  fi
  echo "  ...still waiting ($i/10)"
  sleep 5
done

# Force-rewrite all existing Secrets so they are stored encrypted.
# This reads each Secret and writes it back — the apiserver now encrypts on write.
echo "Re-encrypting all existing Secrets..."
kubectl --kubeconfig /etc/kubernetes/admin.conf \
  get secrets --all-namespaces -o json | \
  kubectl --kubeconfig /etc/kubernetes/admin.conf replace -f -

echo ""
echo "=========================================================="
echo "etcd encryption at rest is ACTIVE."
echo ""
echo "AES key (SAVE THIS TO KEEPASS NOW):"
echo "  ${AES_KEY}"
echo ""
echo "KeePass entry suggested fields:"
echo "  Title:    project-solomon etcd encryption key"
echo "  Username: key1"
echo "  Password: ${AES_KEY}"
echo "  Notes:    AES-256-CBC. Required to decrypt etcd if cluster is"
echo "            restored from raw disk without a Velero backup."
echo "=========================================================="

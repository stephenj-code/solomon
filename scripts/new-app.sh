#!/usr/bin/env bash
# new-app.sh — scaffold a new app from templates/app-template/
#
# Usage:
#   scripts/new-app.sh <app-name> [namespace]
#
# Examples:
#   scripts/new-app.sh frigate-agent
#   scripts/new-app.sh grafana-agent observability
#
# What this does:
#   1. Creates a private GitHub repo under stephenj-code/<app-name>
#   2. Copies templates/app-template/ with all __APP_NAME__ placeholders substituted
#   3. Pushes an initial commit to main
#   4. provision.yaml runs automatically and bootstraps Keycloak, LiteLLM, ArgoCD, etc.
#
# Prerequisites:
#   - gh CLI installed and authenticated (gh auth login)
#   - git configured with your name/email

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
APP_NAME="${1:-}"
NAMESPACE="${2:-$APP_NAME}"

if [[ -z "$APP_NAME" ]]; then
    echo "Usage: scripts/new-app.sh <app-name> [namespace]" >&2
    exit 1
fi

# Validate kebab-case
if ! echo "$APP_NAME" | grep -qE '^[a-z][a-z0-9-]+$'; then
    echo "Error: app name must be lowercase kebab-case (e.g. frigate-agent)" >&2
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_DIR="$REPO_ROOT/templates/app-template"
WORK_DIR="$(mktemp -d)"
APP_DIR="$WORK_DIR/$APP_NAME"

trap 'rm -rf "$WORK_DIR"' EXIT

echo "→ Creating app: $APP_NAME (namespace: $NAMESPACE)"

# ── Create GitHub repo ────────────────────────────────────────────────────────
echo "→ Creating GitHub repo stephenj-code/$APP_NAME..."
gh repo create "stephenj-code/$APP_NAME" \
    --private \
    --description "Solomon agent: $APP_NAME" \
    --clone \
    --gitignore Python \
    -p "" 2>/dev/null || true  # ignore if repo already exists

# If --clone succeeded, gh already cloned it; otherwise clone manually
if [[ ! -d "$APP_DIR" ]]; then
    git clone "https://github.com/stephenj-code/$APP_NAME.git" "$APP_DIR"
fi

# ── Copy template ─────────────────────────────────────────────────────────────
echo "→ Copying template..."
# Copy all files including hidden dirs (.github)
cp -r "$TEMPLATE_DIR"/. "$APP_DIR/"

# ── Substitute placeholders ───────────────────────────────────────────────────
echo "→ Substituting __APP_NAME__ → $APP_NAME, __NAMESPACE__ → $NAMESPACE..."
APP_NAME_UPPER="${APP_NAME//-/_}"
APP_NAME_UPPER="${APP_NAME_UPPER^^}"

# Find all non-binary files and substitute
find "$APP_DIR" -type f \
    ! -path '*/.git/*' \
    ! -name '*.png' ! -name '*.jpg' ! -name '*.ico' \
    | while read -r file; do
        sed -i \
            -e "s|__APP_NAME__|$APP_NAME|g" \
            -e "s|__NAMESPACE__|$NAMESPACE|g" \
            -e "s|__APP_NAME_UPPER__|$APP_NAME_UPPER|g" \
            "$file"
    done

# ── Initial commit ────────────────────────────────────────────────────────────
echo "→ Committing initial scaffold..."
cd "$APP_DIR"
git add -A
git commit -m "feat: initial scaffold from app-template

App: $APP_NAME
Namespace: $NAMESPACE

provision.yaml will run automatically and bootstrap:
  - Cloudflare DNS CNAME
  - Keycloak client (sealed secret)
  - LiteLLM virtual key (sealed secret)
  - ArgoCD Application in solomon platform repo"

git push origin main

echo ""
echo "✓ Done. Repo: https://github.com/stephenj-code/$APP_NAME"
echo ""
echo "Next steps:"
echo "  1. Watch provision.yaml: https://github.com/stephenj-code/$APP_NAME/actions"
echo "  2. Edit app.yaml to adjust needs (database, ui, m2m) and re-run provision.yaml"
echo "  3. Add your app code to app/ and push"

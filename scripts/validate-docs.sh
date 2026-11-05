#!/usr/bin/env bash
# validate-docs.sh — catch documentation drift before committing.
#
# Checks:
#   1. Every infrastructure/ subdirectory is mentioned in ARCHITECTURE.md
#   2. Every namespace in namespaces.yaml is documented in ARCHITECTURE.md
#   3. No unencrypted Secret objects in staged (or all tracked) YAML files
#
# Usage:
#   scripts/validate-docs.sh          # check everything
#   scripts/validate-docs.sh --staged # check only git-staged files (for pre-commit hook)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH="$REPO_ROOT/ARCHITECTURE.md"
NAMESPACES_FILE="$REPO_ROOT/infrastructure/namespaces/namespaces.yaml"
INFRA_DIR="$REPO_ROOT/infrastructure"

STAGED_ONLY=false
[[ "${1:-}" == "--staged" ]] && STAGED_ONLY=true

errors=0
warnings=0

# ── Helpers ───────────────────────────────────────────────────────────────────

fail()    { echo "  FAIL  $*" >&2; ((errors++)) || true; }
warn()    { echo "  WARN  $*"; ((warnings++)) || true; }
ok()      { echo "  OK    $*"; }
section() { echo; echo "── $* ──"; }

# ── 1. Infrastructure subdirectories covered in ARCHITECTURE.md ───────────────

section "infrastructure/ → ARCHITECTURE.md coverage"

for dir in "$INFRA_DIR"/*/; do
    name="$(basename "$dir")"
    # Skip dirs that don't map 1:1 to a k8s namespace
    case "$name" in
        namespaces|sealed-secrets) continue ;;
    esac

    if grep -q "infrastructure/$name" "$ARCH" 2>/dev/null || \
       grep -qi "### \`\?${name}\`\?" "$ARCH" 2>/dev/null; then
        ok "infrastructure/$name"
    else
        warn "infrastructure/$name not found in ARCHITECTURE.md"
    fi
done

# ── 2. Namespaces in namespaces.yaml covered in ARCHITECTURE.md ───────────────

section "namespaces.yaml → ARCHITECTURE.md coverage"

if [[ ! -f "$NAMESPACES_FILE" ]]; then
    warn "namespaces.yaml not found at $NAMESPACES_FILE — skipping"
else
    while IFS= read -r ns; do
        [[ -z "$ns" ]] && continue
        # Skip system namespaces
        case "$ns" in
            kube-system|kube-public|kube-node-lease|default) continue ;;
        esac

        if grep -q "\`$ns\`\|### $ns\b" "$ARCH" 2>/dev/null; then
            ok "namespace: $ns"
        else
            fail "namespace '$ns' in namespaces.yaml not documented in ARCHITECTURE.md"
        fi
    done < <(grep "name:" "$NAMESPACES_FILE" | awk '{print $2}')
fi

# ── 3. No unencrypted Secret objects ─────────────────────────────────────────

section "Unencrypted Secret check"

if $STAGED_ONLY; then
    yaml_files=$(git -C "$REPO_ROOT" diff --cached --name-only --diff-filter=ACM \
                 | grep -E '\.ya?ml$' || true)
else
    yaml_files=$(git -C "$REPO_ROOT" ls-files '*.yaml' '*.yml' || true)
fi

found_secrets=false
while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    full="$REPO_ROOT/$f"
    [[ -f "$full" ]] || continue

    # Match `kind: Secret` but not `kind: SealedSecret`
    if grep -qE '^kind: Secret$' "$full" 2>/dev/null; then
        fail "Unencrypted Secret found: $f — use SealedSecret instead"
        found_secrets=true
    fi
done <<< "$yaml_files"

$found_secrets || ok "No unencrypted Secret objects found"

# ── Summary ───────────────────────────────────────────────────────────────────

echo
if (( errors > 0 )); then
    echo "✗ $errors error(s), $warnings warning(s). Fix before committing."
    exit 1
elif (( warnings > 0 )); then
    echo "✓ $warnings warning(s) — review ARCHITECTURE.md coverage."
    exit 0
else
    echo "✓ All checks passed."
    exit 0
fi

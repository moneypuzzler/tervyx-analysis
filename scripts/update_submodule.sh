#!/usr/bin/env bash
# Update tervyx submodule to pinned commit with sparse checkout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUBMODULE_PATH="${REPO_ROOT}/tervyx"

# Default to main branch, can override with TERVYX_COMMIT env var
PINNED_REF="${TERVYX_COMMIT:-main}"

echo "=== TERVYX Submodule Update ==="
echo "Target: ${PINNED_REF}"
echo ""

# Check if submodule exists
if [ ! -d "${SUBMODULE_PATH}/.git" ]; then
  echo "ERROR: Submodule not found at ${SUBMODULE_PATH}"
  echo "Run: git submodule add -b main https://github.com/moneypuzzler/tervyx tervyx"
  exit 1
fi

cd "${SUBMODULE_PATH}"

echo "[1/4] Fetching updates..."
git fetch --all --tags --quiet

echo "[2/4] Checking out ${PINNED_REF}..."
git checkout "${PINNED_REF}" --quiet

echo "[3/4] Configuring sparse checkout..."
git sparse-checkout init --cone
git sparse-checkout set \
  "entries" \
  "protocol/schemas" \
  "protocol/journal_trust" \
  "policy.yaml" \
  "README.md"

echo "[4/4] Pulling latest changes..."
git pull --quiet || true

CURRENT_COMMIT=$(git rev-parse HEAD)
echo ""
echo "✓ Submodule updated to: ${CURRENT_COMMIT}"
echo "  Sparse paths:"
git sparse-checkout list | sed 's/^/    - /'

cd "${REPO_ROOT}"
echo ""
echo "Done. Run 'make all' to start analysis."

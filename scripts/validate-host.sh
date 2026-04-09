#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

echo "== openEuler release =="
cat /etc/os-release

echo "== container runtime =="
if command -v podman >/dev/null 2>&1; then
  podman --version
fi
if command -v docker >/dev/null 2>&1; then
  docker --version
fi

echo "== ports =="
ss -lntp | grep -E '13000|18080|19090|19093|19115' || true

echo "== compose support =="
if runtime="$(detect_compose_runtime)"; then
  run_compose "${runtime}" version || true
else
  echo "compose runtime not found"
fi

echo "== preflight =="
"${ROOT_DIR}/scripts/preflight-check.sh" || true

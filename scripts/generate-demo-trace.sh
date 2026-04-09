#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

GATEWAY_PORT="${DEMO_GATEWAY_PORT:-18082}"

for _ in 1 2 3; do
  curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/api/v1/checkout" >/dev/null
done

echo "Demo traces generated via demo-gateway -> demo-order."

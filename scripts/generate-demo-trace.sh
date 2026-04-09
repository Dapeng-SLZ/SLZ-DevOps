#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

GATEWAY_PORT="${DEMO_GATEWAY_PORT:-18082}"

for _ in 1 2 3; do
  curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/api/v1/checkout" >/dev/null
done

echo "Demo traces generated via demo-gateway -> demo-order."

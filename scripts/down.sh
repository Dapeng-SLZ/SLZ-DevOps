#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.yaml"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if ! runtime="$(detect_compose_runtime)"; then
  echo "未检测到 docker compose、docker-compose、podman compose 或 podman-compose。" >&2
  exit 1
fi

compose_args=(--env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

if [[ -n "${AIOPS_COMPOSE_PROFILES:-}" ]]; then
  IFS=',' read -r -a profiles <<< "${AIOPS_COMPOSE_PROFILES}"
  for profile in "${profiles[@]}"; do
    trimmed_profile="$(echo "${profile}" | awk '{$1=$1; print}')"
    if [[ -n "${trimmed_profile}" ]]; then
      compose_args+=(--profile "${trimmed_profile}")
    fi
  done
fi

run_compose "${runtime}" "${compose_args[@]}" down

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.yaml"
PODMAN_COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.podman.yaml"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

if ! runtime="$(detect_compose_runtime)"; then
  echo "未检测到 docker compose、docker-compose、podman compose 或 podman-compose。" >&2
  exit 1
fi

if is_podman_runtime "${runtime}"; then
  generate_podman_compose_file "${COMPOSE_FILE}" "${PODMAN_COMPOSE_FILE}"
  compose_file_to_use="${PODMAN_COMPOSE_FILE}"
else
  compose_file_to_use="${COMPOSE_FILE}"
fi

compose_args=(--env-file "${ENV_FILE}" -f "${compose_file_to_use}")

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

if is_podman_runtime "${runtime}"; then
  "${ROOT_DIR}/scripts/stop-default-port-proxies.sh"
fi

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.yaml"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

"${ROOT_DIR}/scripts/preflight-check.sh"

mkdir -p "${ROOT_DIR}/data/prometheus" "${ROOT_DIR}/data/alertmanager" "${ROOT_DIR}/data/grafana" "${ROOT_DIR}/data/loki" "${ROOT_DIR}/data/promtail" "${ROOT_DIR}/data/tempo" "${ROOT_DIR}/data/neo4j/data" "${ROOT_DIR}/data/neo4j/logs"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ENV_FILE}"
fi

load_env_file "${ENV_FILE}"

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

run_compose "${runtime}" "${compose_args[@]}" up -d --build

echo "平台已启动，建议执行 ./scripts/post-deploy-check.sh 进行连通性验证。"

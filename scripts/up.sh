#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.yaml"
PODMAN_COMPOSE_FILE="${ROOT_DIR}/deploy/compose/compose.podman.yaml"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

"${ROOT_DIR}/scripts/preflight-check.sh"

mkdir -p "${ROOT_DIR}/data/prometheus" "${ROOT_DIR}/data/alertmanager" "${ROOT_DIR}/data/grafana" "${ROOT_DIR}/data/loki" "${ROOT_DIR}/data/promtail" "${ROOT_DIR}/data/tempo" "${ROOT_DIR}/data/platform" "${ROOT_DIR}/data/neo4j/data" "${ROOT_DIR}/data/neo4j/logs"
chmod -R a+rwX \
  "${ROOT_DIR}/data/prometheus" \
  "${ROOT_DIR}/data/alertmanager" \
  "${ROOT_DIR}/data/grafana" \
  "${ROOT_DIR}/data/loki" \
  "${ROOT_DIR}/data/promtail" \
  "${ROOT_DIR}/data/tempo" \
  "${ROOT_DIR}/data/platform" \
  "${ROOT_DIR}/data/neo4j/data" \
  "${ROOT_DIR}/data/neo4j/logs"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ENV_FILE}"
fi

load_env_file "${ENV_FILE}"

if ! runtime="$(detect_compose_runtime)"; then
  echo "未检测到 docker compose、docker-compose、podman compose 或 podman-compose。" >&2
  exit 1
fi

if [[ "${runtime}" == "podman" || "${runtime}" == "podman-compose" ]]; then
  "${ROOT_DIR}/scripts/build-python-images.sh"
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

if [[ "${runtime}" == "docker" || "${runtime}" == "docker-compose" ]]; then
  run_compose "${runtime}" "${compose_args[@]}" up -d --build
else
  run_compose "${runtime}" "${compose_args[@]}" up -d
  "${ROOT_DIR}/scripts/start-default-port-proxies.sh"
fi

echo "平台已启动，建议执行 ./scripts/post-deploy-check.sh 进行连通性验证。"

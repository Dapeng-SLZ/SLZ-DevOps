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

has_profile() {
  local wanted="$1"
  IFS=',' read -r -a profiles <<< "${AIOPS_COMPOSE_PROFILES:-}"
  for profile in "${profiles[@]}"; do
    trimmed_profile="$(echo "${profile}" | awk '{$1=$1; print}')"
    if [[ "${trimmed_profile}" == "${wanted}" ]]; then
      return 0
    fi
  done
  return 1
}

check_http() {
  local name="$1"
  local url="$2"
  local code
  code="$(curl -fsS -o /dev/null -w '%{http_code}' "${url}" || true)"
  if [[ "${code}" =~ ^2|3|4 ]]; then
    echo "[OK] ${name}: ${url} (${code})"
  else
    echo "[FAIL] ${name}: ${url}" >&2
    return 1
  fi
}

check_http "AI Engine" "http://127.0.0.1:${AI_ENGINE_PORT:-18080}/healthz"
check_http "Prometheus" "http://127.0.0.1:${PROMETHEUS_PORT:-19090}/-/healthy"
check_http "Alertmanager" "http://127.0.0.1:${ALERTMANAGER_PORT:-19093}/-/healthy"
check_http "Grafana" "http://127.0.0.1:${GRAFANA_PORT:-13000}/login"
check_http "Loki" "http://127.0.0.1:${LOKI_PORT:-13100}/ready"
check_http "Blackbox Exporter" "http://127.0.0.1:${BLACKBOX_PORT:-19115}/-/healthy"

if has_profile analysis; then
  check_http "CMDB" "http://127.0.0.1:${CMDB_PORT:-18081}/healthz"
  check_http "Tempo" "http://127.0.0.1:${TEMPO_PORT:-13200}/ready"
  check_http "Neo4j" "http://127.0.0.1:${NEO4J_HTTP_PORT:-17474}"
  check_http "AI Root Cause Topology" "http://127.0.0.1:${AI_ENGINE_PORT:-18080}/api/v1/root-cause/topology"
fi

if has_profile demo; then
  check_http "Demo Gateway" "http://127.0.0.1:${DEMO_GATEWAY_PORT:-18082}/healthz"
  check_http "Demo Order" "http://127.0.0.1:${DEMO_ORDER_PORT:-18083}/healthz"
fi

echo "部署后检查完成。"


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

echo "部署后检查完成。"

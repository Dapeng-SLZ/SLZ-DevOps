#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
PID_DIR="${ROOT_DIR}/data/runtime/port-proxies"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

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

stop_port_proxy() {
  local host_port="$1"
  while read -r pid; do
    [[ -n "${pid}" ]] || continue
    kill "${pid}" >/dev/null 2>&1 || true
  done < <(pgrep -f "socat TCP-LISTEN:${host_port},bind=0.0.0.0,reuseaddr,fork" || true)
}

[[ -d "${PID_DIR}" ]] || exit 0

for pid_file in "${PID_DIR}"/*.pid; do
  [[ -e "${pid_file}" ]] || continue
  pid="$(cat "${pid_file}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${pid_file}"
done

stop_port_proxy "${GRAFANA_PORT:-13000}"
stop_port_proxy "${PROMETHEUS_PORT:-19090}"
stop_port_proxy "${ALERTMANAGER_PORT:-19093}"
stop_port_proxy "${AI_ENGINE_PORT:-18080}"
stop_port_proxy "${LOKI_PORT:-13100}"
stop_port_proxy "${BLACKBOX_PORT:-19115}"

if has_profile console; then
  stop_port_proxy "${CONSOLE_PORT:-14000}"
  stop_port_proxy "${JOB_RUNNER_PORT:-18084}"
fi

if has_profile analysis; then
  stop_port_proxy "${CMDB_PORT:-18081}"
  stop_port_proxy "${TEMPO_PORT:-13200}"
  stop_port_proxy "${NEO4J_HTTP_PORT:-17474}"
  stop_port_proxy "${NEO4J_BOLT_PORT:-17687}"
fi

if has_profile demo; then
  stop_port_proxy "${DEMO_GATEWAY_PORT:-18082}"
  stop_port_proxy "${DEMO_ORDER_PORT:-18083}"
fi

echo "默认端口代理已停止。"
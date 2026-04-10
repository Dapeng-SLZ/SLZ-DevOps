#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
PID_DIR="${ROOT_DIR}/data/runtime/port-proxies"
LOG_DIR="${ROOT_DIR}/data/runtime/port-proxy-logs"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

command -v socat >/dev/null 2>&1 || {
  echo "未检测到 socat，请先安装。" >&2
  exit 1
}

mkdir -p "${PID_DIR}" "${LOG_DIR}"

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

stop_proxy() {
  local name="$1"
  local host_port="${2:-}"
  local pid_file="${PID_DIR}/${name}.pid"

  if [[ -f "${pid_file}" ]]; then
    pid="$(cat "${pid_file}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${pid_file}"
  fi

  if [[ -n "${host_port}" ]]; then
    while read -r stale_pid; do
      [[ -n "${stale_pid}" ]] || continue
      kill "${stale_pid}" >/dev/null 2>&1 || true
    done < <(pgrep -f "socat TCP-LISTEN:${host_port},bind=0.0.0.0,reuseaddr,fork" || true)
  fi
}

start_proxy() {
  local name="$1"
  local container_name="$2"
  local host_port="$3"
  local container_port="$4"
  local container_ip
  local pid_file="${PID_DIR}/${name}.pid"
  local log_file="${LOG_DIR}/${name}.log"

  stop_proxy "${name}" "${host_port}"

  container_ip="$(podman inspect "${container_name}" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || true)"
  if [[ -z "${container_ip}" ]]; then
    echo "[WARN] 未获取到容器 IP，跳过代理: ${container_name}" >&2
    return 0
  fi

  nohup socat \
    "TCP-LISTEN:${host_port},bind=0.0.0.0,reuseaddr,fork" \
    "TCP:${container_ip}:${container_port}" \
    >"${log_file}" 2>&1 &
  echo $! > "${pid_file}"
}

start_proxy grafana slz-grafana "${GRAFANA_PORT:-13000}" 3000
start_proxy prometheus slz-prometheus "${PROMETHEUS_PORT:-19090}" 9090
start_proxy alertmanager slz-alertmanager "${ALERTMANAGER_PORT:-19093}" 9093
start_proxy ai-engine slz-ai-engine "${AI_ENGINE_PORT:-18080}" 8080
start_proxy loki slz-loki "${LOKI_PORT:-13100}" 3100
start_proxy blackbox slz-blackbox "${BLACKBOX_PORT:-19115}" 9115

if has_profile console; then
  start_proxy console slz-console "${CONSOLE_PORT:-14000}" 80
  start_proxy job-runner slz-job-runner "${JOB_RUNNER_PORT:-18084}" 8084
fi

if has_profile analysis; then
  start_proxy cmdb slz-cmdb "${CMDB_PORT:-18081}" 8081
  start_proxy tempo slz-tempo "${TEMPO_PORT:-13200}" 3200
  start_proxy neo4j-http slz-neo4j "${NEO4J_HTTP_PORT:-17474}" 7474
  start_proxy neo4j-bolt slz-neo4j "${NEO4J_BOLT_PORT:-17687}" 7687
fi

if has_profile demo; then
  start_proxy demo-gateway slz-demo-gateway "${DEMO_GATEWAY_PORT:-18082}" 8082
  start_proxy demo-order slz-demo-order "${DEMO_ORDER_PORT:-18083}" 8083
fi

echo "默认端口代理已启动。"
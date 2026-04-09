#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

warn() {
  echo "[WARN] $*"
}

info() {
  echo "[INFO] $*"
}

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

[[ -f /etc/os-release ]] || fail "无法识别操作系统信息。"
source /etc/os-release

info "检测操作系统: ${PRETTY_NAME:-unknown}"
[[ "${ID:-}" == "openEuler" || "${NAME:-}" == *"openEuler"* ]] || warn "当前不是 openEuler，脚本按兼容模式继续。"

MEM_TOTAL_KB="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
CPU_COUNT="$(nproc)"
DISK_AVAIL_KB="$(df -Pk "${ROOT_DIR}" | awk 'NR==2 {print $4}')"

(( CPU_COUNT >= 2 )) || warn "CPU 少于 2 核，建议至少 4 核。"
(( MEM_TOTAL_KB >= 4 * 1024 * 1024 )) || warn "内存少于 4GB，运行稳定性可能较差。"
(( DISK_AVAIL_KB >= 20 * 1024 * 1024 )) || warn "磁盘可用空间少于 20GB。"

for command_name in tar curl awk ss; do
  command -v "${command_name}" >/dev/null 2>&1 || fail "缺少基础命令: ${command_name}"
done

if ! runtime="$(detect_compose_runtime)"; then
  fail "未检测到 docker compose 或 podman compose。"
fi

info "检测到容器编排运行时: ${runtime}"
run_compose "${runtime}" version >/dev/null

for path in \
  "${ROOT_DIR}/deploy/compose/compose.yaml" \
  "${ROOT_DIR}/deploy/prometheus/prometheus.yml" \
  "${ROOT_DIR}/deploy/alertmanager/alertmanager.yml" \
  "${ROOT_DIR}/deploy/loki/config.yml" \
  "${ROOT_DIR}/deploy/promtail/config.yml" \
  "${ROOT_DIR}/services/ai-engine/Dockerfile"; do
  [[ -f "${path}" ]] || fail "缺少关键文件: ${path}"
done

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  warn ".env 不存在，启动脚本会自动从 .env.example 复制。"
fi

info "预检完成。"

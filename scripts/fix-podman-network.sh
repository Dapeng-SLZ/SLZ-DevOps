#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

CONFIG_DIR="/etc/containers"
CONFIG_FILE="${CONFIG_DIR}/containers.conf"

has_rpm_package() {
  rpm -q "$1" >/dev/null 2>&1
}

find_netavark_binary() {
  if command -v netavark >/dev/null 2>&1; then
    command -v netavark
    return 0
  fi

  rpm -ql netavark 2>/dev/null | grep '/netavark$' | head -n 1
}

mkdir -p "${CONFIG_DIR}"

if ! has_rpm_package netavark; then
  if ! dnf install -y netavark; then
    echo "安装 netavark 失败。" >&2
    exit 1
  fi
fi

if ! has_rpm_package aardvark-dns; then
  if ! dnf install -y aardvark-dns; then
    echo "未在仓库中找到 aardvark-dns，继续切换到 netavark。若后续容器间服务名解析异常，请手动确认 DNS 组件来源。"
  fi
fi

NETAVARK_BIN="$(find_netavark_binary || true)"
if [[ -z "${NETAVARK_BIN}" || ! -e "${NETAVARK_BIN}" ]]; then
  echo "当前系统已安装 netavark 包，但未找到 netavark 可执行文件。" >&2
  exit 1
fi

echo "检测到 netavark 可执行文件: ${NETAVARK_BIN}"

cat > "${CONFIG_FILE}" <<'EOF'
[network]
network_backend = "netavark"
EOF

echo "已写入 Podman 网络后端配置: ${CONFIG_FILE}"
echo "下一步将执行 podman system reset -f，清理旧的 cni 网络与容器状态。"
echo "注意：这会删除当前本机 Podman 容器、网络、镜像缓存。"

podman system reset -f

echo "Podman 网络后端已切换为 netavark。"
echo "建议重新执行 ./scripts/up.sh 启动平台。"
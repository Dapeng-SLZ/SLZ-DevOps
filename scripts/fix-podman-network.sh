#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

CONFIG_DIR="/etc/containers"
CONFIG_FILE="${CONFIG_DIR}/containers.conf"

mkdir -p "${CONFIG_DIR}"

if ! dnf install -y netavark aardvark-dns; then
  echo "安装 netavark 或 aardvark-dns 失败。" >&2
  exit 1
fi

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
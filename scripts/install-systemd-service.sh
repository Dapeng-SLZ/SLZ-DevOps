#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="${ROOT_DIR}/packaging/systemd/slz-aiops.service"
SERVICE_DST="/etc/systemd/system/slz-aiops.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

[[ -f "${SERVICE_SRC}" ]] || {
  echo "缺少 systemd 服务文件: ${SERVICE_SRC}" >&2
  exit 1
}

cp "${SERVICE_SRC}" "${SERVICE_DST}"
systemctl daemon-reload
systemctl enable --now slz-aiops.service
systemctl status slz-aiops.service --no-pager || true

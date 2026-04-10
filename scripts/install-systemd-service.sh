#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_TEMPLATE="${ROOT_DIR}/packaging/systemd/slz-aiops.service.template"
BACKUP_SERVICE_TEMPLATE="${ROOT_DIR}/packaging/systemd/slz-platform-backup.service.template"
BACKUP_TIMER_SRC="${ROOT_DIR}/packaging/systemd/slz-platform-backup.timer"
SERVICE_DST="/etc/systemd/system/slz-aiops.service"
BACKUP_SERVICE_DST="/etc/systemd/system/slz-platform-backup.service"
BACKUP_TIMER_DST="/etc/systemd/system/slz-platform-backup.timer"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

[[ -f "${SERVICE_TEMPLATE}" ]] || {
  echo "缺少 systemd 服务模板: ${SERVICE_TEMPLATE}" >&2
  exit 1
}

[[ -f "${BACKUP_SERVICE_TEMPLATE}" ]] || {
  echo "缺少 systemd 备份服务模板: ${BACKUP_SERVICE_TEMPLATE}" >&2
  exit 1
}

[[ -f "${BACKUP_TIMER_SRC}" ]] || {
  echo "缺少 systemd 备份定时器文件: ${BACKUP_TIMER_SRC}" >&2
  exit 1
}

sed "s|__ROOT_DIR__|${ROOT_DIR}|g" "${SERVICE_TEMPLATE}" > "${SERVICE_DST}"
sed "s|__ROOT_DIR__|${ROOT_DIR}|g" "${BACKUP_SERVICE_TEMPLATE}" > "${BACKUP_SERVICE_DST}"
cp "${BACKUP_TIMER_SRC}" "${BACKUP_TIMER_DST}"
systemctl daemon-reload
systemctl enable --now slz-aiops.service
systemctl enable --now slz-platform-backup.timer
systemctl status slz-aiops.service --no-pager || true
systemctl status slz-platform-backup.timer --no-pager || true

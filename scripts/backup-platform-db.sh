#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_FILE="${ROOT_DIR}/data/platform/platform.db"
BACKUP_DIR="${ROOT_DIR}/data/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RETENTION_DAYS="${PLATFORM_BACKUP_RETENTION_DAYS:-7}"

if [[ ! -f "${DB_FILE}" ]]; then
  echo "平台数据库不存在: ${DB_FILE}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
BACKUP_FILE="${BACKUP_DIR}/platform-${TIMESTAMP}.db"
cp "${DB_FILE}" "${BACKUP_FILE}"

find "${BACKUP_DIR}" -type f -name 'platform-*.db' -mtime "+${RETENTION_DAYS}" -delete

echo "平台数据库备份完成: ${BACKUP_FILE}"
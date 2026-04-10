#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: ./scripts/restore-platform-db.sh <备份文件路径>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_FILE="$1"
TARGET_FILE="${ROOT_DIR}/data/platform/platform.db"

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "备份文件不存在: ${SOURCE_FILE}" >&2
  exit 1
fi

mkdir -p "$(dirname "${TARGET_FILE}")"
cp "${SOURCE_FILE}" "${TARGET_FILE}"

echo "平台数据库恢复完成: ${TARGET_FILE}"
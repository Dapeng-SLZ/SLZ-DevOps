#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${ROOT_DIR}/VERSION"
RELEASE_DIR="${ROOT_DIR}/releases"

if [[ ! -f "${VERSION_FILE}" ]]; then
  echo "VERSION 文件不存在。" >&2
  exit 1
fi

VERSION="$(tr -d '[:space:]' < "${VERSION_FILE}")"
PACKAGE_NAME="slz-devops-${VERSION}"
PACKAGE_PATH="${RELEASE_DIR}/${PACKAGE_NAME}.tar.gz"

mkdir -p "${RELEASE_DIR}"
rm -f "${PACKAGE_PATH}"

tar \
  --exclude='.git' \
  --exclude='data' \
  --exclude='releases' \
  --exclude='.env' \
  -czf "${PACKAGE_PATH}" \
  -C "${ROOT_DIR}" \
  .

echo "发行包已生成: ${PACKAGE_PATH}"

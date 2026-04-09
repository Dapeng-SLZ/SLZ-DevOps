#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 用户执行。" >&2
  exit 1
fi

CONFIG_DIR="/etc/containers/registries.conf.d"
CONFIG_FILE="${CONFIG_DIR}/999-slz-mirrors.conf"

DEFAULT_MIRRORS=(
  "docker.m.daocloud.io"
  "dockerproxy.cn"
)

if [[ -n "${CONTAINER_MIRRORS:-}" ]]; then
  IFS=',' read -r -a mirrors <<< "${CONTAINER_MIRRORS}"
else
  mirrors=("${DEFAULT_MIRRORS[@]}")
fi

mkdir -p "${CONFIG_DIR}"

{
  echo 'unqualified-search-registries = ["docker.io"]'
  echo
  echo '[[registry]]'
  echo 'prefix = "docker.io"'
  echo 'location = "docker.io"'
  echo
  for mirror in "${mirrors[@]}"; do
    trimmed_mirror="$(echo "${mirror}" | awk '{$1=$1; print}')"
    [[ -n "${trimmed_mirror}" ]] || continue
    echo '[[registry.mirror]]'
    echo "location = \"${trimmed_mirror}\""
    echo 'insecure = false'
    echo
  done
} > "${CONFIG_FILE}"

echo "Podman registry mirror 配置已写入: ${CONFIG_FILE}"
echo "可通过设置 CONTAINER_MIRRORS=mirror1,mirror2 自定义镜像源。"
echo "建议执行: podman pull python:3.12-slim"
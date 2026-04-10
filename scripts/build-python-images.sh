#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-slz-aiops}"
PIP_INDEX_URL_VALUE="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_TRUSTED_HOST_VALUE="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"

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

build_image() {
  local service_name="$1"
  local context_dir="$2"
  local image_tag="localhost/${PROJECT_NAME}_${service_name}:latest"

  echo "[INFO] 构建镜像: ${image_tag}"
  podman build \
    --network host \
    --build-arg "PIP_INDEX_URL=${PIP_INDEX_URL_VALUE}" \
    --build-arg "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST_VALUE}" \
    -t "${image_tag}" \
    "${context_dir}"
}

build_generic_image() {
  local service_name="$1"
  local context_dir="$2"
  local image_tag="localhost/${PROJECT_NAME}_${service_name}:latest"

  echo "[INFO] 构建镜像: ${image_tag}"
  podman build \
    --network host \
    -t "${image_tag}" \
    "${context_dir}"
}

build_image "ai-engine" "${ROOT_DIR}/services/ai-engine"

if has_profile console; then
  build_generic_image "console" "${ROOT_DIR}/apps/console"
  build_image "job-runner" "${ROOT_DIR}/services/job-runner"
fi

if has_profile analysis; then
  build_image "cmdb" "${ROOT_DIR}/services/cmdb"
fi

if has_profile demo; then
  build_image "demo-gateway" "${ROOT_DIR}/services/demo-gateway"
  build_image "demo-order" "${ROOT_DIR}/services/demo-order"
fi

echo "[INFO] Python 服务镜像构建完成。"
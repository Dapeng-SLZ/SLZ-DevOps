#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
source "${ROOT_DIR}/scripts/lib/runtime.sh"

load_env_file "${ENV_FILE}"

if ! runtime="$(detect_compose_runtime)"; then
  echo "未检测到 docker compose、docker-compose、podman compose 或 podman-compose。" >&2
  exit 1
fi

CMDB_URL="http://127.0.0.1:${CMDB_PORT:-18081}/api/v1/topology/cypher"
NEO4J_USER="${NEO4J_AUTH%%/*}"
NEO4J_PASSWORD="${NEO4J_AUTH#*/}"
TMP_FILE="$(mktemp)"
trap 'rm -f "${TMP_FILE}"' EXIT

curl -fsS "${CMDB_URL}" -o "${TMP_FILE}"

case "${runtime}" in
  docker)
    docker exec -i slz-neo4j cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" < "${TMP_FILE}"
    ;;
  podman)
    podman exec -i slz-neo4j cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" < "${TMP_FILE}"
    ;;
esac

echo "CMDB 拓扑已同步到 Neo4j。"

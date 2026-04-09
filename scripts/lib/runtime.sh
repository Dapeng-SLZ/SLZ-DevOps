#!/usr/bin/env bash

detect_compose_runtime() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo docker
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    echo docker-compose
    return 0
  fi

  if command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    echo podman
    return 0
  fi

  if command -v podman-compose >/dev/null 2>&1; then
    echo podman-compose
    return 0
  fi

  return 1
}

run_compose() {
  local runtime="${1:?runtime is required}"
  shift

  case "${runtime}" in
    docker)
      docker compose "$@"
      ;;
    docker-compose)
      docker-compose "$@"
      ;;
    podman)
      podman compose "$@"
      ;;
    podman-compose)
      podman-compose "$@"
      ;;
    *)
      echo "Unsupported compose runtime: ${runtime}" >&2
      return 1
      ;;
  esac
}

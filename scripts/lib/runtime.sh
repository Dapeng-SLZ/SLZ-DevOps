#!/usr/bin/env bash

trim_whitespace() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

strip_wrapping_quotes() {
  local value="$1"

  if [[ ${#value} -ge 2 ]]; then
    if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
  fi

  printf '%s' "${value}"
}

load_env_file() {
  local env_file="$1"
  local raw_line line key value

  [[ -f "${env_file}" ]] || return 0

  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    line="${raw_line%$'\r'}"
    line="$(trim_whitespace "${line}")"

    [[ -z "${line}" ]] && continue
    [[ "${line}" == \#* ]] && continue

    if [[ "${line}" == export[[:space:]]* ]]; then
      line="${line#export }"
      line="$(trim_whitespace "${line}")"
    fi

    [[ "${line}" == *=* ]] || continue

    key="${line%%=*}"
    value="${line#*=}"
    key="$(trim_whitespace "${key}")"
    value="$(strip_wrapping_quotes "${value}")"

    [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

    printf -v "${key}" '%s' "${value}"
    export "${key}"
  done < "${env_file}"
}

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

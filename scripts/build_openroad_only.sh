#!/usr/bin/env bash
set -euo pipefail

resolve_workspace_root() {
  local direct_root env_root
  direct_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [[ -d "${direct_root}/flow" && -d "${direct_root}/tools/OpenROAD" && -d "${direct_root}/evolve_agent" ]]; then
    printf '%s\n' "${direct_root}"
    return 0
  fi
  if [[ -n "${ORFS_ROOT:-}" ]]; then
    env_root="$(realpath -m "${ORFS_ROOT}")"
    if [[ -d "${env_root}/flow" && -d "${env_root}/tools/OpenROAD" && -d "${env_root}/evolve_agent" ]]; then
      printf '%s\n' "${env_root}"
      return 0
    fi
  fi
  return 1
}

if ! ROOT_DIR="$(resolve_workspace_root)"; then
  echo "[ERROR] build_openroad_only.sh must run inside an ORFS workspace with this repo mounted as evolve_agent/." >&2
  echo "[ERROR] Re-run from the mounted workspace or set ORFS_ROOT to that workspace." >&2
  exit 1
fi

BUILD_DIR="${OPENROAD_BUILD_DIR:-${ROOT_DIR}/tools/OpenROAD/build}"
INSTALL_ROOT="${OPENROAD_INSTALL_ROOT:-${ROOT_DIR}/tools/install/OpenROAD}"
INSTALL_BIN="${OPENROAD_BINARY:-${INSTALL_ROOT}/bin/openroad}"
THREADS="${1:-8}"
INCREMENTAL_TARGETS_RAW="${OPENROAD_INCREMENTAL_TARGETS:-openroad}"
INITIAL_CMAKE_ARGS_RAW="${OPENROAD_INITIAL_CMAKE_ARGS:-}"

read -r -a INCREMENTAL_TARGETS <<< "${INCREMENTAL_TARGETS_RAW}"
read -r -a INITIAL_CMAKE_ARGS <<< "${INITIAL_CMAKE_ARGS_RAW}"

if [[ ! -x "${ROOT_DIR}/tools/OpenROAD/etc/Build.sh" ]]; then
  echo "[ERROR] Missing OpenROAD build entrypoint under ${ROOT_DIR}/tools/OpenROAD/etc/Build.sh" >&2
  exit 1
fi

if [[ ! -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  echo "[INFO] OpenROAD build tree is missing; configuring OpenROAD only."
  echo "[INFO] build_dir=${BUILD_DIR}"
  echo "[INFO] install_root=${INSTALL_ROOT}"
  build_cmd=(
    "${ROOT_DIR}/tools/OpenROAD/etc/Build.sh"
    "-dir=${BUILD_DIR}"
    "-threads=${THREADS}"
    "-cmake=-D CMAKE_INSTALL_PREFIX=${INSTALL_ROOT}"
  )
  if [[ -n "${CMAKE_INSTALL_RPATH:-}" ]]; then
    build_cmd+=("-cmake=-D CMAKE_INSTALL_RPATH=${CMAKE_INSTALL_RPATH} -D CMAKE_INSTALL_RPATH_USE_LINK_PATH=TRUE")
  fi
  if [[ ${#INITIAL_CMAKE_ARGS[@]} -gt 0 ]]; then
    build_cmd+=("-cmake=${INITIAL_CMAKE_ARGS[*]}")
  fi
  "${build_cmd[@]}"
  cmake --install "${BUILD_DIR}" --prefix "${INSTALL_ROOT}"
  if [[ ! -x "${INSTALL_BIN}" ]]; then
    echo "[ERROR] OpenROAD binary missing after initial OpenROAD-only build: ${INSTALL_BIN}" >&2
    exit 1
  fi
  echo "[INFO] OpenROAD-only initial build complete: ${INSTALL_BIN}"
  exit 0
fi

echo "[INFO] Reusing existing OpenROAD build tree with ${THREADS} threads."
echo "[INFO] build_dir=${BUILD_DIR}"
echo "[INFO] install_bin=${INSTALL_BIN}"
echo "[INFO] incremental_targets=${INCREMENTAL_TARGETS[*]}"
cmake --build "${BUILD_DIR}" --target "${INCREMENTAL_TARGETS[@]}" -j "${THREADS}"
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_ROOT}"

if [[ ! -x "${INSTALL_BIN}" ]]; then
  echo "[ERROR] OpenROAD binary missing after install target: ${INSTALL_BIN}" >&2
  exit 1
fi

echo "[INFO] OpenROAD-only build complete: ${INSTALL_BIN}"

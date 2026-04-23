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
DISABLE_TESTS_RAW="${OPENROAD_DISABLE_TESTS:-1}"
DISABLE_GUI_RAW="${OPENROAD_DISABLE_GUI:-0}"

read -r -a INCREMENTAL_TARGETS <<< "${INCREMENTAL_TARGETS_RAW}"
read -r -a INITIAL_CMAKE_ARGS <<< "${INITIAL_CMAKE_ARGS_RAW}"

is_truthy() {
  local value="${1,,}"
  [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]
}

if [[ ! -x "${ROOT_DIR}/tools/OpenROAD/etc/Build.sh" ]]; then
  echo "[ERROR] Missing OpenROAD build entrypoint under ${ROOT_DIR}/tools/OpenROAD/etc/Build.sh" >&2
  exit 1
fi

reset_mismatched_build_tree() {
  local cache_file="$1/CMakeCache.txt"
  local expected_build_dir expected_home_dir cache_build_dir cache_home_dir
  expected_build_dir="$(realpath -m "$1")"
  expected_home_dir="$(realpath -m "${ROOT_DIR}/tools/OpenROAD")"

  cache_build_dir="$(awk -F= '/^CMAKE_CACHEFILE_DIR:INTERNAL=/{print $2}' "${cache_file}" | tail -n 1)"
  cache_home_dir="$(awk -F= '/^CMAKE_HOME_DIRECTORY:INTERNAL=/{print $2}' "${cache_file}" | tail -n 1)"

  if [[ -n "${cache_build_dir}" && "${cache_build_dir}" != "${expected_build_dir}" ]] \
    || [[ -n "${cache_home_dir}" && "${cache_home_dir}" != "${expected_home_dir}" ]]; then
    echo "[INFO] Existing OpenROAD build tree belongs to another workspace."
    echo "[INFO] cached_build_dir=${cache_build_dir}"
    echo "[INFO] cached_home_dir=${cache_home_dir}"
    echo "[INFO] expected_build_dir=${expected_build_dir}"
    echo "[INFO] expected_home_dir=${expected_home_dir}"
    echo "[INFO] Resetting build tree at ${expected_build_dir}"
    rm -rf "${expected_build_dir}"
  fi
}

if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  reset_mismatched_build_tree "${BUILD_DIR}"
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
  if is_truthy "${DISABLE_TESTS_RAW}"; then
    build_cmd+=("-no-tests")
  fi
  if is_truthy "${DISABLE_GUI_RAW}"; then
    build_cmd+=("-no-gui")
  fi
  if [[ -n "${CMAKE_INSTALL_RPATH:-}" ]]; then
    build_cmd+=("-cmake=-D CMAKE_INSTALL_RPATH=${CMAKE_INSTALL_RPATH} -D CMAKE_INSTALL_RPATH_USE_LINK_PATH=TRUE")
  fi
  if [[ ${#INITIAL_CMAKE_ARGS[@]} -gt 0 ]]; then
    build_cmd+=("-cmake=${INITIAL_CMAKE_ARGS[*]}")
  fi
  echo "[INFO] disable_tests=${DISABLE_TESTS_RAW} disable_gui=${DISABLE_GUI_RAW}"
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

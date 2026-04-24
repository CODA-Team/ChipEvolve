#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"
dpl_init_runtime "build_openroad_only.sh"
echo "[INFO] runtime_orfs_build_root=${ORFS_BUILD_ROOT:-}"
ROOT_DIR="${ORFS_ROOT}"
THREADS="${1:-8}"
INCREMENTAL_TARGETS_RAW="${OPENROAD_INCREMENTAL_TARGETS:-openroad sta}"
INITIAL_CMAKE_ARGS_RAW="${OPENROAD_INITIAL_CMAKE_ARGS:-}"
DISABLE_TESTS_RAW="${OPENROAD_DISABLE_TESTS:-1}"
DISABLE_GUI_RAW="${OPENROAD_DISABLE_GUI:-0}"
INSTALL_MODE="${OPENROAD_INSTALL_MODE:-binaries}"
CORE_ROOT_RAW="${OPENROAD_CORE_ROOT:-}"
BUILD_ROOT="${ORFS_BUILD_ROOT:-${ORFS_ROOT}}"
if [[ "${ORFS_ROOT}" == *" "* && "${BUILD_ROOT}" == "${ORFS_ROOT}" ]]; then
  BUILD_ROOT="$(_dpl_stable_alias_root)"
  export ORFS_BUILD_ROOT="${BUILD_ROOT}"
fi

if [[ -n "${OPENROAD_BUILD_DIR:-}" && "${OPENROAD_BUILD_DIR}" == *" "* ]]; then
  echo "[ERROR] OPENROAD_BUILD_DIR contains spaces. Use the default build dir or a space-free explicit path." >&2
  exit 1
fi
if [[ -n "${OPENROAD_INSTALL_ROOT:-}" && "${OPENROAD_INSTALL_ROOT}" == *" "* ]]; then
  echo "[ERROR] OPENROAD_INSTALL_ROOT contains spaces. Use the default install root or a space-free explicit path." >&2
  exit 1
fi
if [[ -n "${OPENROAD_BINARY:-}" && "${OPENROAD_BINARY}" == *" "* ]]; then
  echo "[ERROR] OPENROAD_BINARY contains spaces. Use the default binary path or a space-free explicit path." >&2
  exit 1
fi

BUILD_DIR="${OPENROAD_BUILD_DIR:-${BUILD_ROOT}/tools/OpenROAD/build}"
INSTALL_ROOT="${OPENROAD_INSTALL_ROOT:-${BUILD_ROOT}/tools/install/OpenROAD}"
INSTALL_BIN="${OPENROAD_BINARY:-${INSTALL_ROOT}/bin/openroad}"
OPENROAD_SRC="${BUILD_ROOT}/tools/OpenROAD"
CORE_ROOT=""
if [[ -n "${CORE_ROOT_RAW}" ]]; then
  CORE_ROOT="$(realpath -m "${CORE_ROOT_RAW}")"
fi

read -r -a INCREMENTAL_TARGETS <<< "${INCREMENTAL_TARGETS_RAW}"
read -r -a INITIAL_CMAKE_ARGS <<< "${INITIAL_CMAKE_ARGS_RAW}"

is_truthy() {
  local value="${1,,}"
  [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]
}

if [[ ! -f "${OPENROAD_SRC}/CMakeLists.txt" ]]; then
  echo "[ERROR] Missing OpenROAD source tree under ${OPENROAD_SRC}" >&2
  exit 1
fi

if [[ -d "${BUILD_ROOT}/dependencies" && -f "${BUILD_ROOT}/dev_env.sh" ]]; then
  # shellcheck disable=SC1090
  . "${BUILD_ROOT}/dev_env.sh"
fi

export CC="${CC:-$(command -v gcc)}"
export CXX="${CXX:-$(command -v g++)}"

BUILD_NEEDS_CONFIGURE=0

seed_from_core_if_needed() {
  if [[ -z "${CORE_ROOT_RAW}" ]]; then
    return 0
  fi
  local core_build_dir core_install_root
  core_build_dir="${CORE_ROOT}/build"
  core_install_root="${CORE_ROOT}/install/OpenROAD"
  if [[ "$(realpath -m "${BUILD_DIR}")" == "$(realpath -m "${core_build_dir}")" \
     && "$(realpath -m "${INSTALL_ROOT}")" == "$(realpath -m "${core_install_root}")" ]]; then
    return 0
  fi
  if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
    return 0
  fi
  if [[ ! -f "${core_build_dir}/CMakeCache.txt" ]]; then
    echo "[ERROR] OPENROAD_CORE_ROOT is set but missing seeded build cache: ${core_build_dir}" >&2
    exit 1
  fi
  if [[ ! -x "${core_install_root}/bin/openroad" ]]; then
    echo "[ERROR] OPENROAD_CORE_ROOT is set but missing core binary: ${core_install_root}/bin/openroad" >&2
    exit 1
  fi
  echo "[INFO] Seeding variant build/install from common core."
  echo "[INFO] core_root=${CORE_ROOT}"
  echo "[INFO] variant_build_dir=${BUILD_DIR}"
  echo "[INFO] variant_install_root=${INSTALL_ROOT}"
  mkdir -p "${BUILD_DIR}" "${INSTALL_ROOT}"
  rsync -a --delete "${core_build_dir}/" "${BUILD_DIR}/"
  rsync -a --delete "${core_install_root}/" "${INSTALL_ROOT}/"
  rm -f "${BUILD_DIR}/CMakeCache.txt" "${BUILD_DIR}/Makefile" "${BUILD_DIR}/cmake_install.cmake"
  if [[ -d "${BUILD_DIR}/CMakeFiles" ]]; then
    find "${BUILD_DIR}/CMakeFiles" -maxdepth 1 -type f -delete
  fi
}

inspect_build_tree() {
  local cache_file="$1/CMakeCache.txt"
  local expected_build_dir expected_home_dir cache_build_dir cache_home_dir
  local expected_build_dir_resolved expected_home_dir_resolved
  local cache_build_dir_resolved cache_home_dir_resolved
  expected_build_dir="$(realpath -m "$1")"
  expected_home_dir="$(realpath -m "${BUILD_ROOT}/tools/OpenROAD")"
  expected_build_dir_resolved="$(realpath -m "${expected_build_dir}")"
  expected_home_dir_resolved="$(realpath -m "${expected_home_dir}")"

  cache_build_dir="$(awk -F= '/^CMAKE_CACHEFILE_DIR:INTERNAL=/{print $2}' "${cache_file}" | tail -n 1)"
  cache_home_dir="$(awk -F= '/^CMAKE_HOME_DIRECTORY:INTERNAL=/{print $2}' "${cache_file}" | tail -n 1)"
  cache_build_dir_resolved="$(realpath -m "${cache_build_dir}")"
  cache_home_dir_resolved="$(realpath -m "${cache_home_dir}")"

  if [[ -n "${cache_home_dir}" && "${cache_home_dir_resolved}" != "${expected_home_dir_resolved}" ]]; then
    echo "[INFO] Existing OpenROAD build tree belongs to another workspace."
    echo "[INFO] cached_home_dir=${cache_home_dir}"
    echo "[INFO] expected_home_dir=${expected_home_dir}"
    echo "[INFO] Resetting build tree at ${expected_build_dir_resolved}"
    rm -rf "${expected_build_dir_resolved}"
    return 0
  fi

  if [[ -n "${cache_build_dir}" && "${cache_build_dir_resolved}" != "${expected_build_dir_resolved}" ]]; then
    echo "[INFO] OpenROAD build cache needs reconfigure for this build dir."
    echo "[INFO] cached_build_dir=${cache_build_dir}"
    echo "[INFO] expected_build_dir=${expected_build_dir}"
    BUILD_NEEDS_CONFIGURE=1
  fi
}

seed_from_core_if_needed

if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  inspect_build_tree "${BUILD_DIR}"
fi

if [[ ! -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  BUILD_NEEDS_CONFIGURE=1
fi

if [[ "${BUILD_NEEDS_CONFIGURE}" == "1" ]]; then
  echo "[INFO] Configuring OpenROAD build tree."
  echo "[INFO] build_dir=${BUILD_DIR}"
  echo "[INFO] install_root=${INSTALL_ROOT}"
  mkdir -p "${BUILD_DIR}" "${INSTALL_ROOT}"
  configure_cmd=(
    cmake
    -S "${OPENROAD_SRC}"
    -B "${BUILD_DIR}"
    -D "CMAKE_INSTALL_PREFIX=${INSTALL_ROOT}"
    -D "CMAKE_EXPORT_COMPILE_COMMANDS=ON"
  )
  if [[ -n "${CMAKE_GENERATOR:-}" ]]; then
    configure_cmd+=(-G "${CMAKE_GENERATOR}")
  fi
  if is_truthy "${DISABLE_TESTS_RAW}"; then
    configure_cmd+=(-D "ENABLE_TESTS=OFF")
  fi
  if is_truthy "${DISABLE_GUI_RAW}"; then
    configure_cmd+=(-D "BUILD_GUI=OFF")
  fi
  if [[ -n "${CMAKE_INSTALL_RPATH:-}" ]]; then
    configure_cmd+=(
      -D "CMAKE_INSTALL_RPATH=${CMAKE_INSTALL_RPATH}"
      -D "CMAKE_INSTALL_RPATH_USE_LINK_PATH=TRUE"
    )
  fi
  if [[ ${#INITIAL_CMAKE_ARGS[@]} -gt 0 ]]; then
    configure_cmd+=("${INITIAL_CMAKE_ARGS[@]}")
  fi
  echo "[INFO] disable_tests=${DISABLE_TESTS_RAW} disable_gui=${DISABLE_GUI_RAW}"
  printf '[INFO] configure_cmd:'
  printf ' %q' "${configure_cmd[@]}"
  printf '\n'
  "${configure_cmd[@]}"
fi

echo "[INFO] Reusing existing OpenROAD build tree with ${THREADS} threads."
echo "[INFO] orfs_root=${ROOT_DIR}"
echo "[INFO] build_root=${BUILD_ROOT}"
echo "[INFO] build_dir=${BUILD_DIR}"
echo "[INFO] install_bin=${INSTALL_BIN}"
echo "[INFO] incremental_targets=${INCREMENTAL_TARGETS[*]}"
if [[ -n "${CORE_ROOT_RAW}" ]]; then
  echo "[INFO] core_root=${CORE_ROOT}"
fi
cmake --build "${BUILD_DIR}" --target "${INCREMENTAL_TARGETS[@]}" -j "${THREADS}"

case "${INSTALL_MODE}" in
  binaries)
    mkdir -p "$(dirname "${INSTALL_BIN}")" "${INSTALL_ROOT}/bin"
    if [[ ! -x "${BUILD_DIR}/bin/openroad" ]]; then
      echo "[ERROR] Built OpenROAD binary missing: ${BUILD_DIR}/bin/openroad" >&2
      exit 1
    fi
    cp -p "${BUILD_DIR}/bin/openroad" "${INSTALL_BIN}"
    if [[ -x "${BUILD_DIR}/src/sta/sta" ]]; then
      cp -p "${BUILD_DIR}/src/sta/sta" "${INSTALL_ROOT}/bin/sta"
    fi
    ;;
  cmake)
    cmake --install "${BUILD_DIR}" --prefix "${INSTALL_ROOT}"
    ;;
  *)
    echo "[ERROR] Unknown OPENROAD_INSTALL_MODE=${INSTALL_MODE}; expected binaries or cmake." >&2
    exit 1
    ;;
esac

if [[ ! -x "${INSTALL_BIN}" ]]; then
  echo "[ERROR] OpenROAD binary missing after install target: ${INSTALL_BIN}" >&2
  exit 1
fi

echo "[INFO] OpenROAD-only build complete: ${INSTALL_BIN}"

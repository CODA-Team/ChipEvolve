#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${OPENROAD_BUILD_DIR:-${ROOT_DIR}/tools/OpenROAD/build}"
INSTALL_ROOT="${OPENROAD_INSTALL_ROOT:-${ROOT_DIR}/tools/install/OpenROAD}"
INSTALL_BIN="${OPENROAD_BINARY:-${INSTALL_ROOT}/bin/openroad}"
THREADS="${1:-8}"
INCREMENTAL_TARGETS_RAW="${OPENROAD_INCREMENTAL_TARGETS:-dpl_evolve_lib dpl_evolve openroad}"

read -r -a INCREMENTAL_TARGETS <<< "${INCREMENTAL_TARGETS_RAW}"

if [[ ! -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  echo "[INFO] OpenROAD build tree is missing; falling back to ./build_openroad.sh --local"
  exec "${ROOT_DIR}/build_openroad.sh" --local --threads "${THREADS}"
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

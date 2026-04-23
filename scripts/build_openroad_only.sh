#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${OPENROAD_BUILD_DIR:-${ROOT_DIR}/tools/OpenROAD/build}"
INSTALL_ROOT="${OPENROAD_INSTALL_ROOT:-${ROOT_DIR}/tools/install/OpenROAD}"
INSTALL_BIN="${OPENROAD_BINARY:-${INSTALL_ROOT}/bin/openroad}"
THREADS="${1:-8}"

if [[ ! -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  echo "[INFO] OpenROAD build tree is missing; falling back to ./build_openroad.sh --local"
  exec "${ROOT_DIR}/build_openroad.sh" --local --threads "${THREADS}"
fi

echo "[INFO] Building OpenROAD only via CMake install target with ${THREADS} threads."
echo "[INFO] build_dir=${BUILD_DIR}"
echo "[INFO] install_bin=${INSTALL_BIN}"
cmake --build "${BUILD_DIR}" -j "${THREADS}"
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_ROOT}"

if [[ ! -x "${INSTALL_BIN}" ]]; then
  echo "[ERROR] OpenROAD binary missing after install target: ${INSTALL_BIN}" >&2
  exit 1
fi

echo "[INFO] OpenROAD-only build complete: ${INSTALL_BIN}"

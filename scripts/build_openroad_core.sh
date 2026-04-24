#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"
dpl_init_runtime "build_openroad_core.sh"

THREADS="${1:-8}"
OPENROAD_SRC="${ORFS_ROOT}/tools/OpenROAD"
OPENROAD_ANCHOR_ID="$(git -C "${OPENROAD_SRC}" rev-parse --short HEAD)"
CORE_ROOT="${OPENROAD_CORE_ROOT:-${DPL_EVOLVE_STATE_ROOT}/openroad_core/${OPENROAD_ANCHOR_ID}}"

export OPENROAD_CORE_ROOT="${CORE_ROOT}"
export OPENROAD_BUILD_DIR="${OPENROAD_BUILD_DIR:-${CORE_ROOT}/build}"
export OPENROAD_INSTALL_ROOT="${OPENROAD_INSTALL_ROOT:-${CORE_ROOT}/install/OpenROAD}"
export OPENROAD_BINARY="${OPENROAD_BINARY:-${OPENROAD_INSTALL_ROOT}/bin/openroad}"

"${SCRIPT_DIR}/build_openroad_only.sh" "${THREADS}"

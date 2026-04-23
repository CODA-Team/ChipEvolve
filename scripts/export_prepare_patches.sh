#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_ROOT="${1:-/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts}"
ANCHORS_JSON="${AGENT_ROOT}/metadata/anchors.json"

SOURCE_ROOT="$(realpath -m "${SOURCE_ROOT}")"

if [[ ! -d "${SOURCE_ROOT}/.git" ]]; then
  echo "[ERROR] Source ORFS repo not found: ${SOURCE_ROOT}" >&2
  exit 1
fi

mkdir -p "${AGENT_ROOT}/patches"

mapfile -t anchor_values < <(
  python3 - <<'PY' "${ANCHORS_JSON}"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data["workspace_model"]["orfs_base_commit"])
print(data["workspace_model"]["openroad_base_commit"])
PY
)

orfs_base_commit="${anchor_values[0]}"
openroad_base_commit="${anchor_values[1]}"

git -C "${SOURCE_ROOT}" diff "${orfs_base_commit}"..HEAD -- .gitmodules flow/Makefile > "${AGENT_ROOT}/patches/orfs_overlay.patch"
git -C "${SOURCE_ROOT}/tools/OpenROAD" diff "${openroad_base_commit}"..HEAD -- src/CMakeLists.txt src/dpl_evolve > "${AGENT_ROOT}/patches/openroad_dpl_evolve_base.patch"

echo "[INFO] Refreshed:"
echo "[INFO]   ${AGENT_ROOT}/patches/orfs_overlay.patch"
echo "[INFO]   ${AGENT_ROOT}/patches/openroad_dpl_evolve_base.patch"

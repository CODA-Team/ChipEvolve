#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ANCHORS_JSON="${AGENT_ROOT}/metadata/anchors.json"

default_source_root=""
if [[ -d "${AGENT_ROOT}/../.git" \
   && -d "${AGENT_ROOT}/../flow" \
   && -d "${AGENT_ROOT}/../tools/OpenROAD" ]]; then
  default_source_root="$(cd "${AGENT_ROOT}/.." && pwd)"
fi

SOURCE_ROOT="${1:-${default_source_root}}"

if [[ -z "${SOURCE_ROOT}" ]]; then
  echo "[ERROR] Missing source ORFS repo root." >&2
  echo "[ERROR] Pass it explicitly, for example:" >&2
  echo "[ERROR]   ${0} /path/to/OpenROAD-flow-scripts" >&2
  exit 1
fi

SOURCE_ROOT="$(realpath -m "${SOURCE_ROOT}")"

if [[ ! -d "${SOURCE_ROOT}/.git" ]]; then
  echo "[ERROR] Source ORFS repo not found: ${SOURCE_ROOT}" >&2
  exit 1
fi

mkdir -p "${AGENT_ROOT}/patches"

for required_tool in filterdiff recountdiff; do
  if ! command -v "${required_tool}" >/dev/null 2>&1; then
    echo "[ERROR] Missing required patchutils tool: ${required_tool}" >&2
    exit 1
  fi
done

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

: > "${AGENT_ROOT}/patches/orfs_overlay.patch"
raw_openroad_patch="$(mktemp)"
filtered_openroad_patch="$(mktemp)"
trap 'rm -f "${raw_openroad_patch}" "${filtered_openroad_patch}"' EXIT

git -C "${SOURCE_ROOT}/tools/OpenROAD" diff "${openroad_base_commit}" -- \
  include/ord/OpenRoad.hh \
  include/ord/Design.h \
  src/OpenRoad.cc \
  src/Design.cc \
  src/Main.cc \
  src/CMakeLists.txt \
  src/dpl_evolve \
  ':(exclude)src/dpl_evolve/test' \
  ':(exclude)src/dpl_evolve/test/**' \
  > "${raw_openroad_patch}"

filterdiff -p1 -x 'src/dpl_evolve/test/*' "${raw_openroad_patch}" \
  | awk '
      /^diff --git / {
        skip = ($0 ~ / a\/src\/dpl_evolve\/test(\/| |$)/ || $0 ~ / b\/src\/dpl_evolve\/test(\/| |$)/)
      }
      !skip { print }
    ' \
  | sed \
      -e '/^\+test\/results$/d' \
      -e 's/^\+command set, its own regression suite, and a baseline sandbox/+command set, and a baseline sandbox/' \
      -e '/^\+- \[`test\/`\](\.\/test): independent CTest \/ Python \/ Tcl regression suite\.$/d' \
      -e '/^\+# Keep dpl_evolve tests in a separate target\/test namespace so they can$/,/^\+endif()$/d' \
      -e 's/^\+## How to build and test$/+## How to build/' \
      -e '/^\+List the independent `dpl_evolve` regressions from$/,/^\+```$/d' \
      -e '/^\+Run one focused smoke regression:$/,/^\+```$/d' \
  > "${filtered_openroad_patch}"

recountdiff "${filtered_openroad_patch}" \
  > "${AGENT_ROOT}/patches/openroad_dpl_evolve_base.patch"

echo "[INFO] Refreshed:"
echo "[INFO]   ${AGENT_ROOT}/patches/orfs_overlay.patch"
echo "[INFO]   ${AGENT_ROOT}/patches/openroad_dpl_evolve_base.patch"

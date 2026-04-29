#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ "${DPL_EVOLVE_SKIP_ENV_SH:-0}" != "1" && -f "${AGENT_ROOT}/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${AGENT_ROOT}/env.sh"
fi

DEFAULT_ORFS_ROOT="${ORFS_ROOT:-$(realpath -m "${AGENT_ROOT}/../OpenROAD-flow-scripts")}"
DEFAULT_STATE_ROOT="${DPL_EVOLVE_STATE_ROOT:-${AGENT_ROOT}/.dpl_evolve_state}"

orfs_root="${DEFAULT_ORFS_ROOT}"
variant_root="${DEFAULT_STATE_ROOT}/variants/default"
dpl_src=""
seed_src_override=""
start_kind="framework"
force=0

usage() {
  cat <<'EOF'
Usage: create_variant_start.sh [options]

Create the initial private dpl_evolve source tree for one experiment variant.

This copies one prepared seed source:
  framework: $DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve
  diamond:   $DPL_EVOLVE_STATE_ROOT/seed_sources/diamond_dpl_evolve
  prepared:  $ORFS_ROOT/tools/OpenROAD/src/dpl_evolve

into:
  <variant-root>/dpl_evolve

The seed snapshots are produced by prepare_workspace.sh.  By default this
script preserves an existing variant source tree; pass --force only when
resetting that variant is intentional.

Options:
  --orfs-root PATH       Prepared ORFS workspace root.
  --variant-root PATH    Variant root. Default: $DPL_EVOLVE_STATE_ROOT/variants/default.
  --dpl-src PATH         Destination dpl_evolve source path.
                         Default: <variant-root>/dpl_evolve.
  --start-kind KIND      Seed type: framework, diamond, or prepared.
                         Default: framework.
  --seed-src PATH        Source dpl_evolve tree to copy instead of the prepared
                         ORFS root seed.  Useful for continuing from a
                         best-so-far elite source backup.
  --force                Replace destination if it already exists.
  --help                 Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --orfs-root)
      orfs_root="$2"
      shift 2
      ;;
    --variant-root)
      variant_root="$2"
      shift 2
      ;;
    --dpl-src)
      dpl_src="$2"
      shift 2
      ;;
    --start-kind)
      start_kind="$2"
      shift 2
      ;;
    --seed-src)
      seed_src_override="$2"
      shift 2
      ;;
    --force)
      force=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

orfs_root="$(realpath -m "${orfs_root}")"
state_root="$(realpath -m "${DEFAULT_STATE_ROOT}")"
variant_root="$(realpath -m "${variant_root}")"
if [[ -z "${dpl_src}" ]]; then
  dpl_src="${variant_root}/dpl_evolve"
fi
dpl_src="$(realpath -m "${dpl_src}")"

if [[ -n "${seed_src_override}" ]]; then
  seed_src="$(realpath -m "${seed_src_override}")"
else
  case "${start_kind}" in
    framework)
      seed_src="${state_root}/seed_sources/framework_dpl_evolve"
      ;;
    diamond)
      seed_src="${state_root}/seed_sources/diamond_dpl_evolve"
      ;;
    prepared)
      seed_src="${orfs_root}/tools/OpenROAD/src/dpl_evolve"
      ;;
    *)
      echo "[ERROR] Unsupported --start-kind: ${start_kind}" >&2
      echo "[ERROR] Expected one of: framework, diamond, prepared" >&2
      exit 1
      ;;
  esac
  seed_src="$(realpath -m "${seed_src}")"
fi
if [[ ! -f "${seed_src}/CMakeLists.txt" ]]; then
  echo "[ERROR] Missing prepared dpl_evolve seed source: ${seed_src}" >&2
  echo "[ERROR] Run scripts/prepare_workspace.sh before creating variants." >&2
  exit 1
fi
if [[ "${start_kind}" == "framework" && -z "${seed_src_override}" && ! -f "${seed_src}/src/EvolveLegalizer.cpp" ]]; then
  echo "[ERROR] Prepared seed source lacks EvolveLegalizer.cpp: ${seed_src}" >&2
  exit 1
fi
if [[ "${start_kind}" == "framework" && -z "${seed_src_override}" && ! -f "${seed_src}/src/LegalmGuidance.cpp" ]]; then
  echo "[ERROR] Prepared seed source lacks LegalmGuidance.cpp: ${seed_src}" >&2
  exit 1
fi

if [[ -e "${dpl_src}" ]]; then
  if [[ "${force}" -ne 1 ]]; then
    echo "[INFO] Variant source already exists, preserving: ${dpl_src}"
    echo "[INFO] Pass --force to reset it from the prepared seed."
    exit 0
  fi
  rm -rf "${dpl_src}"
fi

mkdir -p "$(dirname "${dpl_src}")"
rsync -a --delete "${seed_src}/" "${dpl_src}/"

echo "[INFO] Created variant initial dpl_evolve source"
echo "[INFO] start_kind=${start_kind}"
echo "[INFO] seed_src=${seed_src}"
echo "[INFO] dpl_src=${dpl_src}"

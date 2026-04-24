#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="${DPL_EVOLVE_AGENT_ROOT:-$(realpath -m "${SCRIPT_DIR}/..")}"
DEFAULT_MOUNT_DIR="${AGENT_ROOT}/.mounted_orfs"

workspace_root=""
mount_dir="${DEFAULT_MOUNT_DIR}"

usage() {
  cat <<EOF
Usage: attach_orfs_workspace.sh --workspace-root PATH [--mount-dir PATH]

Create or update a local symlink from this standalone agent repo to an ORFS
workspace. The default ignored mount point is:

  ${DEFAULT_MOUNT_DIR}

Examples:
  ${SCRIPT_DIR}/attach_orfs_workspace.sh --workspace-root /abs/path/to/OpenROAD-flow-scripts
  ${SCRIPT_DIR}/attach_orfs_workspace.sh --workspace-root /abs/path/to/OpenROAD-flow-scripts --mount-dir ${AGENT_ROOT}/orfs
EOF
}

is_orfs_root() {
  local candidate="$1"
  [[ -d "${candidate}/flow" && -d "${candidate}/tools/OpenROAD" ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace-root)
      workspace_root="$2"
      shift 2
      ;;
    --mount-dir)
      mount_dir="$2"
      shift 2
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

if [[ -z "${workspace_root}" ]]; then
  echo "[ERROR] --workspace-root is required." >&2
  usage >&2
  exit 1
fi

workspace_root="$(realpath -m "${workspace_root}")"
mount_dir_parent="$(realpath -m "$(dirname "${mount_dir}")")"
mount_dir="${mount_dir_parent}/$(basename "${mount_dir}")"

if ! is_orfs_root "${workspace_root}"; then
  echo "[ERROR] Not an ORFS workspace: ${workspace_root}" >&2
  echo "[ERROR] Expected flow/ and tools/OpenROAD/ under the target root." >&2
  exit 1
fi

mkdir -p "$(dirname "${mount_dir}")"
rm -rf "${mount_dir}"
ln -s "${workspace_root}" "${mount_dir}"

echo "[INFO] Attached ORFS workspace"
echo "[INFO] agent_root=${AGENT_ROOT}"
echo "[INFO] workspace_root=${workspace_root}"
echo "[INFO] mount_dir=${mount_dir}"
echo "[INFO] export ORFS_ROOT=${workspace_root}"

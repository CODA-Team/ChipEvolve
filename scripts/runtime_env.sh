#!/usr/bin/env bash
set -euo pipefail

_dpl_is_orfs_root() {
  local candidate="$1"
  [[ -d "${candidate}/flow" && -d "${candidate}/tools/OpenROAD" ]]
}

_dpl_default_mount_root() {
  local agent_root="$1"
  printf '%s\n' "${agent_root}/.mounted_orfs"
}

_dpl_contains_space() {
  [[ "$1" == *" "* ]]
}

_dpl_path_id() {
  if command -v sha1sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha1sum | awk '{print $1}'
  else
    printf '%s' "$1" | cksum | awk '{print $1}'
  fi
}

_dpl_lexical_alias_path() {
  local raw="$1"
  local parent base
  parent="$(dirname "${raw}")"
  base="$(basename "${raw}")"
  parent="$(realpath -m "${parent}")"
  printf '%s/%s\n' "${parent%/}" "${base}"
}

_dpl_symlink_target() {
  local link_path="$1"
  local target
  target="$(readlink "${link_path}")"
  if [[ "${target}" = /* ]]; then
    realpath -m "${target}"
  else
    realpath -m "$(dirname "${link_path}")/${target}"
  fi
}

_dpl_stable_alias_root() {
  local alias_path parent path_id

  if [[ -n "${DPL_EVOLVE_ORFS_ALIAS_ROOT:-}" ]]; then
    alias_path="$(_dpl_lexical_alias_path "${DPL_EVOLVE_ORFS_ALIAS_ROOT}")"
  elif ! _dpl_contains_space "${DPL_EVOLVE_STATE_ROOT}"; then
    alias_path="$(_dpl_lexical_alias_path "${DPL_EVOLVE_STATE_ROOT}/orfs_mount")"
  else
    path_id="$(_dpl_path_id "${ORFS_ROOT}")"
    alias_path="$(_dpl_lexical_alias_path "${HOME}/.cache/dpl_evolve_agent/orfs_mounts/${path_id}/orfs_workspace")"
  fi

  parent="$(dirname "${alias_path}")"
  mkdir -p "${parent}"

  if [[ -L "${alias_path}" ]]; then
    if [[ "$(_dpl_symlink_target "${alias_path}")" != "${ORFS_ROOT}" ]]; then
      rm -f "${alias_path}"
      ln -s "${ORFS_ROOT}" "${alias_path}"
    fi
  elif [[ -e "${alias_path}" ]]; then
    if ! _dpl_is_orfs_root "${alias_path}"; then
      echo "[ERROR] Stable ORFS alias path exists but is not an ORFS workspace: ${alias_path}" >&2
      return 1
    fi
  else
    ln -s "${ORFS_ROOT}" "${alias_path}"
  fi

  printf '%s\n' "${alias_path}"
}

dpl_resolve_agent_root() {
  if [[ -n "${DPL_EVOLVE_AGENT_ROOT:-}" ]]; then
    realpath -m "${DPL_EVOLVE_AGENT_ROOT}"
    return 0
  fi
  local helper_dir
  helper_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  realpath -m "${helper_dir}/.."
}

dpl_init_runtime() {
  local script_name="${1:-script}"
  local agent_root candidate

  agent_root="$(dpl_resolve_agent_root)"
  export DPL_EVOLVE_AGENT_ROOT="${agent_root}"

  if [[ -n "${ORFS_ROOT:-}" ]]; then
    candidate="$(realpath -m "${ORFS_ROOT}")"
    if ! _dpl_is_orfs_root "${candidate}"; then
      echo "[ERROR] ${script_name} expected ORFS_ROOT to point at an ORFS workspace, got: ${candidate}" >&2
      return 1
    fi
    export ORFS_ROOT="${candidate}"
  elif _dpl_is_orfs_root "$(_dpl_default_mount_root "${agent_root}")"; then
    export ORFS_ROOT="$(_dpl_default_mount_root "${agent_root}")"
  else
    echo "[ERROR] ${script_name} could not locate an ORFS workspace." >&2
    echo "[ERROR] Set ORFS_ROOT to a workspace containing flow/ and tools/OpenROAD/." >&2
    echo "[ERROR] Or attach one under \$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs via scripts/attach_orfs_workspace.sh." >&2
    return 1
  fi

  if [[ -n "${DPL_EVOLVE_STATE_ROOT:-}" ]]; then
    export DPL_EVOLVE_STATE_ROOT="$(realpath -m "${DPL_EVOLVE_STATE_ROOT}")"
  else
    export DPL_EVOLVE_STATE_ROOT="${ORFS_ROOT}/.dpl_evolve_state"
  fi

  export DPL_EVOLVE_PACKET_DIR="${DPL_EVOLVE_STATE_ROOT}/packets"
  export DPL_EVOLVE_CHECKPOINTS_DIR="${DPL_EVOLVE_STATE_ROOT}/checkpoints"
  export DPL_EVOLVE_OPERATIONS_DIR="${DPL_EVOLVE_CHECKPOINTS_DIR}/operations"

  if _dpl_contains_space "${ORFS_ROOT}"; then
    export ORFS_BUILD_ROOT="$(_dpl_stable_alias_root)"
  else
    export ORFS_BUILD_ROOT="${ORFS_ROOT}"
  fi
}

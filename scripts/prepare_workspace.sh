#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_WORKSPACE_ROOT="$(cd "${AGENT_ROOT}/.." && pwd)"

workspace_root="${DEFAULT_WORKSPACE_ROOT}"
orfs_branch=""
openroad_branch=""
skip_commit=0
force=0

usage() {
  cat <<'EOF'
Usage: prepare_workspace.sh [options]

Bootstrap a clean ORFS/OpenROAD workspace for dpl_evolve experiments.

Actions:
  1. Create a local ORFS branch from the supported ORFS anchor.
  2. Create a local OpenROAD branch from the supported OpenROAD anchor.
  3. Apply the ORFS/OpenROAD prepare patches if needed.
  4. Create local commits for the prepared states unless --skip-commit is used.

Options:
  --workspace-root PATH   ORFS workspace root. Default: parent of this repo.
  --orfs-branch NAME      Local ORFS branch name.
  --openroad-branch NAME  Local OpenROAD branch name.
  --skip-commit           Do not create local commits after patching.
  --force                 Reset branches even if they already exist.
  --help                  Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace-root)
      workspace_root="$2"
      shift 2
      ;;
    --orfs-branch)
      orfs_branch="$2"
      shift 2
      ;;
    --openroad-branch)
      openroad_branch="$2"
      shift 2
      ;;
    --skip-commit)
      skip_commit=1
      shift
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

workspace_root="$(realpath -m "${workspace_root}")"
anchors_json="${AGENT_ROOT}/metadata/anchors.json"
orfs_patch="${AGENT_ROOT}/patches/orfs_overlay.patch"
orfs_make_patch="${AGENT_ROOT}/patches/orfs_make_overlay.patch"
openroad_patch="${AGENT_ROOT}/patches/openroad_dpl_evolve_base.patch"
agent_remote_url="$(git -C "${AGENT_ROOT}" remote get-url origin 2>/dev/null || true)"
agent_target_ref="$(git -C "${AGENT_ROOT}" rev-parse HEAD)"

if [[ ! -d "${workspace_root}/.git" ]]; then
  echo "[ERROR] workspace root is not a git repository: ${workspace_root}" >&2
  exit 1
fi

if [[ ! -d "${workspace_root}/tools/OpenROAD" ]]; then
  echo "[ERROR] Missing OpenROAD checkout at ${workspace_root}/tools/OpenROAD" >&2
  exit 1
fi

mapfile -t anchor_values < <(
  python3 - <<'PY' "${anchors_json}"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
print(data["workspace_model"]["orfs_base_commit"])
print(data["workspace_model"]["openroad_base_commit"])
PY
)

orfs_base_commit="${anchor_values[0]}"
openroad_base_commit="${anchor_values[1]}"

stamp="$(date +%Y%m%d_%H%M%S)"
orfs_branch="${orfs_branch:-dpl_evolve_agent_prepare_${stamp}}"
openroad_branch="${openroad_branch:-dpl_evolve_agent_prepare_${stamp}}"

ensure_clean_or_reset() {
  local repo_root="$1"
  local target_branch="$2"
  local target_commit="$3"
  local label="$4"

  if [[ "${force}" -ne 1 ]]; then
    if [[ -n "$(git -C "${repo_root}" status --short)" ]]; then
      echo "[ERROR] ${label} repo has local changes: ${repo_root}" >&2
      echo "[ERROR] Re-run with --force only if it is safe to reset the branch." >&2
      exit 1
    fi
  fi

  if git -C "${repo_root}" show-ref --verify --quiet "refs/heads/${target_branch}"; then
    if [[ "${force}" -ne 1 ]]; then
      echo "[ERROR] Branch already exists in ${label}: ${target_branch}" >&2
      echo "[ERROR] Re-run with --force to reset it." >&2
      exit 1
    fi
  fi

  git -C "${repo_root}" checkout -B "${target_branch}" "${target_commit}"
}

apply_patch_if_needed() {
  local repo_root="$1"
  local patch_file="$2"
  local label="$3"

  if [[ ! -s "${patch_file}" ]]; then
    echo "[INFO] ${label}: patch file is empty, skipping ${patch_file}"
    return
  fi

  if git -C "${repo_root}" apply --check "${patch_file}" >/dev/null 2>&1; then
    git -C "${repo_root}" apply "${patch_file}"
    echo "[INFO] ${label}: applied $(basename "${patch_file}")"
    return
  fi

  if git -C "${repo_root}" apply --reverse --check "${patch_file}" >/dev/null 2>&1; then
    echo "[INFO] ${label}: patch already present, skipping $(basename "${patch_file}")"
    return
  fi

  echo "[ERROR] ${label}: patch does not apply cleanly: ${patch_file}" >&2
  exit 1
}

commit_if_dirty() {
  local repo_root="$1"
  local message="$2"
  shift 2
  if [[ "${skip_commit}" -eq 1 ]]; then
    return
  fi
  if [[ -n "$(git -C "${repo_root}" status --short)" ]]; then
    if [[ $# -gt 0 ]]; then
      git -C "${repo_root}" add -A -- "$@"
    elif [[ "${repo_root}" == "${workspace_root}" ]]; then
      git -C "${repo_root}" add -A -- . \
        ":(exclude)evolve_agent" \
        ":(exclude)evolve_agent/**" \
        ":(exclude)tools/OpenROAD" \
        ":(exclude)tools/OpenROAD/**"
    else
      git -C "${repo_root}" add -A
    fi
    git -C "${repo_root}" commit -m "${message}"
  fi
}

ensure_agent_submodule() {
  local repo_root="$1"
  local agent_path="${repo_root}/evolve_agent"

  if [[ -z "${agent_remote_url}" ]]; then
    echo "[ERROR] Could not resolve dpl_evolve_agent origin URL from ${AGENT_ROOT}" >&2
    exit 1
  fi

  if ! git -C "${repo_root}" config -f .gitmodules --get-regexp '^submodule\\.evolve_agent\\.path$' >/dev/null 2>&1; then
    rm -rf "${agent_path}"
    git -C "${repo_root}" submodule add -f "${agent_remote_url}" evolve_agent
  else
    git -C "${repo_root}" submodule sync -- evolve_agent
    git -C "${repo_root}" submodule update --init evolve_agent
  fi

  git -C "${agent_path}" fetch origin main
  git -C "${agent_path}" checkout "${agent_target_ref}" >/dev/null 2>&1 \
    || git -C "${agent_path}" checkout origin/main
}

ensure_clean_or_reset "${workspace_root}" "${orfs_branch}" "${orfs_base_commit}" "ORFS"
ensure_clean_or_reset "${workspace_root}/tools/OpenROAD" "${openroad_branch}" "${openroad_base_commit}" "OpenROAD"

# After pinning the ORFS/OpenROAD anchors, sync nested submodules so OpenROAD
# sources and bundled dependencies (for example src/sta) match the selected
# base commit before we apply any prepare patches.
git -C "${workspace_root}" submodule sync --recursive
git -C "${workspace_root}" submodule update --init --recursive tools/OpenROAD
git -C "${workspace_root}/tools/OpenROAD" submodule sync --recursive
git -C "${workspace_root}/tools/OpenROAD" submodule update --init --recursive

apply_patch_if_needed "${workspace_root}" "${orfs_patch}" "ORFS"
apply_patch_if_needed "${workspace_root}" "${orfs_make_patch}" "ORFS"
apply_patch_if_needed "${workspace_root}/tools/OpenROAD" "${openroad_patch}" "OpenROAD"
ensure_agent_submodule "${workspace_root}"

commit_if_dirty "${workspace_root}/tools/OpenROAD" "Prepare clean dpl_evolve base"
commit_if_dirty "${workspace_root}" "Prepare ORFS overlay for dpl_evolve_agent" flow/Makefile .gitmodules evolve_agent

echo "[INFO] prepare complete"
echo "[INFO] workspace_root=${workspace_root}"
echo "[INFO] orfs_branch=${orfs_branch}"
echo "[INFO] openroad_branch=${openroad_branch}"

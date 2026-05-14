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
start_kind="evolved_legalm"
force=0
git_branch=""

usage() {
  cat <<'EOF'
Usage: create_variant_start.sh [options]

Create the initial private dpl_evolve source tree for one experiment variant.

This copies one prepared seed source:
  framework:    $DPL_EVOLVE_STATE_ROOT/seed_sources/framework_dpl_evolve
  diamond:      $DPL_EVOLVE_STATE_ROOT/seed_sources/diamond_dpl_evolve
  evolved_diamond:     $DPL_EVOLVE_STATE_ROOT/seed_sources/evolved_diamond_dpl_evolve
  evolved_legalm:      $DPL_EVOLVE_STATE_ROOT/seed_sources/evolved_legalm_dpl_evolve
  evolved_negotiation: $DPL_EVOLVE_STATE_ROOT/seed_sources/evolved_negotiation_dpl_evolve
  prepared:     $ORFS_ROOT/tools/OpenROAD/src/dpl_evolve

into:
  <variant-root>/dpl_evolve

The seed snapshots are produced by prepare_workspace.sh.  By default this
script preserves an existing variant source tree; pass --force only when
resetting that variant is intentional.
The destination is initialized as a local git repository so every agent
iteration can be recorded as a source commit instead of a copied backup tree.

Options:
  --orfs-root PATH       Prepared ORFS workspace root.
  --variant-root PATH    Variant root. Default: $DPL_EVOLVE_STATE_ROOT/variants/default.
  --dpl-src PATH         Destination dpl_evolve source path.
                         Default: <variant-root>/dpl_evolve.
  --start-kind KIND      Seed type: framework, diamond,
                         evolved_diamond, evolved_legalm,
                         evolved_negotiation, or prepared.
                         Default: evolved_legalm.
  --seed-src PATH        Source dpl_evolve tree to copy instead of the prepared
                         ORFS root seed.  Useful for continuing from a
                         best-so-far elite source commit export.
  --git-branch NAME      Switch/create this local branch after seeding.
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
    --git-branch)
      git_branch="$2"
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

orfs_root="$(realpath -m "${orfs_root}")"
state_root="$(realpath -m "${DEFAULT_STATE_ROOT}")"
variant_root="$(realpath -m "${variant_root}")"
if [[ -z "${dpl_src}" ]]; then
  dpl_src="${variant_root}/dpl_evolve"
fi
dpl_src="$(realpath -m "${dpl_src}")"

file_sha256() {
  python3 - "$1" <<'PY'
import hashlib
import pathlib
import sys

print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

validate_evolved_seed() {
  local expected_seed="$1"
  local expected_patch="$2"
  local manifest="${seed_src}/.dpl_evolve_seed_manifest.json"
  local expected_sha

  if [[ ! -f "${manifest}" ]]; then
    echo "[ERROR] Evolved seed lacks materialization manifest: ${manifest}" >&2
    echo "[ERROR] Run scripts/prepare_workspace.sh --force to refresh evolved legalizer seeds." >&2
    exit 1
  fi
  if [[ ! -f "${expected_patch}" ]]; then
    echo "[ERROR] Missing expected evolved framework delta patch: ${expected_patch}" >&2
    exit 1
  fi
  expected_sha="$(file_sha256 "${expected_patch}")"
  python3 - "${manifest}" "${expected_seed}" "${expected_sha}" <<'PY'
import json
import pathlib
import sys

manifest = pathlib.Path(sys.argv[1])
payload = json.loads(manifest.read_text(encoding="utf-8"))
expected_seed = sys.argv[2]
expected_sha = sys.argv[3]
problems = []
if payload.get("seed_name") != expected_seed:
    problems.append(f"seed_name={payload.get('seed_name')!r}")
if payload.get("patch_sha256") != expected_sha:
    problems.append("patch_sha256_mismatch")
if payload.get("apply_base") != "framework_dpl_evolve":
    problems.append(f"apply_base={payload.get('apply_base')!r}")
if payload.get("status") != "materialized":
    problems.append(f"status={payload.get('status')!r}")
if problems:
    raise SystemExit(
        "invalid evolved seed manifest "
        + str(manifest)
        + ": "
        + ", ".join(problems)
    )
PY
  if [[ -d "${state_root}/seed_sources/framework_dpl_evolve" ]] \
      && diff -qr "${seed_src}" "${state_root}/seed_sources/framework_dpl_evolve" >/dev/null 2>&1; then
    echo "[ERROR] Evolved seed is identical to framework seed: ${seed_src}" >&2
    echo "[ERROR] Run scripts/prepare_workspace.sh --force to materialize the evolved legalizer patch." >&2
    exit 1
  fi
}

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
    evolved_diamond)
      seed_src="${state_root}/seed_sources/evolved_diamond_dpl_evolve"
      ;;
    evolved_legalm)
      seed_src="${state_root}/seed_sources/evolved_legalm_dpl_evolve"
      ;;
    evolved_negotiation)
      seed_src="${state_root}/seed_sources/evolved_negotiation_dpl_evolve"
      ;;
    prepared)
      seed_src="${orfs_root}/tools/OpenROAD/src/dpl_evolve"
      ;;
    *)
      echo "[ERROR] Unsupported --start-kind: ${start_kind}" >&2
      echo "[ERROR] Expected one of: framework, diamond, evolved_diamond, evolved_legalm, evolved_negotiation, prepared" >&2
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
if [[ ("${start_kind}" == "framework" || "${start_kind}" == "evolved_diamond" || "${start_kind}" == "evolved_legalm" || "${start_kind}" == "evolved_negotiation") && -z "${seed_src_override}" && ! -f "${seed_src}/src/LegalmGuidance.cpp" ]]; then
  echo "[ERROR] Prepared seed source lacks LegalmGuidance.cpp: ${seed_src}" >&2
  exit 1
fi
if [[ -z "${seed_src_override}" ]]; then
  case "${start_kind}" in
    evolved_diamond)
      validate_evolved_seed \
        "evolved_diamond_dpl_evolve" \
        "${AGENT_ROOT}/patches/evolved_legalizers/openroad_dpl_evolve_diamond_iter30_framework_delta.patch"
      ;;
    evolved_legalm)
      validate_evolved_seed \
        "evolved_legalm_dpl_evolve" \
        "${AGENT_ROOT}/patches/evolved_legalizers/openroad_dpl_evolve_legalm_iter30_framework_delta.patch"
      ;;
    evolved_negotiation)
      validate_evolved_seed \
        "evolved_negotiation_dpl_evolve" \
        "${AGENT_ROOT}/patches/evolved_legalizers/openroad_dpl_evolve_negotiation_iter30_framework_delta.patch"
      ;;
  esac
fi

existing_git_repo=0
switched_existing_branch=0

ensure_local_git_repo() {
  local repo="$1"
  local top
  top="$(git -C "${repo}" rev-parse --show-toplevel 2>/dev/null || true)"
  top="$(realpath -m "${top}")"
  if [[ "${top}" != "$(realpath -m "${repo}")" ]]; then
    echo "[ERROR] ${repo} is not an independent git repo; top-level is ${top}" >&2
    exit 2
  fi
}

init_local_git_repo() {
  local repo="$1"
  if [[ ! -d "${repo}/.git" ]]; then
    git init "${repo}" >/dev/null
  fi
  ensure_local_git_repo "${repo}"
  git -C "${repo}" config user.email "dpl-evolve-agent@example.invalid"
  git -C "${repo}" config user.name "dpl-evolve-agent"
}

if [[ -e "${dpl_src}" ]]; then
  if [[ "${force}" -ne 1 ]]; then
    echo "[INFO] Variant source already exists, preserving: ${dpl_src}"
    if [[ ! -d "${dpl_src}/.git" ]]; then
      init_local_git_repo "${dpl_src}"
      git -C "${dpl_src}" add -A
      if ! git -C "${dpl_src}" diff --cached --quiet; then
        git -C "${dpl_src}" commit -m "Initialize preserved dpl_evolve workspace" >/dev/null
      fi
      echo "[INFO] Initialized local git repo for preserved variant source"
    else
      init_local_git_repo "${dpl_src}"
    fi
    if [[ -n "${git_branch}" ]]; then
      git -C "${dpl_src}" switch -C "${git_branch}" >/dev/null
      echo "[INFO] source_branch=${git_branch}"
    fi
    echo "[INFO] Pass --force to reset it from the prepared seed."
    exit 0
  fi
  if [[ -d "${dpl_src}/.git" ]]; then
    existing_git_repo=1
    init_local_git_repo "${dpl_src}"
    if [[ -n "${git_branch}" ]]; then
      git -C "${dpl_src}" switch -C "${git_branch}" >/dev/null
      switched_existing_branch=1
    fi
    find "${dpl_src}" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  else
    rm -rf "${dpl_src}"
  fi
fi

mkdir -p "$(dirname "${dpl_src}")"
rsync -a --delete --exclude='.git' "${seed_src}/" "${dpl_src}/"
init_local_git_repo "${dpl_src}"
git -C "${dpl_src}" add -A
if ! git -C "${dpl_src}" diff --cached --quiet; then
  git -C "${dpl_src}" commit -m "Seed dpl_evolve ${start_kind} source" >/dev/null
fi
if [[ -n "${git_branch}" && "${switched_existing_branch}" -ne 1 ]]; then
  git -C "${dpl_src}" switch -C "${git_branch}" >/dev/null
fi

display_start_kind="${start_kind}"
if [[ -n "${seed_src_override}" ]]; then
  display_start_kind="custom_seed:$(basename "${seed_src}")"
fi

echo "[INFO] Created variant initial dpl_evolve source"
echo "[INFO] start_kind=${display_start_kind}"
if [[ -n "${seed_src_override}" ]]; then
  echo "[INFO] seed_src_override=1"
  echo "[INFO] seed_src_label=$(basename "${seed_src}")"
  echo "[INFO] requested_start_kind_ignored=${start_kind}"
fi
echo "[INFO] seed_src=${seed_src}"
echo "[INFO] dpl_src=${dpl_src}"
echo "[INFO] source_repo=${dpl_src}"
echo "[INFO] source_repo_top=$(git -C "${dpl_src}" rev-parse --show-toplevel)"
if [[ -n "${git_branch}" ]]; then
  echo "[INFO] source_branch=${git_branch}"
fi

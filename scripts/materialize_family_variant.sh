#!/usr/bin/env bash
set -euo pipefail

resolve_workspace_root() {
  local direct_root env_root
  direct_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [[ -d "${direct_root}/flow" && -d "${direct_root}/tools/OpenROAD" && -d "${direct_root}/evolve_agent" ]]; then
    printf '%s\n' "${direct_root}"
    return 0
  fi
  if [[ -n "${ORFS_ROOT:-}" ]]; then
    env_root="$(realpath -m "${ORFS_ROOT}")"
    if [[ -d "${env_root}/flow" && -d "${env_root}/tools/OpenROAD" && -d "${env_root}/evolve_agent" ]]; then
      printf '%s\n' "${env_root}"
      return 0
    fi
  fi
  return 1
}

if ! ROOT_DIR="$(resolve_workspace_root)"; then
  echo "[ERROR] materialize_family_variant.sh must run inside an ORFS workspace with this repo mounted as evolve_agent/." >&2
  echo "[ERROR] Re-run from the mounted workspace or set ORFS_ROOT to that workspace." >&2
  exit 1
fi

BASE_DPL_EVOLVE_DIR="${ROOT_DIR}/tools/OpenROAD/src/dpl_evolve"
DEFAULT_OUTPUT_ROOT="${ROOT_DIR}/.codex_state/family_variants"

family_id=""
output_dir=""
force=0

usage() {
  cat <<'EOF'
Usage: materialize_family_variant.sh --family FAMILY_ID [--output-dir PATH] [--force]

Materializes a family-specific dpl_evolve source tree from the clean initial
evolve base in tools/OpenROAD/src/dpl_evolve.

Options:
  --family FAMILY_ID      Variant family to materialize. Currently supported:
                          legalm_engine
  --output-dir PATH       Destination directory for the materialized
                          dpl_evolve source tree. Default:
                          .codex_state/family_variants/<family>/dpl_evolve
  --force                 Replace an existing output directory.
  --help                  Show this message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --family)
      family_id="$2"
      shift 2
      ;;
    --output-dir)
      output_dir="$2"
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

if [[ -z "$family_id" ]]; then
  echo "[ERROR] --family is required" >&2
  usage >&2
  exit 1
fi

case "$family_id" in
  legalm_engine)
    patch_file="${ROOT_DIR}/evolve_agent/family_variants/legalm_engine/dpl_evolve.patch"
    ;;
  *)
    echo "[ERROR] Unsupported family: ${family_id}" >&2
    exit 1
    ;;
esac

if [[ ! -f "$patch_file" ]]; then
  echo "[ERROR] Missing family patch: ${patch_file}" >&2
  exit 1
fi

output_dir="${output_dir:-${DEFAULT_OUTPUT_ROOT}/${family_id}/dpl_evolve}"
output_dir="$(realpath -m "$output_dir")"

if [[ -e "$output_dir" ]]; then
  if [[ "$force" -ne 1 ]]; then
    echo "[ERROR] Output already exists: ${output_dir}" >&2
    echo "[ERROR] Re-run with --force to replace it." >&2
    exit 1
  fi
  rm -rf "$output_dir"
fi

mkdir -p "$(dirname "$output_dir")"
cp -a "$BASE_DPL_EVOLVE_DIR" "$output_dir"

git -C "$output_dir" apply "$patch_file"

echo "[INFO] Materialized family variant"
echo "[INFO] family=${family_id}"
echo "[INFO] base=${BASE_DPL_EVOLVE_DIR}"
echo "[INFO] patch=${patch_file}"
echo "[INFO] output=${output_dir}"

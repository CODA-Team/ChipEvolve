#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
openroad_src="${ORFS_ROOT:-}"
out=""
cxx="${CXX:-g++}"

usage() {
  cat <<'EOF'
Usage: build.sh --openroad-src PATH --out PATH

Build the minimal DPL-Evolve V1 shared plugin.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --openroad-src)
      openroad_src="$2"
      shift 2
      ;;
    --out)
      out="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${openroad_src}" || -z "${out}" ]]; then
  usage >&2
  exit 1
fi

openroad_src="$(realpath -sm "${openroad_src}")"
out="$(realpath -sm "${out}")"
api_dir="${openroad_src}/src/dpl_evolve/src"

if [[ ! -f "${api_dir}/EvolvePluginApi.h" ]]; then
  echo "[ERROR] Missing EvolvePluginApi.h under prepared OpenROAD: ${api_dir}" >&2
  exit 1
fi

mkdir -p "$(dirname "${out}")"
"${cxx}" -std=c++17 -O2 -fPIC -shared \
  -I"${api_dir}" \
  "${SCRIPT_DIR}/default_diamond_plugin.cpp" \
  -o "${out}"

echo "[INFO] Built ${out}"

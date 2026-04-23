#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENROAD_SRC="${ROOT_DIR}/tools/OpenROAD"
DEFAULT_VARIANT_ROOT="${ROOT_DIR}/.codex_state/openroad_variants/default"
EXISTING_CACHE="${ROOT_DIR}/tools/OpenROAD/build/CMakeCache.txt"

variant_root="${OPENROAD_VARIANT_ROOT:-$DEFAULT_VARIANT_ROOT}"
build_dir="${OPENROAD_BUILD_DIR:-}"
install_root="${OPENROAD_INSTALL_ROOT:-}"
dpl_evolve_src="${DPL_EVOLVE_SRC_DIR:-}"
generator="${CMAKE_GENERATOR:-}"

usage() {
  cat <<'EOF'
Usage: configure_openroad_variant.sh [options]

Options:
  --variant-root PATH      Root directory for this variant. Default:
                           .codex_state/openroad_variants/default
  --build-dir PATH         Explicit build directory override.
  --install-root PATH      Explicit install root override.
  --dpl-src PATH           External dpl_evolve source directory override.
  --generator NAME         CMake generator. Default: Ninja.
  --help                   Show this message.

Environment fallbacks:
  OPENROAD_VARIANT_ROOT
  OPENROAD_BUILD_DIR
  OPENROAD_INSTALL_ROOT
  DPL_EVOLVE_SRC_DIR
  CMAKE_GENERATOR
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant-root)
      variant_root="$2"
      shift 2
      ;;
    --build-dir)
      build_dir="$2"
      shift 2
      ;;
    --install-root)
      install_root="$2"
      shift 2
      ;;
    --dpl-src)
      dpl_evolve_src="$2"
      shift 2
      ;;
    --generator)
      generator="$2"
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

variant_root="$(realpath -m "$variant_root")"
build_dir="${build_dir:-${variant_root}/build}"
install_root="${install_root:-${variant_root}/install/OpenROAD}"
build_dir="$(realpath -m "$build_dir")"
install_root="$(realpath -m "$install_root")"

if [[ -z "$generator" ]]; then
  if [[ -f "$EXISTING_CACHE" ]]; then
    generator="$(sed -n 's/^CMAKE_GENERATOR:INTERNAL=//p' "$EXISTING_CACHE" | tail -n 1)"
  fi
  generator="${generator:-Unix Makefiles}"
fi

mkdir -p "$build_dir" "$install_root"

cd "$ROOT_DIR"
. dev_env.sh

cmake_args=(
  -S "$OPENROAD_SRC"
  -B "$build_dir"
  -G "$generator"
  -D "CMAKE_INSTALL_PREFIX=${install_root}"
)

if [[ -n "$dpl_evolve_src" ]]; then
  dpl_evolve_src="$(realpath -m "$dpl_evolve_src")"
  if [[ ! -f "${dpl_evolve_src}/CMakeLists.txt" ]]; then
    echo "[ERROR] External dpl_evolve source dir lacks CMakeLists.txt: ${dpl_evolve_src}" >&2
    exit 1
  fi
  cmake_args+=(-D "DPL_EVOLVE_SRC_DIR=${dpl_evolve_src}")
fi

echo "[INFO] Configuring OpenROAD variant"
echo "[INFO] source=${OPENROAD_SRC}"
echo "[INFO] build_dir=${build_dir}"
echo "[INFO] install_root=${install_root}"
if [[ -n "$dpl_evolve_src" ]]; then
  echo "[INFO] dpl_evolve_src=${dpl_evolve_src}"
fi

cmake "${cmake_args[@]}"

echo "[INFO] Variant configure complete"
echo "[INFO] export OPENROAD_BUILD_DIR=${build_dir}"
echo "[INFO] export OPENROAD_INSTALL_ROOT=${install_root}"
echo "[INFO] export OPENROAD_BINARY=${install_root}/bin/openroad"

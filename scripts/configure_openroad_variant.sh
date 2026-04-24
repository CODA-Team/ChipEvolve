#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"
dpl_init_runtime "configure_openroad_variant.sh"

ROOT_DIR="${ORFS_ROOT}"

OPENROAD_SRC="${ROOT_DIR}/tools/OpenROAD"
OPENROAD_ANCHOR_ID="$(git -C "${OPENROAD_SRC}" rev-parse --short HEAD)"
DEFAULT_CORE_ROOT="${DPL_EVOLVE_STATE_ROOT}/openroad_core/${OPENROAD_ANCHOR_ID}"
DEFAULT_VARIANT_ROOT="${DPL_EVOLVE_STATE_ROOT}/variants/default"
EXISTING_CACHE="${ROOT_DIR}/tools/OpenROAD/build/CMakeCache.txt"

variant_root="${OPENROAD_VARIANT_ROOT:-$DEFAULT_VARIANT_ROOT}"
build_dir="${OPENROAD_BUILD_DIR:-}"
install_root="${OPENROAD_INSTALL_ROOT:-}"
dpl_evolve_src="${DPL_EVOLVE_SRC_DIR:-}"
core_root="${OPENROAD_CORE_ROOT:-$DEFAULT_CORE_ROOT}"
generator="${CMAKE_GENERATOR:-}"
disable_tests_raw="${OPENROAD_DISABLE_TESTS:-1}"
disable_gui_raw="${OPENROAD_DISABLE_GUI:-0}"

usage() {
  cat <<'EOF'
Usage: configure_openroad_variant.sh [options]

Options:
  --variant-root PATH      Root directory for this variant. Default:
                           ${DPL_EVOLVE_STATE_ROOT}/variants/default
  --build-dir PATH         Explicit build directory override.
  --install-root PATH      Explicit install root override.
  --dpl-src PATH           External dpl_evolve source directory override.
  --core-root PATH         Common-core seed root. Default:
                           <state>/openroad_core/<openroad-head>
  --generator NAME         CMake generator. Default: reuse existing cache or
                           fall back to Unix Makefiles.
  --help                   Show this message.

Output:
  Writes <variant-root>/variant_env.sh with OPENROAD_BUILD_DIR,
  OPENROAD_INSTALL_ROOT, OPENROAD_BINARY, and optional DPL_EVOLVE_SRC_DIR.

Environment fallbacks:
  OPENROAD_VARIANT_ROOT
  OPENROAD_BUILD_DIR
  OPENROAD_INSTALL_ROOT
  DPL_EVOLVE_SRC_DIR
  OPENROAD_CORE_ROOT
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
    --core-root)
      core_root="$2"
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
core_root="$(realpath -m "$core_root")"
variant_env="${variant_root}/variant_env.sh"

is_truthy() {
  local value="${1,,}"
  [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]
}

seed_from_core_if_needed() {
  local core_build_dir core_install_root
  if [[ -f "${build_dir}/CMakeCache.txt" ]]; then
    return 0
  fi
  core_build_dir="${core_root}/build"
  core_install_root="${core_root}/install/OpenROAD"
  if [[ ! -f "${core_build_dir}/CMakeCache.txt" ]]; then
    return 0
  fi
  if [[ ! -x "${core_install_root}/bin/openroad" ]]; then
    return 0
  fi
  echo "[INFO] Seeding variant build/install from common core"
  echo "[INFO] core_build_dir=${core_build_dir}"
  echo "[INFO] core_install_root=${core_install_root}"
  mkdir -p "${build_dir}" "${install_root}"
  rsync -a --delete "${core_build_dir}/" "${build_dir}/"
  rsync -a --delete "${core_install_root}/" "${install_root}/"
  rm -f "${build_dir}/CMakeCache.txt" "${build_dir}/Makefile" "${build_dir}/cmake_install.cmake"
  if [[ -d "${build_dir}/CMakeFiles" ]]; then
    find "${build_dir}/CMakeFiles" -maxdepth 1 -type f -delete
  fi
}

if [[ -z "$generator" ]]; then
  if [[ -f "$EXISTING_CACHE" ]]; then
    generator="$(sed -n 's/^CMAKE_GENERATOR:INTERNAL=//p' "$EXISTING_CACHE" | tail -n 1)"
  fi
  generator="${generator:-Unix Makefiles}"
fi

mkdir -p "$build_dir" "$install_root"
seed_from_core_if_needed

cd "$ROOT_DIR"
. dev_env.sh

cmake_args=(
  -S "$OPENROAD_SRC"
  -B "$build_dir"
  -G "$generator"
  -D "CMAKE_INSTALL_PREFIX=${install_root}"
  -D "CMAKE_EXPORT_COMPILE_COMMANDS=ON"
)

if [[ -n "$dpl_evolve_src" ]]; then
  dpl_evolve_src="$(realpath -m "$dpl_evolve_src")"
  if [[ ! -f "${dpl_evolve_src}/CMakeLists.txt" ]]; then
    echo "[ERROR] External dpl_evolve source dir lacks CMakeLists.txt: ${dpl_evolve_src}" >&2
    exit 1
  fi
  cmake_args+=(-D "DPL_EVOLVE_SRC_DIR=${dpl_evolve_src}")
fi

if is_truthy "${disable_tests_raw}"; then
  cmake_args+=(-D "ENABLE_TESTS=OFF")
fi
if is_truthy "${disable_gui_raw}"; then
  cmake_args+=(-D "BUILD_GUI=OFF")
fi

echo "[INFO] Configuring OpenROAD variant"
echo "[INFO] source=${OPENROAD_SRC}"
echo "[INFO] build_dir=${build_dir}"
echo "[INFO] install_root=${install_root}"
echo "[INFO] core_root=${core_root}"
echo "[INFO] disable_tests=${disable_tests_raw} disable_gui=${disable_gui_raw}"
if [[ -n "$dpl_evolve_src" ]]; then
  echo "[INFO] dpl_evolve_src=${dpl_evolve_src}"
fi

cmake "${cmake_args[@]}"

{
  echo "#!/usr/bin/env bash"
  echo "# Generated by configure_openroad_variant.sh"
  echo "export OPENROAD_VARIANT_ROOT=$(printf '%q' "${variant_root}")"
  echo "export OPENROAD_CORE_ROOT=$(printf '%q' "${core_root}")"
  echo "export OPENROAD_BUILD_DIR=$(printf '%q' "${build_dir}")"
  echo "export OPENROAD_INSTALL_ROOT=$(printf '%q' "${install_root}")"
  echo "export OPENROAD_BINARY=$(printf '%q' "${install_root}/bin/openroad")"
  if [[ -n "$dpl_evolve_src" ]]; then
    echo "export DPL_EVOLVE_SRC_DIR=$(printf '%q' "${dpl_evolve_src}")"
  fi
} > "${variant_env}"
chmod +x "${variant_env}"

echo "[INFO] Variant configure complete"
echo "[INFO] variant_env=${variant_env}"
echo "[INFO] export OPENROAD_CORE_ROOT=${core_root}"
echo "[INFO] export OPENROAD_BUILD_DIR=${build_dir}"
echo "[INFO] export OPENROAD_INSTALL_ROOT=${install_root}"
echo "[INFO] export OPENROAD_BINARY=${install_root}/bin/openroad"
echo "[INFO] source ${variant_env}"

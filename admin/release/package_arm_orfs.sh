#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 || $(uname -m) != aarch64 ]]; then
    echo 'Usage on Linux aarch64: package_arm_orfs.sh BASE.sif OUTPUT.sif' >&2
    exit 2
fi
base=$(realpath -- "$1")
output=$(realpath -m -- "$2")
test ! -e "$output"

scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
rootfs="$scratch/orfs"
apptainer build --sandbox "$rootfs" "$base"
# The pinned aarch64 dependency installer builds KLayout under /usr/local,
# while ORFS discovers it by executable name on PATH.
test -x "$rootfs/usr/local/klayout"
ln -s ../klayout "$rootfs/usr/local/bin/klayout"
apptainer build "$output" "$rootfs"
apptainer exec --cleanenv --containall "$output" klayout -b -v
sha256sum "$output"

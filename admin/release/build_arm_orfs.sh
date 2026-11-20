#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 || $(uname -m) != aarch64 ]]; then
    echo 'Usage on Linux aarch64: build_arm_orfs.sh NEW_BUILD_DIRECTORY OUTPUT.sif' >&2
    exit 2
fi
build=$(realpath -m -- "$1")
output=$(realpath -m -- "$2")
test ! -e "$output"
mkdir -- "$build"

orfs=5105b0a77fe8b3ae107bed67112eb5f83caca5d5
openroad=27288f5c90265ae5296b2f5a9fa6e8714fa191ad
ubuntu=ubuntu@sha256:2926e8e6ef0b816e19849e33ccc728c72b921a428286e6595d52fa92c5716626
export GIT_TERMINAL_PROMPT=0 GIT_LFS_SKIP_SMUDGE=1
cd -- "$build"
git init -q
git remote add origin https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git
git fetch --depth 1 origin "$orfs"
git checkout --detach FETCH_HEAD
git submodule update --init --recursive --depth 1
test "$(git -C tools/OpenROAD rev-parse HEAD)" = "$openroad"

# ORFS uses an x86-only architecture flag for the Kepler C++ build at this pin.
test "$(grep -c -- '-march=x86-64-v3' build_openroad.sh)" = 1
sed -i 's/-march=x86-64-v3/-march=armv8-a/' build_openroad.sh
git diff -- build_openroad.sh > arm-build.patch

cp tools/OpenROAD/etc/DependencyInstaller.sh etc/InstallerOpenROAD.sh
yosys_version=$(awk -F '"' '/^yosys_ver =/ {print $2}' tools/yosys/docs/source/conf.py)
test -n "$yosys_version"
dev_image=chipevolve-orfs-arm-dev:${orfs:0:12}
image=chipevolve-orfs-arm:${orfs:0:12}
docker buildx build --load --file docker/Dockerfile.dev --tag "$dev_image" \
    --build-arg fromImage="$ubuntu" --build-arg "options=-yosys-ver=v$yosys_version" etc
docker buildx build --load --file docker/Dockerfile.builder --tag "$image" \
    --build-arg fromImage="$dev_image" --build-arg "numThreads=$(nproc)" .
apptainer build "$output" "docker-daemon:$image"
sha256sum "$output"

#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export GIT_LFS_SKIP_SMUDGE=1

goal=agent/goalevolve
git submodule update --init --depth 1 -- . ":(exclude)$goal"
if [[ ! -e "$goal/.git" ]]; then
    git submodule init -- "$goal"
    url=$(git config --get submodule.goalevolve.url)
    branch=$(git config --file .gitmodules --get submodule.goalevolve.branch)
    pin=$(git rev-parse "HEAD:$goal")
    git clone --depth 1 --filter=blob:none --no-checkout --branch "$branch" "$url" "$goal"
    git -C "$goal" sparse-checkout set \
        goalevolve config scripts tests toolchain experiments third_party/official_checker
    if [[ $(git -C "$goal" rev-parse HEAD) != "$pin" ]]; then
        git -C "$goal" fetch --depth 1 --filter=blob:none origin "$pin"
    fi
    git -C "$goal" checkout --detach "$pin"
fi
git submodule absorbgitdirs -- "$goal"
git submodule update --init --depth 1 -- "$goal"

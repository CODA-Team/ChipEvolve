#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
resolve_workspace_root() {
  local direct_root env_root
  direct_root="$(cd "${SCRIPT_DIR}/../.." && pwd)"
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

checkpoint_id=""
checkpoint_title="pre-run checkpoint"
checkpoint_summary="state saved before one bounded Codex iteration"
skip_checkpoint=0
pass_through=()

usage() {
  cat <<'EOF'
Usage: run_codex_loop.sh [options] [-- <run_codex_once args>]

This is a minimal pre-run checkpoint helper:
1. optionally create a local checkpoint
2. call run_codex_once.sh
3. print the next manual checkpoint step

This script does not invoke `codex exec`. It only wraps checkpoint creation
around `run_codex_once.sh`.

Options:
  --checkpoint-id NAME      Create a pre-run checkpoint with this id
  --checkpoint-title TEXT   Optional checkpoint title
  --checkpoint-summary TXT  Optional checkpoint summary
  --skip-checkpoint         Do not create a pre-run checkpoint
  --help                    Show this message

All remaining arguments are passed through to run_codex_once.sh.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkpoint-id) checkpoint_id="$2"; shift 2 ;;
    --checkpoint-title) checkpoint_title="$2"; shift 2 ;;
    --checkpoint-summary) checkpoint_summary="$2"; shift 2 ;;
    --skip-checkpoint) skip_checkpoint=1; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; pass_through+=("$@"); break ;;
    *) pass_through+=("$1"); shift ;;
  esac
done

if ! REPO_ROOT="$(resolve_workspace_root)"; then
  echo "[ERROR] run_codex_loop.sh must run inside an ORFS workspace with this repo mounted as evolve_agent/." >&2
  echo "[ERROR] Re-run from the mounted workspace or set ORFS_ROOT to that workspace." >&2
  exit 1
fi

cd "${REPO_ROOT}"

if [[ "${skip_checkpoint}" != "1" ]]; then
  checkpoint_id="${checkpoint_id:-pre_loop_$(date +%Y%m%d_%H%M%S)}"
  python3 evolve_agent/scripts/checkpoint.py create \
    --checkpoint-id "${checkpoint_id}" \
    --title "${checkpoint_title}" \
    --summary "${checkpoint_summary}"
  echo "[run_codex_loop] Created checkpoint: ${checkpoint_id}"
fi

"${SCRIPT_DIR}/run_codex_once.sh" "${pass_through[@]}"

cat <<EOF
[run_codex_loop] Bounded iteration finished.
[run_codex_loop] Recommended next step:
  python3 evolve_agent/scripts/checkpoint.py create \\
    --checkpoint-id post_run_\$(date +%Y%m%d_%H%M%S) \\
    --title "post-run checkpoint" \\
    --summary "capture state after review of evaluator output"
EOF

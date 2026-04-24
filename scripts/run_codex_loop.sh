#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/runtime_env.sh"
dpl_init_runtime "run_codex_loop.sh"

REPO_ROOT="${ORFS_ROOT}"
AGENT_DIR="${DPL_EVOLVE_AGENT_ROOT}"

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

cd "${REPO_ROOT}"

if [[ "${skip_checkpoint}" != "1" ]]; then
  checkpoint_id="${checkpoint_id:-pre_loop_$(date +%Y%m%d_%H%M%S)}"
  python3 "${AGENT_DIR}/scripts/checkpoint.py" create \
    --checkpoint-id "${checkpoint_id}" \
    --title "${checkpoint_title}" \
    --summary "${checkpoint_summary}"
  echo "[run_codex_loop] Created checkpoint: ${checkpoint_id}"
fi

"${SCRIPT_DIR}/run_codex_once.sh" "${pass_through[@]}"

cat <<EOF
[run_codex_loop] Bounded iteration finished.
[run_codex_loop] Recommended next step:
  python3 "\$DPL_EVOLVE_AGENT_ROOT/scripts/checkpoint.py" create \\
    --checkpoint-id post_run_\$(date +%Y%m%d_%H%M%S) \\
    --title "post-run checkpoint" \\
    --summary "capture state after review of evaluator output"
EOF

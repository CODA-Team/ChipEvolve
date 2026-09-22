#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="$repo_root/tests/fixtures/sample_workspace"
export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"
query_agent=(python -m query_agent)

echo "== Query Agent Phase I demo =="
echo
echo "[A] Experiment metric query"
if [[ -n "${QUERY_AGENT_KERNEL_URL:-}" ]]; then
  "${query_agent[@]}" ask "What is the routing WNS for run_02?" \
    --kernel-url "$QUERY_AGENT_KERNEL_URL" --design gcd --run run_02 --stage routing
else
  echo "No kernel URL; using the bounded local timing artifact instead."
  "${query_agent[@]}" ask "WNS" --workspace "$workspace" --stage routing
fi

echo
echo "[B] Root-cause query with insufficient evidence"
"${query_agent[@]}" ask "Why did timing become worse?" --workspace "$workspace" --run run-1

echo
echo "[C] EDA-Corpus knowledge query"
if [[ -n "${EDA_CORPUS_ROOT:-}" ]]; then
  "${query_agent[@]}" ask "What is global routing?" \
    --workspace "$workspace" --eda-corpus "$EDA_CORPUS_ROOT"
else
  echo "Set EDA_CORPUS_ROOT to a real EDA-Corpus checkout to run this example."
fi

echo
echo "[benchmark]"
"${query_agent[@]}" benchmark "$repo_root/benchmarks/phase1"

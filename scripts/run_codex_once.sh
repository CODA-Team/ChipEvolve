#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

problem_dir="evolve_agent/problems/gcd_nangate45"
packet_dir="evolve_agent/knowledge/packets"
config_path="evolve_agent/configs/codex_smoke.yaml"
eval_out="evolve_agent/checkpoints/latest_eval.json"
mode="single"
line="evolve_line"
flow_variant=""
run_tag=""
tag_prefix=""
threads="8"
evolve_engine="default"
skip_build=0
use_existing=0
dry_run=0
packet_only=0

usage() {
  cat <<'EOF'
Usage: run_codex_once.sh [options]

This is a thin packet-and-evaluator wrapper:
1. build a fresh packet with kb_query.py
2. optionally run evaluator.py for one line or one suite

This script does not invoke `codex exec`.

Options:
  --problem-dir PATH        Problem directory. Default: evolve_agent/problems/gcd_nangate45
  --packet-dir PATH         Packet output directory. Default: evolve_agent/knowledge/packets
  --config PATH             Evaluator config YAML. Default: evolve_agent/configs/codex_smoke.yaml
  --eval-out PATH           Evaluator JSON output. Default: evolve_agent/checkpoints/latest_eval.json
  --mode MODE               single|suite. Default: single
  --line NAME               Single-line target. Default: evolve_line
  --flow-variant NAME       FLOW_VARIANT to reuse or create
  --run-tag NAME            Run tag for single mode
  --tag-prefix NAME         Prefix for suite mode
  --threads N               Worker threads. Default: 8
  --evolve-engine MODE      default|negotiation|negotiation_abacus|legalm. Default: default
  --skip-build              Skip build step in evaluator
  --use-existing            Reuse existing artifacts
  --dry-run                 Resolve commands only
  --packet-only             Only regenerate packet, do not call evaluator
  --help                    Show this message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --problem-dir) problem_dir="$2"; shift 2 ;;
    --packet-dir) packet_dir="$2"; shift 2 ;;
    --config) config_path="$2"; shift 2 ;;
    --eval-out) eval_out="$2"; shift 2 ;;
    --mode) mode="$2"; shift 2 ;;
    --line) line="$2"; shift 2 ;;
    --flow-variant) flow_variant="$2"; shift 2 ;;
    --run-tag) run_tag="$2"; shift 2 ;;
    --tag-prefix) tag_prefix="$2"; shift 2 ;;
    --threads) threads="$2"; shift 2 ;;
    --evolve-engine) evolve_engine="$2"; shift 2 ;;
    --skip-build) skip_build=1; shift ;;
    --use-existing) use_existing=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    --packet-only) packet_only=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "${mode}" in
  single|suite) ;;
  *) echo "Unsupported mode: ${mode}" >&2; exit 1 ;;
esac

problem_dir="${problem_dir#./}"
packet_dir="${packet_dir#./}"
config_path="${config_path#./}"
eval_out="${eval_out#./}"

problem_yaml="${problem_dir}/problem.yaml"

cd "${REPO_ROOT}"

python3 evolve_agent/adapters/science_codeevolve/kb_query.py \
  --problem_dir "${problem_dir}" \
  --out_dir "${packet_dir}"

if [[ "${packet_only}" == "1" ]]; then
  echo "[run_codex_once] Packet refreshed at ${packet_dir}"
  exit 0
fi

cmd=(
  python3
  evolve_agent/adapters/science_codeevolve/evaluator.py
  --problem "${problem_yaml}"
  --config "${config_path}"
  --out "${eval_out}"
  --mode "${mode}"
  --threads "${threads}"
  --evolve-engine "${evolve_engine}"
)

if [[ -n "${flow_variant}" ]]; then
  cmd+=(--flow-variant "${flow_variant}")
fi

if [[ "${mode}" == "single" ]]; then
  cmd+=(--line "${line}")
  if [[ -n "${run_tag}" ]]; then
    cmd+=(--run-tag "${run_tag}")
  fi
else
  if [[ -n "${tag_prefix}" ]]; then
    cmd+=(--tag-prefix "${tag_prefix}")
  fi
fi

if [[ "${skip_build}" == "1" ]]; then
  cmd+=(--skip-build)
fi
if [[ "${use_existing}" == "1" ]]; then
  cmd+=(--use-existing)
fi
if [[ "${dry_run}" == "1" ]]; then
  cmd+=(--dry-run)
fi

echo "[run_codex_once] Packet: ${packet_dir}/current_run_packet.md"
echo "[run_codex_once] Evaluator out: ${eval_out}"
printf '[run_codex_once] Command:'
printf ' %q' "${cmd[@]}"
printf '\n'

"${cmd[@]}"

echo "[run_codex_once] Done. Inspect ${eval_out}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE_DIR="${SCRIPT_DIR}/../baseline"

usage() {
  cat <<'EOF'
Usage: run_canonical_line.sh --line NAME [options]

Canonical lines:
  baseline_default
  baseline_dreamplace_abacus
  evolve_line

Options:
  --line NAME              Canonical line to run.
  --family-variant NAME    Optional evolve family variant. Current value:
                           legalm_engine
  --openroad-binary PATH   Optional binary override. Exported as OPENROAD_BINARY.
  --help                   Show this message.

All remaining arguments are passed through to the selected baseline wrapper.
EOF
}

line=""
family_variant=""
openroad_binary=""
pass_through=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --line)
      line="$2"
      shift 2
      ;;
    --family-variant)
      family_variant="$2"
      shift 2
      ;;
    --openroad-binary)
      openroad_binary="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      pass_through+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${line}" ]]; then
  echo "Missing required --line." >&2
  usage >&2
  exit 1
fi

if [[ -n "${openroad_binary}" ]]; then
  export OPENROAD_BINARY="$(realpath -m "${openroad_binary}")"
fi

case "${line}" in
  baseline_default)
    exec "${BASELINE_DIR}/run_or_default.sh" "${pass_through[@]}"
    ;;
  baseline_dreamplace_abacus)
    exec "${BASELINE_DIR}/run_dp_abacus.sh" "${pass_through[@]}"
    ;;
  evolve_line)
    cmd=("${BASELINE_DIR}/run_evolve_line.sh")
    if [[ -n "${family_variant}" ]]; then
      cmd+=(--family-variant "${family_variant}")
    fi
    exec "${cmd[@]}" "${pass_through[@]}"
    ;;
  *)
    echo "Unsupported canonical line: ${line}" >&2
    usage >&2
    exit 1
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: run_evolve_line.sh [options]

This wrapper runs the clean standalone evolve line.

Options:
  --family-variant NAME     Optional evolve family variant. Current value:
                            legalm_engine
                            This requires a matching family-specific binary.
  --engine MODE             Internal compatibility option. Avoid using this
                            directly in new agent prompts.
  --help                    Show this message.

All other arguments are passed through to `run_baseline.sh`.
EOF
}

engine=""
family_variant=""
pass_through=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --family-variant)
      family_variant="$2"
      shift 2
      ;;
    --engine)
      engine="$2"
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

if [[ -n "${family_variant}" ]]; then
  case "${family_variant}" in
    legalm_engine)
      if [[ -n "${engine}" && "${engine}" != "legalm" ]]; then
        echo "family variant ${family_variant} requires engine=legalm." >&2
        exit 1
      fi
      engine="legalm"
      ;;
    *)
      echo "Unsupported family variant: ${family_variant}" >&2
      usage >&2
      exit 1
      ;;
  esac
fi

if [[ -n "${engine}" ]]; then
  case "${engine}" in
    default|negotiation|negotiation_abacus|legalm) ;;
    *)
      echo "Unsupported evolve engine: ${engine}" >&2
      usage >&2
      exit 1
      ;;
  esac
fi

cmd=(
  "${SCRIPT_DIR}/run_baseline.sh"
  --command-set evolve
)

if [[ -n "${engine}" ]]; then
  cmd+=(--engine "${engine}")
fi

exec "${cmd[@]}" "${pass_through[@]}"

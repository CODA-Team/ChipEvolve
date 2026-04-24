#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/runtime_env.sh"
dpl_init_runtime "run_baseline_suite.sh"
WORKSPACE_ROOT="${ORFS_ROOT}"

FLOW_DIR="${WORKSPACE_ROOT}/flow"
FLOW_HOME="${FLOW_HOME:-${FLOW_DIR}}"
FLOW_HOME="$(realpath -m "${FLOW_HOME}")"
DEFAULT_CONFIG="./designs/nangate45/gcd/config.mk"
export FLOW_HOME

usage() {
  cat <<'EOF'
Usage: run_baseline_suite.sh [options]

Runs the canonical strict comparison bundle:
  1. baseline_default
  2. baseline_dreamplace_abacus
  3. evolve_line

Options:
  --design-config PATH      Flow design config. Default: DESIGN_CONFIG or ./designs/nangate45/gcd/config.mk.
  --flow-variant NAME       FLOW_VARIANT shared by all runs.
                            Default: dpl_evolve_suite_<timestamp>.
  --threads N               NUM_CORES passed to each run.
  --input-stage NAME        Input placement stage. Default: 3_4_place_resized.
  --tag-prefix NAME         Prefix added to every run tag.
  --evolve-family-variant NAME
                            Optional family variant for evolve_line.
                            Current value: legalm_engine.
  --evolve-engine MODE      Internal compatibility option. Avoid using this
                            directly in new agent prompts.
  --dreamplace-root PATH    DREAMPlace root. Default: /opt/EDAs/DREAMPlace.
  --dreamplace-python PATH  Python interpreter for DreamPlace. Default: auto-detect.
  --help                    Show this message.
EOF
}

normalize_flow_relpath() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    printf '\n'
    return
  fi
  if [[ "${path}" == "${FLOW_HOME}/"* ]]; then
    printf '%s\n' "${path#${FLOW_HOME}/}"
    return
  fi
  if [[ "${path}" == /* ]]; then
    printf '%s\n' "${path}"
    return
  fi
  path="${path#./}"
  printf '%s\n' "${path}"
}

to_flow_relative_if_possible() {
  local path="$1"
  local abs_path
  abs_path="$(realpath -m "${path}")"
  if [[ "${abs_path}" == "${FLOW_HOME}/"* ]]; then
    printf '%s\n' "${abs_path#${FLOW_HOME}/}"
  else
    printf '%s\n' "${path}"
  fi
}

flow_abs() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    realpath -m "${path}"
  else
    realpath -m "${FLOW_HOME}/${path}"
  fi
}

shell_join() {
  local out=()
  local arg
  for arg in "$@"; do
    out+=("$(printf '%q' "${arg}")")
  done
  printf '%s' "${out[*]}"
}

design_config="${DESIGN_CONFIG:-}"
flow_variant=""
threads="${NUM_CORES:-}"
input_stage="3_4_place_resized"
tag_prefix=""
evolve_engine="default"
evolve_family_variant=""
dreamplace_root="/opt/EDAs/DREAMPlace"
dreamplace_python=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --design-config)
      design_config="$2"
      shift 2
      ;;
    --flow-variant)
      flow_variant="$2"
      shift 2
      ;;
    --threads)
      threads="$2"
      shift 2
      ;;
    --input-stage)
      input_stage="$2"
      shift 2
      ;;
    --tag-prefix)
      tag_prefix="$2"
      shift 2
      ;;
    --evolve-engine)
      evolve_engine="$2"
      shift 2
      ;;
    --evolve-family-variant)
      evolve_family_variant="$2"
      shift 2
      ;;
    --dreamplace-root)
      dreamplace_root="$2"
      shift 2
      ;;
    --dreamplace-python)
      dreamplace_python="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

design_config="${design_config:-$DEFAULT_CONFIG}"
if [[ "${design_config}" == /* ]]; then
  design_config="$(to_flow_relative_if_possible "${design_config}")"
else
  design_config="$(normalize_flow_relpath "${design_config}")"
fi

case "${evolve_engine}" in
  default|negotiation|negotiation_abacus|legalm) ;;
  *)
    echo "Unsupported evolve engine: ${evolve_engine}" >&2
    usage >&2
    exit 1
    ;;
esac

flow_variant="${flow_variant:-dpl_evolve_suite_$(date +%Y%m%d_%H%M%S)}"
flow_variant="$(normalize_flow_relpath "${flow_variant}")"

tag_prefix="${tag_prefix#./}"
if [[ -n "${tag_prefix}" && "${tag_prefix}" != *_ ]]; then
  tag_prefix="${tag_prefix}_"
fi

make_base=(make -C "${FLOW_HOME}" --no-print-directory DESIGN_CONFIG="${design_config}" FLOW_VARIANT="${flow_variant}")
if [[ -n "${threads}" ]]; then
  make_base+=(NUM_CORES="${threads}")
fi

print_make_var() {
  local var="$1"
  "${make_base[@]}" "print-${var}" | sed -n "s/^${var}: //p" | tail -n 1
}

reports_dir="$(normalize_flow_relpath "$(print_make_var REPORTS_DIR)")"
report_root="${reports_dir}/dpl_evolve_baseline"
suite_summary_tsv="$(flow_abs "${report_root}/suite_runs.tsv")"
mkdir -p "$(dirname "${suite_summary_tsv}")"

cat > "${suite_summary_tsv}" <<'EOF'
line_id	run_tag	metrics_json
EOF

common_args=(
  --design-config "${design_config}"
  --track strict
  --input-stage "${input_stage}"
  --flow-variant "${flow_variant}"
)
if [[ -n "${threads}" ]]; then
  common_args+=(--threads "${threads}")
fi

run_case() {
  local line_id="$1"
  local run_tag="$2"
  local runner="$3"
  shift 3

  local -a cmd=(
    "${runner}"
    "${common_args[@]}"
    --run-tag "${run_tag}"
    "$@"
  )

  echo
  echo "==> Running ${line_id}"
  echo "    $(shell_join "${cmd[@]}")"
  "${cmd[@]}"

  local metrics_json
  metrics_json="$(flow_abs "${report_root}/${run_tag}/metrics.json")"
  printf '%s\t%s\t%s\n' \
    "${line_id}" \
    "${run_tag}" \
    "${metrics_json}" >> "${suite_summary_tsv}"
}

run_case \
  "baseline_default" \
  "${tag_prefix}baseline_default" \
  "${SCRIPT_DIR}/run_or_default.sh"

dreamplace_args=()
if [[ -n "${dreamplace_root}" ]]; then
  dreamplace_args+=(--dreamplace-root "${dreamplace_root}")
fi
if [[ -n "${dreamplace_python}" ]]; then
  dreamplace_args+=(--dreamplace-python "${dreamplace_python}")
fi
run_case \
  "baseline_dreamplace_abacus" \
  "${tag_prefix}baseline_dreamplace_abacus" \
  "${SCRIPT_DIR}/run_dp_abacus.sh" \
  "${dreamplace_args[@]}"

evolve_args=()
if [[ -n "${evolve_family_variant}" ]]; then
  evolve_args+=(--family-variant "${evolve_family_variant}")
else
  evolve_args+=(--engine "${evolve_engine}")
fi

run_case \
  "evolve_line" \
  "${tag_prefix}evolve_line" \
  "${SCRIPT_DIR}/run_evolve_line.sh" \
  "${evolve_args[@]}"

echo
echo "Suite complete."
echo "  flow_variant: ${flow_variant}"
echo "  summary_tsv: ${suite_summary_tsv}"
cat "${suite_summary_tsv}"

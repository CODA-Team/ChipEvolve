#!/usr/bin/env bash

set -euo pipefail

resolve_workspace_root() {
  local direct_root env_root
  direct_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

MAX_TASKS="${MAX_TASKS:-5}"
NUM_CORES="${NUM_CORES:-16}"
TARGET="${TARGET:-place}"
FLOW_VARIANT="${FLOW_VARIANT:-place_batch_$(date +%Y%m%d_%H%M%S)}"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"

DESIGN_CONFIGS=(
  "./designs/nangate45/ibex/config.mk"
  "./designs/nangate45/jpeg/config.mk"
  "./designs/nangate45/aes/config.mk"
  "./designs/nangate45/ariane133/config.mk"
  "./designs/nangate45/bp_quad/config.mk"
  "./designs/asap7/aes/config.mk"
  "./designs/asap7/ethmac/config.mk"
  "./designs/asap7/gcd/config.mk"
  "./designs/asap7/ibex/config.mk"
  "./designs/asap7/jpeg/config.mk"
  "./designs/asap7/megaboom/config.mk"
  "./designs/asap7/riscv32i/config.mk"
  "./designs/asap7/swerv_wrapper/config.mk"
)

usage() {
  cat <<'EOF'
Usage: run_place_batch.sh

Environment overrides:
  MAX_TASKS     Max concurrent jobs. Default: 5
  NUM_CORES     Threads per ORFS invocation. Default: 16
  TARGET        ORFS target. Default: place
  FLOW_VARIANT  Shared FLOW_VARIANT for this batch. Default: place_batch_<timestamp>

This script prepares the initial place snapshots used later by code evolve.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if ! REPO_ROOT="$(resolve_workspace_root)"; then
  echo "[ERROR] run_place_batch.sh must run inside an ORFS workspace with this repo mounted as evolve_agent/." >&2
  echo "[ERROR] Re-run from the mounted workspace or set ORFS_ROOT to that workspace." >&2
  exit 1
fi

FLOW_DIR="${REPO_ROOT}/flow"
RUN_DIR="${FLOW_DIR}/logs/batch_runs/${FLOW_VARIANT}_${RUN_STAMP}"
STATUS_FILE="${RUN_DIR}/status.tsv"
SUMMARY_FILE="${RUN_DIR}/summary.txt"
cd "${FLOW_DIR}"

mkdir -p "${RUN_DIR}"
printf "config\tstatus\tlog\tstart\tend\n" > "${STATUS_FILE}"

label_from_config() {
  local config="$1"
  local label
  label="${config#./designs/}"
  label="${label%/config.mk}"
  label="${label//\//__}"
  printf "%s\n" "${label}"
}

run_case() {
  local config="$1"
  local label log start_ts end_ts rc

  label="$(label_from_config "${config}")"
  log="${RUN_DIR}/${label}.log"
  start_ts="$(date '+%F %T')"

  set +e
  {
    printf "[START] %s\n" "${start_ts}"
    printf "[INFO] config=%s\n" "${config}"
    printf "[INFO] target=%s max_tasks=%s num_cores=%s flow_variant=%s\n" \
      "${TARGET}" "${MAX_TASKS}" "${NUM_CORES}" "${FLOW_VARIANT}"
    printf "[INFO] workdir=%s\n" "${FLOW_DIR}"
    make \
      DESIGN_CONFIG="${config}" \
      FLOW_VARIANT="${FLOW_VARIANT}" \
      NUM_CORES="${NUM_CORES}" \
      check-openroad check-yosys "${TARGET}"
  } > "${log}" 2>&1
  rc=$?
  set -e
  end_ts="$(date '+%F %T')"

  if [[ ${rc} -eq 0 ]]; then
    printf "%s\tPASS\t%s\t%s\t%s\n" "${config}" "${log}" "${start_ts}" "${end_ts}" >> "${STATUS_FILE}"
  else
    printf "%s\tFAIL(%s)\t%s\t%s\t%s\n" "${config}" "${rc}" "${log}" "${start_ts}" "${end_ts}" >> "${STATUS_FILE}"
  fi

  return "${rc}"
}

write_summary() {
  local passed failed total
  total=$(tail -n +2 "${STATUS_FILE}" | wc -l | tr -d ' ')
  passed=$(awk -F '\t' 'NR > 1 && $2 == "PASS" { count++ } END { print count + 0 }' "${STATUS_FILE}")
  failed=$(awk -F '\t' 'NR > 1 && $2 != "PASS" { count++ } END { print count + 0 }' "${STATUS_FILE}")

  {
    printf "FLOW_VARIANT=%s\n" "${FLOW_VARIANT}"
    printf "TARGET=%s\n" "${TARGET}"
    printf "MAX_TASKS=%s\n" "${MAX_TASKS}"
    printf "NUM_CORES=%s\n" "${NUM_CORES}"
    printf "RUN_DIR=%s\n" "${RUN_DIR}"
    printf "TOTAL=%s\n" "${total}"
    printf "PASSED=%s\n" "${passed}"
    printf "FAILED=%s\n" "${failed}"
  } > "${SUMMARY_FILE}"
}

if ! [[ "${MAX_TASKS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "MAX_TASKS must be a positive integer, got '${MAX_TASKS}'" >&2
  exit 2
fi

if ! [[ "${NUM_CORES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "NUM_CORES must be a positive integer, got '${NUM_CORES}'" >&2
  exit 2
fi

echo "Batch placement run"
echo "  target      : ${TARGET}"
echo "  flow_variant: ${FLOW_VARIANT}"
echo "  max_tasks   : ${MAX_TASKS}"
echo "  num_cores   : ${NUM_CORES}"
echo "  run_dir     : ${RUN_DIR}"
echo "  cases       : ${#DESIGN_CONFIGS[@]}"
echo

echo "Checking OpenROAD and Yosys availability..."
make check-openroad check-yosys
echo

declare -a pids=()
overall_rc=0

for config in "${DESIGN_CONFIGS[@]}"; do
  while (( $(jobs -pr | wc -l) >= MAX_TASKS )); do
    if ! wait -n; then
      overall_rc=1
    fi
  done

  label="$(label_from_config "${config}")"
  echo "Launching ${label}"
  run_case "${config}" &
  pids+=("$!")
done

for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    overall_rc=1
  fi
done

write_summary

echo
echo "Completed batch run. Summary:"
cat "${SUMMARY_FILE}"
echo
echo "Status file: ${STATUS_FILE}"

exit "${overall_rc}"

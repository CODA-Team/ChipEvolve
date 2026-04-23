#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLOW_DIR="$(cd "${SCRIPT_DIR}/../../flow" && pwd)"
FLOW_HOME="${FLOW_HOME:-${FLOW_DIR}}"
FLOW_HOME="$(realpath -m "${FLOW_HOME}")"
DEFAULT_CONFIG="./designs/nangate45/gcd/config.mk"
export FLOW_HOME

if [[ -n "${OPENROAD_BINARY:-}" && -z "${OPENROAD_EXE:-}" ]]; then
  export OPENROAD_EXE="$(realpath -m "${OPENROAD_BINARY}")"
fi

usage() {
  cat <<'EOF'
Usage: run_baseline.sh [options]

Options:
  --design-config PATH      Flow design config. Defaults to DESIGN_CONFIG or ./designs/nangate45/gcd/config.mk.
  --track MODE              strict|flow. Default: strict.
  --engine MODE             default|negotiation|negotiation_abacus|legalm|dreamplace_abacus. Default: default.
                            Classic baseline uses only `default` and
                            `dreamplace_abacus`. Other engines are evolve-side
                            modes.
  --command-set MODE        classic|evolve. Default: classic.
  --input-stage NAME        3_3_place_gp|3_4_place_resized. Default: 3_4_place_resized for strict.
  --flow-variant NAME       FLOW_VARIANT for the run. Default: dpl_evolve_<track>_<engine>.
  --run-tag NAME            Stable tag used under results/reports.
  --threads N               NUM_CORES passed to ORFS.
  --dreamplace-root PATH    DREAMPlace root. Default: /opt/EDAs/DREAMPlace.
  --dreamplace-python PATH  Python interpreter for DreamPlace. Default: auto-detect.
  --help                    Show this message.
EOF
}

design_config="${DESIGN_CONFIG:-}"
track="strict"
engine="default"
command_set="classic"
input_stage=""
flow_variant=""
run_tag=""
threads="${NUM_CORES:-}"
dreamplace_root="/opt/EDAs/DREAMPlace"
dreamplace_python=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --design-config)
      design_config="$2"
      shift 2
      ;;
    --track)
      track="$2"
      shift 2
      ;;
    --engine)
      engine="$2"
      shift 2
      ;;
    --command-set)
      command_set="$2"
      shift 2
      ;;
    --input-stage)
      input_stage="$2"
      shift 2
      ;;
    --flow-variant)
      flow_variant="$2"
      shift 2
      ;;
    --run-tag)
      run_tag="$2"
      shift 2
      ;;
    --threads)
      threads="$2"
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

flow_abs() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    realpath -m "${path}"
  else
    realpath -m "${FLOW_HOME}/${path}"
  fi
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

design_config="${design_config:-$DEFAULT_CONFIG}"
if [[ "${design_config}" == /* ]]; then
  design_config="$(to_flow_relative_if_possible "${design_config}")"
else
  design_config="$(normalize_flow_relpath "${design_config}")"
fi

case "${track}" in
  strict|flow) ;;
  *)
    echo "Unsupported track: ${track}" >&2
    exit 1
    ;;
esac

case "${engine}" in
  default)
    engine_family="openroad"
    ;;
  negotiation)
    engine_family="openroad"
    ;;
  negotiation_abacus)
    engine_family="openroad"
    ;;
  legalm)
    engine_family="openroad"
    ;;
  dreamplace_abacus)
    engine_family="dreamplace"
    ;;
  *)
    echo "Unsupported engine: ${engine}" >&2
    exit 1
    ;;
esac

case "${command_set}" in
  classic)
    check_cmd="check_placement"
    ;;
  evolve)
    check_cmd="check_placement_evolve"
    ;;
  *)
    echo "Unsupported command set: ${command_set}" >&2
    exit 1
    ;;
esac

case "${command_set}:${engine}" in
  classic:default) legalizer_mode="dpl" ;;
  classic:negotiation) legalizer_mode="dpl_nblg" ;;
  classic:negotiation_abacus) legalizer_mode="dpl_nblg_abacus" ;;
  classic:legalm) legalizer_mode="unsupported" ;;
  classic:dreamplace_abacus) legalizer_mode="dreamplace_abacus" ;;
  evolve:default) legalizer_mode="evolve" ;;
  evolve:negotiation) legalizer_mode="evolve_nblg" ;;
  evolve:negotiation_abacus) legalizer_mode="evolve_nblg_abacus" ;;
  evolve:legalm) legalizer_mode="evolve_legalm" ;;
  evolve:dreamplace_abacus) legalizer_mode="dreamplace_abacus" ;;
  *)
    echo "Unsupported legalizer combination: ${command_set}:${engine}" >&2
    exit 1
    ;;
esac

if [[ "${command_set}" == "classic" && "${engine}" != "default" && "${engine}" != "dreamplace_abacus" ]]; then
  echo "Classic baseline supports only engine=default or engine=dreamplace_abacus." >&2
  exit 1
fi

if [[ -z "${input_stage}" ]]; then
  input_stage="3_4_place_resized"
fi

if [[ "${track}" == "flow" && "${input_stage}" != "3_4_place_resized" ]]; then
  echo "Reduced flow track currently expects --input-stage 3_4_place_resized." >&2
  exit 1
fi

if [[ "${track}" == "flow" && "${engine_family}" == "dreamplace" ]]; then
  echo "DreamPlace Abacus is currently supported only on the strict baseline track." >&2
  exit 1
fi

flow_variant="${flow_variant:-dpl_evolve_${track}_${engine}}"
flow_variant="$(normalize_flow_relpath "${flow_variant}")"
run_tag="${run_tag:-$(date +%Y%m%d_%H%M%S)_${track}_${engine}}"

make_base=(make -C "${FLOW_HOME}" --no-print-directory DESIGN_CONFIG="${design_config}" FLOW_VARIANT="${flow_variant}")
if [[ -n "${threads}" ]]; then
  make_base+=(NUM_CORES="${threads}")
fi

print_make_var() {
  local var="$1"
  "${make_base[@]}" "print-${var}" | sed -n "s/^${var}: //p" | tail -n 1
}

results_dir="$(normalize_flow_relpath "$(print_make_var RESULTS_DIR)")"
reports_dir="$(normalize_flow_relpath "$(print_make_var REPORTS_DIR)")"
log_dir="$(normalize_flow_relpath "$(print_make_var LOG_DIR)")"
objects_dir="$(normalize_flow_relpath "$(print_make_var OBJECTS_DIR)")"

run_dir="${results_dir}/dpl_evolve_baseline/${run_tag}"
report_dir="${reports_dir}/dpl_evolve_baseline/${run_tag}"
run_log_dir="${log_dir}/dpl_evolve_baseline/${run_tag}"
run_objects_dir="${objects_dir}/dpl_evolve_baseline/${run_tag}"
mkdir -p \
  "$(flow_abs "${run_dir}")" \
  "$(flow_abs "${report_dir}")" \
  "$(flow_abs "${run_log_dir}")" \
  "$(flow_abs "${run_objects_dir}")"

manifest_json="${report_dir}/run_manifest.json"
cat > "$(flow_abs "${manifest_json}")" <<EOF
{
  "track": "${track}",
  "engine": "${engine}",
  "command_set": "${command_set}",
  "design_config": "${design_config}",
  "flow_variant": "${flow_variant}",
  "input_stage": "${input_stage}",
  "run_tag": "${run_tag}",
  "threads": ${threads:-0},
  "flow_home": "${FLOW_HOME}",
  "results_dir": "${results_dir}",
  "reports_dir": "${reports_dir}",
  "log_dir": "${log_dir}"
}
EOF

script_dir_rel="$(realpath --relative-to="${FLOW_HOME}" "${SCRIPT_DIR}")"

shell_join() {
  local parts=()
  local quoted
  for arg in "$@"; do
    printf -v quoted '%q' "$arg"
    parts+=("$quoted")
  done
  printf '%s ' "${parts[@]}"
}

write_tcl_driver() {
  local wrapper_path="$1"
  local target_script="$2"
  shift 2
  {
    echo "set ::dpl_evolve_options [dict create \\"
    while [[ $# -gt 0 ]]; do
      printf '  %s {%s} \\\n' "$1" "$2"
      shift 2
    done
    echo "]"
    printf 'source {%s}\n' "${target_script}"
  } > "${wrapper_path}"
}

echo "Preparing input snapshot ${input_stage} for ${flow_variant}..."
"${make_base[@]}" "${input_stage}"

if [[ "${track}" == "strict" ]]; then
  before_snapshot="${run_dir}/before.tsv"
  after_snapshot="${run_dir}/after.tsv"
  before_summary="${report_dir}/before_summary.json"
  legalize_summary_json="${report_dir}/legalize_summary.json"
  post_metrics_summary_json="${report_dir}/post_metrics_summary.json"
  metadata_json="${report_dir}/metadata.json"
  metrics_json="${report_dir}/metrics.json"
  dp_report="${report_dir}/detailed_placement_report.json"
  check_report="${report_dir}/check_placement_report.json"
  bridge_manifest="${report_dir}/dreamplace_manifest.json"
  dreamplace_input="${report_dir}/dreamplace_input.json"
  bridge_coords="${run_dir}/dreamplace_coords.tsv"
  output_odb="${run_dir}/legalized.odb"
  output_def="${run_dir}/legalized.def"
  output_sdc="${run_dir}/legalized.sdc"
  stage_metrics_json="${run_log_dir}/3_5_place_dp.json"
  legalize_log_stem="dpl_evolve_${run_tag}_legalize"
  case "${command_set}:${engine}" in
    classic:default) run_script="${script_dir_rel}/detail_place_only.tcl" ;;
    classic:dreamplace_abacus) run_script="${script_dir_rel}/detail_place_dreamplace.tcl" ;;
    evolve:default) run_script="${script_dir_rel}/detail_place_only_evolve.tcl" ;;
    evolve:negotiation) run_script="${script_dir_rel}/detail_place_only_evolve_nblg.tcl" ;;
    evolve:negotiation_abacus) run_script="${script_dir_rel}/detail_place_only_evolve_nblg_abacus.tcl" ;;
    evolve:legalm) run_script="${script_dir_rel}/detail_place_only_evolve_legalm.tcl" ;;
    evolve:dreamplace_abacus) run_script="${script_dir_rel}/detail_place_dreamplace.tcl" ;;
    *)
      echo "Unsupported strict baseline: ${command_set}:${engine}" >&2
      exit 1
      ;;
  esac
  strict_driver="${run_objects_dir}/${run_tag}_legalize_driver.tcl"
  if [[ "${engine_family}" == "dreamplace" ]]; then
    if [[ -n "${dreamplace_python}" ]]; then
      write_tcl_driver "$(flow_abs "${strict_driver}")" "$(flow_abs "${run_script}")" \
        input-odb "${input_stage}.odb" \
        input-sdc "2_floorplan.sdc" \
        run-dir "${run_dir}" \
        report-dir "${report_dir}" \
        before-snapshot "${before_snapshot}" \
        before-summary "${before_summary}" \
        export-json "${dreamplace_input}" \
        coords-tsv "${bridge_coords}" \
        bridge-manifest "${bridge_manifest}" \
        output-odb "${output_odb}" \
        output-def "${output_def}" \
        output-sdc "${output_sdc}" \
        after-snapshot "${after_snapshot}" \
        summary-json "${legalize_summary_json}" \
        track "${track}" \
        legalizer "${legalizer_mode}" \
        dreamplace-root "${dreamplace_root}" \
        python "${dreamplace_python}"
    else
      write_tcl_driver "$(flow_abs "${strict_driver}")" "$(flow_abs "${run_script}")" \
        input-odb "${input_stage}.odb" \
        input-sdc "2_floorplan.sdc" \
        run-dir "${run_dir}" \
        report-dir "${report_dir}" \
        before-snapshot "${before_snapshot}" \
        before-summary "${before_summary}" \
        export-json "${dreamplace_input}" \
        coords-tsv "${bridge_coords}" \
        bridge-manifest "${bridge_manifest}" \
        output-odb "${output_odb}" \
        output-def "${output_def}" \
        output-sdc "${output_sdc}" \
        after-snapshot "${after_snapshot}" \
        summary-json "${legalize_summary_json}" \
        track "${track}" \
        legalizer "${legalizer_mode}" \
        dreamplace-root "${dreamplace_root}"
    fi
  else
    write_tcl_driver "$(flow_abs "${strict_driver}")" "$(flow_abs "${run_script}")" \
      input-odb "${input_stage}.odb" \
      input-sdc "2_floorplan.sdc" \
      run-dir "${run_dir}" \
      report-dir "${report_dir}" \
      before-snapshot "${before_snapshot}" \
      after-snapshot "${after_snapshot}" \
      output-odb "${output_odb}" \
      output-def "${output_def}" \
      output-sdc "${output_sdc}" \
      summary-json "${legalize_summary_json}" \
      dp-report "${dp_report}" \
      track "${track}"
  fi

  start_ns="$(date +%s%N)"
  "${make_base[@]}" \
    run \
    RUN_SCRIPT="$(flow_abs "${strict_driver}")" \
    RUN_LOG_NAME_STEM="${legalize_log_stem}"
  end_ns="$(date +%s%N)"
  runtime_sec="$(awk "BEGIN {printf \"%.3f\", (${end_ns} - ${start_ns}) / 1000000000}")"

  metrics_make_base=(
    "${make_base[@]}"
    RESULTS_DIR="$(flow_abs "${run_dir}")"
    REPORTS_DIR="$(flow_abs "${report_dir}")"
    LOG_DIR="$(flow_abs "${run_log_dir}")"
    OBJECTS_DIR="$(flow_abs "${run_objects_dir}")"
  )

  metrics_driver="${run_objects_dir}/${run_tag}_metrics_driver.tcl"
  write_tcl_driver "$(flow_abs "${metrics_driver}")" "$(flow_abs "${script_dir_rel}/report_legalized_metrics.tcl")" \
    input-odb "legalized.odb" \
    input-sdc "legalized.sdc" \
    check-cmd "${check_cmd}" \
    check-report "${check_report}" \
    summary-json "${post_metrics_summary_json}" \
    metrics-json "${stage_metrics_json}" \
    track "${track}" \
    legalizer "${legalizer_mode}"
  metrics_openroad_args="$(shell_join -metrics "$(flow_abs "${stage_metrics_json}")")"
  "${metrics_make_base[@]}" \
    run \
    RUN_SCRIPT="$(flow_abs "${metrics_driver}")" \
    RUN_LOG_NAME_STEM="3_5_place_dp" \
    RUN_OPENROAD_ARGS="${metrics_openroad_args}"

  FLOW_HOME="${FLOW_HOME}" python3 "${SCRIPT_DIR}/gen_orfs_metadata.py" \
    --orfs-metrics "${stage_metrics_json}" \
    --output "${metadata_json}"

  FLOW_HOME="${FLOW_HOME}" python3 "${SCRIPT_DIR}/collect_metrics.py" \
    --before "${before_snapshot}" \
    --after "${after_snapshot}" \
    --run-summary "${legalize_summary_json}" \
    --post-metrics-summary "${post_metrics_summary_json}" \
    --before-summary "${before_summary}" \
    --manifest "${manifest_json}" \
    --bridge-manifest "${bridge_manifest}" \
    --detailed-placement-report "${dp_report}" \
    --orfs-metrics "${stage_metrics_json}" \
    --orfs-metadata "${metadata_json}" \
    --runtime-seconds "${runtime_sec}" \
    --output "${metrics_json}"

  echo "Strict baseline complete."
  echo "  run_dir: ${run_dir}"
  echo "  report_dir: ${report_dir}"
  echo "  metrics: ${metrics_json}"
  exit 0
fi

before_snapshot="${run_dir}/before.tsv"
after_snapshot="${run_dir}/after.tsv"
legalize_summary_json="${report_dir}/legalize_summary.json"
post_metrics_summary_json="${report_dir}/post_metrics_summary.json"
metadata_json="${report_dir}/metadata.json"
metrics_json="${report_dir}/metrics.json"
dp_report="${report_dir}/detailed_placement_report.json"
check_report="${report_dir}/check_placement_report.json"
output_odb="${run_dir}/legalized.odb"
output_def="${run_dir}/legalized.def"
output_sdc="${run_dir}/legalized.sdc"
stage_metrics_json="${run_log_dir}/3_5_place_dp.json"

case "${command_set}:${engine}" in
  classic:default) flow_run_script="${script_dir_rel}/flow/detail_place_flow_classic.tcl" ;;
  evolve:default) flow_run_script="${script_dir_rel}/flow/detail_place_flow_evolve.tcl" ;;
  evolve:negotiation) flow_run_script="${script_dir_rel}/flow/detail_place_flow_evolve_nblg.tcl" ;;
  evolve:negotiation_abacus) flow_run_script="${script_dir_rel}/flow/detail_place_flow_evolve_nblg_abacus.tcl" ;;
  evolve:legalm) flow_run_script="${script_dir_rel}/flow/detail_place_flow_evolve_legalm.tcl" ;;
  *)
    echo "Unsupported flow baseline: ${command_set}:${engine}" >&2
    exit 1
    ;;
esac

flow_driver="${run_objects_dir}/${run_tag}_legalize_driver.tcl"
write_tcl_driver "$(flow_abs "${flow_driver}")" "$(flow_abs "${flow_run_script}")" \
  input-odb "${input_stage}.odb" \
  input-sdc "2_floorplan.sdc" \
  run-dir "${run_dir}" \
  report-dir "${report_dir}" \
  before-snapshot "${before_snapshot}" \
  after-snapshot "${after_snapshot}" \
  output-odb "${output_odb}" \
  output-def "${output_def}" \
  output-sdc "${output_sdc}" \
  summary-json "${legalize_summary_json}" \
  dp-report "${dp_report}" \
  track "${track}"

start_ns="$(date +%s%N)"
"${make_base[@]}" \
  run \
  RUN_SCRIPT="$(flow_abs "${flow_driver}")" \
  RUN_LOG_NAME_STEM="dpl_evolve_${run_tag}_legalize"
end_ns="$(date +%s%N)"
runtime_sec="$(awk "BEGIN {printf \"%.3f\", (${end_ns} - ${start_ns}) / 1000000000}")"

metrics_make_base=(
  "${make_base[@]}"
  RESULTS_DIR="$(flow_abs "${run_dir}")"
  REPORTS_DIR="$(flow_abs "${report_dir}")"
  LOG_DIR="$(flow_abs "${run_log_dir}")"
  OBJECTS_DIR="$(flow_abs "${run_objects_dir}")"
)

metrics_driver="${run_objects_dir}/${run_tag}_metrics_driver.tcl"
write_tcl_driver "$(flow_abs "${metrics_driver}")" "$(flow_abs "${script_dir_rel}/report_legalized_metrics.tcl")" \
  input-odb "legalized.odb" \
  input-sdc "legalized.sdc" \
  check-cmd "${check_cmd}" \
  check-report "${check_report}" \
  summary-json "${post_metrics_summary_json}" \
  metrics-json "${stage_metrics_json}" \
  track "${track}" \
  legalizer "${legalizer_mode}"
metrics_openroad_args="$(shell_join -metrics "$(flow_abs "${stage_metrics_json}")")"
"${metrics_make_base[@]}" \
  run \
  RUN_SCRIPT="$(flow_abs "${metrics_driver}")" \
  RUN_LOG_NAME_STEM="3_5_place_dp" \
  RUN_OPENROAD_ARGS="${metrics_openroad_args}"

FLOW_HOME="${FLOW_HOME}" python3 "${SCRIPT_DIR}/gen_orfs_metadata.py" \
  --orfs-metrics "${stage_metrics_json}" \
  --output "${metadata_json}"

FLOW_HOME="${FLOW_HOME}" python3 "${SCRIPT_DIR}/collect_metrics.py" \
  --before "${before_snapshot}" \
  --after "${after_snapshot}" \
  --run-summary "${legalize_summary_json}" \
  --post-metrics-summary "${post_metrics_summary_json}" \
  --manifest "${manifest_json}" \
  --orfs-metrics "${stage_metrics_json}" \
  --orfs-metadata "${metadata_json}" \
  --runtime-seconds "${runtime_sec}" \
  --output "${metrics_json}"

echo "Reduced-flow baseline complete."
echo "  run_dir: ${run_dir}"
echo "  report_dir: ${report_dir}"
echo "  metrics: ${metrics_json}"

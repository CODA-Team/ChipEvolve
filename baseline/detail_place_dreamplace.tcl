utl::set_metrics_stage "dpl_evolve__dreamplace__{}"

source $::env(SCRIPTS_DIR)/load.tcl
source [file join [file dirname [info script]] dpl_evolve_helpers.tcl]

set options [dpl_evolve_baseline::parse_options $argv [dict create \
  input-odb "3_4_place_resized.odb" \
  input-sdc "2_floorplan.sdc" \
  run-dir [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace] \
  report-dir [file join $::env(REPORTS_DIR) dpl_evolve_baseline dreamplace] \
  before-snapshot [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace before.tsv] \
  before-summary [file join $::env(REPORTS_DIR) dpl_evolve_baseline dreamplace before_summary.json] \
  export-json [file join $::env(REPORTS_DIR) dpl_evolve_baseline dreamplace dreamplace_input.json] \
  coords-tsv [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace dreamplace_coords.tsv] \
  bridge-manifest [file join $::env(REPORTS_DIR) dpl_evolve_baseline dreamplace dreamplace_manifest.json] \
  output-odb [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace legalized.odb] \
  output-def [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace legalized.def] \
  output-sdc [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace legalized.sdc] \
  after-snapshot [file join $::env(RESULTS_DIR) dpl_evolve_baseline dreamplace after.tsv] \
  summary-json [file join $::env(REPORTS_DIR) dpl_evolve_baseline dreamplace legalize_summary.json] \
  track "strict" \
  legalizer "dreamplace_abacus" \
  dreamplace-root "/opt/EDAs/DREAMPlace" \
  python ""]]

set input_odb [dpl_evolve_baseline::option_value $options input-odb]
set input_sdc [dpl_evolve_baseline::option_value $options input-sdc]
set run_dir [dpl_evolve_baseline::option_value $options run-dir]
set report_dir [dpl_evolve_baseline::option_value $options report-dir]
set before_snapshot [dpl_evolve_baseline::option_value $options before-snapshot]
set before_summary [dpl_evolve_baseline::option_value $options before-summary]
set export_json [dpl_evolve_baseline::option_value $options export-json]
set coords_tsv [dpl_evolve_baseline::option_value $options coords-tsv]
set bridge_manifest [dpl_evolve_baseline::option_value $options bridge-manifest]
set output_odb [dpl_evolve_baseline::option_value $options output-odb]
set output_def [dpl_evolve_baseline::option_value $options output-def]
set output_sdc [dpl_evolve_baseline::option_value $options output-sdc]
set after_snapshot [dpl_evolve_baseline::option_value $options after-snapshot]
set summary_json [dpl_evolve_baseline::option_value $options summary-json]
set track [dpl_evolve_baseline::option_value $options track]
set legalizer [dpl_evolve_baseline::option_value $options legalizer]
set dreamplace_root [dpl_evolve_baseline::option_value $options dreamplace-root]
set requested_python [dpl_evolve_baseline::option_value $options python]

file mkdir [dpl_evolve_baseline::resolve_flow_path $run_dir]
file mkdir [dpl_evolve_baseline::resolve_flow_path $report_dir]

load_design $input_odb $input_sdc
source_step_tcl PRE DETAIL_PLACE

dpl_evolve_baseline::write_dreamplace_input $export_json $input_odb $input_sdc
dpl_evolve_baseline::dump_instance_snapshot $before_snapshot

set before_summary_payload [dict create \
  status "ok" \
  track $track \
  legalizer_mode $legalizer \
  input_odb $input_odb \
  input_sdc $input_sdc \
  snapshot_tsv $before_snapshot \
  dbu_per_micron [dpl_evolve_baseline::get_dbu_per_micron] \
  hpwl_proxy_dbu [dpl_evolve_baseline::compute_hpwl_proxy]]
foreach {key value} [dpl_evolve_baseline::snapshot_stats] {
  dict set before_summary_payload $key $value
}
dpl_evolve_baseline::write_summary_json $before_summary $before_summary_payload

set python_candidates {}
if { $requested_python ne "" } {
  lappend python_candidates $requested_python
}
lappend python_candidates \
  /opt/conda/miniforge3/envs/dreamplace/bin/python \
  /home/zhiyuzheng/.conda/envs/xplace/bin/python \
  python3

set python_exe ""
foreach candidate $python_candidates {
  if { $candidate eq "" || [auto_execok $candidate] eq "" } {
    continue
  }
  if { [catch {exec $candidate -c {import torch}}] == 0 } {
    set python_exe $candidate
    break
  }
}
if { $python_exe eq "" } {
  error "Could not find a Python interpreter with torch."
}

set bridge_script [file join [file dirname [info script]] run_dp_abacus_bridge.py]
if { [catch {
  exec $python_exe $bridge_script \
    --dreamplace-input $export_json \
    --dreamplace-root $dreamplace_root \
    --output-coords $coords_tsv \
    --output-manifest $bridge_manifest
} bridge_err bridge_opts] } {
  puts stderr [dict get $bridge_opts -errorinfo]
  error $bridge_err
}

dpl_evolve_baseline::apply_snapshot_rows $coords_tsv 0
dpl_evolve_baseline::dump_instance_snapshot $after_snapshot

set summary [dict create \
  status "ok" \
  track $track \
  legalizer_mode $legalizer \
  input_odb $input_odb \
  input_sdc $input_sdc \
  coords_tsv $coords_tsv \
  output_odb $output_odb \
  output_def $output_def \
  output_sdc $output_sdc \
  snapshot_tsv $after_snapshot \
  bridge_manifest $bridge_manifest \
  hpwl_after_dbu [dpl_evolve_baseline::compute_hpwl_proxy] \
  dbu_per_micron [dpl_evolve_baseline::get_dbu_per_micron]]

log_cmd write_db [dpl_evolve_baseline::resolve_flow_path $output_odb]
log_cmd write_def [dpl_evolve_baseline::resolve_flow_path $output_def]
log_cmd write_sdc -no_timestamp [dpl_evolve_baseline::resolve_flow_path $output_sdc]

foreach {key value} [dpl_evolve_baseline::snapshot_stats] {
  dict set summary $key $value
}

dpl_evolve_baseline::write_summary_json $summary_json $summary
source_step_tcl POST DETAIL_PLACE

utl::set_metrics_stage "dpl_evolve__strict_legalizer__{}"

source $::env(SCRIPTS_DIR)/load.tcl
source [file join [file dirname [info script]] dpl_evolve_helpers.tcl]

if { ![info exists legalizer_name] || ![info exists padding_cmd] || ![info exists place_cmd] \
  || ![info exists use_negotiation] || ![info exists use_abacus] } {
  error "Strict core expects legalizer_name, padding_cmd, place_cmd, use_negotiation, and use_abacus."
}
if { ![info exists use_legalm] } {
  set use_legalm 0
}
if { ![info exists two_stage_negotiation] } {
  set two_stage_negotiation 0
}

set options [dpl_evolve_baseline::parse_options $argv [dict create \
  input-odb "3_4_place_resized.odb" \
  input-sdc "2_floorplan.sdc" \
  run-dir [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict] \
  report-dir [file join $::env(REPORTS_DIR) dpl_evolve_baseline strict] \
  before-snapshot [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict before.tsv] \
  after-snapshot [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict after.tsv] \
  output-odb [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict legalized.odb] \
  output-def [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict legalized.def] \
  output-sdc [file join $::env(RESULTS_DIR) dpl_evolve_baseline strict legalized.sdc] \
  summary-json [file join $::env(REPORTS_DIR) dpl_evolve_baseline strict legalize_summary.json] \
  dp-report [file join $::env(REPORTS_DIR) dpl_evolve_baseline strict detailed_placement_report.json] \
  track "strict"]]

set input_odb [dpl_evolve_baseline::option_value $options input-odb]
set input_sdc [dpl_evolve_baseline::option_value $options input-sdc]
set run_dir [dpl_evolve_baseline::option_value $options run-dir]
set report_dir [dpl_evolve_baseline::option_value $options report-dir]
set before_snapshot [dpl_evolve_baseline::option_value $options before-snapshot]
set after_snapshot [dpl_evolve_baseline::option_value $options after-snapshot]
set output_odb [dpl_evolve_baseline::option_value $options output-odb]
set output_def [dpl_evolve_baseline::option_value $options output-def]
set output_sdc [dpl_evolve_baseline::option_value $options output-sdc]
set summary_json [dpl_evolve_baseline::option_value $options summary-json]
set dp_report [dpl_evolve_baseline::option_value $options dp-report]
set track [dpl_evolve_baseline::option_value $options track]

load_design $input_odb $input_sdc
source_step_tcl PRE DETAIL_PLACE

file mkdir [dpl_evolve_baseline::resolve_flow_path $run_dir]
file mkdir [dpl_evolve_baseline::resolve_flow_path $report_dir]

set pad_sites 0

set dbu_per_micron [dpl_evolve_baseline::get_dbu_per_micron]
set hpwl_before [dpl_evolve_baseline::compute_hpwl_proxy]
dpl_evolve_baseline::dump_instance_snapshot $before_snapshot

log_cmd $padding_cmd -global -left $pad_sites -right $pad_sites

set dpl_args [list -report_file_name [dpl_evolve_baseline::resolve_flow_path $dp_report]]
if { $use_negotiation } {
  lappend dpl_args -use_negotiation
}
if { $use_legalm } {
  lappend dpl_args -use_legalm
}
if { $use_abacus } {
  lappend dpl_args -abacus
}

set prepass_report ""
if { $two_stage_negotiation } {
  set prepass_report [file join $report_dir detailed_placement_prepass_report.json]
  log_cmd $place_cmd -report_file_name [dpl_evolve_baseline::resolve_flow_path $prepass_report]
}
log_cmd $place_cmd {*}$dpl_args

set hpwl_after [dpl_evolve_baseline::compute_hpwl_proxy]
dpl_evolve_baseline::dump_instance_snapshot $after_snapshot
log_cmd write_db [dpl_evolve_baseline::resolve_flow_path $output_odb]
log_cmd write_def [dpl_evolve_baseline::resolve_flow_path $output_def]
log_cmd write_sdc -no_timestamp [dpl_evolve_baseline::resolve_flow_path $output_sdc]

set summary [dict create \
  status "ok" \
  track $track \
  legalizer_mode $legalizer_name \
  input_odb $input_odb \
  input_sdc $input_sdc \
  output_odb $output_odb \
  output_def $output_def \
  output_sdc $output_sdc \
  before_snapshot $before_snapshot \
  after_snapshot $after_snapshot \
  detailed_placement_report $dp_report \
  detailed_placement_prepass_report $prepass_report \
  dbu_per_micron $dbu_per_micron \
  hpwl_before_dbu $hpwl_before \
  hpwl_after_dbu $hpwl_after \
  hpwl_delta_dbu [expr {$hpwl_after - $hpwl_before}] \
  place_command $place_cmd \
  padding_command $padding_cmd \
  two_stage_negotiation [expr {$two_stage_negotiation ? "true" : "false"}] \
  use_negotiation [expr {$use_negotiation ? "true" : "false"}] \
  use_legalm [expr {$use_legalm ? "true" : "false"}] \
  use_abacus [expr {$use_abacus ? "true" : "false"}]]

foreach {key value} [dpl_evolve_baseline::snapshot_stats] {
  dict set summary $key $value
}

dpl_evolve_baseline::write_summary_json $summary_json $summary
source_step_tcl POST DETAIL_PLACE

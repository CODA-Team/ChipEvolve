"""STA report names and OpenDB escaped names must address the same ECO gate."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORK = r"""
namespace eval ord {}
namespace eval sta {}
proc ord::get_db_block {} {return block}
proc block {method name} {
    if {$method ne "findInst"} {error "Unexpected block method"}
    if {$name eq {unit/reg\[3\]$_DFF_} || $name eq "ordinary"} {return driver}
    return NULL
}
proc get_cells {args} {
    switch -- [lindex $args end] {
        {unit/reg[3]$_DFF_} {return sta_driver}
        {ambiguous*} {return {sta_driver another_driver}}
        default {return {}}
    }
}
proc sta::sta_to_db_inst {cell} {
    if {$cell ne "sta_driver"} {error "Wrong STA object"}
    return driver
}
proc driver {method} {
    switch -- $method {
        getITerms {return {output sink_a sink_b}}
        getName {return {unit/reg\[3\]$_DFF_}}
        getMaster {return master}
    }
}
proc master {method} {return DFFR_X1}
proc output {method} {
    switch -- $method {getMTerm {return output_term} getNet {return output_net}}
}
proc output_term {method} {
    switch -- $method {getSigType {return SIGNAL} getIoType {return OUTPUT} getName {return Q}}
}
proc output_net {method} {
    switch -- $method {getName {return result} getITerms {return {output sink_a sink_b}}}
}
proc sink_a {method} {
    switch -- $method {getMTerm {return input_term} getInst {return load_a}}
}
proc sink_b {method} {
    switch -- $method {getMTerm {return input_term} getInst {return load_b}}
}
proc input_term {method} {
    switch -- $method {getSigType {return SIGNAL} getIoType {return INPUT} getName {return A}}
}
proc load_a {method} {return load_a}
proc load_b {method} {return load_b}
proc get_pins {name} {return $name}
proc report_checks {args} {
    set f [open [lindex $args end] w]
    puts $f {endpoint 0.0 0.0 -0.125 (VIOLATED)}
    close $f
}
proc make_instance {name master} {error "REACHED_NATIVE_CLONE:$name:$master"}
"""


def tcl(program: str) -> str:
    result = subprocess.run(
        ["tclsh"],
        input=f"source {{{ROOT / 'OpenROAD_utils/eco_procs.tcl'}}}\n"
        + NETWORK
        + program,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    return result.stdout


def test_fanout_ranking_accepts_report_name_and_preserves_raw_name_results():
    result = tcl(r"""
set raw [eco_rank_fanout_by_slack {unit/reg\[3\]$_DFF_}]
set code [catch {eco_rank_fanout_by_slack {unit/reg[3]$_DFF_}} display]
puts [list DISPLAY_CODE $code]
puts [list MATCH [expr {$raw eq $display}]]
puts [list RAW $raw]
""")
    assert "DISPLAY_CODE 0" in result
    assert "MATCH 1" in result
    assert "load_a/A -0.125" in result and "load_b/A -0.125" in result


def test_clone_resolves_report_name_before_calling_original_native_action():
    result = tcl(r"""
catch {eco_clone_gate {unit/reg[3]$_DFF_} clone {load_a/A}} message
puts $message
""")
    assert "REACHED_NATIVE_CLONE:clone:DFFR_X1" in result


def test_missing_or_ambiguous_instances_keep_original_failure():
    result = tcl(r"""
foreach name {missing ambiguous*} {
    set code [catch {eco_rank_fanout_by_slack $name} message]
    puts [list REJECTED $name $code $message]
}
""")
    assert "REJECTED missing 1" in result
    assert "REJECTED ambiguous* 1" in result
    assert result.count("not found") == 2


def test_exact_db_name_remains_preferred():
    result = tcl(r"""
rename get_cells original_get_cells
proc get_cells {args} {error {Exact DB lookup must not need STA matching}}
puts [list ROWS [llength [eco_rank_fanout_by_slack ordinary]]]
""")
    assert "ROWS 2" in result

"""Buffer actions keep native pinouts and STA/DB sink identity across PDKs."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORK = r"""
namespace eval ord {}
namespace eval sta {}
set output_name Z
set calls {}
proc ord::get_db_block {} {return block}
proc ord::get_db {} {return database}
proc ord::dbu_to_microns {value} {return $value}
proc database {method name} {return buffer_master}
proc block {method name} {
    switch -- $name {
        driver {return driver}
        buffer {return buffer}
        {unit/reg\[3\]$_DFF_} {return load}
        default {return NULL}
    }
}
proc get_cells {args} {
    switch -- [lindex $args end] {
        {unit/reg[3]$_DFF_} {return load_sta}
        {ambiguous*} {return {load_sta other_sta}}
        default {return {}}
    }
}
proc sta::sta_to_db_inst {object} {
    switch -- $object {driver_sta {return driver} buffer_sta {return buffer} load_sta {return load}}
}
proc sta::sta_to_db_net {object} {return new_net_db}
proc driver {method} {
    switch -- $method {getName {return driver} getLocation {return {10 20}}}
}
proc load {method} {
    switch -- $method {getName {return {unit/reg\[3\]$_DFF_}} getLocation {return {30 40}}}
}
proc buffer {method} {
    switch -- $method {getName {return buffer} getMaster {return buffer_master}}
}
proc buffer_master {method} {return {vdd input_term output_term}}
proc vdd {method} {
    switch -- $method {getSigType {return POWER} getIoType {return INOUT} getName {return VDD}}
}
proc input_term {method} {
    switch -- $method {getSigType {return SIGNAL} getIoType {return INPUT} getName {return A}}
}
proc output_term {method} {
    switch -- $method {getSigType {return SIGNAL} getIoType {return OUTPUT} getName {return $::output_name}}
}
proc driver_terminal {method} {
    switch -- $method {getInst {return driver} getMTerm {return output_term}}
}
proc sink_terminal {method} {
    switch -- $method {getInst {return load} getMTerm {return input_term}}
}
proc buffer_terminal {method} {return buffer}
proc old_net_db {method} {
    switch -- $method {getITerms {return {driver_terminal sink_terminal}} getBTerms {return {}}}
}
proc new_net_db {method} {
    switch -- $method {getITerms {return {buffer_terminal sink_terminal}} getBTerms {return {}}}
}
proc driver_pin {method} {
    switch -- $method {instance {return driver_sta} net {return old_net_sta}}
}
proc buffer_input {method} {
    switch -- $method {instance {return buffer_sta} net {return old_net_sta}}
}
proc buffer_output {method} {
    switch -- $method {instance {return buffer_sta} net {return new_net_sta}}
}
proc get_pins {name} {
    lappend ::calls [list PIN $name]
    switch -- $name {
        driver/Q {return driver_pin}
        buffer/A {return buffer_input}
        {unit/reg\[3\]$_DFF_/A} {return sink_pin}
    }
    if {$name eq "buffer/$::output_name"} {return buffer_output}
    return {}
}
proc get_name {name} {return $name}
proc get_nets {name} {return $name}
proc make_net {name} {lappend ::calls [list CREATE_NET $name]; return new_net}
proc make_instance {args} {lappend ::calls [list CREATE_INSTANCE {*}$args]}
proc connect_pin {net pin} {lappend ::calls [list CONNECT $net $pin]}
proc disconnect_pin {net pin} {lappend ::calls [list DISCONNECT $net $pin]}
proc place_inst {args} {lappend ::calls [list PLACE {*}$args]}
proc delete_instance {name} {lappend ::calls [list DELETE_INSTANCE $name]}
proc delete_net {name} {lappend ::calls [list DELETE_NET $name]}
"""


def run_tcl(program: str) -> str:
    result = subprocess.run(
        ["tclsh"],
        input=f"source {{{ROOT / 'OpenROAD_utils/eco_procs.tcl'}}}\n"
        + NETWORK
        + program,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    return result.stdout


def test_insert_buffer_uses_nangate_output_pin_and_connects_selected_load():
    output = run_tcl(r"""
rename sta::sta_to_db_net original_net_bridge
proc sta::sta_to_db_net {object} {return old_net_db}
eco_insert_buffer signal driver/Q BUF_X2 buffer -sinks [list {unit/reg\[3\]$_DFF_/A}]
puts $calls
""")
    assert "CONNECT new_net buffer_output" in output
    assert "CONNECT new_net sink_pin" in output
    assert "PIN buffer/Z" in output and "PIN buffer/Y" not in output


def test_insert_buffer_resolves_display_sink_to_same_db_terminal():
    output = run_tcl(r"""
rename sta::sta_to_db_net original_net_bridge
proc sta::sta_to_db_net {object} {return old_net_db}
eco_insert_buffer signal driver/Q BUF_X2 buffer -sinks [list {unit/reg[3]$_DFF_/A}] -at centroid
puts $calls
""")
    assert "CONNECT new_net sink_pin" in output
    assert "-location {30.0 40.0}" in output


def test_remove_buffer_uses_master_output_and_restores_load():
    output = run_tcl("eco_remove_buffer buffer\nputs $calls\n")
    assert "DISCONNECT new_net_sta buffer_output" in output
    assert "CONNECT old_net_sta sink_pin" in output
    assert "DELETE_INSTANCE buffer" in output and "DELETE_NET new_net_sta" in output


def test_original_asap7_y_pin_behavior_remains():
    output = run_tcl(r"""
set output_name Y
rename sta::sta_to_db_net original_net_bridge
proc sta::sta_to_db_net {object} {return old_net_db}
eco_insert_buffer signal driver/Q original_buffer buffer
puts $calls
""")
    assert "PIN buffer/Y" in output
    assert "CONNECT new_net buffer_output" in output
    assert "PIN buffer/Z" not in output


def test_ambiguous_sink_does_not_create_topology():
    output = run_tcl(r"""
rename sta::sta_to_db_net original_net_bridge
proc sta::sta_to_db_net {object} {return old_net_db}
set code [catch {eco_insert_buffer signal driver/Q BUF_X2 buffer -sinks {ambiguous*/A}} message]
puts [list REJECTED $code $message]
puts $calls
""")
    assert "REJECTED 1" in output and "no sinks to move" in output
    assert "CREATE_NET" not in output and "CREATE_INSTANCE" not in output


def test_non_buffer_pinout_is_rejected_before_mutation():
    output = run_tcl(r"""
rename buffer_master original_master
proc buffer_master {method} {return {input_term input_term output_term}}
rename sta::sta_to_db_net original_net_bridge
proc sta::sta_to_db_net {object} {return old_net_db}
set code [catch {eco_insert_buffer signal driver/Q wrong_cell buffer} message]
puts [list REJECTED $code $message]
puts $calls
""")
    assert "REJECTED 1" in output and "one signal input" in output
    assert "CREATE_NET" not in output and "CREATE_INSTANCE" not in output


def test_remove_buffer_keeps_original_asap7_pinout():
    output = run_tcl("set output_name Y\neco_remove_buffer buffer\nputs $calls\n")
    assert "PIN buffer/Y" in output and "PIN buffer/Z" not in output
    assert "CONNECT old_net_sta sink_pin" in output

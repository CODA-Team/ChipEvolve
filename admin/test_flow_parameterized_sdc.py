"""Exercise native variable clocks and their I/O expressions with real Tcl."""

import subprocess

import pytest

from chip_evolve.clock import flow_sdc

TEMPLATE = """set_cmd_units -time ps
set clk_name clk
set clk_port_name clk
set clk_period 810
set clk_io_pct 0.2
set clk_port [get_ports $clk_port_name]
create_clock -name $clk_name -period $clk_period $clk_port
set non_clock_inputs [all_inputs -no_clocks]
set_input_delay [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs
set_output_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_outputs]
"""


def test_native_template_preserves_original_program_and_live_IO_constraints():
    actual = flow_sdc(TEMPLATE, 0.81)
    assert actual == TEMPLATE
    procedures = """
proc set_cmd_units {args} {}
proc get_ports {port} {return $port}
proc all_inputs {args} {return d}
proc all_outputs {} {return q}
proc create_clock {args} {
    set index [lsearch -exact $args -period]
    puts "clock=[lindex $args [expr {$index + 1}]] port=[lindex $args end]"
}
proc set_input_delay {delay args} {puts "input=$delay"}
proc set_output_delay {delay args} {puts "output=$delay"}
"""
    for script, expected in [
        (actual, ["clock=810 port=clk", "input=162.0", "output=162.0"]),
        (
            actual.replace("set clk_period 810", "set clk_period 900"),
            ["clock=900 port=clk", "input=180.0", "output=180.0"],
        ),
    ]:
        result = subprocess.run(
            ["tclsh"],
            input=procedures + script,
            text=True,
            capture_output=True,
            check=True,
        )
        assert result.stderr == ""
        assert result.stdout.splitlines() == expected


@pytest.mark.parametrize(
    "sdc",
    [
        TEMPLATE.replace("set clk_period 810", "set clk_period 800"),
        TEMPLATE.replace("set clk_period 810", "set clk_period $other"),
        TEMPLATE.replace(
            "set clk_period 810", "set clk_period 810\nset clk_period 800"
        ),
        TEMPLATE.replace("set_cmd_units -time ps", "set_cmd_units -time ns"),
        TEMPLATE.replace("set clk_port_name clk", "set clk_port_name $other"),
        TEMPLATE.replace(
            "set clk_port [get_ports $clk_port_name]", "set clk_port other"
        ),
        TEMPLATE.replace("-period $clk_period", "-period $other"),
        TEMPLATE + "create_clock -name extra -period $clk_period $clk_port\n",
    ],
)
def test_unknown_or_mismatched_native_clock_is_not_silently_rewritten(sdc):
    with pytest.raises(ValueError):
        flow_sdc(sdc, 0.81)

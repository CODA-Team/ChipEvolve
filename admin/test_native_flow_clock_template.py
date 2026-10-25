"""Native single-clock variables retain matching virtual clocks and live IO."""

import subprocess

import pytest

from chip_evolve.clock import flow_sdc


def template(unit, period, virtual=True, header=""):
    return (
        header
        + f"set_cmd_units -time {unit}\ncurrent_design example\n"
        + f"set clk_period {period}\nset clk_port_name clk\nset clk_io_pct 0.2\n"
        + "set clk_port [get_ports $clk_port_name]\n"
        + "create_clock -name core -period $clk_period $clk_port\n"
        + ("create_clock -name vclk -period $clk_period\n" if virtual else "")
        + "set_input_delay [expr $clk_period * $clk_io_pct] -clock core [all_inputs]\n"
        + "set_output_delay [expr $clk_period * $clk_io_pct] -clock core [all_outputs]\n"
    )


@pytest.mark.parametrize("unit,period,clock_ns", [("ns", 0.5, 0.5), ("ps", 810, 0.81)])
@pytest.mark.parametrize("virtual", [False, True])
@pytest.mark.parametrize("header", ["", "# Original native timing constraints\n\n"])
def test_known_native_templates_preserve_all_constraint_bytes(
    unit, period, clock_ns, virtual, header
):
    original = template(unit, period, virtual, header)
    assert flow_sdc(original, clock_ns, time_unit=unit) == original


@pytest.mark.parametrize("unit,period,clock_ns", [("ns", 0.5, 0.5), ("ps", 500, 0.5)])
def test_numeric_serialization_keeps_comments_and_existing_delays(
    unit, period, clock_ns
):
    original = (
        "# Exported timing constraints\n\n"
        + f"set_cmd_units -time {unit}\ncreate_clock -name core -period {period} [get_ports clk]\n"
        + f"create_clock -name virtual -period {period}\nset_input_delay 7 -clock virtual [get_ports d]\n"
    )
    actual = flow_sdc(original, clock_ns, time_unit=unit)
    assert original.replace(f"-period {period}", "-period $clk_period") in actual
    assert "set_input_delay 7 -clock virtual" in actual


@pytest.mark.parametrize(
    "change", ["period", "virtual", "port", "two_physical", "unit"]
)
def test_inconsistent_clock_templates_are_rejected(change):
    original = template("ns", 0.5)
    if change == "period":
        original = original.replace("set clk_period 0.5", "set clk_period 0.7")
    elif change == "virtual":
        original = original.replace(
            "-name vclk -period $clk_period", "-name vclk -period $other_period"
        )
    elif change == "port":
        original = original.replace("get_ports $clk_port_name", "get_ports other")
    elif change == "two_physical":
        original += "create_clock -name another -period $clk_period $clk_port\n"
    else:
        original = original.replace("-time ns", "-time ps")
    with pytest.raises(ValueError):
        flow_sdc(original, 0.5, time_unit="ns")


def test_native_period_edits_keep_io_expressions_live_in_real_tcl():
    interpreter = """
proc set_cmd_units {args} {}
proc current_design {args} {}
proc get_ports {args} {return clk}
proc all_inputs {} {return d}
proc all_outputs {} {return q}
proc create_clock {args} {puts CLOCK:[lindex $args 3]}
proc set_input_delay {delay args} {puts INPUT:$delay}
proc set_output_delay {delay args} {puts OUTPUT:$delay}
"""
    for period in [0.5, 0.8]:
        source = template("ns", period, header="# Keep live native constraints\n")
        bound = flow_sdc(source, period, time_unit="ns")
        result = subprocess.run(
            ["tclsh"],
            input=interpreter + bound,
            text=True,
            capture_output=True,
            check=True,
        )
        assert not result.stderr
        observed = [line.split(":", 1) for line in result.stdout.splitlines()]
        clocks = [float(value) for name, value in observed if name == "CLOCK"]
        delays = [
            float(value) for name, value in observed if name in {"INPUT", "OUTPUT"}
        ]
        assert clocks == [period, period]
        assert delays == pytest.approx([period * 0.2, period * 0.2])

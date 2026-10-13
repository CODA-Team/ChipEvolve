"""Exercise the SDC serialization Tcl with readers using different initial units."""

import subprocess

import pytest

from overnight_finish import sdc_export_commands


@pytest.mark.parametrize("reader_unit", ["ps", "ns"])
def test_sdc_roundtrip_preserves_clock_period_across_reader_units(
    tmp_path, reader_unit
):
    destination = tmp_path / "design with spaces.sdc"
    # Small timing-command test double; actual OpenSTA is verified by the EF run.
    script = """
set unit ns
proc set_cmd_units {flag value} { global unit; set unit $value }
proc write_sdc {path} {
    global unit
    set period [expr {$unit eq "ps" ? 310.0 : 0.310}]
    set handle [open $path w]
    puts $handle "create_clock -period $period"
    close $handle
}
proc create_clock {flag value} {
    global unit period_ns
    set period_ns [expr {$unit eq "ps" ? $value / 1000.0 : $value}]
}
"""
    script += "\n".join(sdc_export_commands(destination))
    script += f"\nset unit {reader_unit}\nsource {{{destination}}}\nputs $period_ns\n"
    result = subprocess.run(
        ["tclsh"], input=script, text=True, capture_output=True, check=True
    )
    assert not result.stderr
    assert float(result.stdout.strip()) == pytest.approx(0.310)

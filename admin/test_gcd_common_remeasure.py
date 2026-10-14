"""Keep comparison units and authoritative power parsing unambiguous."""

import hashlib
import json
import subprocess

import pytest
from gcd_common_remeasure import power_total, reference_liberties, reference_sdc


def test_reference_sdc_uses_explicit_ns_with_ps_reader(tmp_path):
    source = tmp_path / "original.sdc"
    source.write_text("create_clock -name core_clock -period 0.3100 [get_ports clk]\n")
    destination = tmp_path / "fixed.sdc"
    reference_sdc(source, destination)
    script = """
set unit ps
proc set_cmd_units {flag value} { global unit; set unit $value }
proc get_ports {name} { return $name }
proc create_clock {args} {
    global unit
    set period [lindex $args [expr {[lsearch $args -period]+1}]]
    puts [expr {$unit eq "ns" ? $period : $period / 1000.0}]
}
"""
    result = subprocess.run(
        ["tclsh"],
        input=script + f"source {{{destination}}}\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert not result.stderr
    assert float(result.stdout.strip()) == pytest.approx(0.310)


def test_power_uses_total_not_component_or_percentage():
    assert power_total("Total 1e-3 2e-3 3e-6 0.003003 100%\n") == pytest.approx(
        0.003003
    )


@pytest.mark.parametrize("log", ["", "Total 1 2 3 6\nTotal 1 2 3 6\n"])
def test_missing_or_multiple_power_reports_are_not_a_measurement(log):
    with pytest.raises(ValueError):
        power_total(log)


def test_reference_library_identity_rejects_same_filename_different_content(tmp_path):
    lib = tmp_path / "same_name_FF.lib"
    lib.write_text("original reference")
    folder = tmp_path / "handoffs/original-qualified"
    folder.mkdir(parents=True)
    receipt = {
        "library_sha256": {str(lib): hashlib.sha256(lib.read_bytes()).hexdigest()}
    }
    (folder / "input-receipt.json").write_text(json.dumps(receipt))
    assert reference_liberties(tmp_path) == [lib]
    lib.write_text("another nominal corner")
    with pytest.raises(ValueError, match="reference liberty changed"):
        reference_liberties(tmp_path)

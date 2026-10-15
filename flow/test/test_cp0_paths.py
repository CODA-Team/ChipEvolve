"""A CP0 score requires a timing path, including for combinational designs."""

import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("has_path", [False, True])
def test_unlinked_timing_is_rejected_but_constrained_combinational_paths_work(
    tmp_path, has_path
):
    evaluator = Path(__file__).resolve().parents[1] / "eval_tns.tcl"
    harness = tmp_path / "evaluate.tcl"
    harness.write_text(
        """
set ::env(LIB_FILES) {}
set ::env(ODB_PATH) unused.odb
set ::env(SPEF_PATH) unused.spef
set ::env(CP0) 590.868
set ::env(CLK_PORT) clk
proc read_db {args} {}
proc all_clocks {} {return {}}
proc get_ports {args} {return clock_pin}
proc create_clock {args} {}
proc estimate_parasitics {args} {}
proc set_propagated_clock {args} {}
proc all_registers {} {return {}}
proc report_checks {args} {puts "actual path report"}
proc report_tns {} {puts "tns max 0.00"}
proc report_wns {} {puts "wns max 0.00"}
proc set_cmd_units {args} {}
proc report_power {} {puts "Total 0.1 0.1 0.0 0.2"}
"""
        + (
            "proc find_timing_paths {args} {return path}\n"
            if has_path
            else "proc find_timing_paths {args} {return {}}\n"
        )
        + f"source {{{evaluator}}}\n"
    )
    result = subprocess.run(["tclsh", str(harness)], capture_output=True, text=True)
    if has_path:
        assert result.returncode == 0
        assert "tns max 0.00" in result.stdout
    else:
        assert result.returncode != 0
        assert "no constrained setup path" in result.stderr
        assert "tns max" not in result.stdout

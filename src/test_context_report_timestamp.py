"""Native context writers must not need lazy Tcl timezone initialization."""

from pathlib import Path

import pytest
from test_native_instance_identity import tcl

REPORTS = r"""
rename get_cells base_get_cells
proc get_cells {args} {
    if {[lindex $args end] eq "ordinary"} {return sta_driver}
    return [base_get_cells {*}$args]
}
proc report_checks {args} {
    set f [open [lindex $args end] w]
    if {[lindex $args [expr {[lsearch $args -format]+1}]] eq "full"} {
        puts $f {0.0 0.0 ^ ordinary/Q (BUF_X1)}
    } else {
        puts $f {endpoint 0.0 0.0 -0.125 (VIOLATED)}
    }
    close $f
}
"""
COMMANDS = (
    ("eco_rank_fanout_by_slack ordinary", "", "load_a/A -0.125"),
    ("eco_dump_path_siblings", "1", "endpoint -0.125"),
    ("eco_dump_fanout_ranks", "2", "load_a/A -0.125"),
)


@pytest.mark.parametrize(("command", "args", "row"), COMMANDS)
def test_report_body_survives_unavailable_timezone_formatting(
    tmp_path: Path, command: str, args: str, row: str
):
    original, limited = tmp_path / "normal.rpt", tmp_path / "limited.rpt"
    result = tcl(
        REPORTS
        + f"\n{command} {{{original}}} {args}\n"
        + r"""
rename clock native_clock
proc clock {subcommand args} {
    if {$subcommand in {seconds microseconds}} {
        return [native_clock $subcommand {*}$args]
    }
    error {timezone formatting unavailable in embedded Tcl}
}
"""
        + f"\nset code [catch {{{command} {{{limited}}} {args}}} message]\n"
        + "puts [list REPORT_STATUS $code $message]\n"
    )
    assert "REPORT_STATUS 0" in result
    first, second = original.read_text(), limited.read_text()
    assert "epoch " in second.splitlines()[0]
    assert row.split() in [line.split() for line in first.splitlines()]
    assert row.split() in [line.split() for line in second.splitlines()]
    # Only the comment timestamp may change; retain the original context body.
    assert first.splitlines()[1:] == second.splitlines()[1:]


@pytest.mark.parametrize(("command", "args", "row"), COMMANDS)
def test_writer_still_reports_actual_output_failure(
    tmp_path: Path, command: str, args: str, row: str
):
    missing = tmp_path / "missing-directory/report.rpt"
    result = tcl(
        REPORTS
        + f"\nset code [catch {{{command} {{{missing}}} {args}}} message]\n"
        + "puts [list REPORT_STATUS $code $message]\n"
    )
    assert "REPORT_STATUS 1" in result
    assert "couldn't open" in result
    assert not missing.exists()

"""Check real experiment integrity boundaries without simulating EDA quality."""

import subprocess

import pytest
from gcd_targeted_refine import change_commands, connection_signature


def test_size_or_vt_change_preserves_named_connection_signature():
    before = "module gcd (clk);\n NOR2x1_R u158 (.A(a), .B(b), .Y(n));\nendmodule"
    after = "module gcd (clk);\n NOR2x1_SL u158 (.Y(n), .B(b), .A(a));\nendmodule"
    assert connection_signature(before) == {"u158": {"A": "a", "B": "b", "Y": "n"}}
    assert connection_signature(before) == connection_signature(after)


def test_rewire_is_visible_even_with_same_instance_and_master():
    before = "NOR2x1_R u158 (.A(a), .B(b), .Y(n));"
    after = "NOR2x1_R u158 (.A(a), .B(c), .Y(n));"
    assert connection_signature(before) != connection_signature(after)


def test_instance_removal_is_visible():
    assert connection_signature("BUFx2_R b (.A(a), .Y(y));") != connection_signature("")


@pytest.mark.parametrize(
    "recorded_master,applied", [("NOR2x1_R", True), ("NOR2x2_R", False)]
)
def test_explicit_input_master_is_checked_before_cell_action(
    tmp_path, recorded_master, applied
):
    commands = change_commands(
        [{"instance": "u158", "before": recorded_master, "after": "NOR2x1_L"}]
    )
    script = tmp_path / "action.tcl"
    script.write_text(
        """
namespace eval ord {}
proc ord::get_db_block {} {return block}
proc block {cmd args} {return inst}
proc inst {cmd args} {return master}
proc master {cmd args} {return NOR2x1_R}
proc get_cells {name} {return $name}
proc replace_cell {inst name} {puts "APPLIED $inst $name"}
"""
        + "\n".join(commands)
    )
    result = subprocess.run(
        ["tclsh", str(script)], text=True, capture_output=True, check=False
    )
    if applied:
        assert result.returncode == 0
        assert "APPLIED u158 NOR2x1_L" in result.stdout
    else:
        assert result.returncode != 0
        assert "Input master differs" in result.stderr
        assert "APPLIED" not in result.stdout

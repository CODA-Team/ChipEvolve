"""A different PDK keeps the native flow and meaningful sequential checks."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from goalevolve.evaluation.contest2026 import (
    Contest2026Config,
    Contest2026OpenROADEvaluator,
    _write_rmp_combined_liberty,
    official_four_check,
)
from goalevolve.execution.execution import ExecutionPolicy

CHECKER = (
    Path(__file__).resolve().parents[2] / "third_party/official_checker/validity_check"
)


def test_explicit_pdk_loads_technology_before_cells_and_retains_native_recipe(tmp_path):
    bench = tmp_path / "benchmarks/unit"
    bench.mkdir(parents=True)
    for name in ("unit.v", "unit.def", "unit.sdc"):
        (bench / name).write_text("")
    pdk = tmp_path / "nangate45"
    (pdk / "lef").mkdir(parents=True)
    (pdk / "lib").mkdir()
    for name in ("Nangate.macro.lef", "Nangate.tech.lef"):
        (pdk / "lef" / name).write_text("")
    (pdk / "lib/Nangate.lib").write_text("")
    (pdk / "setRC.tcl").write_text("")
    evaluator = Contest2026OpenROADEvaluator(
        Contest2026Config("unit", bench.parent, tmp_path)
    )
    script = tmp_path / "evaluate.tcl"
    with patch(
        "goalevolve.evaluation.contest2026.load_platform_profile",
        return_value={"pdk_root": str(pdk)},
    ):
        evaluator._write_tcl(tcl=script, output=tmp_path / "out")
    text = script.read_text()
    assert text.index("Nangate.tech.lef") < text.index("Nangate.macro.lef")
    assert str(pdk / "lib/Nangate.lib") in text
    assert str(pdk / "setRC.tcl") in text
    assert "repair_timing" in text and "global_route" in text
    assert "/asap7/" not in text


def test_official_checks_use_the_explicit_pdk_cell_catalog(tmp_path):
    profile = {"equivalent_cells": str(tmp_path / "nangate-cells.csv")}
    with (
        patch(
            "goalevolve.evaluation.contest2026.load_platform_profile",
            return_value=profile,
        ),
        patch("goalevolve.evaluation.contest2026.ResilientCommandRunner") as runner,
    ):
        runner.return_value.run.return_value = SimpleNamespace(
            stdout_tail="SUMMARY: 4/4 checks passed", stderr_tail="", ok=True
        )
        ok, _ = official_four_check(
            pre_opt=tmp_path,
            post_opt=tmp_path,
            output_log=tmp_path / "checks.log",
            policy=ExecutionPolicy(),
        )
        assert ok
        command = runner.return_value.run.call_args.kwargs["command"]
        assert (
            command[command.index("--equiv_cells") + 1] == profile["equivalent_cells"]
        )


@pytest.mark.parametrize(
    "cell,pin", [("DFFHQNx1_ASAP7_75t_R", "CLK"), ("DFF_X1", "CK"), ("SDFFR_X2", "CK")]
)
def test_sequential_clock_pins_are_not_silently_unobserved(tmp_path, cell, pin):
    netlist = tmp_path / "test.v"
    netlist.write_text(f"{cell} state (.D(d), .Q(q), .{pin}(clk));\n")
    parse = runpy.run_path(str(CHECKER / "flipflop_check.py"))["parse_dffs"]
    states = parse(str(netlist))
    assert states["state"]["CLK"] == "clk"


@pytest.mark.parametrize("mutation", ["clock", "delete"])
def test_nangate_structural_checker_rejects_real_clock_and_state_mutations(
    tmp_path, mutation
):
    pre, post = tmp_path / "pre", tmp_path / "post"
    pre.mkdir()
    post.mkdir()
    (pre / "unit.v").write_text("input clk;\nDFF_X1 state (.D(d), .Q(q), .CK(clk));\n")
    (post / "unit.v").write_text(
        "input clk;\n"
        + (
            ""
            if mutation == "delete"
            else "DFF_X1 state (.D(d), .Q(q), .CK(other_clk));\n"
        )
    )
    code = 'import json,runpy,sys; m=runpy.run_path(sys.argv[1]); print(json.dumps(m["check_ff_integrity"](sys.argv[2],sys.argv[3])))'
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(CHECKER / "def_validity_check.py"),
            str(pre),
            str(post),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)[0] is False


def test_rmp_standard_cell_lib_does_not_include_nangate_sram(tmp_path):
    standard = tmp_path / "NangateOpenCellLibrary_typical.lib"
    macro = tmp_path / "fakeram45_256x16.lib"
    standard.write_text("library (nangate) { cell (INV_X1) { area : 1; } }")
    macro.write_text("library (fakeram) { cell (fakeram45_256x16) { area : 1000; } }")
    merged = _write_rmp_combined_liberty([standard, macro], tmp_path / "output")
    assert "INV_X1" in merged.read_text()
    assert "fakeram45_256x16" not in merged.read_text()

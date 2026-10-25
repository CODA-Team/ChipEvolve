"""The original ECO loop and its exporter use all explicitly bound models."""

import os
import subprocess
from pathlib import Path

import pytest
from platform_execution import session_libraries


def test_default_keeps_the_original_fifteen_asap7_models():
    libraries = session_libraries({"ASAP7_PDK": "/original/asap7"})
    assert len(libraries) == 15
    assert all(
        str(path).startswith("/original/asap7/lib/NLDM/asap7") for path in libraries
    )
    assert all("_FF_" in path.name for path in libraries)


def test_explicit_standard_and_macro_models_are_identical_at_export():
    names = ["/frozen/selected FF.lib.gz", "/frozen/sram_asap7_64x64.lib"]
    libraries = session_libraries({"TIMINGECO_LIB_FILES": "\n".join(names)})
    assert libraries == [Path(name) for name in names]


@pytest.mark.parametrize("explicit", [False, True])
def test_actual_loader_reads_the_explicit_sram_model(tmp_path, explicit):
    loader = (
        Path(__file__).resolve().parents[1] / "OpenROAD_utils/OpenROAD_load_design.tcl"
    )
    # Tcl stubs verify actual loading/control flow without executing EDA.
    program = """
rename source original_source
proc source {args} {return ""}
proc unknown {args} {return ""}
proc read_lef {args} {puts "ACTUAL_READ_LEF: $args"}
set f [open {%s} r]
set script [read $f]
close $f
eval $script
""".replace("%s", str(loader))
    names = [str(tmp_path / "std cells.lib"), str(tmp_path / "sram.lib")]
    environment = dict(os.environ, ASAP7_PDK=str(tmp_path), DESIGN_DIR=str(tmp_path))
    environment.pop("TIMINGECO_LIB_FILES", None)
    if explicit:
        environment["TIMINGECO_LIB_FILES"] = "\n".join(names)
    result = subprocess.run(
        ["tclsh"],
        input=program,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    observed = [
        line.removeprefix("READ_LIBERTY: ")
        for line in result.stdout.splitlines()
        if line.startswith("READ_LIBERTY: ")
    ]
    if explicit:
        assert observed == names
        assert "ACTUAL_READ_LEF:" not in result.stdout
    else:
        assert len(observed) == 15
        assert result.stdout.count("ACTUAL_READ_LEF:") == 5

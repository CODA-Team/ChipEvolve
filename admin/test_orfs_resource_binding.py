"""Use the declared native-flow reservation without changing the experiment."""

import pytest

from admin.test_local_business import deployment
from chip_evolve.config import write
from chip_evolve.jobs import Jobs
from chip_evolve.physical import baseline


@pytest.mark.parametrize("declared,expected", [(None, 24), (4, 4), (12, 12)])
def test_native_flow_uses_deployment_memory_and_preserves_inputs(
    tmp_path, monkeypatch, declared, expected
):
    d = deployment(tmp_path)
    sdc = tmp_path / "frozen.sdc"
    sdc.write_text("set_cmd_units -time ps\ncreate_clock -period 310 [get_ports clk]\n")
    design = {
        "sdc": str(sdc),
        "orfs_config": "designs/asap7/example/config.mk",
        "baseline_overrides": "export OTHER_VT = LVT SLVT\n",
        "libraries": [],
    }
    if declared is not None:
        design["orfs_execution"] = {"memory_gib": declared}
    d.value["designs"]["gcd"] = design
    d.value["runtime"] = {"image": "/frozen/toolchain.sif"}
    write(d.path, d.value)
    experiment = d.experiment("gcd", "actual-native-flow")
    original = sdc.read_bytes()

    class Submitted(Exception):
        pass

    def submit(self, key, inputs, staged, **options):
        assert key == "orfs"
        assert options.get("memory_gib", 24) == expected
        assert inputs["threads"] == 8
        assert inputs["orfs_image"] == "/frozen/toolchain.sif"
        assert inputs["design_config"] == design["orfs_config"]
        assert options["seconds"] == 900
        assert {"source": str(sdc), "destination": "inputs/design.sdc"} in staged
        assert (experiment / "inputs/design.mk").read_text() == (
            "include /OpenROAD-flow-scripts/flow/"
            + design["orfs_config"]
            + "\n"
            + design["baseline_overrides"]
        )
        raise Submitted

    monkeypatch.setattr(Jobs, "submit", submit)
    with pytest.raises(Submitted):
        baseline(d, "gcd", experiment, 900)
    assert sdc.read_bytes() == original

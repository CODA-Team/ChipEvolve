"""Use the declared native-flow reservation without changing the experiment."""

import pytest

from admin.test_local_business import deployment
from chip_evolve.config import write
from chip_evolve.jobs import Jobs, digest
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


@pytest.mark.parametrize("declared,expected", [(None, 24), (8, 8)])
def test_source_copy_uses_same_declared_reservation(
    tmp_path, monkeypatch, declared, expected
):
    from chip_evolve import professional
    from chip_evolve.flow_recipe import qualify_prepared_recipe

    d = deployment(tmp_path)
    if declared is not None:
        d.value["designs"]["gcd"]["orfs_execution"] = {"memory_gib": declared}
    exp = d.experiment("gcd", "source-copy")
    source = exp / "source"
    source.mkdir()
    config = source / "config.mk"
    config.write_text("export SYNTH_USE_SYN = 0\n")
    reference = exp / "original-result.json"
    objective = exp / "objective.json"
    write(reference, {"objective": str(objective)})
    write(
        exp / "recipe.json",
        {
            "source_result": str(reference),
            "source": str(source),
            "config_path": str(config),
            "resolved_config_sha256": digest(config),
            "design_id": "gcd",
            "physical_run_id": "original-native-flow",
        },
    )
    monkeypatch.setattr(professional, "tool_profile", lambda *a: exp / "profile.json")

    class Submitted(Exception):
        pass

    def submit(self, key, inputs, staged, **options):
        assert options.get("memory_gib", 24) == expected
        assert key == inputs["stage"] == "place"
        assert inputs["adapter"] == "a2_stage" and inputs["threads"] == 8
        assert options["parent"] == "original-native-flow"
        assert options["objective"] == objective
        assert options["seconds"] == 1800
        raise Submitted

    monkeypatch.setattr(Jobs, "submit", submit)
    with pytest.raises(Submitted):
        qualify_prepared_recipe(d, exp, seconds=1800)
    assert config.read_text() == "export SYNTH_USE_SYN = 0\n"


@pytest.mark.parametrize("declared,expected", [(None, 24), (4, 4), (12, 12)])
def test_common_physical_delivery_honors_same_design_reservation(
    tmp_path, monkeypatch, declared, expected
):
    from chip_evolve.physical import qualify

    d = deployment(tmp_path)
    design = {
        "libraries": [],
        "sdc": str(tmp_path / "unchanged.sdc"),
    }
    if declared is not None:
        design["orfs_execution"] = {"memory_gib": declared}
    d.value["designs"]["gcd"] = design
    d.value["runtime"] = {
        "executable": "apptainer",
        "bind_roots": [str(tmp_path)],
        "image": "/frozen/toolchain.sif",
    }
    d.value["tools"] = {"openroad": "/frozen/bin/openroad"}
    experiment = d.experiment("gcd", "common-final")
    source = tmp_path / "source.odb"
    objective = tmp_path / "objective.json"

    class Submitted(Exception):
        pass

    def command(self, key, argv, **options):
        assert key == "qualification"
        assert options.get("memory_gib", 24) == expected
        assert options["parent"] == "original-professional-producer"
        assert options["objective"] == objective
        assert argv[argv.index("-threads") + 1] == "8"
        script = experiment / "qualification/route.tcl"
        content = script.read_text()
        assert f"read_db {{{source}}}" in content
        assert f"read_sdc {{{design['sdc']}}}" in content
        assert "global_route -congestion_iterations 50" in content
        assert "detailed_route -output_drc" in content
        assert "extract_parasitics -ext_model_file" in content
        assert source in options["capture"]
        raise Submitted

    monkeypatch.setattr(Jobs, "command", command)
    with pytest.raises(Submitted):
        qualify(
            Jobs(d, "gcd", experiment),
            source,
            "original-professional-producer",
            objective,
            tmp_path / "pdk",
        )

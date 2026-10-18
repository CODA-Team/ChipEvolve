"""A downstream source must retain auxiliary files from a submitted design."""

from pathlib import Path

from chip_evolve.config import Deployment, write
from chip_evolve.professional import flow_source


def prepare(tmp_path: Path, dependencies: bool):
    template = tmp_path / "template"
    config = "designs/technology/arbitrary-design/config.mk"
    (template / "flow" / config).parent.mkdir(parents=True)
    (template / "flow" / config).write_text("export DESIGN_NAME = example\n")
    formal = tmp_path / "professional"
    (formal / "flow").mkdir(parents=True)
    for name in ("eval_tns.sh", "eval_tns.tcl", "maindriver.sh"):
        (formal / "flow" / name).write_text(name + "\n")
    (formal / "run.sh").write_text("run\n")
    design = {
        "orfs_config": config,
        "libraries": [],
        "baseline_overrides": "export CTS_CLUSTER_SIZE = 25\n",
    }
    if dependencies:
        files = []
        for index, destination in enumerate(
            ("inputs/first/route.tcl", "inputs/second/route.tcl")
        ):
            original = tmp_path / f"original-{index}.tcl"
            original.write_text(
                f"set_global_routing_layer_adjustment M{index + 2} 0.25\n"
            )
            files.append({"source": str(original), "destination": destination})
        design["flow_dependencies"] = files
        design["baseline_overrides"] += (
            "export FASTROUTE_TCL = /work/inputs/first/route.tcl\n"
            "export PRE_GLOBAL_ROUTE_TCL = /work/inputs/second/route.tcl\n"
        )
    path = tmp_path / "local.json"
    write(
        path,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "runtime"),
            "flow_template": str(template),
            "professional": {"flow": {"source": str(formal)}},
            "designs": {"example": design},
        },
    )
    return Deployment(path), design, config


def test_declared_auxiliary_bytes_and_relative_layout_survive_handoff(tmp_path):
    deployment, design, config = prepare(tmp_path, True)
    source = flow_source(deployment, tmp_path / "delivery", design_id="example")
    text = (source / "flow" / config).read_text()
    assert "/work/inputs/" not in text
    assert "export CTS_CLUSTER_SIZE = 25\n" in text
    for entry in design["flow_dependencies"]:
        copied = source / "flow/source-bindings" / entry["destination"]
        assert str(copied) in text
        assert copied.read_bytes() == Path(entry["source"]).read_bytes()


def test_design_without_auxiliary_inputs_keeps_original_overrides(tmp_path):
    deployment, design, config = prepare(tmp_path, False)
    source = flow_source(deployment, tmp_path / "delivery", design_id="example")
    assert (source / "flow" / config).read_text() == (
        "export DESIGN_NAME = example\n\n" + design["baseline_overrides"]
    )
    assert not (source / "flow/source-bindings").exists()

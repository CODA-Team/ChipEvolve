"""Flow recipes inherit submitted inputs and retain physical source identity."""

from pathlib import Path

import pytest

from chip_evolve.config import read, write
from chip_evolve.flow_recipe import bind_config, inherit_prepared_source, source_binding
from chip_evolve.jobs import digest


def source(root):
    original = root / "original"
    original.mkdir()
    config, sdc, library = (
        original / name for name in ("design.mk", "design.sdc", "lib.lib")
    )
    config.write_text(
        "include /OpenROAD-flow-scripts/flow/designs/pdk/design/config.mk\nexport SYNTH_USE_SYN = 1\nexport CORE_UTILIZATION = 67\n"
    )
    sdc.write_text("create_clock -period 10 [get_ports clk]\n")
    library.write_text("library(test) {}\n")
    frame = original / "result.json"
    write(
        frame,
        {
            "design_id": "design",
            "run_id": "measurement",
            "physical_run_id": "actual-orfs",
        },
    )
    folder = original / "jobs/orfs"
    write(
        folder / "task.json",
        {
            "design_id": "design",
            "inputs": {
                "adapter": "orfs_flow",
                "orfs_image": "/frozen.sif",
                "design_config": "designs/pdk/design/config.mk",
                "config_path": "inputs/design.mk",
                "sdc_path": "inputs/design.sdc",
                "liberty_paths": ["inputs/lib.lib"],
            },
            "staged_inputs": [
                {"source": str(p), "destination": "inputs/" + p.name}
                for p in [config, sdc, library]
            ],
        },
    )
    write(folder / "submission.json", {"run": {"run_id": "actual-orfs"}})
    write(
        folder / "staged-hashes.json",
        {str(p): digest(p) for p in [config, sdc, library]},
    )
    return frame


def test_source_recipe_preserves_submitted_overrides_and_exact_library_bytes(tmp_path):
    frame = source(tmp_path)
    binding = source_binding(frame)
    flow = tmp_path / "prepared-flow"
    flow.mkdir()
    config = bind_config(flow, binding)
    text = config.read_text()
    assert "export CORE_UTILIZATION = 67" in text
    assert "export SYNTH_USE_SYN = 1" in text
    assert "include " + str(flow / "designs/pdk/design/config.mk") in text
    assert "override export LIB_FILES = " in text
    assert (flow / "source-bindings/0-lib.lib").read_bytes() == Path(
        binding["libraries"][0]
    ).read_bytes()
    assert (flow / "source-bindings/design.sdc").read_bytes() == Path(
        binding["sdc"]
    ).read_bytes()
    assert binding["physical_run_id"] == "actual-orfs"


def test_changed_registered_source_cannot_become_a_new_recipe(tmp_path):
    frame = source(tmp_path)
    (frame.parent / "design.mk").write_text("export CORE_UTILIZATION = 10\n")
    with pytest.raises(ValueError, match="input changed"):
        source_binding(frame)


def test_native_source_does_not_silently_convert_ns_to_ps(tmp_path, monkeypatch):
    from admin.test_local_business import deployment
    from chip_evolve import flow_recipe

    frame = source(tmp_path)
    sdc = frame.parent / "design.sdc"
    sdc.write_text(
        "set_cmd_units -time ns\ncreate_clock -period 0.31 [get_ports clk]\n"
    )
    hashes = frame.parent / "jobs/orfs/staged-hashes.json"
    write(hashes, {**read(hashes), str(sdc): digest(sdc)})
    d = deployment(tmp_path)
    exp = d.experiment("gcd", "units")
    monkeypatch.setattr(
        flow_recipe,
        "prepare_flow_recipe",
        lambda *a: pytest.fail("must reject before EDA"),
    )
    with pytest.raises(ValueError, match="ps-serialized source"):
        flow_recipe.prepare_native_source(d, frame, exp)


def test_native_clock_binding_uses_registered_input_not_a_later_measurement(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from admin.test_local_business import deployment
    from chip_evolve import flow_recipe, professional

    d = deployment(tmp_path)
    d.value["designs"]["gcd"] = {
        "platform": "pdk",
        "nickname": "test",
        "clock_period_ns": 0.31,
    }
    exp = d.experiment("gcd", "clock-binding")
    prepared = exp / "source"
    design = prepared / "flow/designs/pdk/test"
    design.mkdir(parents=True)
    registered = exp / "actual-source.sdc"
    registered.write_text(
        "set_cmd_units -time ps\ncreate_clock -period 310 [get_ports clk]\nset_input_delay 62 -clock clk [get_ports d]\n"
    )
    measured = exp / "later-measurement.sdc"
    measured.write_text(registered.read_text().replace("delay 62", "delay 22"))
    write(exp / "recipe.json", {"sdc": str(registered)})
    monkeypatch.setattr(flow_recipe, "prepare_native_source", lambda *a: prepared)

    class CheckedBinding(Exception):
        pass

    def check(*args):
        actual = (design / "constraint.sdc").read_text()
        assert "set_input_delay 62" in actual and "set_input_delay 22" not in actual
        assert "-period $clk_period" in actual
        raise CheckedBinding()

    monkeypatch.setattr(professional, "tool_profile", check)
    args = SimpleNamespace(
        flow_recipe="source", source=exp / "result.json", design="gcd"
    )
    with pytest.raises(CheckedBinding):
        professional.run_flow(
            d,
            args,
            exp,
            {"files": {"sdc": str(measured)}},
            exp / "objective.json",
            exp / "context.json",
        )


def test_staged_source_hook_is_relocated_with_its_frozen_bytes(tmp_path):
    frame = source(tmp_path)
    hook = frame.parent / "routing.tcl"
    hook.write_text("puts original-routing-hook\n")
    config = frame.parent / "design.mk"
    with config.open("a") as stream:
        stream.write("export FASTROUTE_TCL = /work/inputs/routing.tcl\n")
    task_file = frame.parent / "jobs/orfs/task.json"
    task = read(task_file)
    task["staged_inputs"].append(
        {"source": str(hook), "destination": "inputs/routing.tcl"}
    )
    write(task_file, task)
    hashes = frame.parent / "jobs/orfs/staged-hashes.json"
    write(
        hashes, {**read(hashes), str(hook): digest(hook), str(config): digest(config)}
    )
    flow = tmp_path / "flow"
    flow.mkdir()
    bound = bind_config(flow, source_binding(frame))
    assert "/work/inputs/routing.tcl" not in bound.read_text()
    assert (
        flow / "source-bindings/input-0-routing.tcl"
    ).read_bytes() == hook.read_bytes()
    hook.write_text("puts changed-routing\n")
    with pytest.raises(ValueError, match="input changed"):
        source_binding(frame)


@pytest.mark.parametrize(
    "backend,unset,error", [("1", False, "Yosys"), ("0", True, "unset")]
)
def test_unqualified_backend_or_unset_knob_is_not_silently_accepted(
    tmp_path, monkeypatch, backend, unset, error
):
    from admin.test_local_business import deployment
    from chip_evolve import flow_recipe

    d = deployment(tmp_path)
    exp = d.experiment("gcd", "resolve")
    values = {name: "1" for name in flow_recipe.NATIVE_PARAMETERS}
    values["SYNTH_USE_SYN"] = backend
    if unset:
        values["PLACE_DENSITY_LB_ADDON"] = "__UNSET__"
    monkeypatch.setattr(
        flow_recipe.Jobs,
        "command",
        lambda *a, **k: write(exp / "resolved-native-parameters.json", values),
    )
    monkeypatch.setattr(flow_recipe, "container", lambda *a: [])
    with pytest.raises(ValueError, match=error):
        flow_recipe.resolve_native_parameters(
            d,
            exp,
            {
                "source": str(exp / "source"),
                "design_id": "gcd",
                "config_path": "config.mk",
                "physical_run_id": "producer",
            },
        )


def test_source_must_own_the_recorded_physical_producer(tmp_path):
    frame = source(tmp_path)
    value = read(frame)
    value["physical_run_id"] = "another-orfs"
    write(frame, value)
    with pytest.raises(ValueError, match="does not own"):
        source_binding(frame)


def test_wrapper_cannot_silently_choose_another_base_design(tmp_path):
    frame = source(tmp_path)
    binding = source_binding(frame)
    Path(binding["config"]).write_text("include unrelated/config.mk\n")
    flow = tmp_path / "prepared"
    flow.mkdir()
    with pytest.raises(ValueError, match="recorded design"):
        bind_config(flow, binding)


def test_legacy_source_without_input_identity_needs_explicit_reconstruction(tmp_path):
    frame = source(tmp_path)
    (frame.parent / "jobs/orfs/staged-hashes.json").unlink()
    with pytest.raises(ValueError, match="lacks frozen input hashes"):
        source_binding(frame)


@pytest.mark.parametrize("native_overlay", [False, True])
def test_handoff_inherits_pinned_physical_tree_and_rejects_changed_scripts(
    tmp_path, native_overlay
):
    original = tmp_path / "prepared"
    flow = original / "flow"
    flow.mkdir(parents=True)
    makefile = flow / "Makefile"
    makefile.write_text("modern physical flow\n")
    write(original / "image-files.json", {"Makefile": digest(makefile)})
    if native_overlay:
        write(original / "prepared-files.json", {"flow/Makefile": digest(makefile)})
    config = flow / "source-config.mk"
    config.write_text("export CORE_UTILIZATION = 67\n")
    recipe = tmp_path / "recipe.json"
    write(
        recipe,
        {
            "source": str(original),
            "config_path": str(config),
            "resolved_config_sha256": digest(config),
            "physical_tree_sha256": "tree",
        },
    )
    experiment = tmp_path / "next-agent"
    experiment.mkdir()
    result = inherit_prepared_source({"flow_recipe": str(recipe)}, experiment)
    assert (result / "flow/Makefile").read_bytes() == makefile.read_bytes()
    assert read(experiment / "inherited-recipe.json")["source_recipe_sha256"] == digest(
        recipe
    )
    makefile.write_text("unexpected old template\n")
    other = tmp_path / "other-agent"
    other.mkdir()
    with pytest.raises(ValueError, match="physical source changed"):
        inherit_prepared_source({"flow_recipe": str(recipe)}, other)


@pytest.mark.parametrize("explicit_recipe", [False, True])
def test_layout_resume_uses_explicit_source_and_keeps_legacy_default(
    tmp_path, monkeypatch, explicit_recipe
):
    from types import SimpleNamespace

    from admin.test_local_business import deployment
    from chip_evolve import professional

    d = deployment(tmp_path)
    experiment = d.experiment("gcd", "handoff")
    (experiment / "source-checkpoint.zip").write_bytes(b"already materialized")
    physical = tmp_path / "physical/flow"
    physical.mkdir(parents=True)
    (physical / "Makefile").write_text("actual-source")
    write(
        physical.parent / "image-files.json",
        {"Makefile": digest(physical / "Makefile")},
    )
    config = physical / "source-config.mk"
    config.write_text("source binding")
    recipe = tmp_path / "recipe.json"
    write(
        recipe,
        {
            "source": str(physical.parent),
            "config_path": str(config),
            "resolved_config_sha256": digest(config),
            "physical_tree_sha256": "tree",
        },
    )
    frame = {"flow_archive": "registered.zip"}
    if explicit_recipe:
        frame["flow_recipe"] = str(recipe)

    def legacy(_, folder):
        source = folder / "source"
        (source / "flow").mkdir(parents=True)
        (source / "flow/Makefile").write_text("legacy-template")
        return source

    class SelectedSource(Exception):
        pass

    def profile(_, selected, folder):
        assert (selected / "flow/Makefile").read_text() == (
            "actual-source" if explicit_recipe else "legacy-template"
        )
        raise SelectedSource()

    monkeypatch.setattr(professional, "flow_source", legacy)
    monkeypatch.setattr(professional, "tool_profile", profile)
    with pytest.raises(SelectedSource):
        professional.resume_layout(
            SimpleNamespace(deployment=d, experiment=experiment, design_id="gcd"),
            tmp_path / "placement.odb",
            frame,
            tmp_path / "objective.json",
            "producer",
        )

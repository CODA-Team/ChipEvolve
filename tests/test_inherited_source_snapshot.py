"""A handoff inherits its registered recipe, not unrelated search checkpoints."""

import pytest

from chip_evolve.config import read, write
from chip_evolve.flow_recipe import inherit_prepared_source
from chip_evolve.jobs import digest


def prepared_source(tmp_path):
    source = tmp_path / "prepared"
    registered = {
        "flow/Makefile": b"original modern flow\n",
        "flow/source-config.mk": b"export DETAILED_ROUTE_END_ITERATION = 64\n",
        "flow/designs/pdk/example/config.mk": b"export DESIGN_NAME = example\n",
        "flow/source-bindings/design.sdc": b"set_cmd_units -time ps\n",
        "flow/platforms/pdk/lib/results/cells.lib": b"registered library\n",
        "flow/results/declared-input.dat": b"explicitly registered dependency\n",
        "config/env.local.sh": b"export ORIGINAL_TOOLCHAIN=1\n",
    }
    for name, data in registered.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write(
        source / "prepared-files.json",
        {name: digest(source / name) for name in registered},
    )
    recipe = tmp_path / "recipe.json"
    write(
        recipe,
        {
            "source": str(source),
            "config_path": str(source / "flow/source-config.mk"),
            "resolved_config_sha256": digest(source / "flow/source-config.mk"),
            "physical_tree_sha256": "registered-tree",
            "design_config": "designs/pdk/example/config.mk",
        },
    )
    return source, recipe, registered


def test_only_registered_recipe_files_are_inherited_and_old_outputs_stay_owned(
    tmp_path,
):
    source, recipe, registered = prepared_source(tmp_path)
    unrelated = {
        "flow/results/pdk/example/run_19/5_route.odb": b"another candidate layout",
        "flow/reports/run_19/setup.rpt": b"another candidate timing",
        "flow/backup_dir/iteration2/candidate.json": b"another search iteration",
        "flow/config_19.mk": b"unselected mutable candidate config",
    }
    for name, data in unrelated.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    experiment = tmp_path / "next"
    experiment.mkdir()
    result = inherit_prepared_source({"flow_recipe": str(recipe)}, experiment)
    copied = {str(p.relative_to(result)) for p in result.rglob("*") if p.is_file()}
    assert copied == {*registered, "prepared-files.json"}
    for name, data in registered.items():
        assert (result / name).read_bytes() == data
    for name, data in unrelated.items():
        assert not (result / name).exists()
        assert (source / name).read_bytes() == data
    assert read(result / "prepared-files.json") == read(source / "prepared-files.json")


@pytest.mark.parametrize("removed", [False, True])
def test_registered_dependency_change_is_rejected_before_copy(tmp_path, removed):
    source, recipe, _ = prepared_source(tmp_path)
    dependency = source / "flow/source-bindings/design.sdc"
    if removed:
        dependency.unlink()
    else:
        dependency.write_bytes(b"changed clock")
    experiment = tmp_path / "next"
    experiment.mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        inherit_prepared_source({"flow_recipe": str(recipe)}, experiment)
    assert not (experiment / "source").exists()

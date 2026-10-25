"""Goal-generated validation inputs must be captured before they exist."""

import argparse
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chip_evolve import native
from chip_evolve.config import Deployment


@pytest.mark.parametrize("top", ["gcd", "ariane_tile"])
def test_prepare_declares_generated_csvs_before_running_eda(tmp_path: Path, top: str):
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    inputs = tmp_path / "source-inputs"
    inputs.mkdir()
    files = {}
    for ext in ("def", "v", "sdc", "odb"):
        source = inputs / (top + "." + ext)
        source.write_text("unit input\n")
        files[ext] = str(source)
    pdk = tmp_path / "pdk"
    (pdk / "lib").mkdir(parents=True)
    (pdk / "setRC.tcl").write_text("# unit fixture\n")
    library = inputs / "unit.lib"
    library.write_text("unit library\n")
    official = tmp_path / "official"
    (official / "validity_check").mkdir(parents=True)
    (official / "validity_check/OpenROAD_utils.tcl").write_text("# unit fixture\n")
    deployment = Mock(spec=Deployment)
    deployment.value = {
        "professional": {
            "goal": {
                "source": str(tmp_path / "agent"),
                "official_checker": str(official),
                "pdk_template": str(pdk),
            }
        },
        "tools": {"openroad": "openroad"},
    }
    deployment.design.return_value = {
        "top": top,
        "platform": "unit-pdk",
        "libraries": [{"path": str(library)}],
    }
    jobs = Mock()
    observed = []

    class Prepared(Exception):
        pass

    def execute_prepare(key, command, **kwargs):
        bench = experiment / "inputs/benchmarks" / top
        assert not (bench / "node.csv").exists()
        assert not (bench / "nets.csv").exists()
        observed.extend(kwargs["capture"])
        # These outputs appear only while the tool runs.
        (bench / "node.csv").write_text("unit node output\n")
        (bench / "nets.csv").write_text("unit net output\n")
        raise Prepared

    jobs.command.side_effect = execute_prepare
    with (
        patch.object(
            native, "freeze", side_effect=lambda source, target, **kw: target.mkdir()
        ),
        patch.object(native, "Jobs", return_value=jobs),
        patch.object(
            native, "container", side_effect=lambda deployment, command: command
        ),
        pytest.raises(Prepared),
    ):
        native.run_goal(
            deployment,
            argparse.Namespace(seconds=60, code_source=None, design=top),
            experiment,
            {"files": files, "run_id": "source-run"},
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    bench = experiment / "inputs/benchmarks" / top
    assert set(observed) == {
        experiment / "prepare.tcl",
        *(bench / (top + "." + ext) for ext in ("def", "v", "sdc", "odb")),
        bench / "node.csv",
        bench / "nets.csv",
    }
    assert "write_node_and_net_files" in (experiment / "prepare.tcl").read_text()

"""Explicit Code physical memory must reach native profiles before dispatch."""

from argparse import Namespace
from copy import deepcopy
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from chip_evolve.config import Deployment, read, write
from chip_evolve.environment import deployment_binding
from chip_evolve.native import run_goal
from chip_evolve.professional import run_dpl


class NativeEntryReached(Exception):
    pass


class PreparedJobs:
    campaign = "resource-test"

    def __init__(self, *args):
        pass

    def command(self, *args, **kwargs):
        pass


def local_fixture(tmp_path, role, memory):
    template = tmp_path / "profile.json"
    native = tmp_path / "native"
    (native / "orfs/flow").mkdir(parents=True)
    namespace = native / "orfs/tools/OpenROAD/src/dpl_evolve"
    namespace.mkdir(parents=True)
    (namespace / "README.md").write_text("Original framework seed\n")
    (native / "state/seed_sources").mkdir(parents=True)
    (native / "official_checker").mkdir()
    (native / "pdk").mkdir()
    (native / "pdk/setRC.tcl").write_text("# native PDK\n")
    campaign = native / "campaign.json"
    write(campaign, {})
    write(
        template,
        {
            "orfs_root": str(native / "orfs"),
            "state_root": str(native / "state"),
            "core_binary": "/core/bin/openroad",
            "source_seed": str(native / "source-seed"),
            "resources": {
                "build": {"cpu_cores": 8, "memory_bytes": 32 << 30},
                "physical": {"cpu_cores": 1, "memory_bytes": 64 << 30},
                "analysis": {"cpu_cores": 1, "memory_bytes": 4 << 30},
            },
            "container_environment": {},
        },
    )
    binding = {
        "source": str(native / "controller"),
        "profile_template": str(template),
        "candidate_source": str(native / "candidate"),
        "official_checker": str(native / "official_checker"),
        "pdk_template": str(native / "pdk"),
        "campaign_template": str(campaign),
    }
    if memory is not None:
        binding["physical_memory_gib"] = memory
    local = tmp_path / "local.json"
    write(
        local,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "runtime"),
            "kernel_url": "http://localhost:1",
            "data_url": "http://localhost:2",
            "client_python": "/client/bin/python",
            "goal_python": "/goal/bin/python",
            "runtime": {
                "executable": "/apptainer",
                "bind_roots": [],
                "image": "/tool.sif",
            },
            "tools": {"openroad": "/tool/bin/openroad"},
            "professional": {role: binding},
            "designs": {
                "jpeg": {
                    "top": "jpeg_encoder",
                    "platform": "asap7",
                    "nickname": "jpeg",
                    "libraries": [],
                }
            },
        },
    )
    deployment = Deployment(local)
    experiment = deployment.experiment("jpeg", "resource-test")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    files = {}
    for ext in ("def", "v", "sdc", "odb"):
        path = inputs / ("input." + ext)
        path.write_text("frozen original " + ext)
        files[ext] = str(path)
    archive = inputs / "flow.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("flow/results/3_place.odb", "original placement")
    frame = {
        "files": files,
        "run_id": "parent-run",
        "flow_archive": str(archive),
        "snapshot_ids": {"opendb": "parent-objects", "orfs": "parent-metrics"},
    }
    args = Namespace(
        design="jpeg", code_source=None, operation="evolve", seconds=43200, rounds=1
    )
    return deployment, args, experiment, frame


def freeze_controller(source, destination, **kwargs):
    destination.mkdir(parents=True)


@pytest.mark.parametrize("role,run", [("dpl", run_dpl), ("goal", run_goal)])
@pytest.mark.parametrize("memory,expected", [(None, 24), (8, 8), (64, 64)])
def test_native_profile_keeps_original_threads_and_explicit_memory(
    tmp_path, role, run, memory, expected
):
    deployment, args, experiment, frame = local_fixture(tmp_path, role, memory)
    module = "chip_evolve.native" if role == "goal" else "chip_evolve.professional"
    with (
        patch(module + ".freeze", side_effect=freeze_controller),
        patch(module + ".Jobs", PreparedJobs),
        patch("chip_evolve.dpl_case.prepare_case", return_value="jpeg_asap7"),
        patch(module + ".invoke", side_effect=NativeEntryReached) as invoke,
        pytest.raises(NativeEntryReached),
    ):
        run(
            deployment,
            args,
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    assert invoke.call_count == 1
    profile = read(experiment / "profile.json")
    assert profile["resources"]["physical"] == {
        "cpu_cores": 8,
        "memory_bytes": expected << 30,
        "processes": 2048,
    }
    assert profile["resources"]["build"] == {"cpu_cores": 8, "memory_bytes": 32 << 30}
    assert profile["resources"]["analysis"] == {"cpu_cores": 1, "memory_bytes": 4 << 30}
    assert profile["data_context"]["parent_run_id"] == "parent-run"
    assert invoke.call_args.args[-1] == args.seconds


@pytest.mark.parametrize("role,run", [("dpl", run_dpl), ("goal", run_goal)])
@pytest.mark.parametrize("memory", [0, -1, True, 1.5, "8"])
def test_invalid_explicit_memory_fails_before_preparation_or_eda(
    tmp_path, role, run, memory
):
    deployment, args, experiment, frame = local_fixture(tmp_path, role, memory)
    module = "chip_evolve.native" if role == "goal" else "chip_evolve.professional"
    with (
        patch(module + ".freeze") as prepare,
        patch(module + ".Jobs") as jobs,
        patch(module + ".invoke", side_effect=NativeEntryReached),
        pytest.raises(ValueError, match="physical_memory_gib"),
    ):
        run(
            deployment,
            args,
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    prepare.assert_not_called()
    jobs.assert_not_called()


def test_explicit_budget_is_part_of_existing_deployment_identity(tmp_path):
    deployment, *_ = local_fixture(tmp_path, "goal", None)
    original = deployment_binding(deployment, "jpeg")
    original = deepcopy(original)
    deployment.value["professional"]["goal"]["physical_memory_gib"] = 8
    assert deployment_binding(deployment, "jpeg") != original

"""ECO uses the explicitly bound PDK without changing its native algorithm."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from chip_evolve.config import Deployment
from chip_evolve.native import run_eco


class CopyBoundaryReached(Exception):
    pass


def deployment_for(tmp_path, **binding):
    path = tmp_path / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "chip-evolve.local.v1",
                "state_root": str(tmp_path / "state"),
                "professional": {
                    "eco": {"source": str(tmp_path / "upstream"), **binding}
                },
                "designs": {"any-design": {}},
            }
        )
    )
    return Deployment(path)


def first_pdk_copy(tmp_path, **binding):
    deployment = deployment_for(tmp_path, **binding)
    with (
        patch("chip_evolve.native.freeze"),
        patch(
            "chip_evolve.native.shutil.copytree", side_effect=CopyBoundaryReached
        ) as copy,
        pytest.raises(CopyBoundaryReached),
    ):
        run_eco(
            deployment,
            argparse.Namespace(design="any-design"),
            tmp_path / "experiment",
            {},
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    return copy.call_args


def test_explicit_eco_pdk_uses_common_frozen_template(tmp_path):
    pdk = tmp_path / "qualified-common-pdk"
    call = first_pdk_copy(tmp_path, pdk_template=str(pdk))
    assert call.args == (pdk, tmp_path / "experiment/source/asap7")


def test_unconfigured_eco_keeps_original_project_pdk(tmp_path):
    call = first_pdk_copy(tmp_path)
    assert call.args[0] == tmp_path / "upstream/asap7"


def test_missing_explicit_pdk_does_not_fall_back_to_upstream(tmp_path):
    upstream = tmp_path / "upstream"
    (upstream / "asap7").mkdir(parents=True)
    deployment = deployment_for(tmp_path, pdk_template=str(tmp_path / "missing-pdk"))
    with (
        patch(
            "chip_evolve.native.freeze",
            side_effect=lambda _origin, target, **_kwargs: Path(target).mkdir(
                parents=True
            ),
        ),
        pytest.raises(FileNotFoundError, match="missing-pdk"),
    ):
        run_eco(
            deployment,
            argparse.Namespace(design="any-design"),
            tmp_path / "experiment",
            {},
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )


@pytest.mark.parametrize("memory_gib", [None, 16])
def test_flat_common_pdk_prepares_native_layout_and_preserves_bound_rc(
    tmp_path, memory_gib
):
    pdk = tmp_path / "common-pdk"
    (pdk / "lib").mkdir(parents=True)
    (pdk / "setRC.tcl").write_text("set_layer_rc -layer M2 -resistance 0.0462311\n")
    library = tmp_path / "selected-FF.lib"
    library.write_text("library (unit) {}\n")
    deployment = deployment_for(tmp_path, pdk_template=str(pdk))
    deployment.value.update(
        runtime={
            "executable": "unused-runtime",
            "image": "unused-image",
            "bind_roots": [],
        },
        tools={"openroad": "unused-openroad"},
        kernel_url="http://127.0.0.1:1",
        data_url="http://127.0.0.1:1",
        toolchain={"test_identity": "unit"},
    )
    deployment.value["professional"]["eco"]["python"] = "unused-python"
    if memory_gib is not None:
        deployment.value["professional"]["eco"]["session_memory_gib"] = memory_gib
    deployment.value["designs"]["any-design"] = {
        "libraries": [{"path": str(library)}],
        "top": "unit",
    }
    frame = {
        "run_id": "unit-parent",
        "snapshot_ids": {"opendb": "unit-objects", "orfs": "unit-metrics"},
        "exports": {
            "opendb": {
                "execution": {
                    "artifacts": [
                        {"store_key": "unit." + ext, "artifact_id": "unit-" + ext}
                        for ext in ("odb", "sdc", "spef")
                    ]
                }
            }
        },
    }
    experiment = tmp_path / "experiment"
    with (
        patch(
            "chip_evolve.native.freeze",
            side_effect=lambda _origin, target, **_kwargs: target.mkdir(parents=True),
        ),
        patch("chip_evolve.native.environment", return_value={}),
        patch("chip_evolve.native.Jobs", side_effect=CopyBoundaryReached),
        pytest.raises(CopyBoundaryReached),
    ):
        run_eco(
            deployment,
            argparse.Namespace(design="any-design", rounds=8, seconds=7200),
            experiment,
            frame,
            tmp_path / "objective.json",
            tmp_path / "context.json",
        )
    assert (experiment / "source/asap7/setRC.tcl").read_bytes() == (
        pdk / "setRC.tcl"
    ).read_bytes()
    assert (
        experiment / "source/asap7/lib/NLDM" / library.name
    ).read_bytes() == library.read_bytes()
    profile = json.loads((experiment / "profile.json").read_text())
    assert profile["parent_run_id"] == "unit-parent"
    assert profile["memory_gib"] == (24 if memory_gib is None else memory_gib)
    assert profile["input_artifacts"]["odb"] == "unit-odb"
    # Exercise the generated launcher: --cleanenv must not drop tool threads.
    import os
    import runpy
    import sys

    calls = []
    with (
        patch.object(sys, "argv", ["openroad", "-exit", "measure.tcl"]),
        patch.object(os, "execvp", side_effect=lambda exe, argv: calls.append(argv)),
    ):
        runpy.run_path(str(experiment / "openroad"))
    assert calls[0][-5:] == ["unused-openroad", "-threads", "8", "-exit", "measure.tcl"]

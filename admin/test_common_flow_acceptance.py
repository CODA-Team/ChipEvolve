"""An accepted request alone cannot prove the stage used the common binary."""

import hashlib
import json
import zipfile
from copy import deepcopy

import pytest
from accept_common_flow_campaign import (
    IMAGE_SHA,
    OPENROAD,
    ORFS,
    area_facts,
    verify_identity,
)


@pytest.mark.parametrize("corruption", [None, "hash", "unit"])
def test_area_comes_from_registered_reports_and_declared_units(tmp_path, corruption):
    path = tmp_path / "platform-state/iteration-1/slot-1-route_finish.zip"
    path.parent.mkdir(parents=True)
    files = {
        "flow/logs/6_report.json": {
            "finish__design__die__area": 38927.3,
            "finish__design__instance__area__stdcell": 20749.1,
        },
        "flow/logs/2_1_floorplan.json": {
            "run__flow__platform__distance_units": "1nm"
            if corruption == "unit"
            else "1um"
        },
    }
    artifacts = []
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in files.items():
            raw = json.dumps(value).encode()
            archive.writestr(name, raw)
            artifacts.append(
                {"store_key": name, "sha256": hashlib.sha256(raw).hexdigest()}
            )
    if corruption == "hash":
        artifacts[0]["sha256"] = "a" * 64
    tasks = {
        "iteration-1/slot-1-route_finish.json": {
            "stage": "route_finish",
            "iteration": 1,
            "candidate_slot": 1,
            "run_id": "physical-1",
            "artifacts": artifacts,
        }
    }
    if corruption:
        with pytest.raises(ValueError):
            area_facts(tmp_path, tasks)
    else:
        result = area_facts(tmp_path, tasks)
        assert result[0]["die_area"] == 38927.3 and result[0]["unit"] == "um^2"


@pytest.fixture
def stage():
    profile = {
        "runtime": {"executable": "/apptainer", "image": "/fixed.sif"},
        "toolchain": {
            "image_sha256": IMAGE_SHA,
            "orfs_commit": ORFS,
            "openroad_commit": OPENROAD,
            "binaries": {"openroad": {"sha256": "a" * 64}},
        },
    }
    receipt = {
        "profile": profile,
        "toolchain": {**profile["toolchain"], "runtime": profile["runtime"]},
        "command": ["/apptainer", "exec", "/fixed.sif", "/image/openroad"],
        "returncode": 0,
    }
    return deepcopy(profile), deepcopy(receipt)


def test_exact_registered_stage_identity_is_valid(stage):
    verify_identity(*stage)


@pytest.mark.parametrize("change", ["missing", "binary", "profile", "host", "failure"])
def test_missing_or_different_actual_execution_never_passes(stage, change):
    profile, receipt = stage
    if change == "missing":
        receipt.pop("toolchain")
    elif change == "binary":
        receipt["toolchain"]["binaries"]["openroad"]["sha256"] = "b" * 64
    elif change == "profile":
        receipt["profile"] = {}
    elif change == "host":
        receipt["command"] = ["/old/openroad"]
    else:
        receipt["returncode"] = 1
    with pytest.raises(ValueError):
        verify_identity(profile, receipt)

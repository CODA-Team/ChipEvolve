"""An accepted request alone cannot prove the stage used the common binary."""

from copy import deepcopy

import pytest
from accept_common_flow_campaign import IMAGE_SHA, OPENROAD, ORFS, verify_identity


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

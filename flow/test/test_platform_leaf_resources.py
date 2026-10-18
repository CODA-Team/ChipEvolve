"""Stage reservations reach EF without changing native work or fallback settings."""

import json
from unittest.mock import patch

import pytest

import platform_leaf


@pytest.mark.parametrize("stage", ["place", "cts", "route_finish", "eval_final"])
@pytest.mark.parametrize("overrides", [False, True])
def test_leaf_selects_only_its_explicit_stage_reservation(tmp_path, stage, overrides):
    default = {"memory_bytes": 12 << 30, "processes": 2048}
    placement = {"memory_bytes": 8 << 30, "processes": 2048}
    settings = {
        "kernel_url": "http://localhost:1",
        "data_url": "http://localhost:2",
        "state_root": str(tmp_path / "state"),
        "profile_path": "profile.json",
        "threads": 8,
        "timeout_seconds": 72000,
        "resources": default,
    }
    if overrides:
        settings["stage_resources"] = {"place": placement, "cts": placement}
    original = json.loads(json.dumps(settings))
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(settings))
    with (
        patch.dict(
            "os.environ",
            {
                "DRP_PLATFORM_CONFIG": str(path),
                "DRP_ITER": "2",
                "DRP_CAMPAIGN_ID": "original-campaign",
                "CP0": "545",
                "CLK_PORT": "clk",
                "LIB_FILES": "actual.lib",
            },
        ),
        patch(
            "sys.argv",
            ["platform_leaf.py", "candidate.mk", "3", "asap7", "jpeg", stage],
        ),
        patch.object(
            platform_leaf, "candidate_binding", return_value=("candidate-3", 7)
        ),
        patch.object(
            platform_leaf,
            "config_snapshot",
            return_value={
                "effective_sdc": {"resolved_path": str(tmp_path / "original.sdc")}
            },
        ),
        patch.object(platform_leaf, "KernelClient"),
        patch.object(platform_leaf, "publish_feedback"),
        patch.object(platform_leaf, "PlatformExecution") as executor,
    ):
        executor.return_value.execute.return_value = {
            "run_id": "run-same",
            "status": "succeeded",
        }
        platform_leaf.main()
    expected = placement if overrides and stage in {"place", "cts"} else default
    assert executor.call_args.kwargs["resources"] == expected
    assert executor.call_args.args[4:] == ("original-campaign", 8, 72000)
    task = executor.return_value.execute.call_args.kwargs
    assert task["iteration"] == 2 and task["slot"] == 3
    assert task["candidate_id"] == "candidate-3" and task["stage"] == stage
    assert task["donor_slot"] == (None if stage == "place" else 7)
    assert json.loads(path.read_text()) == original

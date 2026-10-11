"""Recovery audit must detect replaced producers and missing source records."""

from copy import deepcopy

import pytest
from accept_platform_campaign import consumed_parameters, retained_tasks


@pytest.mark.parametrize("field", ["task", "run_id", "artifacts", "idempotency_key"])
def test_recovery_rejects_changed_registered_identity(field):
    before = {
        "iteration-1/slot-1-place.json": {
            "task": {"inputs": {"stage": "place"}},
            "run_id": "original-run",
            "artifacts": [{"artifact_id": "original-odb", "sha256": "original-hash"}],
            "idempotency_key": "original-key",
            "status": "succeeded",
        }
    }
    final = deepcopy(before)
    final["iteration-1/slot-1-place.json"][field] = "replaced"
    assert not retained_tasks(before, final)


def test_prepared_task_can_finish_but_cannot_disappear():
    before = {
        "iteration-1/slot-1-place.json": {"task": {"inputs": {}}, "status": "prepared"}
    }
    final = deepcopy(before)
    final["iteration-1/slot-1-place.json"].update(
        run_id="accepted-run", status="succeeded"
    )
    assert retained_tasks(before, final)
    assert not retained_tasks(before, {})


@pytest.mark.parametrize(
    "scope,config,log",
    [
        (
            "cts",
            "export CTS_CLUSTER_SIZE = 24\nexport CTS_CLUSTER_DIAMETER = 96\n",
            (
                "clock_tree_synthesis -sink_clustering_enable -sink_clustering_size 24 "
                "-sink_clustering_max_diameter 96\n"
            ),
        ),
        (
            "routing",
            "export PIN_LAYER_ADJUST = 0.45\nexport ABOVE_LAYER_ADJUST = 0.2\n",
            "A2_LAYER_ADJUST scope=routing pin=0.45 above=0.2\n",
        ),
    ],
)
def test_tool_consumption_detects_changed_config_or_missing_command(scope, config, log):
    assert consumed_parameters(config, log, scope)["matched"]
    changed = config.replace("24", "25").replace("0.45", "0.35")
    assert not consumed_parameters(changed, log, scope)["matched"]
    assert not consumed_parameters(config, "No executed command\n", scope)["matched"]

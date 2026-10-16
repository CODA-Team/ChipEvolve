"""A closed native batch must not leave unconsumed EF work running."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from platform_execution import digest, write_record
from platform_stage_finalize import finalize


def inputs(tmp_path):
    state = tmp_path / "state"
    rows = {}
    for slot, status in [(1, "succeeded"), (2, "queued"), (3, "running")]:
        write_record(
            state / f"iteration-1/slot-{slot}-place.json",
            {
                "campaign_id": "owned",
                "iteration": 1,
                "stage": "place",
                "candidate_slot": slot,
                "design": "design",
                "platform": "pdk",
                "run_id": f"run-{slot}",
                "status": status,
            },
        )
        rows[f"run-{slot}"] = {
            "run_id": f"run-{slot}",
            "status": "running" if slot == 2 else status,
            "project_id": "a2-flow",
            "design_id": "design",
            "labels": {
                "campaign_id": "owned",
                "iteration": "1",
                "stage": "place",
                "candidate_slot": str(slot),
            },
        }

    class Client:
        def __init__(self):
            self.cancelled = []

        def run(self, run_id):
            return rows[run_id]

        def cancel(self, run_id):
            self.cancelled.append(run_id)
            rows[run_id]["status"] = "cancel_requested"
            return {"run": rows[run_id]}

    return state, rows, Client()


def close(state, client):
    return finalize(client, state, "owned", 1, "pdk", "design", "place", 124)


def test_terminal_batch_cancels_only_its_live_work_and_keeps_native_evidence(tmp_path):
    state, _, client = inputs(tmp_path)
    hashes = {p: digest(p) for p in state.glob("iteration-1/slot-*.json")}
    result = close(state, client)
    assert client.cancelled == ["run-2", "run-3"]
    assert result["native_exit_code"] == 124
    assert result["status"] == "completed"
    assert all(digest(p) == sha for p, sha in hashes.items())
    assert close(state, client) == result
    assert client.cancelled == ["run-2", "run-3"]
    assert json.loads((state / "iteration-1/finalize-place.json").read_text()) == result


def test_no_cancel_if_remote_work_already_completed(tmp_path):
    state, rows, client = inputs(tmp_path)
    rows["run-2"]["status"] = "succeeded"
    rows["run-3"]["status"] = "failed"
    close(state, client)
    assert client.cancelled == []


def test_foreign_remote_identity_is_rejected_before_cancellation(tmp_path):
    state, rows, client = inputs(tmp_path)
    rows["run-2"]["labels"]["campaign_id"] = "other"
    with pytest.raises(ValueError, match="ownership"):
        close(state, client)
    assert client.cancelled == []


def test_unknown_submission_is_explicit_and_never_resubmitted(tmp_path):
    state, _, client = inputs(tmp_path)
    path = state / "iteration-1/slot-2-place.json"
    value = json.loads(path.read_text())
    value.pop("run_id")
    write_record(path, value)
    with pytest.raises(ValueError, match="unresolved submission"):
        close(state, client)
    assert client.cancelled == []


def test_whole_scope_is_checked_before_any_cancellation(tmp_path):
    state, rows, client = inputs(tmp_path)
    rows["run-3"]["design_id"] = "foreign"
    with pytest.raises(ValueError, match="ownership"):
        close(state, client)
    assert client.cancelled == []


def test_partial_close_reconnects_without_recancelling_acknowledged_work(tmp_path):
    state, _, client = inputs(tmp_path)
    original = client.cancel

    def interrupted(run_id):
        if run_id == "run-3":
            raise ConnectionError("close interrupted")
        return original(run_id)

    client.cancel = interrupted
    with pytest.raises(ConnectionError):
        close(state, client)
    client.cancel = original
    result = close(state, client)
    assert client.cancelled == ["run-2", "run-3"]
    assert result["awaiting_terminal_run_ids"] == ["run-2", "run-3"]
    with pytest.raises(ValueError, match="ownership"):
        finalize(client, state, "foreign", 1, "pdk", "design", "place", 124)


def test_native_controller_closes_only_platform_batches_and_propagates_failure(
    tmp_path,
):
    source = (Path(__file__).parents[1] / "maindriver.sh").read_text()
    helper = source.split("platform_finalize_stage() {", 1)[1].split("\n}\n", 1)[0]
    script = "platform_finalize_stage() {" + helper + "\n}\n"
    stub = tmp_path / "platform_stage_finalize.py"
    stub.write_text("import sys\nraise SystemExit(7)\n")
    env = dict(
        os.environ, SCRIPT_DIR=str(tmp_path), PLATFORM="pdk", DESIGN="design", iter="1"
    )
    for backend, expected in [("native", 0), ("platform", 1)]:
        completed = subprocess.run(
            ["bash", "-c", script + "platform_finalize_stage place 124"],
            env=env | {"DRP_EXECUTION_BACKEND": backend},
            capture_output=True,
            text=True,
        )
        assert completed.returncode == expected
    for stage in ["place", "cts", "route_finish"]:
        assert f'platform_finalize_stage {stage} "$stage_rc"' in source

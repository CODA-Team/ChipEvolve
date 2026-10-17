"""Business progress resolves live EF states, scopes and unfinished barriers."""

import json

import pytest
from openroad_platform_client import KernelClient

from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.progress import flow_progress


class Client(KernelClient):
    def __init__(self, runs):
        self.values = runs
        self.lists = []
        self.reads = []

    def runs(self, *, status=None, limit=None, offset=0, **scope):
        self.lists.append((status, offset))
        rows = [
            r
            for r in self.values
            if r["status"] == status and all(r.get(k) == v for k, v in scope.items())
        ]
        return rows[offset : offset + limit if limit is not None else None]

    def run(self, run_id):
        self.reads.append(run_id)
        return next(r for r in self.values if r["run_id"] == run_id)


def run(slot, status, campaign="current", design="native-design"):
    return {
        "run_id": "run-" + str(slot),
        "project_id": "a2-flow",
        "design_id": design,
        "experiment_id": campaign,
        "status": status,
        "labels": {
            "iteration": "1",
            "stage": "place",
            "candidate_slot": str(slot),
            "candidate_id": "candidate-" + str(slot),
        },
    }


def native(root, statuses):
    state = root / "platform-state"
    write(
        state / "campaign.json",
        {
            "campaign_id": "current",
            "design": "native-design",
            "iteration": 1,
            "phase": 0,
            "runs": len(statuses),
        },
    )
    for slot, status in enumerate(statuses, 1):
        value = {
            "campaign_id": "current",
            "design": "native-design",
            "iteration": 1,
            "stage": "place",
            "candidate_slot": slot,
            "candidate_id": "candidate-" + str(slot),
            "status": status,
        }
        if status != "prepared":
            value["run_id"] = "run-" + str(slot)
        if status == "succeeded":
            value["terminal_run"] = run(slot, status)
        write(state / f"iteration-1/slot-{slot}-place.json", value)
    return state


def test_live_stage_is_visible_before_the_native_barrier_commits(tmp_path):
    native(tmp_path, ["queued", "queued", "succeeded", "prepared"])
    client = Client([run(1, "queued"), run(2, "running"), run(5, "running", "other")])
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}
    result = flow_progress(client, tmp_path)
    assert result is not None
    assert result["last_completed_phase"] == 0
    assert result["native_design_id"] == "native-design"
    assert result["planned_candidates"] == 4
    assert result["stages"]["place"] == {
        "recorded": 4,
        "submitted": 3,
        "counts": {"prepared": 1, "queued": 1, "running": 1, "succeeded": 1},
    }
    assert client.reads == []
    assert all(p.read_bytes() == before[str(p)] for p in tmp_path.rglob("*.json"))


def test_task_finishing_before_native_receipt_resolves_the_same_handle(tmp_path):
    native(tmp_path, ["queued"])
    client = Client([run(1, "succeeded")])
    result = flow_progress(client, tmp_path)
    assert result is not None
    assert result["stages"]["place"]["counts"] == {"succeeded": 1}
    assert client.reads == ["run-1"]
    assert (
        read(tmp_path / "platform-state/iteration-1/slot-1-place.json")["status"]
        == "queued"
    )


def test_active_pagination_does_not_hide_the_actual_campaign(tmp_path):
    native(tmp_path, ["queued"])
    unrelated = [run(i, "queued", "other") for i in range(2, 103)]
    client = Client([*unrelated, run(1, "queued")])
    result = flow_progress(client, tmp_path)
    assert result is not None
    assert result["stages"]["place"]["counts"] == {"queued": 1}
    assert ("queued", 100) in client.lists
    assert not client.reads


@pytest.mark.parametrize("wrong", ["campaign", "candidate"])
def test_same_named_task_from_another_scope_cannot_count(tmp_path, wrong):
    native(tmp_path, ["queued"])
    observed = run(1, "queued")
    if wrong == "campaign":
        observed["experiment_id"] = "other"
    else:
        observed["labels"]["candidate_slot"] = "2"
    with pytest.raises(ValueError, match="differs from the native campaign"):
        flow_progress(Client([observed]), tmp_path)


def test_non_native_experiment_requires_no_ef_reads(tmp_path):
    client = Client([])
    assert flow_progress(client, tmp_path) is None
    assert not client.lists and not client.reads


def test_feedback_receipts_are_not_native_stage_tasks(tmp_path):
    state = native(tmp_path, ["succeeded"])
    write(
        state / "iteration-1/slot-1-eval_place-feedback.json",
        {"campaign_id": "current", "evaluation_run_id": "analysis-import"},
    )
    result = flow_progress(Client([]), tmp_path)
    assert result is not None
    assert result["stages"] == {
        "place": {"recorded": 1, "submitted": 1, "counts": {"succeeded": 1}}
    }


def test_uncommitted_campaign_has_no_invented_iteration_or_tasks(tmp_path):
    write(
        tmp_path / "platform-state/campaign.json",
        {"campaign_id": "current", "design": "native-design", "platform": "pdk"},
    )
    client = Client([])
    result = flow_progress(client, tmp_path)
    assert result is not None and result["progress_available"] is False
    assert result["iteration"] is None and result["stages"] == {}
    assert not client.lists and not client.reads


def test_business_status_keeps_existing_fields_and_reports_native_stage(
    tmp_path, monkeypatch, capsys
):
    from chip_evolve.cli import main

    d = deployment(tmp_path)
    exp = d.experiment("gcd", "full-flow")
    write(exp / "request.json", {"capability": "flow"})
    native(exp, ["queued"])
    client = Client([run(1, "running")])
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: client)
    monkeypatch.setattr(
        "sys.argv",
        ["chip-evolve", "--config", str(d.path), "status", "--design", "gcd"],
    )
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["design_id"] == "gcd" and "active_eda_jobs" in result
    row = result["experiments"][0]
    assert row["experiment"] == "full-flow" and row["status"]["status"] == "in_progress"
    assert row["result"] is None and row["lifecycle"] == []
    assert row["native_progress"]["stages"]["place"]["counts"] == {"running": 1}


def test_validation_status_exposes_its_pending_children_without_scanning_source(
    tmp_path, monkeypatch, capsys
):
    from chip_evolve.cli import main

    d = deployment(tmp_path)
    exp = d.experiment("gcd", "validation")
    write(exp / "validation-request.json", {"result": "candidate.json"})
    pending = [
        "jobs/direct/lifecycle.json",
        "logic/jobs/parse-gold/lifecycle.json",
        "replay/jobs/qualification/lifecycle.json",
        "replay/imports/artifact.json",
    ]
    for name in pending:
        write(exp / name, {"status": "waiting", "state": "resource_wait"})
    write(exp / "logic/jobs/done/lifecycle.json", {"status": "succeeded"})
    write(exp / "source/jobs/foreign/lifecycle.json", {"status": "waiting"})
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: Client([]))
    monkeypatch.setattr(
        "sys.argv",
        ["chip-evolve", "--config", str(d.path), "status", "--design", "gcd"],
    )
    assert main() == 0
    row = json.loads(capsys.readouterr().out)["experiments"][0]
    assert {r["receipt"] for r in row["lifecycle"]} == {
        str(exp / name) for name in pending
    }
    assert all(r["state"] == "resource_wait" for r in row["lifecycle"])

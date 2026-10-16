"""Frozen preflight preserves scopes, attempts and explicit method boundaries."""

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from eda_toolkits.objectives import objective_id

from admin import freeze_formal_campaign as freezing
from admin import report_formal_campaign as reporting
from admin import run_formal_preflight as running
from admin.test_adoption_consistency import frame_at, validation_for
from admin.test_local_business import deployment
from chip_evolve.config import read, write


def campaign(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    d.value.update(client_python=sys.executable, qualified_environments={})
    rows = []
    for design in ("gcd", "aes"):
        root = tmp_path / design
        root.mkdir()
        baseline, candidate = (
            frame_at(root, "reference"),
            frame_at(root, "candidate", 0.9),
        )
        goal = read(root / "objective.json")
        goal["design_id"] = design
        goal["objective_id"] = objective_id(goal)
        write(root / "objective.json", goal)
        for path in (baseline, candidate):
            value = read(path)
            value.update(design_id=design, objective_id=goal["objective_id"])
            write(path, value)
        selected = root / "selected.json"
        shutil.copyfile(candidate, selected)
        environment = root / "environment.json"
        write(environment, {})
        d.value["qualified_environments"][design] = str(environment)
        rows.append(
            {
                "design_id": design,
                "reference": str(baseline),
                "selected_source": str(selected),
                "flow_candidates": [str(candidate)],
                "selection_reason": "Codex explicit test selection",
            }
        )
    write(d.path, d.value)
    spec = tmp_path / "spec.json"
    write(
        spec,
        {
            "purpose": "fixed_method_integration_preflight",
            "experiment_prefix": "a18",
            "designs": rows,
            "steps": [
                {
                    "key": "dpl-fixed",
                    "capability": "dpl",
                    "operation": "replay",
                    "input": "selected_source",
                    "seconds": 10,
                }
            ],
        },
    )
    monkeypatch.setattr(freezing, "check_environment", lambda *a: {})
    monkeypatch.setattr(freezing, "query_facts", lambda *a: {})
    monkeypatch.setattr(running, "check_environment", lambda *a: {})
    monkeypatch.setattr(reporting, "query_facts", lambda *a: {})
    return d, spec, tmp_path / "campaign.json"


@pytest.mark.parametrize(
    "mutation",
    [
        "mode",
        "mixed_design",
        "mixed_conditions",
        "unknown_source",
        "future_step",
        "evolve",
        "zero_budget",
    ],
)
def test_freeze_refuses_ambiguous_or_unapproved_study_inputs(
    tmp_path, monkeypatch, mutation
):
    d, spec, output = campaign(tmp_path, monkeypatch)
    value = read(spec)
    if mutation == "mode":
        value["purpose"] = "full_formal_search"
    elif mutation == "mixed_design":
        p = value["designs"][0]["reference"]
        frame = read(p)
        frame["design_id"] = "aes"
        write(Path(p), frame)
    elif mutation == "mixed_conditions":
        p = value["designs"][0]["selected_source"]
        frame = read(p)
        frame["condition_id"] = "different"
        write(Path(p), frame)
    elif mutation == "unknown_source":
        p = value["designs"][0]["selected_source"]
        frame = read(p)
        frame["run_id"] = "not-declared"
        write(Path(p), frame)
    elif mutation == "future_step":
        value["steps"][0]["input"] = "later"
    elif mutation == "evolve":
        value["steps"][0]["operation"] = "evolve"
    else:
        value["steps"][0]["seconds"] = 0
    write(spec, value)
    with pytest.raises(ValueError):
        freezing.freeze(d.path, spec, output)
    assert not output.exists()


def test_freeze_and_inputs_remain_immutable(tmp_path, monkeypatch):
    d, spec, output = campaign(tmp_path, monkeypatch)
    value = freezing.freeze(d.path, spec, output)
    assert freezing.checked(output) == value
    assert not value["full_formal_campaign_authorized_by_this_manifest"]
    with pytest.raises(FileExistsError):
        freezing.freeze(d.path, spec, output)
    path = value["designs"][0]["selected_source"]["path"]
    frame = read(path)
    frame["run_id"] = "mutated"
    write(Path(path), frame)
    with pytest.raises(ValueError, match="input changed"):
        freezing.checked(output)


def test_verified_same_condition_baseline_can_replace_infeasible_flow_source(
    tmp_path, monkeypatch
):
    d, spec, output = campaign(tmp_path, monkeypatch)
    value = read(spec)
    row = value["designs"][0]
    baseline = Path(row["reference"])
    alternative = baseline.parent.parent / "alternative.json"
    frame = read(baseline)
    frame["run_id"] = "verified-alternative"
    write(alternative, frame)
    validation = validation_for(alternative, baseline)
    row["additional_sources"] = [
        {"result": str(alternative), "validation": str(validation)}
    ]
    shutil.copyfile(alternative, row["selected_source"])
    write(spec, value)
    frozen = freezing.freeze(d.path, spec, output)
    assert frozen["designs"][0]["additional_sources"][0]["validation"]["path"] == str(
        validation
    )
    receipt = read(validation)
    receipt["passed"] = False
    write(validation, receipt)
    with pytest.raises(ValueError, match="input changed"):
        freezing.checked(output)


def test_completed_step_reentry_does_not_repeat_eda(tmp_path, monkeypatch):
    d, spec, manifest = campaign(tmp_path, monkeypatch)
    freezing.freeze(d.path, spec, manifest)
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        write(
            tmp_path / "experiments/gcd/a18-dpl-fixed/result.json",
            read(read(spec)["designs"][0]["selected_source"]),
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(running.subprocess, "run", execute)
    first = running.run_step(manifest, "gcd", "dpl-fixed")
    assert running.run_step(manifest, "gcd", "dpl-fixed") == first
    assert len(calls) == 1 and "run" in calls[0]
    report = reporting.report(manifest)
    assert report["execution_gate"] == "incomplete"
    assert report["designs"][1]["steps"][0]["status"] == "not_started"
    assert not report["formal_study_ready"]


def test_pending_step_reconnects_same_key_and_keeps_both_attempts(
    tmp_path, monkeypatch
):
    d, spec, manifest = campaign(tmp_path, monkeypatch)
    freezing.freeze(d.path, spec, manifest)
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        exp = tmp_path / "experiments/gcd/a18-dpl-fixed"
        exp.mkdir(parents=True, exist_ok=True)
        if len(calls) == 1:
            return SimpleNamespace(returncode=3)
        write(exp / "result.json", read(read(spec)["designs"][0]["selected_source"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(running.subprocess, "run", execute)
    assert running.run_step(manifest, "gcd", "dpl-fixed")["status"] == "pending"
    assert running.run_step(manifest, "gcd", "dpl-fixed")["status"] == "succeeded"
    assert "resume" in calls[1] and "run" not in calls[1]
    rows = reporting.report(manifest)["designs"][0]["steps"][0]
    assert len(rows["attempts"]) == 2
    assert [r["status"] for r in rows["attempt_outcomes"]] == ["pending", "succeeded"]
    assert rows["completed_attempt_wall_seconds_sum"] == sum(
        read(path)["wall_seconds"] for path in rows["attempts"]
    )


def test_failed_step_is_included_in_all_attempts_report(tmp_path, monkeypatch):
    d, spec, manifest = campaign(tmp_path, monkeypatch)
    freezing.freeze(d.path, spec, manifest)
    monkeypatch.setattr(
        running.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1)
    )
    assert running.run_step(manifest, "gcd", "dpl-fixed")["status"] == "failed"
    value = reporting.report(manifest)
    assert value["execution_gate"] == "failed"
    assert value["designs"][0]["steps"][0]["status"] == "failed"
    assert len(value["designs"][0]["steps"][0]["attempts"]) == 1

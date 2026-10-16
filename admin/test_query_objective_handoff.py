"""Query receives the real acceptance criteria alongside measured design facts."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from eda_toolkits.objectives import condition_id, objective_id

from admin.test_adoption_consistency import frame_at
from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.diagnosis import diagnose


def inputs(tmp_path):
    d = deployment(tmp_path)
    d.value.update(query_python="query-python", data_url="http://localhost:2")
    source = frame_at(tmp_path, "reference")
    frame = read(source)
    objective = read(frame["objective"])
    objective["reference_run_id"] = "reference"
    objective["conditions"]["units"] = {"power": "W", "area": "um^2", "time": "ns"}
    objective["objective_id"] = objective_id(objective)
    write(Path(frame["objective"]), objective)
    frame.update(
        objective_id=objective["objective_id"],
        condition_id=condition_id(objective),
        snapshot_ids={"opendb": "db", "orfs": "metrics", "opensta": "timing"},
    )
    write(source, frame)
    return d, source, objective


def backend(monkeypatch, questions):
    monkeypatch.setattr("chip_evolve.stage_facts.ensure_stage_facts", lambda *a: None)
    monkeypatch.setattr(
        "chip_evolve.diagnosis.scoped_analysis_references", lambda *a: []
    )

    def run(command, **kwargs):
        if "investigate" in command:
            questions.append(command[command.index("investigate") + 1])
            state = {
                "scopes": [{"design_id": "gcd", "run_id": "reference"}],
                "answer": "Measured facts and supplied acceptance criteria",
                "evidence": ["measured-evidence"],
                "investigation_id": "query",
            }
            return SimpleNamespace(returncode=0, stdout=json.dumps(state), stderr="")
        target = Path(command[command.index("--package-output") + 1])
        write(
            target,
            {
                "context_id": "query-context",
                "summary": "Measured facts and acceptance criteria",
                "confirmed_facts": [],
                "hypotheses": [],
                "limitations": [],
            },
        )
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("chip_evolve.diagnosis.subprocess.run", run)


def test_query_gets_complete_frozen_limits_and_conditions(tmp_path, monkeypatch):
    d, source, objective = inputs(tmp_path)
    questions = []
    backend(monkeypatch, questions)
    receipt = diagnose(d, source, "Explain this design", 60, 4)
    prompt = questions[0]
    start = prompt.index("{", prompt.index("<platform_shared_objective>"))
    supplied, _ = json.JSONDecoder().raw_decode(prompt[start:])
    assert supplied["constraints"] == objective["constraints"]
    assert supplied["conditions"] == objective["conditions"]
    assert supplied["objective_id"] == objective["objective_id"]
    assert "Native TimingECOAgent is dispatched separately by ChipEvolve" in prompt
    assert "built-in per-cell buffer_eco receiver" in prompt
    assert "Never invent cell/master permissions" in prompt
    assert receipt["identity_bindings"]["source"]["run_id"] == "reference"


@pytest.mark.parametrize("field", ["objective_id", "condition_id", "design_id"])
def test_mismatched_goal_binding_is_rejected_before_model(tmp_path, monkeypatch, field):
    d, source, _ = inputs(tmp_path)
    frame = read(source)
    frame[field] = "different"
    write(source, frame)
    questions = []
    backend(monkeypatch, questions)
    with pytest.raises(ValueError, match="objective"):
        diagnose(d, source, "Explain this design", 60, 4)
    assert not questions

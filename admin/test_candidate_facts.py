"""Candidate views preserve original decisions, limits and verifiable sources."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from eda_toolkits.objectives import SCHEMA, condition_id, objective_id

from admin.test_local_business import deployment
from chip_evolve.candidate_facts import (
    BRIEF_BYTES,
    build_candidate_facts,
    candidate_row,
    compact_view,
    flow_feedback,
    native_facts,
)
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


def frame(root, name="reference"):
    goal = {
        "schema_version": SCHEMA,
        "design_id": "gcd",
        "conditions": {
            "libraries": [{"path": "/lib", "sha256": "library"}],
            "sdc": {"path": "/sdc", "sha256": "constraint"},
            "units": {"time": "ns", "power": "W", "area": "um^2"},
        },
        "constraints": {
            "max_slew_violations": 0,
            "max_cap_violations": 0,
            "placement_violations": 0,
            "route_drc": 0,
            "power_total_w_max": 1,
            "cell_area_um2_max": 10,
            "core_area_um2_max": 20,
            "die_area_um2_max": 30,
            "setup_tns_ns_min": 0,
            "hold_tns_ns_min": 0,
        },
    }
    goal["objective_id"] = objective_id(goal)
    objective = root / "objective.json"
    write(objective, goal)
    return {
        "design_id": "gcd",
        "run_id": name,
        "physical_run_id": name + "-physical",
        "objective": str(objective),
        "objective_id": goal["objective_id"],
        "condition_id": condition_id(goal),
        "snapshot_ids": {"orfs": name + "-metrics"},
        "route_drc": 0,
        "metrics": {
            "finish__timing__setup__tns": 0,
            "finish__timing__hold__tns": 0,
            "finish__timing__setup__ws": 0.1,
            "finish__power__total": 1,
            "finish__design__instance__area": 10,
            "finish__design__core__area": 20,
            "finish__design__die__area": 30,
            "finish__timing__drv__max_slew": 0,
            "finish__timing__drv__max_cap": 0,
            "design__violations": 0,
        },
    }


def sdk(_, measured):
    return {
        "scopes": {},
        "metrics": {
            "data": {
                "metrics": [
                    {"raw_key": k, "raw_value": v}
                    for k, v in measured["metrics"].items()
                ],
                "raw_metrics": [],
            }
        },
    }


def test_original_winner_can_be_final_infeasible_without_being_reselected(tmp_path):
    d = deployment(tmp_path)
    d.value["client_python"] = "/usr/bin/python3"
    reference = frame(tmp_path)
    candidate = deepcopy(reference)
    candidate.update(
        run_id="student2",
        physical_run_id="student2-physical",
        native_method={
            "kind": "original",
            "choice": {
                "accepted": True,
                "candidate": "student2",
            },
        },
    )
    candidate["metrics"]["finish__design__instance__area"] = 10.1
    paths = [tmp_path / "reference.json", tmp_path / "student2.json"]
    for p, v in zip(paths, [reference, candidate], strict=True):
        write(p, v)
    experiment = d.experiment("gcd", "facts")
    commands = []

    def register(self, key, command, **kwargs):
        commands.append((key, command, kwargs))
        return {"run": {"run_id": "facts-analysis"}}

    with (
        patch("chip_evolve.candidate_facts.query_facts", side_effect=sdk),
        patch("chip_evolve.candidate_facts.Jobs.command", register),
    ):
        brief = build_candidate_facts(d, paths[0], paths[1:], experiment)
    view = read(brief)
    row = view["candidates"][0]
    assert row["native"]["decision"] == {"accepted": True, "candidate": "student2"}
    assert row["final_feasible"] is False
    assert row["final_constraint_violations"] == ["cell_area_um2_max"]
    assert view["constraints"]["cell_area_um2_max"] == 10
    assert "winner" not in view and "adopted" not in row
    assert commands[0][2]["analysis_parent"] == "reference"
    assert read(experiment / "facts-receipt.json")["eda_jobs_launched"] == 0
    assert row["evidence"]["result"]["sha256"] == digest(paths[1])


@pytest.mark.parametrize(
    "field,value",
    [
        ("condition_id", "other-corner"),
        ("design_id", "other-design"),
        ("objective_id", "other-caps"),
    ],
)
def test_mismatched_candidates_rejected_before_data_reads(tmp_path, field, value):
    d = deployment(tmp_path)
    reference = frame(tmp_path)
    candidate = {**reference, field: value}
    r, c = tmp_path / "ref.json", tmp_path / "candidate.json"
    write(r, reference)
    write(c, candidate)
    with patch("chip_evolve.candidate_facts.query_facts") as query:
        with pytest.raises(ValueError):
            build_candidate_facts(d, r, [c], tmp_path / "not-created")
    query.assert_not_called()
    assert not (tmp_path / "not-created").exists()


def test_sdk_constraint_facts_must_match_before_claiming_feasibility(tmp_path):
    measured = frame(tmp_path)
    response = sdk(None, measured)
    for row in response["metrics"]["data"]["metrics"]:
        if row["raw_key"] == "finish__timing__drv__max_slew":
            row["raw_value"] = 1
    jobs = SimpleNamespace(deployment=deployment(tmp_path))
    with patch("chip_evolve.candidate_facts.query_facts", return_value=response):
        with pytest.raises(ValueError, match="hard-constraint"):
            candidate_row(jobs, measured, tmp_path / "result.json", tmp_path / "row")


def test_missing_native_score_stays_unknown(tmp_path):
    measured = frame(tmp_path)
    row = native_facts(SimpleNamespace(), measured, tmp_path)
    assert row["decision"] is None and row["metrics"] is None
    assert "not inferred" in row["limitation"]


def test_registered_native_metrics_are_read_from_actual_producer(tmp_path):
    source = tmp_path / "registered.json"
    write(
        source, {"hpwl": {"after_micron": 123}, "legality": {"placement_violations": 0}}
    )
    artifact = {
        "artifact_id": "native-metrics",
        "kind": "raw_flow_metadata",
        "store_key": "outputs/0/metrics.json",
        "sha256": digest(source),
    }
    client = SimpleNamespace(
        run=lambda _: {"design_id": "gcd", "status": "succeeded"},
        artifacts=lambda _: [artifact],
        materialize_artifact=lambda run, art, dest: Path(dest).write_bytes(
            source.read_bytes()
        ),
    )
    measured = frame(tmp_path)
    measured["native_method"] = {"kind": "native", "producer": "original-eda"}
    result = native_facts(SimpleNamespace(client=client), measured, tmp_path)
    assert result["metrics"]["hpwl"]["after_micron"] == 123
    assert result["evidence"][0]["run_id"] == "original-eda"
    client.run = lambda _: {"design_id": "another-design", "status": "succeeded"}
    with pytest.raises(ValueError, match="producer"):
        native_facts(SimpleNamespace(client=client), measured, tmp_path)


def test_large_native_details_keep_constraints_and_expandable_refs(tmp_path):
    row = {
        "run_id": "run",
        "final_metrics": {"finish__power__total": 1.0},
        "final_feasible": False,
        "final_constraint_violations": ["cell_area_um2_max"],
        "detail_ref": {"path": "candidate-1/facts.json", "sha256": "details"},
        "native": {"large_original_verdict": "x" * BRIEF_BYTES},
    }
    document = {
        "constraints": {"cell_area_um2_max": 10},
        "reference": row,
        "candidates": [row],
    }
    full = tmp_path / "full.json"
    write(full, document)
    brief = compact_view(document, full)
    assert brief["constraints"] == document["constraints"]
    assert brief["candidates"][0]["final_constraint_violations"] == [
        "cell_area_um2_max"
    ]
    assert brief["candidates"][0]["detail_ref"] == row["detail_ref"]
    assert brief["candidates"][0]["final_metrics"] == row["final_metrics"]
    assert brief["full_facts"]["sha256"] == digest(full)


def test_native_delivery_checkpoint_must_describe_same_original_method(tmp_path):
    measured = frame(tmp_path)
    measured["native_method"] = {"kind": "framework"}
    source = tmp_path / "result.json"
    write(source, measured)
    write(
        tmp_path / "delivery-checkpoint.json",
        {
            "design_id": "gcd",
            "native_method": {"kind": "another-method"},
            "producer": "unrelated-producer",
        },
    )
    with pytest.raises(ValueError, match="checkpoint differs"):
        native_facts(SimpleNamespace(), measured, tmp_path, source)


def test_changed_goal_is_rejected_even_when_frame_claims_original_identity(tmp_path):
    d = deployment(tmp_path)
    reference = frame(tmp_path)
    path = tmp_path / "reference.json"
    write(path, reference)
    goal = read(Path(reference["objective"]))
    goal["constraints"]["cell_area_um2_max"] = 100
    write(Path(reference["objective"]), goal)
    with pytest.raises(ValueError, match="changed"):
        build_candidate_facts(d, path, [path], tmp_path / "facts")


def test_flow_proxy_conditions_and_units_are_not_relabelled_as_final(tmp_path):
    original = tmp_path / "feedback.json"
    write(
        original,
        {
            "observations": {"tns": {"value": -2, "unit": "ns"}},
            "evaluation": {"cp0_ns": 0.59, "library_patterns": ["TT"]},
            "parasitic_mode": "spef",
        },
    )
    seen = []

    def runs(**kwargs):
        seen.append(kwargs)
        return (
            []
            if kwargs["offset"]
            else [
                {"run_id": "native-eval", "status": "succeeded"},
                {"run_id": "export-copy", "status": "succeeded"},
            ]
        )

    artifact = {
        "kind": "raw_flow_metadata",
        "store_key": "a2-evaluation.json",
        "artifact_id": "feedback",
        "sha256": digest(original),
    }
    client = SimpleNamespace(
        runs=runs,
        artifacts=lambda _: [artifact],
        materialize_artifact=lambda run, art, dest: Path(dest).write_bytes(
            original.read_bytes()
        ),
    )
    measured = frame(tmp_path)
    measured["candidate_id"] = "original-candidate"
    value = flow_feedback(SimpleNamespace(client=client), measured, tmp_path)
    assert value["evaluations"][0]["evaluation"]["cp0_ns"] == 0.59
    assert value["evaluations"][0]["evaluation"]["library_patterns"] == ["TT"]
    assert value["evaluations"][0]["observations"]["tns"]["unit"] == "ns"
    assert len(value["evaluations"]) == 1
    assert len(value["evaluations"][0]["evidence_refs"]) == 2
    assert seen[0]["analysis_of_run_id"] == measured["physical_run_id"]
    assert value["decision"] is None


@pytest.mark.parametrize("failed", [False, True])
def test_candidates_cli_forwards_explicit_inputs_and_records_outcome(tmp_path, failed):
    from chip_evolve.cli import main

    d = deployment(tmp_path)
    reference = tmp_path / "reference.json"
    candidate = tmp_path / "candidate.json"
    write(reference, frame(tmp_path))
    write(candidate, frame(tmp_path, "candidate"))
    experiment = d.state / "experiments/gcd/cli-facts"
    with (
        patch(
            "sys.argv",
            [
                "chip-evolve",
                "--config",
                str(d.path),
                "candidates",
                "--reference",
                str(reference),
                "--result",
                str(candidate),
                "--key",
                "cli-facts",
            ],
        ),
        patch("chip_evolve.candidate_facts.build_candidate_facts") as build,
    ):
        if failed:
            build.side_effect = ValueError("different conditions")
            with pytest.raises(ValueError, match="different conditions"):
                main()
        else:
            build.return_value = experiment / "candidate-brief.json"
            assert main() == 0
        assert build.call_args.args[1:] == (reference, [candidate], experiment)
    assert read(experiment / "status.json")["status"] == (
        "failed" if failed else "succeeded"
    )
    assert read(experiment / "request.json")["design"] == "gcd"

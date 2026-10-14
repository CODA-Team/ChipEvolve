import pytest

from admin.continue_goal_timing import (
    checkpoint_method,
    checkpoint_producer,
    continuation_contract,
)
from admin.run_local_quality import STAGES, stage_metrics
from admin.test_local_business import deployment
from admin.test_local_comparisons import result
from chip_evolve.comparisons import professional_facts
from chip_evolve.config import write
from chip_evolve.diagnosis import scoped_analysis_references
from chip_evolve.jobs import Jobs, digest


def test_diagnosis_discovers_only_successful_evidence_attached_to_fixed_runs(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from chip_evolve import diagnosis

    calls = []

    def runs(**kwargs):
        calls.append(kwargs)
        if kwargs["offset"] or kwargs["analysis_of_run_id"] == "reference":
            return []
        return [
            {"run_id": "evidence", "status": "succeeded"},
            {"run_id": "failed", "status": "failed"},
        ]

    artifact = {
        "artifact_id": "raw",
        "kind": "raw_flow_metadata",
        "store_key": "query-data/stages.json",
        "sha256": "hash",
        "size_bytes": 12,
    }
    monkeypatch.setattr(
        diagnosis,
        "KernelClient",
        lambda *args, **kwargs: SimpleNamespace(
            runs=runs, artifacts=lambda _: [artifact, {"kind": "extractor_log"}]
        ),
    )
    references = scoped_analysis_references(
        deployment(tmp_path), [{"run_id": "candidate"}, {"run_id": "reference"}]
    )
    assert references == [
        {
            "analysis_run_id": "evidence",
            "analysis_of_run_id": "candidate",
            "artifacts": [artifact],
        }
    ]
    assert all(call["run_type"] == "analysis" for call in calls)
    assert [call["offset"] for call in calls] == [0, 2, 0]


@pytest.mark.parametrize(
    "changed_source,changed_output", [(False, False), (True, False), (False, True)]
)
def test_continuation_traces_inherited_or_new_output_to_actual_ef_capture(
    tmp_path, changed_source, changed_output
):
    previous, current = tmp_path / "previous", tmp_path / "current"
    checkpoint = tmp_path / "selected.odb"
    checkpoint.write_bytes(b"inherited")
    original_hash = digest(checkpoint)
    frame = {
        "run_id": "final-metrics-not-the-native-producer",
        "qualification": {
            "input_odb_sha256": original_hash,
            "producer_run_id": "old-native",
        },
    }
    imported = {"source_hash": "old-source"}
    final = {"source_hash": "new-source" if changed_source else "old-source"}
    old_operation = previous / "operations/physical"
    write(
        old_operation / "leaf.json",
        {
            "request": {"operation": "physical"},
            "output_files": {"post_route.odb": original_hash},
        },
    )
    write(old_operation / "execution.json", {"run": {"run_id": "old-native"}})
    if changed_output:
        checkpoint.write_bytes(b"new-output")
    if changed_source or changed_output:
        # A source/output change must have a current EF capture. A final-metrics
        # run identifier or an old equal-byte artifact cannot substitute for it.
        with pytest.raises(ValueError, match="no EF producer"):
            checkpoint_producer(previous, current, checkpoint, imported, final, frame)
        new_operation = current / "operations/physical"
        write(
            new_operation / "leaf.json",
            {
                "request": {"operation": "physical"},
                "output_files": {"post_route.odb": digest(checkpoint)},
            },
        )
        write(new_operation / "execution.json", {"run": {"run_id": "new-native"}})
    assert checkpoint_producer(
        previous, current, checkpoint, imported, final, frame
    ) == ("new-native" if changed_source or changed_output else "old-native")


def test_stage_evidence_keeps_signs_and_identifies_loss_before_final_route():
    text = "\n".join(
        f"GOALEVOLVE_CHECKPOINT_METRIC {stage} {name} {value}"
        for stage in STAGES
        for name, value in [
            ("tns_abs_ns", -0.1 if stage == "post_repair_power" else 0),
            ("wns_abs_ns", -0.01),
        ]
    )
    values = stage_metrics(text)
    assert values[2]["setup_tns_ns"] == -0.1
    with pytest.raises(ValueError, match="incomplete"):
        stage_metrics(text.replace("post_placement", "missing"))


def test_selected_stage_baseline_keeps_lineage_and_actual_method_separate(tmp_path):
    previous, current = tmp_path / "previous", tmp_path / "current"
    operation, baseline = current / "operations/physical", tmp_path / "baseline"
    checkpoint = tmp_path / "selected.odb"
    checkpoint.write_bytes(b"measured-stage-output")
    parent = {
        "source_hash": "same-source",
        "evaluation_mode": "power_only",
        "timing_recipe_id": "legacy_setup",
        "metrics": {"tns_abs_ns": 0.4},
    }
    measured = {
        **parent,
        "evaluation_mode": "power_then_timing",
        "metrics": {"tns_abs_ns": 0.002},
        "artifacts": {"checkpoint_post_route_db": str(checkpoint)},
    }
    write(operation / "execution.json", {"run": {"run_id": "native-stage"}})
    write(operation / "request.json", {"cwd": str(baseline)})
    write(baseline / "baseline.json", measured)
    actual = checkpoint_method(previous, current, "native-stage", checkpoint, parent)
    assert actual["evaluation_mode"] == "power_then_timing"
    assert actual["metrics"]["tns_abs_ns"] == 0.002
    assert (
        parent["evaluation_mode"] == "power_only"
        and parent["metrics"]["tns_abs_ns"] == 0.4
    )
    other = tmp_path / "different.odb"
    other.write_bytes(b"different-stage-output")
    measured["artifacts"]["checkpoint_post_route_db"] = str(other)
    write(baseline / "baseline.json", measured)
    with pytest.raises(ValueError, match="checkpoint bytes"):
        checkpoint_method(previous, current, "native-stage", checkpoint, parent)


def test_stage_collector_validates_selected_method_not_old_lineage(
    tmp_path, monkeypatch
):
    import zipfile
    from types import SimpleNamespace

    from admin import run_local_quality

    frame = result(tmp_path)
    frame["qualification"] = {"producer_run_id": "native", "input_odb_sha256": "odb"}
    frame["native_method"] = {
        "parent": {"metrics": {"tns_abs_ns": 0.4}},
        "selected_checkpoint": {"metrics": {"tns_abs_ns": 0.002}},
    }
    result_path = tmp_path / "result.json"
    write(result_path, frame)
    log = "\n".join(
        f"GOALEVOLVE_CHECKPOINT_METRIC {stage} {name} {value}"
        for stage in STAGES
        for name, value in [
            ("tns_abs_ns", -0.002 if stage == "post_route" else 0),
            ("wns_abs_ns", -0.001),
        ]
    )

    def materialize(record, kind, destination):
        with zipfile.ZipFile(destination, "w") as archive:
            archive.writestr("evaluation.log", log)
        return {"artifact_id": "native-log", "sha256": digest(destination)}

    jobs = SimpleNamespace(
        client=SimpleNamespace(
            run=lambda _: {"design_id": frame["design_id"], "status": "succeeded"},
            artifacts=lambda _: [],
        ),
        materialize=materialize,
        command=lambda *args, **kwargs: {"run": {"run_id": "scoped"}, "artifacts": []},
    )
    monkeypatch.setattr(run_local_quality, "Jobs", lambda *args: jobs)
    receipt = run_local_quality.collect(
        deployment(tmp_path), result_path, tmp_path / "evidence"
    )
    assert receipt["stages"][-2]["setup_tns_ns"] == -0.002
    assert receipt["facts"]["native_method"]["parent"]["metrics"]["tns_abs_ns"] == 0.4


def test_native_promotion_does_not_turn_open_final_timing_into_a_feasible_design(
    tmp_path,
):
    frame = result(tmp_path)
    frame["native_method"] = {"kind": "native-search", "choice": {"accepted": True}}
    frame["metrics"]["finish__timing__setup__tns"] = -0.01
    evidence = professional_facts(frame)
    assert evidence["native_method"]["choice"]["accepted"]
    assert not evidence["final_feasible"]
    assert "setup_tns_ns_min" in evidence["final_constraint_violations"]


def test_command_evidence_keeps_the_final_run_scope_and_registered_extra_paths(
    tmp_path, monkeypatch
):
    config = deployment(tmp_path)
    config.value["client_python"] = "/usr/bin/python3"
    jobs = Jobs(config, "gcd", tmp_path)
    captured = {}

    def submit(key, inputs, staged, **kwargs):
        captured.update(inputs=inputs, **kwargs)
        return {"run": {"run_id": "analysis"}}

    monkeypatch.setattr(jobs, "submit", submit)
    jobs.command(
        "facts",
        ["sha256sum", "native.log"],
        analysis_parent="final",
        extra_paths=["query-data/0/native.log"],
        cpu=1,
        memory_gib=1,
    )
    assert captured["analysis_parent"] == "final"
    assert captured["inputs"]["native_extra_paths"] == ["query-data/0/native.log"]


def test_timing_continuation_preserves_original_targets_and_promotion(tmp_path):
    original = {
        "target_metrics": {
            "dynamic_power_pw": 10,
            "leakage_power_pw": 10,
            "tns_abs_ns": 0,
        },
        "baseline_metrics": {"dynamic_power_pw": 20},
        "promotion": "power_first_promotion",
        "power_stage_tns_ceiling_ns": 60,
        "power_stage_protected_rounds": 10,
    }
    parent = {
        "metrics": {"dynamic_power_pw": 5, "leakage_power_pw": 5, "tns_abs_ns": 0.4},
        "source_commit": "commit",
        "source_hash": "hash",
        "evaluation_mode": "power_only",
    }
    config = continuation_contract(
        original, parent, tmp_path, tmp_path / "source", tmp_path / "db"
    )
    for name, value in original.items():
        assert config[name] == value
    parent["metrics"]["dynamic_power_pw"] = 11
    with pytest.raises(ValueError, match="power targets"):
        continuation_contract(
            original, parent, tmp_path, tmp_path / "source", tmp_path / "db"
        )

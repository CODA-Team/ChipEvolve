import pytest

from admin.continue_goal_timing import continuation_contract
from admin.run_local_quality import STAGES, stage_metrics
from admin.test_local_business import deployment
from admin.test_local_comparisons import result
from chip_evolve.comparisons import professional_facts
from chip_evolve.jobs import Jobs


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

"""Two-run means must not hide mismatched methods or a failed trial."""

import pytest

from admin.relay_repeat_summary import summarize
from chip_evolve.config import read, write


def make_pair(tmp_path, monkeypatch):
    import admin.relay_repeat_summary as module

    baseline = tmp_path / "baseline.json"
    write(
        baseline,
        {"metrics": {"finish__power__total": 10, "finish__design__instance__area": 20}},
    )
    paths = []
    for n, power in enumerate([8, 9], 1):
        p = tmp_path / f"trial{n}/result.json"
        write(
            p,
            {
                "run_id": f"measure{n}",
                "native_method": {"optimization_run_id": f"opt{n}"},
                "metrics": {
                    "finish__power__total": power,
                    "finish__design__instance__area": 18,
                },
            },
        )
        write(
            p.parent / "repetition-method.json",
            {
                "kind": "independent-fixed-strategy-optimization",
                "binary_sha256": "bin",
                "original_script_sha256": "tcl",
                "input_hashes": {"input.def": "sha"},
                "condition_id": "fixed",
                "objective_id": "goal",
                "scope": "fixed full optimization action, not source search",
            },
        )
        paths.append(p)
    monkeypatch.setattr(
        module,
        "compare",
        lambda baseline, frame: {
            "constraint_violations": frame.get("failed_constraints", [])
        },
    )
    return baseline, paths


def test_two_measured_optimizations_have_raw_values_and_mean(tmp_path, monkeypatch):
    reference, results = make_pair(tmp_path, monkeypatch)
    summary = summarize(reference, results)
    assert summary["qualified_ppa_pair"]
    assert summary["metrics"]["finish__power__total"] == {
        "trial_1": 8,
        "trial_2": 9,
        "mean": 8.5,
    }


@pytest.mark.parametrize("problem", ["worse", "constraint"])
def test_one_failed_trial_invalidates_pair_even_if_average_improves(
    tmp_path, monkeypatch, problem
):
    reference, results = make_pair(tmp_path, monkeypatch)
    frame = read(results[1])
    if problem == "worse":
        frame["metrics"]["finish__power__total"] = 11
    else:
        frame["failed_constraints"] = ["setup_tns_ns_min"]
    write(results[1], frame)
    summary = summarize(reference, results)
    assert not summary["qualified_ppa_pair"]
    assert summary["status"] == "requires_cause_review_and_correction"
    assert summary["problems"][0]["trial"] == 2


@pytest.mark.parametrize("problem", ["same_run", "method", "routing_only", "one_trial"])
def test_incomplete_or_unmatched_experiments_cannot_supply_mean(
    tmp_path, monkeypatch, problem
):
    reference, results = make_pair(tmp_path, monkeypatch)
    if problem == "one_trial":
        results = results[:1]
    elif problem == "same_run":
        value = read(results[1])
        value["native_method"]["optimization_run_id"] = "opt1"
        write(results[1], value)
    else:
        p = results[1].parent / "repetition-method.json"
        value = read(p)
        value["binary_sha256" if problem == "method" else "kind"] = "different"
        write(p, value)
    with pytest.raises(ValueError):
        summarize(reference, results)

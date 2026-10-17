"""The planned denominator, native identity and failure costs cannot disappear."""

import pytest

from admin import report_native_operation_matrix as matrix
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


def prepared(tmp_path, purpose="formal"):
    task, program = tmp_path / "task.json", tmp_path / "oracle.py"
    write(task, {"business_goal": "Complete same experiment and verify original PPA"})
    program.write_text("# independent domain oracle\n")
    arms = {}
    for arm in matrix.ARMS:
        spec = tmp_path / (arm + ".json")
        write(
            spec,
            {
                "schema": "chip-evolve.native-codex-episode.v1",
                "native_command": ["same-native-codex"],
                "model": "gpt-6.1-sol",
                "reasoning_effort": "medium",
                "wall_seconds": 900,
                "formal_episode": purpose == "formal",
                "input_hashes": {str(task): digest(task)},
            },
        )
        arms[arm] = {
            "episode": str(tmp_path / arm),
            "specification": str(spec),
            "oracle": str(tmp_path / (arm + "-verdict.json")),
            "oracle_program": str(program),
        }
    request, frozen = tmp_path / "request.json", tmp_path / "frozen.json"
    write(
        request,
        {
            "purpose": purpose,
            "pairs": [
                {
                    "pair_id": "gcd-start-r1",
                    "design_id": "gcd",
                    "scenario": "complete",
                    "task": str(task),
                    "workload_equivalent": True,
                    "arms": arms,
                }
            ],
        },
    )
    return request, frozen, arms


def finish(
    entry,
    *,
    correct=True,
    complete=True,
    status="native_completed",
    inputs=100,
    cached=60,
    outputs=5,
    wall=10,
):
    from pathlib import Path

    episode = Path(entry["episode"])
    usage = {
        "input_tokens": inputs,
        "cached_input_tokens": cached,
        "output_tokens": outputs,
    }
    write(
        episode / "receipt.json",
        {
            "status": status,
            "specification_sha256": digest(Path(entry["specification"])),
            "usage_complete": complete,
            "usage": usage if complete else None,
            "known_usage_lower_bound": usage,
            "wall_seconds": wall,
        },
    )
    evidence = episode / "raw-independent-verdict.json"
    write(evidence, {"status": "passed" if correct else "failed"})
    write(
        Path(entry["oracle"]),
        {
            "episode": str(episode),
            "receipt_sha256": digest(episode / "receipt.json"),
            "program_sha256": digest(Path(entry["oracle_program"])),
            "evidence": matrix.reference(evidence),
            "status": "passed" if correct else "failed",
        },
    )


def test_all_planned_including_unstarted_remain_and_unknown_usage_is_not_zero(tmp_path):
    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["platform"], correct=False, complete=False, status="failed", inputs=80)
    report = matrix.report(frozen)
    assert report["planned_attempts"] == 2 and report["observed_attempts"] == 1
    assert report["correct_attempts"] == 0 and report["cost_comparable_pairs"] == 0
    assert len(report["unknown_usage_attempts"]) == 2
    assert report["known_input_plus_output_tokens"] == 85
    assert report["pairs"][0]["outcomes"]["direct"]["known_usage_lower_bound"] is None


def test_live_native_receipt_is_observed_with_unknown_cost_and_not_a_failure(tmp_path):
    from pathlib import Path

    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    entry = arms["direct"]
    write(
        Path(entry["episode"]) / "receipt.json",
        {
            "status": "running",
            "specification_sha256": digest(Path(entry["specification"])),
        },
    )
    value = matrix.report(frozen)
    assert value["observed_attempts"] == 1 and value["planned_attempts"] == 2
    actual = value["pairs"][0]["outcomes"]["direct"]
    assert (
        actual["execution_status"] == "running"
        and actual["known_usage_lower_bound"] is None
    )
    assert actual["wall_seconds"] is None and not actual["cost_pair_eligible"]


def test_different_native_backend_and_overwrite_are_rejected(tmp_path):
    from pathlib import Path

    request, frozen, arms = prepared(tmp_path)
    spec = Path(arms["platform"]["specification"])
    original = read(spec)
    changed = {**original, "native_command": ["another-codex"]}
    write(spec, changed)
    with pytest.raises(ValueError, match="same native"):
        matrix.freeze(request, frozen)
    write(spec, original)
    matrix.freeze(request, frozen)
    before = digest(frozen)
    with pytest.raises(FileExistsError):
        matrix.freeze(request, frozen)
    assert digest(frozen) == before


def test_wrong_faster_answer_cannot_count_as_efficiency_but_its_cost_remains(tmp_path):
    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["direct"])
    finish(arms["platform"], correct=False, inputs=10, cached=0, wall=1)
    value = matrix.report(frozen)
    assert value["correct_attempts"] == 1 and value["correct_rate_all_planned"] == 0.5
    assert value["known_input_plus_output_tokens"] == 120
    assert value["pairs"][0]["costs"] is None


def test_formal_correct_pairs_use_input_plus_output_without_adding_cache(tmp_path):
    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["direct"], inputs=100, outputs=5)
    finish(arms["platform"], inputs=40, cached=30, outputs=2, wall=5)
    value = matrix.report(frozen)
    assert value["cost_comparable_pairs"] == 1
    costs = value["pairs"][0]["costs"]
    assert costs["input_plus_output_tokens"]["platform_over_direct"] == 0.4
    assert costs["wall_seconds"]["platform_over_direct"] == 0.5
    assert value["known_input_plus_output_tokens"] == 147


def test_correct_business_result_with_incomplete_usage_is_excluded_only_from_cost_pair(
    tmp_path,
):
    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["direct"])
    finish(arms["platform"], complete=False)
    value = matrix.report(frozen)
    assert value["correct_attempts"] == 2 and value["correct_rate_all_planned"] == 1
    assert value["cost_comparable_pairs"] == 0
    assert value["known_input_plus_output_tokens"] == 210


def test_qualification_and_incomplete_usage_never_produce_formal_ratio(tmp_path):
    request, frozen, arms = prepared(tmp_path, purpose="qualification")
    finish(arms["direct"])
    finish(arms["platform"])
    matrix.freeze(request, frozen)
    assert matrix.report(frozen)["cost_comparable_pairs"] == 0
    value = read(request)
    value["purpose"] = "formal"
    write(request, value)
    with pytest.raises(ValueError, match="before execution"):
        matrix.freeze(request, tmp_path / "retroactive.json")


@pytest.mark.parametrize(
    "field,value",
    [("model", "other-model"), ("wall_seconds", 1200), ("reasoning_effort", "xhigh")],
)
def test_mismatched_backend_or_budget_cannot_be_frozen_as_pair(tmp_path, field, value):
    from pathlib import Path

    request, frozen, arms = prepared(tmp_path)
    p = Path(arms["platform"]["specification"])
    data = read(p)
    data[field] = value
    write(p, data)
    with pytest.raises(ValueError, match="must match"):
        matrix.freeze(request, frozen)


def test_duplicate_episode_and_changed_frozen_task_are_rejected(tmp_path):
    request, frozen, arms = prepared(tmp_path)
    value = read(request)
    value["pairs"][0]["arms"]["platform"]["episode"] = arms["direct"]["episode"]
    write(request, value)
    with pytest.raises(ValueError, match="count twice"):
        matrix.freeze(request, frozen)
    value["pairs"][0]["arms"]["platform"]["episode"] = arms["platform"]["episode"]
    write(request, value)
    matrix.freeze(request, frozen)
    (tmp_path / "task.json").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        matrix.report(frozen)


def test_exit_zero_without_oracle_is_not_a_correct_answer(tmp_path):
    from pathlib import Path

    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["direct"])
    Path(arms["direct"]["oracle"]).unlink()
    report = matrix.report(frozen)
    assert report["correct_attempts"] == 0
    assert report["pairs"][0]["outcomes"]["direct"]["correctness"] == "unverified"


def test_another_attempts_verdict_and_mutated_evidence_do_not_authorize_cost_pair(
    tmp_path,
):
    from pathlib import Path

    request, frozen, arms = prepared(tmp_path)
    matrix.freeze(request, frozen)
    finish(arms["direct"])
    path = Path(arms["direct"]["oracle"])
    original = read(path)
    wrong = {**original, "receipt_sha256": "another attempt"}
    write(path, wrong)
    with pytest.raises(ValueError, match="not bound"):
        matrix.report(frozen)
    write(path, original)
    Path(original["evidence"]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        matrix.report(frozen)

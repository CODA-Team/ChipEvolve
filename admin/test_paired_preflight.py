"""Incomplete usage and wrong evidence must not become efficiency wins."""

from copy import deepcopy

import pytest

from admin.paired_preflight import correct, paired_summary, task_prompt, token_usage


def test_both_arms_have_the_same_explicit_target_scope_and_reference_policy():
    prompts = [
        task_prompt("aes", ["candidate-a", "candidate-b"], catalog, "/venv/python")
        for catalog in (["/a.json", "/b.json"], ["/brief-with-reference.json"])
    ]
    for prompt in prompts:
        assert (
            'Target candidate run IDs (the complete answer scope): ["candidate-a", "candidate-b"]'
            in prompt
        )
        assert "context only and MUST NOT appear" in prompt
        assert "EXACTLY these runs" in prompt


def test_cached_tokens_are_not_added_twice():
    usage = token_usage(
        [
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "output_tokens": 20,
                },
            }
        ]
    )
    assert usage["complete"] and usage["total_tokens"] == 120


@pytest.mark.parametrize(
    "events",
    [
        [],
        [{"type": "turn.completed", "usage": {"input_tokens": 100}}],
        [{"type": "turn.failed"}],
        [
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
            {"type": "turn.failed"},
        ],
    ],
)
def test_unknown_or_failed_model_usage_is_not_zero(events):
    usage = token_usage(events)
    assert not usage["complete"] and usage["total_tokens"] is None


def test_correct_facts_with_evidence_for_wrong_candidate_are_rejected():
    answer = {
        "design_id": "aes",
        "feasible_run_ids": ["good"],
        "rejected": [{"run_id": "bad", "violations": ["power_total_w_max"]}],
        "evidence": [
            {"run_id": "good", "path": "/good.json"},
            {"run_id": "bad", "path": "/bad.json"},
        ],
    }
    expected = {"good": [], "bad": ["power_total_w_max"]}
    allowed = {"good": {"/good.json"}, "bad": {"/bad.json"}}
    assert correct(answer, "aes", expected, allowed)
    answer["evidence"][1]["path"] = "/good.json"
    assert not correct(answer, "aes", expected, allowed)


def test_wrong_fast_answer_and_unknown_cost_do_not_enter_paired_cost_table():
    rows = [
        {
            "design_id": "aes",
            "repeat": 0,
            "arm": arm,
            "status": "succeeded",
            "correct": True,
            "wall_seconds": 1,
            "usage": {"complete": True, "total_tokens": 100},
        }
        for arm in ("direct", "platform")
    ]
    assert paired_summary(rows)["correct_pairs_with_complete_usage"] == 1
    wrong = deepcopy(rows)
    wrong[1]["correct"] = False
    assert paired_summary(wrong)["correct_pairs_with_complete_usage"] == 0
    missing = deepcopy(rows)
    missing[1]["usage"] = {"complete": False, "total_tokens": None}
    assert paired_summary(missing)["correct_pairs_with_complete_usage"] == 0
    assert paired_summary(missing)["unknown_usage_attempts"] == 1

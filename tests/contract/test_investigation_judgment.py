"""Judgment failures preserve main reasoning; probabilities cannot grant scope."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest
from tests.contract.test_investigation import service

from query_agent.application.investigation import InvestigationPolicyError
from query_agent.domain.evidence import JsonValue
from query_agent.domain.investigation import (
    AnalysisRequest,
    AnswerClaim,
    InvestigationAnswer,
    InvestigationDecision,
    ReadOperation,
)
from query_agent.domain.judgment import JudgmentAdvice


class Advice:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    def judge(
        self,
        kind: Literal["route", "rank", "verify"],
        payload: dict[str, JsonValue],
        *,
        seconds: float,
    ) -> JudgmentAdvice:
        self.calls.append(kind)
        assert 0 < seconds <= 15
        result: dict[str, JsonValue] = {}
        if kind == "verify":
            result = {
                "results": [
                    {"verdict": "contradicted", "confidence": 0.9, "same_subject": 0.99}
                ]
            }
        return JudgmentAdvice(
            kind=kind,
            input_sha256=hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
            status="fallback" if self.fail else "available",
            payload=result,
            seconds=0.1,
            error="real service failure" if self.fail else None,
        )


def test_failed_optional_judgment_keeps_evidence_and_main_workflow(
    tmp_path: Path,
) -> None:
    app, _ = service(tmp_path)
    advice = Advice(fail=True)
    app.judgment = advice
    state = app.create("why worse?", ["s"])
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="check facts",
            reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="inspect")],
        ),
    )
    assert advice.calls == ["route", "rank"]
    assert state.evidence[0].content == {
        "slack": -0.1616,
        "coverage": "one sorted stored path",
    }
    assert state.judgments[0].status == "fallback"
    assert state.active_seconds >= 0.2
    with pytest.raises(InvestigationPolicyError, match="fixed snapshot"):
        app.apply(
            state,
            InvestigationDecision(
                action="analyze",
                reasoning_summary="bad proposal",
                analysis=AnalysisRequest(
                    snapshot_id="other", question_to_verify="not permitted"
                ),
            ),
        )


def test_support_advice_requests_one_review_without_becoming_answer_authority(
    tmp_path: Path,
) -> None:
    app, _ = service(tmp_path)
    advice = Advice()
    app.judgment = advice
    state = app.create("what slack?", ["s"])
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="check facts",
            reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="inspect")],
        ),
    )
    answer = InvestigationDecision(
        action="answer",
        reasoning_summary="give observation",
        answer=InvestigationAnswer(
            summary="Recorded slack is -0.1616 ns in a sample.",
            claims=[
                AnswerClaim(
                    text="Recorded slack -0.1616 ns.",
                    evidence_ids=["ev-page"],
                    kind="fact",
                    certainty="observed",
                )
            ],
            outcome="partial",
        ),
    )
    with pytest.raises(InvestigationPolicyError, match="possible contradiction"):
        app.apply(state, answer)
    assert state.answer is None and advice.calls == ["route", "rank", "verify"]
    assert "semantic_advice" in app.context(state)
    # The main reasoner may explain a faulty semantic warning using real evidence.
    state = app.apply(
        state,
        answer.model_copy(
            update={"reasoning_summary": "Source checked; value explicitly recorded."}
        ),
    )
    assert state.status == "answered"
    assert advice.calls.count("verify") == 1

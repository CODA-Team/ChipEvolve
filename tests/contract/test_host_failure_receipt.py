"""Native host failures remain actionable without a second model loop."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tests.contract.test_investigation import service

from query_agent.adapters.llm.codex_host import CodexInvestigationHost
from query_agent.domain.investigation import InvestigationStatus


@pytest.mark.parametrize("event_type", ["error", "turn.failed"])
def test_native_capacity_failure_retains_reason_exit_and_trace(
    tmp_path: Path, event_type: str
) -> None:
    message = "Selected model is at capacity. Please try a different model."
    event: dict[str, object] = {"type": event_type}
    event.update(
        {"message": message}
        if event_type == "error"
        else {"error": {"message": message}}
    )
    app, _ = service(tmp_path / "states")
    state = app.create("why?", ["s"])
    process = Mock(returncode=1)

    def communicate(*args: object, **kwargs: object) -> None:
        events = next((tmp_path / "traces").glob("*/events.jsonl"))
        events.write_text(json.dumps(event) + "\n")

    process.communicate.side_effect = communicate
    with (
        patch("query_agent.adapters.llm.codex_host.shutil.which", return_value="codex"),
        patch(
            "query_agent.adapters.llm.codex_host.subprocess.Popen", return_value=process
        ) as popen,
    ):
        host = CodexInvestigationHost(
            trace_root=tmp_path / "traces",
            program=["python", "-m", "query_agent"],
            action_options=[],
            state_root=tmp_path / "states",
        )
        finished = host.run(app, state)
    receipt_path = next((tmp_path / "traces").glob("*/receipt.json"))
    receipt = json.loads(receipt_path.read_text())
    assert finished.status == InvestigationStatus.PAUSED
    assert message in (finished.stop_reason or "")
    assert "exit_code=1" in (finished.stop_reason or "")
    assert str(receipt_path.parent) in (finished.stop_reason or "")
    assert receipt["model_error"] == message
    assert receipt["failure_reason"] == finished.stop_reason
    assert not finished.evidence and finished.steps_used == 0
    assert popen.call_count == 1


def test_completed_turn_clears_transient_error(tmp_path: Path) -> None:
    app, _ = service(tmp_path / "states")
    state = app.create("why?", ["s"])
    process = Mock(returncode=0)

    def communicate(*args: object, **kwargs: object) -> None:
        events = next((tmp_path / "traces").glob("*/events.jsonl"))
        events.write_text(
            json.dumps({"type": "error", "message": "temporary connection error"})
            + "\n"
            + json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12}})
            + "\n"
        )

    process.communicate.side_effect = communicate
    with (
        patch("query_agent.adapters.llm.codex_host.shutil.which", return_value="codex"),
        patch(
            "query_agent.adapters.llm.codex_host.subprocess.Popen", return_value=process
        ),
    ):
        host = CodexInvestigationHost(
            trace_root=tmp_path / "traces",
            program=["python", "-m", "query_agent"],
            action_options=[],
            state_root=tmp_path / "states",
        )
        finished = host.run(app, state)
    receipt = json.loads(next((tmp_path / "traces").glob("*/receipt.json")).read_text())
    assert receipt["model_error"] is None and receipt["failure_reason"] is None
    assert receipt["usage"] == {"input_tokens": 12}
    assert finished.status == InvestigationStatus.PAUSED
    assert (
        finished.stop_reason == "host exited before an answer; raw model trace retained"
    )


def test_failure_reason_does_not_override_budget_stop(tmp_path: Path) -> None:
    app, _ = service(tmp_path)
    state = app.create("why?", ["s"])
    app.begin_host_session(state)
    finished = app.finish_host_session(
        state.investigation_id,
        initial_active_seconds=0,
        wall_seconds=state.budget.max_seconds,
        failed=True,
        failure_reason="model capacity",
    )
    assert finished.status == InvestigationStatus.STOPPED
    assert finished.stop_reason == "host wall time budget exhausted"


@pytest.mark.parametrize(
    "status", [InvestigationStatus.ANSWERED, InvestigationStatus.FAILED]
)
def test_failure_reason_preserves_terminal_state(
    tmp_path: Path, status: InvestigationStatus
) -> None:
    app, _ = service(tmp_path)
    state = app.create("why?", ["s"])
    state.status = status
    state.stop_reason = "existing terminal reason"
    app.store.save(state, state.revision)
    finished = app.finish_host_session(
        state.investigation_id,
        initial_active_seconds=0,
        wall_seconds=1,
        failed=True,
        failure_reason="model capacity",
    )
    assert finished.status == status
    assert finished.stop_reason == "existing terminal reason"

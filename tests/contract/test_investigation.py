"""Exercise evidence loss, immutable scopes and recovery of a real effect intent."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import ClassVar

import pytest
from eda_ai_client import EdaAiClient

from query_agent.adapters.investigation.data import ScopedDataReads
from query_agent.adapters.investigation.skills import InstalledInvestigationSkills
from query_agent.adapters.investigation.store import (
    ConcurrentInvestigationUpdate,
    JsonInvestigationStore,
)
from query_agent.application.investigation import (
    InvestigationBudgetExceeded,
    InvestigationPolicyError,
    InvestigationService,
    collect_sources,
)
from query_agent.application.investigation_context import compact
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
    JsonValue,
)
from query_agent.domain.investigation import (
    AnalysisRequest,
    AnalysisTicket,
    AnswerClaim,
    FixedScope,
    HandoffRequest,
    InvestigationAnswer,
    InvestigationBudget,
    InvestigationDecision,
    InvestigationStatus,
    OperationArgument,
    ReadOperation,
)
from query_agent.ports.llm import OutputModel


def scope(sid: str = "s") -> FixedScope:
    return FixedScope(
        snapshot_id=sid,
        design_id="gcd",
        run_id="run-" + sid,
        revision_id="revision-" + sid,
        stage="finish",
    )


class Wire(BaseHTTPRequestHandler):
    calls: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        type(self).calls.append(self.path)
        status = self.path.rsplit("/", 1)[-1]
        reported = scope().model_dump(exclude={"role", "parent_snapshot_id"})
        envelope: dict[str, JsonValue] = {
            "status": status if status != "wrong-revision" else "available",
            "scope": reported,
            "data": {
                "timing_paths": [{"slack": -0.1616, "unit": "ns"}],
                "count": 38,
                "returned": 1,
                "next_offset": 1,
            },
            "evidence": [],
            "missing": [],
        }
        if status == "wrong-revision":
            reported["revision_id"] = "other"
        payload = json.dumps(envelope).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def reader(tmp_path: Path) -> Iterator[ScopedDataReads]:
    Wire.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Wire)
    thread = Thread(target=server.serve_forever)
    thread.start()
    yield ScopedDataReads(
        EdaAiClient(f"http://127.0.0.1:{server.server_port}"), tmp_path / "evidence"
    )
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("truncated", EvidenceStatus.PARTIAL),
        ("available", EvidenceStatus.SUFFICIENT),
        ("partial", EvidenceStatus.PARTIAL),
        ("unavailable", EvidenceStatus.INSUFFICIENT),
        ("incomparable", EvidenceStatus.CONFLICTING),
        ("unknown-future-state", EvidenceStatus.INSUFFICIENT),
    ],
)
def test_wire_coverage_preserves_observations_without_completeness(
    reader: ScopedDataReads,
    status: str,
    expected: EvidenceStatus,
) -> None:
    item = reader.read(
        ReadOperation(path="/snapshots/s/" + status, purpose="test coverage"), [scope()]
    )
    assert item.status == expected
    assert isinstance(item.content, dict)
    assert item.content["data"] == {
        "timing_paths": [{"slack": -0.1616, "unit": "ns"}],
        "count": 38,
        "returned": 1,
        "next_offset": 1,
    }
    persisted = reader.evidence_root / (item.evidence_id + ".json")
    assert json.loads(persisted.read_text()) == item.content


def test_source_deduplication_keeps_original_excerpt_and_locator() -> None:
    ref: dict[str, JsonValue] = {
        "artifact_id": "art-native",
        "sha256": "a" * 64,
        "logical_path": "timing_report.json",
        "run_id": "run-s",
    }
    excerpt: dict[str, JsonValue] = {
        "artifact_id": "art-native",
        "sha256": "a" * 64,
        "text": "slack -0.1616 ns",
        "offset": 1024,
        "bytes_read": 17,
        "truncated": True,
        "next_offset": 1041,
    }
    original: dict[str, JsonValue] = {"source": ref, "excerpt": excerpt}
    preview = compact(original)
    assert isinstance(preview, dict) and isinstance(preview["excerpt"], dict)
    assert preview["excerpt"]["text"] == "slack -0.1616 ns"
    assert preview["excerpt"]["offset"] == 1024
    assert preview["excerpt"]["next_offset"] == 1041
    sources: dict[str, JsonValue] = {}
    collect_sources(original, sources)
    assert sources["art-native"] == ref
    assert original["excerpt"] == excerpt


@pytest.mark.parametrize(
    "path",
    [
        "/snapshots/other/summary",
        "/snapshots/s/analyses/timing",
        "/snapshots/s/native-queries",
        "/snapshots/s/compare/other/metrics",
        "https://elsewhere/snapshots/s/summary",
        "/snapshots/s/summary?run=other",
    ],
)
def test_illegal_reads_never_reach_transport(
    reader: ScopedDataReads, path: str
) -> None:
    with pytest.raises(ValueError):
        reader.read(ReadOperation(path=path, purpose="boundary check"), [scope()])
    assert not Wire.calls


def test_same_snapshot_id_with_foreign_revision_is_rejected(
    reader: ScopedDataReads,
) -> None:
    with pytest.raises(ValueError, match="revision_id"):
        reader.read(
            ReadOperation(path="/snapshots/s/wrong-revision", purpose="scope check"),
            [scope()],
        )


class Data:
    def set_timeout(self, seconds: float) -> None:
        assert seconds > 0

    def resolve_scope(self, snapshot_id: str, role: str) -> FixedScope:
        return scope(snapshot_id).model_copy(update={"role": role})

    def read(self, operation: ReadOperation, scopes: list[FixedScope]) -> Evidence:
        return Evidence(
            evidence_id="ev-page",
            source_kind=EvidenceSourceKind.DESIGN_DATA,
            content={"slack": -0.1616, "coverage": "one sorted stored path"},
            scope=EvidenceScope(
                **scopes[0].model_dump(exclude={"role", "parent_snapshot_id"})
            ),
            locator=EvidenceLocator(uri="http://df" + operation.path),
            provenance=EvidenceProvenance(
                provider="contract-test", retrieved_at=datetime.now(UTC)
            ),
            status=EvidenceStatus.PARTIAL,
        )


class Analysis:
    def __init__(self) -> None:
        self.requests: list[AnalysisRequest] = []
        self.fail_after_submit = True
        self.cancelled: list[str] = []

    def set_timeout(self, seconds: float) -> None:
        assert seconds > 0

    def submit(
        self, request: AnalysisRequest, scopes: list[FixedScope]
    ) -> AnalysisTicket:
        self.requests.append(request)
        if self.fail_after_submit:
            self.fail_after_submit = False
            raise RuntimeError("connection lost after EF accepted effect")
        return AnalysisTicket(
            run_id="run-existing",
            snapshot_id="supplement",
            parent_snapshot_id="s",
            request=request,
            status="succeeded",
        )

    def poll(self, ticket: AnalysisTicket) -> tuple[AnalysisTicket, FixedScope | None]:
        return ticket, scope("supplement").model_copy(
            update={"role": "supplement", "parent_snapshot_id": "s"}
        )

    def cancel(self, ticket: AnalysisTicket) -> AnalysisTicket:
        self.cancelled.append(ticket.run_id)
        return ticket.model_copy(update={"status": "cancelled"})


def service(tmp_path: Path) -> tuple[InvestigationService, Analysis]:
    analysis = Analysis()
    return InvestigationService(
        data=Data(),
        analysis=analysis,
        store=JsonInvestigationStore(tmp_path),
        skills=InstalledInvestigationSkills(),
    ), analysis


def test_model_handoff_cannot_manufacture_operator_permissions(tmp_path: Path) -> None:
    app, analysis = service(tmp_path)
    state = app.create("prepare a bounded ECO", ["s"])
    before = state.revision
    with pytest.raises(InvestigationPolicyError, match="operator-granted"):
        app.apply(
            state,
            InvestigationDecision(
                action="handoff",
                reasoning_summary="request downstream work",
                handoff=HandoffRequest(
                    snapshot_id="s", role="eco", objective="check setup and hold"
                ),
                answer=InvestigationAnswer(
                    summary="Fixed data missing", outcome="insufficient"
                ),
            ),
        )
    assert (
        state.revision == before
        and not analysis.requests
        and not state.handoff_packages
    )


def test_handoff_action_builds_persistent_package_without_dispatch(
    tmp_path: Path,
) -> None:
    from query_agent.domain.handoff import BufferPermission, HandoffPackage

    class Inputs(Data):
        def read(self, operation: ReadOperation, scopes: list[FixedScope]) -> Evidence:
            evidence = super().read(operation, scopes)
            if operation.purpose.startswith("freeze original input"):
                return evidence.model_copy(
                    update={
                        "evidence_id": "ev-inputs",
                        "content": {
                            "data": {
                                "snapshot": {
                                    "source_artifacts": [
                                        {
                                            "category": kind,
                                            "logical_path": kind + ".bin",
                                            "artifact_id": "art-" + kind,
                                            "run_id": "run-s",
                                            "sha256": "a" * 64,
                                            "size_bytes": 10,
                                        }
                                        for kind in (
                                            "raw_design_database",
                                            "raw_constraints",
                                            "raw_library",
                                        )
                                    ]
                                }
                            }
                        },
                    }
                )
            return evidence

    app, analysis = service(tmp_path)
    app.data = Inputs()
    permission = BufferPermission(
        instance="buf", original_master="BUF_X1", allowed_masters=["BUF_X2"]
    )
    app.handoff_permissions = {"s": [permission]}
    state = app.create("prepare a bounded ECO", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="check observed setup",
            reads=[
                ReadOperation(path="/snapshots/s/timing-paths", purpose="check setup")
            ],
        ),
    )
    app.apply(
        state,
        InvestigationDecision(
            action="handoff",
            reasoning_summary="deliver measured issue and bounded next task",
            handoff=HandoffRequest(
                snapshot_id="s",
                role="eco",
                objective=(
                    "measure whether the allowed buffer resize improves setup "
                    "without a hold regression"
                ),
            ),
            answer=InvestigationAnswer(
                summary="Stored setup slack is -0.1616 ns; a resize is untested",
                outcome="partial",
                claims=[
                    AnswerClaim(
                        text="Observed setup slack is -0.1616 ns",
                        evidence_ids=["ev-page"],
                        kind="fact",
                        certainty="observed",
                    )
                ],
            ),
        ),
    )
    restored = app.store.load(state.investigation_id)
    package = HandoffPackage.model_validate(restored.handoff_packages[0])
    assert package.buffer_permissions == [permission]
    assert package.budget.max_experiments == 1
    assert package.scope == state.scopes[0]
    assert restored.status == InvestigationStatus.PAUSED
    assert (
        restored.operations[-1].kind == "handoff_export"
        and restored.operations[-1].status == "prepared"
    )
    assert len(package.fixed_inputs) == 3 and not analysis.requests


@pytest.mark.parametrize("hosted", [False, True])
def test_explicit_resume_clears_current_pause_but_preserves_history(
    tmp_path: Path, hosted: bool
) -> None:
    app, _ = service(tmp_path)
    state = app.create("resume an interrupted investigation", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="pause",
            reasoning_summary="transient interruption",
            stop_reason="provider schema failed",
        ),
    )
    prior_revision = state.revision
    prior_calls = state.tool_calls_used
    if hosted:
        resumed = app.begin_host_session(app.store.load(state.investigation_id))
    else:

        class Model:
            def set_timeout(self, seconds: float) -> None:
                assert seconds > 0

            def complete(
                self, prompt: str, response_model: type[OutputModel]
            ) -> OutputModel:
                assert '"status": "active"' in prompt
                assert '"stop_reason": null' in prompt
                return response_model.model_validate(
                    {
                        "action": "stop",
                        "reasoning_summary": "new session evaluated remaining evidence",
                        "stop_reason": "no further data available",
                    }
                )

        app.model = Model()
        resumed = app.run(state.investigation_id)
    assert resumed.scopes == state.scopes
    assert resumed.tool_calls_used == prior_calls
    assert resumed.operations[-1].kind == "resume"
    assert (
        resumed.operations[-1].request["previous_stop_reason"]
        == "provider schema failed"
    )
    history = json.loads(
        (
            tmp_path / state.investigation_id / "history" / f"{prior_revision:06d}.json"
        ).read_text()
    )
    assert (
        history["status"] == "paused"
        and history["stop_reason"] == "provider schema failed"
    )
    assert resumed.stop_reason != "provider schema failed"


def test_resume_replays_same_effect_identity_without_spending_another_analysis(
    tmp_path: Path,
) -> None:
    app, analysis = service(tmp_path)
    state = app.create("missing endpoint detail", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="analyze",
            reasoning_summary="Verify endpoint with native STA",
            analysis=AnalysisRequest(
                snapshot_id="s", question_to_verify="endpoint slack"
            ),
        ),
    )
    assert state.status == InvestigationStatus.PAUSED
    assert state.operations[-1].status == "planned"
    restored = app.store.load(state.investigation_id)
    app.poll(restored)
    assert analysis.requests[0] == analysis.requests[1]
    assert analysis.requests[0].request_id and analysis.requests[0].created_at
    assert restored.analyses_used == 1 and restored.tool_calls_used == 2
    assert restored.pending_analyses[0].status == "imported"
    assert restored.scopes[-1].parent_snapshot_id == "s"
    assert len(restored.pending_analyses) == 1
    app.poll(restored)
    assert len(analysis.requests) == 2
    assert len(restored.scopes) == 2


def test_resume_cannot_change_candidate_scope_or_append_unimported_scope(
    tmp_path: Path,
) -> None:
    app, _ = service(tmp_path)
    state = app.create("compare", ["s", "candidate"])
    altered = state.model_copy(deep=True)
    altered.scopes[1] = scope("different")
    with pytest.raises(ValueError, match="fixed scopes"):
        app.store.save(altered, state.revision)
    altered = state.model_copy(deep=True)
    altered.scopes.append(scope("invented"))
    with pytest.raises(ValueError, match="imported analysis"):
        app.store.save(altered, state.revision)


def test_stale_host_revision_cannot_overwrite_new_checkpoint(tmp_path: Path) -> None:
    app, _ = service(tmp_path)
    state = app.create("compare", ["s"])
    stale = app.store.load(state.investigation_id)
    app.store.save(state, state.revision)
    with pytest.raises(ConcurrentInvestigationUpdate):
        app.store.save(stale, stale.revision)


def test_partial_page_supports_observed_fact_and_original_source_reaches_model(
    tmp_path: Path,
) -> None:
    app, _ = service(tmp_path)
    state = app.create("worst stored path", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="Read STA",
            reads=[
                ReadOperation(
                    path="/snapshots/s/timing-paths", purpose="worst stored path"
                )
            ],
        ),
    )
    assert "Runtime skills:" in app.context(state)
    assert len(state.skills) == 4
    assert all(skill.content in app.context(state) for skill in state.skills)
    app.apply(
        state,
        InvestigationDecision(
            action="answer",
            reasoning_summary="Report coverage",
            answer=InvestigationAnswer(
                summary="Worst stored path slack is -0.1616 ns",
                outcome="answered",
                claims=[
                    AnswerClaim(
                        text="Observed slack is -0.1616 ns",
                        evidence_ids=["ev-page"],
                        kind="fact",
                        certainty="observed",
                    )
                ],
                missing_evidence=["complete native path universe"],
            ),
        ),
    )
    assert state.status == InvestigationStatus.ANSWERED
    revision = state.revision
    app.poll(state)
    assert state.status == InvestigationStatus.ANSWERED and state.revision == revision


def test_unsupported_cause_and_foreign_analysis_are_rejected_before_effect(
    tmp_path: Path,
) -> None:
    app, analysis = service(tmp_path)
    state = app.create("why worse?", ["s"])
    with pytest.raises(InvestigationPolicyError, match="retrieved evidence"):
        app.apply(
            state,
            InvestigationDecision(
                action="answer",
                reasoning_summary="guess",
                answer=InvestigationAnswer(
                    summary="Cell changes caused it",
                    outcome="answered",
                    claims=[
                        AnswerClaim(
                            text="It is caused by cells",
                            evidence_ids=[],
                            kind="causal",
                            certainty="supported",
                        )
                    ],
                ),
            ),
        )
    with pytest.raises(InvestigationPolicyError, match="fixed snapshot"):
        app.apply(
            state,
            InvestigationDecision(
                action="analyze",
                reasoning_summary="guess",
                analysis=AnalysisRequest(
                    snapshot_id="other", question_to_verify="wrong"
                ),
            ),
        )
    assert not analysis.requests and not state.operations


def test_time_budget_prevents_new_native_effect(tmp_path: Path) -> None:
    app, analysis = service(tmp_path)
    state = app.create("why?", ["s"], budget=InvestigationBudget(max_seconds=1))
    state.active_seconds = 1
    with pytest.raises(InvestigationBudgetExceeded):
        app.apply(
            state,
            InvestigationDecision(
                action="analyze",
                reasoning_summary="verify",
                analysis=AnalysisRequest(snapshot_id="s", question_to_verify="STA"),
            ),
        )
    assert not analysis.requests


def test_explicit_stop_cancels_only_its_own_pending_analysis(tmp_path: Path) -> None:
    app, analysis = service(tmp_path)
    analysis.fail_after_submit = False
    state = app.create("STA", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="analyze",
            reasoning_summary="need endpoint timing",
            analysis=AnalysisRequest(
                snapshot_id="s", question_to_verify="endpoint timing"
            ),
        ),
    )
    app.apply(
        state,
        InvestigationDecision(
            action="stop",
            reasoning_summary="user stopped work",
            stop_reason="user stop",
        ),
    )
    assert state.status == InvestigationStatus.STOPPED
    assert analysis.cancelled == ["run-existing"]
    assert state.pending_analyses[0].status == "cancelled"
    assert state.operations[-1].kind == "cancel"


def test_native_deadline_is_clamped_to_remaining_investigation_budget(
    tmp_path: Path,
) -> None:
    app, analysis = service(tmp_path)
    state = app.create("STA", ["s"], budget=InvestigationBudget(max_seconds=20))
    state.active_seconds = 10
    app.apply(
        state,
        InvestigationDecision(
            action="analyze",
            reasoning_summary="need endpoint timing",
            analysis=AnalysisRequest(
                snapshot_id="s",
                question_to_verify="endpoint timing",
                timeout_seconds=120,
            ),
        ),
    )
    assert 1 <= analysis.requests[0].timeout_seconds <= 10


def test_host_delta_does_not_replay_prior_evidence_or_skills(tmp_path: Path) -> None:
    app, _ = service(tmp_path)
    state = app.create("why?", ["s"])
    read = InvestigationDecision(
        action="read",
        reasoning_summary="read a fact",
        reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="STA")],
    )
    app.apply(state, read)
    state.evidence[0] = state.evidence[0].model_copy(
        update={"content": {"slack": -0.1616, "text": "a" * 10000}}
    )
    first = json.loads(app.observation(state))
    assert first["new_evidence"][0]["preview_truncated"]
    assert "-0.1616" in first["new_evidence"][0]["preview"]
    assert len(first["new_evidence"][0]["preview"]) <= 1800
    assert state.evidence[0].content == {"slack": -0.1616, "text": "a" * 10000}
    delta = json.loads(app.observation(state, after_evidence=1, after_operation=1))
    assert delta["new_evidence"] == [] and delta["new_operations"] == []
    assert "Runtime skills:" not in app.observation(state)


def test_host_lease_counts_whole_wall_time_and_rejects_concurrent_start(
    tmp_path: Path,
) -> None:
    app, _ = service(tmp_path)
    state = app.create("why?", ["s"])
    app.begin_host_session(state)
    with pytest.raises(InvestigationPolicyError, match="still active"):
        app.begin_host_session(app.store.load(state.investigation_id))
    finished = app.finish_host_session(
        state.investigation_id, initial_active_seconds=0, wall_seconds=180, failed=True
    )
    assert finished.active_seconds == 180 and finished.external_deadline is None
    assert finished.status == InvestigationStatus.STOPPED
    with pytest.raises(InvestigationPolicyError, match="terminal"):
        app.begin_host_session(finished)


def test_expired_host_cannot_reset_unrecorded_wall_time(tmp_path: Path) -> None:
    app, _ = service(tmp_path)
    state = app.create("why?", ["s"])
    state.external_deadline = datetime(2000, 1, 1, tzinfo=UTC)
    app.store.save(state, state.revision)
    with pytest.raises(InvestigationBudgetExceeded, match="persisted deadline"):
        app.begin_host_session(state)
    restored = app.store.load(state.investigation_id)
    assert restored.active_seconds == restored.budget.max_seconds
    assert restored.status == InvestigationStatus.STOPPED


def test_evidence_cli_dispatch_and_paging_are_same_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from query_agent.interfaces.cli import main

    root = tmp_path / "qa"
    app, _ = service(root / "investigations")
    state = app.create("why?", ["s"])
    app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="retrieve STA",
            reads=[
                ReadOperation(path="/snapshots/s/timing-paths", purpose="worst path")
            ],
        ),
    )
    assert (
        main(
            [
                "evidence",
                state.investigation_id,
                "--state-root",
                str(root),
                "--evidence-id",
                "ev-page",
                "--max-characters",
                "50",
            ]
        )
        == 0
    )
    page = json.loads(capsys.readouterr().out)
    assert page["text"] == state.evidence[0].model_dump_json()[:50]
    assert page["next_offset"] == 50
    assert len(page["sha256"]) == 64
    updated = app.store.load(state.investigation_id)
    assert updated.tool_calls_used == state.tool_calls_used + 1
    assert updated.read_bytes_used > state.read_bytes_used
    assert updated.operations[-1].kind == "evidence_page"


def test_bounded_context_can_expand_exact_saved_evidence(tmp_path: Path) -> None:
    app, _ = service(tmp_path)
    state = app.create("investigate", ["s"])
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="obtain evidence",
            reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="read")],
        ),
    )
    original = state.evidence[0].model_copy(
        update={"content": {"slack": -0.1616, "source_text": "tail" * 20000}}
    )
    state.evidence[0] = original
    context = json.loads(app.context(state).split("Investigation state:\n")[1])
    assert context["evidence"][0]["preview_truncated"]
    assert len(app.context(state)) < 20000
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="expand saved response",
            reads=[ReadOperation(path="/evidence/ev-page/page", purpose="expand")],
        ),
    )
    page = state.evidence[-1]
    assert isinstance(page.content, dict)
    assert (
        page.content["text"] == json.dumps(original.content, ensure_ascii=False)[:6000]
    )
    assert page.content["next_offset"] == 6000
    assert page.status == EvidenceStatus.PARTIAL
    assert state.evidence[0] == original
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="check access restriction",
            reads=[ReadOperation(path="/evidence/unknown/page", purpose="scope check")],
        ),
    )
    assert state.operations[-1].status == "failed"
    assert "belong" in (state.operations[-1].error or "")


def test_execution_reader_checks_parent_before_excerpt(
    tmp_path: Path,
) -> None:
    from unittest.mock import MagicMock

    execution = MagicMock()
    execution.run.return_value = {
        "design_id": "gcd",
        "labels": {"parent_snapshot_id": "s"},
        "status": "failed",
        "run_id": "native-failure",
    }
    execution.logs.return_value = {"text": "actual library load error"}
    execution.base_url = "http://ef"
    reads = ScopedDataReads(EdaAiClient("http://df"), tmp_path, execution)
    evidence = reads.read(
        ReadOperation(
            path="/executions/native-failure/logs", purpose="inspect the real failure"
        ),
        [scope()],
    )
    assert evidence.source_kind == EvidenceSourceKind.EXECUTION_RUN
    assert evidence.scope.snapshot_id == "s"
    execution.run.return_value = {
        "design_id": "gcd",
        "labels": {
            "parent_snapshot_id": "another",
            "analysis_of_run_id": scope().run_id,
        },
    }
    execution.logs.reset_mock()
    with pytest.raises(ValueError, match="fixed investigation scope"):
        reads.read(
            ReadOperation(
                path="/executions/native-failure/logs", purpose="wrong parent"
            ),
            [scope()],
        )
    execution.logs.assert_not_called()


def test_source_point_preview_preserves_deep_numeric_observations() -> None:
    from query_agent.application.investigation_context import compact

    point: dict[str, JsonValue] = {
        "pin": "u/A[0]",
        "arrival": 4.316e-10,
        "cell": "BUF_X1",
    }
    response: JsonValue = {
        "data": {"fragments": [{"original": {"check": {"source_path": [point]}}}]}
    }
    view = compact(response)
    text = json.dumps(view)
    assert "u/A[0]" in text and "4.316e-10" in text and "BUF_X1" in text
    many = compact(list(range(20)))
    assert isinstance(many, dict)
    assert many["preview_only"] is True and many["original_item_count"] == 20
    assert "complete" not in many  # A preview limit must not change data coverage.


def test_saved_projection_preserves_all_selected_points_without_retruncation(
    tmp_path: Path,
) -> None:
    from query_agent.application.investigation_context import evidence_view

    app, _ = service(tmp_path)
    state = app.create("investigate", ["s"])
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="read original source",
            reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="read")],
        ),
    )
    points: list[JsonValue] = [{"pin": f"u/{i}", "arrival": i} for i in range(30)]
    state.evidence[0] = state.evidence[0].model_copy(
        update={"content": {"data": {"raw/points": points}, "metadata": "x" * 20000}}
    )
    operation = ReadOperation(
        path="/evidence/ev-page/page",
        purpose="retrieve all points without repeated metadata",
        arguments=[OperationArgument(name="pointer", value="/data/raw~1points")],
    )
    state = app.apply(
        state,
        InvestigationDecision(
            action="read", reasoning_summary="expand selected points", reads=[operation]
        ),
    )
    page = state.evidence[-1]
    assert isinstance(page.content, dict)
    assert json.loads(str(page.content["text"])) == points
    assert page.content["complete"] is True
    assert page.scope == state.evidence[0].scope
    view = evidence_view(page, 100)
    assert view["preview_truncated"] is False
    assert view["content"] == page.content
    assert state.evidence[0].content != page.content
    for pointer in ("data", "/missing", "/data/raw~1points/01"):
        state = app.apply(
            state,
            InvestigationDecision(
                action="read",
                reasoning_summary="check invalid selection",
                reads=[
                    operation.model_copy(
                        update={
                            "arguments": [
                                OperationArgument(name="pointer", value=pointer)
                            ]
                        }
                    )
                ],
            ),
        )
        assert state.operations[-1].status == "failed"


def test_reverse_investigation_comparison_rejected_before_data_access(
    tmp_path: Path,
) -> None:
    from unittest.mock import MagicMock

    client = MagicMock(spec=EdaAiClient)
    reader = ScopedDataReads(client, tmp_path / "evidence")
    baseline = FixedScope(
        snapshot_id="b",
        design_id="chip",
        revision_id="before",
        run_id="run-b",
        stage="finish",
        role="baseline",
    )
    candidate = baseline.model_copy(
        update={
            "snapshot_id": "c",
            "revision_id": "after",
            "run_id": "run-c",
            "role": "candidate",
        }
    )
    with pytest.raises(ValueError, match="candidate minus baseline"):
        reader.read(
            ReadOperation(path="/snapshots/c/compare/b/inventory", purpose="compare"),
            [baseline, candidate],
        )
    client.read_query.assert_not_called()


def test_partial_delivery_review_preserves_budget_and_allows_honest_stop(
    tmp_path: Path,
) -> None:
    app, analysis = service(tmp_path)
    state = app.create("investigate the missing measurements", ["s"])
    decision = InvestigationDecision(
        action="answer",
        reasoning_summary="deliver a partial result",
        answer=InvestigationAnswer(
            summary="The required fixed input is absent; a conclusion is unavailable.",
            outcome="partial",
            missing_evidence=["original SDC is absent"],
        ),
    )
    original_budget = state.budget
    with pytest.raises(InvestigationPolicyError, match="pre-delivery review"):
        app.apply(state, decision)
    restored = app.store.load(state.investigation_id)
    assert restored.status == InvestigationStatus.ACTIVE
    assert restored.answer is None and restored.draft_answer == decision.answer
    assert restored.completion_review_done and restored.budget == original_budget
    assert not analysis.requests
    # The review is advice to continue where possible, never a fabricated pass.
    restored = app.apply(restored, decision)
    assert restored.status == InvestigationStatus.ANSWERED
    assert restored.answer and restored.answer.outcome == "partial"


def test_source_catalog_deduplication_does_not_claim_missing_facts(
    tmp_path: Path,
) -> None:
    from query_agent.application.investigation_context import evidence_view

    app, _ = service(tmp_path)
    state = app.create("investigate", ["s"])
    state = app.apply(
        state,
        InvestigationDecision(
            action="read",
            reasoning_summary="read source",
            reads=[ReadOperation(path="/snapshots/s/timing-paths", purpose="read")],
        ),
    )
    item = state.evidence[0].model_copy(
        update={
            "content": {
                "artifact_id": "source",
                "sha256": "a" * 64,
                "text": "actual slack -0.2 ns",
            }
        }
    )
    view = evidence_view(item, 6000)
    assert view["preview_truncated"] is False
    assert isinstance(view["content"], dict)
    assert view["content"]["text"] == "actual slack -0.2 ns"


def test_scope_request_keeps_ambiguity_before_investigation_effects(
    tmp_path: Path,
) -> None:
    from unittest.mock import MagicMock

    from query_agent.adapters.investigation.scope import resolve_requests

    client = MagicMock()
    client.read_query.return_value = {
        "status": "partial",
        "data": {"candidates": [{"snapshot_id": "s"}, {"snapshot_id": "other"}]},
    }
    result = resolve_requests(
        client, [{"revision_id": "candidate"}], question="why worse?", output=tmp_path
    )
    assert result["status"] == "needs_scope" and result["snapshot_ids"] == []
    assert len(list(tmp_path.glob("scope-*.json"))) == 1

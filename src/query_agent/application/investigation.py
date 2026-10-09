"""Evidence-first investigation with persisted effects, bounded work and recovery."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from query_agent.domain.errors import LLMContractError
from query_agent.domain.evidence import Evidence, EvidenceStatus, JsonValue
from query_agent.domain.handoff import BufferPermission, HandoffPackage
from query_agent.domain.investigation import (
    AnalysisRequest,
    InvestigationAnswer,
    InvestigationBudget,
    InvestigationDecision,
    InvestigationState,
    InvestigationStatus,
    OperationReceipt,
    ReadOperation,
)
from query_agent.ports.investigation import (
    InvestigationAnalysisPort,
    InvestigationDataPort,
    InvestigationModel,
    InvestigationStore,
    SkillProvider,
)
from query_agent.ports.judgment import InvestigationJudgmentPort

from .handoff import create_handoff
from .investigation_context import (
    collect_sources,
    compact,
    evidence_view,
    operation_views,
    scalar_first,
)


class InvestigationPolicyError(ValueError):
    """The proposal needs corrected scope, evidence or budget before execution."""


class InvestigationBudgetExceeded(InvestigationPolicyError):
    """A fixed investigation limit prevents further work."""


class InvestigationService:
    def __init__(
        self,
        *,
        data: InvestigationDataPort,
        analysis: InvestigationAnalysisPort,
        store: InvestigationStore,
        skills: SkillProvider,
        model: InvestigationModel | None = None,
        judgment: InvestigationJudgmentPort | None = None,
        handoff_permissions: dict[str, list[BufferPermission]] | None = None,
    ) -> None:
        self.data, self.analysis, self.store, self.skills, self.model = (
            data,
            analysis,
            store,
            skills,
            model,
        )
        self.judgment = judgment
        self.handoff_permissions = handoff_permissions or {}

    def create(
        self,
        question: str,
        snapshot_ids: list[str],
        *,
        budget: InvestigationBudget | None = None,
        use_skills: bool = True,
    ) -> InvestigationState:
        if not snapshot_ids or len(set(snapshot_ids)) != len(snapshot_ids):
            raise InvestigationPolicyError(
                "investigation needs unique explicit snapshots"
            )
        scopes = [
            self.data.resolve_scope(
                sid,
                "subject"
                if len(snapshot_ids) == 1
                else ("baseline" if index == 0 else "candidate"),
            )
            for index, sid in enumerate(snapshot_ids)
        ]
        if len({scope.design_id for scope in scopes}) != 1:
            raise InvestigationPolicyError(
                "comparison snapshots must belong to the same design"
            )
        state = InvestigationState(
            investigation_id="inv-" + uuid.uuid4().hex,
            question=question,
            scopes=scopes,
            budget=budget or InvestigationBudget(),
            skills=self.skills.load(
                [
                    "timing-degradation",
                    "experiment-comparison",
                    "tool-failure",
                    "task-handoff",
                ]
            )
            if use_skills
            else [],
        )
        self.store.save(state, 0)
        self._judge(state, "route", {"question": state.question})
        return state

    def context(self, state: InvestigationState) -> str:
        sources: dict[str, JsonValue] = {}
        for item in state.evidence:
            collect_sources(item.content, sources)
        per_item = max(1200, min(6000, 48000 // max(1, len(state.evidence))))
        ranked_ids: list[str] = []
        for advice in state.judgments:
            if advice.kind == "rank" and advice.status == "available":
                ranked_ids = [
                    str(row["id"])
                    for row in cast(
                        list[dict[str, JsonValue]], advice.payload.get("ranked", [])
                    )
                ]
        ordered = sorted(
            state.evidence,
            key=lambda item: (
                ranked_ids.index(item.evidence_id)
                if item.evidence_id in ranked_ids
                else len(ranked_ids)
            ),
        )
        evidence = [evidence_view(item, per_item) for item in ordered]
        catalog = """Actions: read/compare with up to 8 scoped GET operations; analyze
with a fixed snapshot and a discriminating STA question; wait for submitted jobs;
answer with evidence IDs and limitations; pause/stop with a reason; handoff.
All data paths below begin with /snapshots/{id}/; do not drop this prefix.
Read paths: /snapshots/{id}/summary (detail=full for original sources), constraints,
metrics, timing-overview, timing-paths (check=setup|hold,endpoint,startpoint,group,
limit,offset,sort=slack,order=worst,detail=full for per-path source locators),
timing-paths/{path_id}/engineering, objects (kind,name,limit,offset,fields),
objects/statistics, objects/{id}/relationships, nets/{name}/engineering,
instances/{name}/engineering, compare/{other_id}/metrics (name),
compare/{other_id}/inventory, compare/{other_id}/timing-paths/{path_id} (to_path_id),
records/timing_paths/{path_id}/fragments (original file-local JSON with digest),
records/timing_points/{point_id}/fragments,
sources/{artifact_id}/excerpt (offset,max_bytes), run-inventory,
artifacts/files (limit,offset), artifacts/files/excerpt (path,offset,max_bytes).
Object projection fields are name,kind,identity,attributes,engineering,physical,
spatial,object_id,parent_id or nested keys (e.g. attributes.direction).
Timing reads: check=setup|hold; analyze: check=both.
Registered sources (including area) use sources/{artifact_id}/excerpt. The separate
artifacts/files ORFS tree may be empty for a standalone analysis.
For an omitted saved response, read /evidence/{evidence_id}/page with offset and
max_characters (1..12000); next_offset preserves every byte of the saved JSON.
Optional pointer is an RFC6901 JSON pointer into the saved response, e.g.
/data/fragments/0/fragment/source_path. It selects existing data, not new facts.
A truncated preview is not a complete observation. Retrieve necessary omitted
values before claiming them. Do not repeatedly fetch identical full reports.
Original fragments project actual keys: fragments.fragment.slack or
fragments.fragment.source_path, using fields.
Computed increments use engineering; they are not fields of the raw fragment.
Execution evidence uses /executions/{run_id}, /executions/{run_id}/logs,
/executions/{run_id}/resources, /executions/{run_id}/artifacts and
/executions/{run_id}/artifacts/{artifact_id}/excerpt (offset,max_bytes).
Code verifies that each run belongs to a fixed snapshot/design before reading it.
For relationships, kind is the source object kind; only kind,limit,offset apply.
Prefer instances/{name}/engineering for a named cell's master and nets.
timing-overview performs domain joins and defaults to many paths. When needed,
use limit=1 and fields=paths,selected_path_count,stored_matching_paths,coverage_scope;
never fetch an unprojected overview just to rediscover known worst paths.
For cell/wire decomposition, read timing-paths/{path_id}/engineering with
fields=path,data_path_increments,data_point_extrema,association_coverage,units.
compare/{other_snapshot}/inventory?include_instance_changes=1 returns complete
stored instance/master changes with counts, identity ambiguity and native coverage.
Use timing-points filtered by instance_id (from instance engineering) to locate
paths touching a changed cell. Project fields including path_id,pin_name,
cell_name,arrival_ns,load_ff,slew_ns.
Metrics comparison needs name (e.g. SETUP_WNS). Native area retains precision.
For cross-experiment timing comparison use mode=experiment and explicit to_path_id.
Select fields=timing,input_conditions,matching,analysis_context,interpretation;
full object matching/relations carry rich repeated provenance and are unnecessary
for this numerical comparison. Expand physical changes only when needed.
Experiment mode preserves input SHA identities; default stage mode requires the
same run/revision. Indexing IDs alone do not establish changed physical inputs.
For a timing comparison, the first batch should include each snapshot's summary
(fields=snapshot.source_artifacts,record_counts,coverage; avoid the large producer
manifest in detail=full),
constraints, worst setup timing-paths and worst hold timing-paths (limit=1;
fields=path_id,startpoint,endpoint,slack_ns,arrival_ns,required_ns,check).
Use sort=slack,order=worst; an unsorted path:0 is not necessarily the worst path.
Then retrieve the relevant SDC excerpts and file-local records/fragments for the
named paths. These slices expose original values without paging whole JSON reports.
Arguments are separate name/value strings, never appended to path. Encode native
names as path segments. Only fixed scopes are allowed. POST-like reads are forbidden.
Analysis loads the exact original inputs; it exports setup and hold and adds a new
supplement scope after success/import. Never infer no path from an empty sample.
Find new path IDs by endpoint in each supplement; old snapshot IDs do not transfer.
Different scope/corner/constraints invalidate unqualified performance comparison.
Give facts/comparisons/hypotheses/causal statements separate claim kinds. A definite
causal claim needs retrieved original excerpts and support from both comparison
scopes, and must discuss alternatives. Never invent facts, evidence IDs or
execution results.
If complete, answer promptly; do not spend budget on unrelated data.
With fewer than 6 calls or 30000 bytes left, prioritize a scoped answer and gaps.
Include only observations needed to answer the question. Numeric claims must
match retrieved values and units. Use returned deterministic comparison deltas
for derived arithmetic; do not add unrequested thresholds or runners-up.
Deltas are target minus source: use baseline -> candidate. Reversing reverses sign.
effective.sdc is derived; compare the loaded SDC in input_conditions.
Negative setup slack can improve without closure. A worst-path switch alone
proves neither improvement nor its absence; compare the old endpoint in both scopes.
Rounded area retains direction, but cannot prove a sub-unit exact difference.
Only update at most 3 hypotheses per action; omit unchanged hypotheses and facts.
Keep reasoning_summary to 3 sentences, summary to 150 words and claims to at
most 6 concise observations. Empty unused payloads are preferable. For an answer
action, confirmed_facts should be empty: the application records answer claims.
source_ref refers to the source catalog below.
Optional semantic judgments are advice, not source facts. Low confidence or
failed judgments return to this reasoning workflow. Relevance does not mean
truth; keep counterevidence. Support warnings should prompt a cited revision or
an explicit explanation, never a fabricated fact or automatic causal certainty.
If fewer than 30 seconds remain, deliver the supported partial answer and gaps."""
        return (
            catalog
            + "\n\nRuntime skills:\n"
            + "\n\n".join(skill.content for skill in state.skills)
            + "\n\nInvestigation state:\n"
            + json.dumps(
                {
                    "question": state.question,
                    "status": state.status,
                    "stop_reason": state.stop_reason,
                    "answer": state.answer.model_dump(mode="json")
                    if state.answer
                    else None,
                    "draft_answer": state.draft_answer.model_dump(mode="json")
                    if state.draft_answer
                    else None,
                    "completion_review_done": state.completion_review_done,
                    "scopes": [scope.model_dump(mode="json") for scope in state.scopes],
                    "evidence": evidence,
                    "source_catalog": sources,
                    "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
                    "missing_evidence": state.missing_evidence,
                    "pending_analyses": [
                        ticket.model_dump(mode="json")
                        for ticket in state.pending_analyses
                    ],
                    "handoff_permissions": {
                        sid: [p.model_dump(mode="json") for p in grants]
                        for sid, grants in self.handoff_permissions.items()
                        if sid in {scope.snapshot_id for scope in state.scopes}
                    },
                    "handoff_packages": state.handoff_packages,
                    "semantic_advice": [
                        item.model_dump(mode="json") for item in state.judgments
                    ],
                    "operations": operation_views(state.operations),
                    "budget": state.budget.model_dump(),
                    "steps_used": state.steps_used,
                    "tool_calls_used": state.tool_calls_used,
                    "analyses_used": state.analyses_used,
                    "read_bytes_used": state.read_bytes_used,
                    "active_seconds": state.active_seconds,
                    "remaining_seconds": max(
                        0, state.budget.max_seconds - state.active_seconds
                    ),
                },
                ensure_ascii=False,
            )
        )

    def observation(
        self,
        state: InvestigationState,
        *,
        after_evidence: int = 0,
        after_operation: int = 0,
    ) -> str:
        """Deliver a bounded delta to a host that already received skills/context.

        Complete evidence remains in the checkpoint. Preview truncation is explicit
        and a host can request the named evidence separately; it is never coverage.
        """
        remaining = state.budget.max_seconds - state.active_seconds
        if state.external_deadline is not None:
            remaining = min(
                remaining,
                (state.external_deadline - datetime.now(UTC)).total_seconds(),
            )
        items: list[dict[str, object]] = []
        sources: dict[str, JsonValue] = {}
        for item in state.evidence[after_evidence:][:8]:
            collect_sources(item.content, sources)
            content = item.content
            if isinstance(content, dict):
                content = {
                    key: value
                    for key, value in content.items()
                    if key not in ("scope", "contract_version", "tool")
                }
                data = content.get("data")
                if isinstance(data, dict):
                    content["data"] = {
                        key: value for key, value in data.items() if key != "snapshot"
                    }
            view = evidence_view(item.model_copy(update={"content": content}), 1800)
            viewed = view["content"]
            text = (
                str(viewed["preview"])
                if isinstance(viewed, dict) and "preview" in viewed
                else json.dumps(scalar_first(viewed), ensure_ascii=False)
            )
            items.append(
                {
                    "evidence_id": item.evidence_id,
                    "snapshot_id": item.scope.snapshot_id,
                    "status": item.status,
                    "reason": item.reason,
                    "path": item.locator.uri,
                    "arguments": item.locator.section,
                    "preview": text,
                    "preview_truncated": view["preview_truncated"],
                    "expand": "evidence --evidence-id " + item.evidence_id,
                }
            )
        return json.dumps(
            {
                "investigation_id": state.investigation_id,
                "status": state.status,
                "stop_reason": state.stop_reason,
                "answer": state.answer.model_dump(mode="json")
                if state.answer
                else None,
                "scopes": [scope.model_dump(mode="json") for scope in state.scopes],
                "draft_answer": state.draft_answer.model_dump(mode="json")
                if state.draft_answer
                else None,
                "completion_review_done": state.completion_review_done,
                "new_evidence": items,
                "new_source_catalog": sources,
                "semantic_advice": [
                    item.model_dump(mode="json") for item in state.judgments
                ],
                "evidence_count": len(state.evidence),
                "omitted_evidence_count": max(
                    0, len(state.evidence) - after_evidence - len(items)
                ),
                "new_operations": [
                    item.model_dump(mode="json")
                    for item in state.operations[after_operation:][-8:]
                ],
                "hypotheses": [
                    item.model_dump(mode="json") for item in state.hypotheses
                ],
                "missing_evidence": state.missing_evidence,
                "pending_analyses": [
                    item.model_dump(mode="json") for item in state.pending_analyses
                ],
                "remaining_seconds": max(0, remaining),
                "remaining_read_bytes": max(
                    0, state.budget.max_read_bytes - state.read_bytes_used
                ),
                "steps_used": state.steps_used,
                "tool_calls_used": state.tool_calls_used,
                "read_bytes_used": state.read_bytes_used,
            },
            ensure_ascii=False,
        )

    def _save(self, state: InvestigationState) -> None:
        self.store.save(state, state.revision)

    def _judge(
        self,
        state: InvestigationState,
        kind: Literal["route", "rank", "verify"],
        payload: dict[str, JsonValue],
    ) -> None:
        if self.judgment is None or any(item.kind == kind for item in state.judgments):
            return
        remaining = state.budget.max_seconds - state.active_seconds
        if remaining <= 5:
            return
        self._budget(state, reads=1)
        advice = self.judgment.judge(kind, payload, seconds=min(15, remaining))
        state.judgments.append(advice)
        state.tool_calls_used += 1
        state.active_seconds += advice.seconds
        self._save(state)

    def export_handoff(
        self,
        state: InvestigationState,
        *,
        snapshot_id: str,
        role: str,
        objective: str,
        permissions: list[BufferPermission],
    ) -> HandoffPackage:
        self._budget(state, reads=1)
        self.data.set_timeout(min(30, state.budget.max_seconds - state.active_seconds))
        from query_agent.domain.investigation import OperationArgument, ReadOperation

        operation = ReadOperation(
            path="/snapshots/" + snapshot_id + "/summary",
            purpose="freeze original input identities for downstream handoff",
            arguments=[
                OperationArgument(name="fields", value="snapshot.source_artifacts")
            ],
        )
        evidence = (
            self._evidence_page(state, operation)
            if operation.path.startswith("/evidence/")
            else self.data.read(operation, state.scopes)
        )
        content = evidence.content
        if not isinstance(content, dict):
            raise InvestigationPolicyError(
                "handoff source response must be an envelope"
            )
        data = content.get("data")
        snapshot = data.get("snapshot") if isinstance(data, dict) else None
        if not isinstance(snapshot, dict) or not isinstance(
            snapshot.get("source_artifacts"), list
        ):
            raise InvestigationPolicyError(
                "handoff needs registered original input sources"
            )
        state.evidence.append(evidence)
        state.tool_calls_used += 1
        state.read_bytes_used += len(evidence.model_dump_json().encode())
        self._save(state)
        self._budget(state)
        package = create_handoff(
            state,
            snapshot_id=snapshot_id,
            role=role,
            objective=objective,
            source_artifacts=cast(
                list[dict[str, JsonValue]], snapshot["source_artifacts"]
            ),
            buffer_permissions=permissions,
        )
        state.handoff_packages.append(
            cast(dict[str, JsonValue], package.model_dump(mode="json"))
        )
        state.operations.append(
            OperationReceipt(
                operation_id=package.handoff_id,
                kind="handoff_export",
                request={
                    "snapshot_id": snapshot_id,
                    "role": role,
                    "objective": objective,
                },
                status="prepared",
                seconds=0,
            )
        )
        self._save(state)
        return package

    def stop_for_budget(
        self, state: InvestigationState, error: InvestigationBudgetExceeded
    ) -> InvestigationState:
        state.status = InvestigationStatus.STOPPED
        state.stop_reason = str(error)
        self._cancel_outstanding(state)
        self._save(state)
        return state

    def begin_host_session(self, state: InvestigationState) -> InvestigationState:
        if state.status in (
            InvestigationStatus.ANSWERED,
            InvestigationStatus.STOPPED,
            InvestigationStatus.FAILED,
        ):
            raise InvestigationPolicyError("terminal investigation cannot start a host")
        if (
            state.external_deadline is not None
            and state.external_deadline > datetime.now(UTC)
        ):
            raise InvestigationPolicyError("another host session is still active")
        if state.external_deadline is not None:
            state.active_seconds = state.budget.max_seconds
            state.external_deadline = None
            state.status = InvestigationStatus.STOPPED
            state.stop_reason = "previous host exceeded its persisted deadline"
            self._cancel_outstanding(state)
            self._save(state)
            raise InvestigationBudgetExceeded(state.stop_reason)
        state.external_deadline = None
        self._budget(state)
        self._resume_paused(state)
        state.external_deadline = datetime.now(UTC) + timedelta(
            seconds=state.budget.max_seconds - state.active_seconds
        )
        self._save(state)
        return state

    def _resume_paused(self, state: InvestigationState) -> None:
        if state.status != InvestigationStatus.PAUSED:
            return
        state.operations.append(
            OperationReceipt(
                operation_id="resume-" + uuid.uuid4().hex,
                kind="resume",
                request={"previous_stop_reason": state.stop_reason},
                status="completed",
                seconds=0,
            )
        )
        state.status = InvestigationStatus.ACTIVE
        state.stop_reason = None
        self._save(state)

    def finish_host_session(
        self,
        investigation_id: str,
        *,
        initial_active_seconds: float,
        wall_seconds: float,
        failed: bool,
    ) -> InvestigationState:
        state = self.store.load(investigation_id)
        state.active_seconds = max(
            state.active_seconds, initial_active_seconds + wall_seconds
        )
        state.external_deadline = None
        if state.status not in (
            InvestigationStatus.ANSWERED,
            InvestigationStatus.STOPPED,
            InvestigationStatus.FAILED,
        ):
            if state.active_seconds >= state.budget.max_seconds:
                state.status = InvestigationStatus.STOPPED
                state.stop_reason = "host wall time budget exhausted"
                self._cancel_outstanding(state)
            elif failed or state.status == InvestigationStatus.ACTIVE:
                state.status = InvestigationStatus.PAUSED
                state.stop_reason = (
                    "host exited before an answer; raw model trace retained"
                )
        self._save(state)
        return state

    def _budget(
        self, state: InvestigationState, *, reads: int = 0, analyses: int = 0
    ) -> None:
        if (
            state.external_deadline is not None
            and datetime.now(UTC) >= state.external_deadline
        ):
            raise InvestigationBudgetExceeded("host wall time budget exhausted")
        if state.steps_used >= state.budget.max_steps:
            raise InvestigationBudgetExceeded("step budget exhausted")
        if state.tool_calls_used + reads + analyses > state.budget.max_tool_calls:
            raise InvestigationBudgetExceeded("tool call budget exhausted")
        if state.analyses_used + analyses > state.budget.max_analyses:
            raise InvestigationBudgetExceeded("analysis budget exhausted")
        if state.read_bytes_used >= state.budget.max_read_bytes:
            raise InvestigationBudgetExceeded("read budget exhausted")
        if state.active_seconds >= state.budget.max_seconds:
            raise InvestigationBudgetExceeded("active time budget exhausted")

    def _remaining(self, state: InvestigationState, started: float) -> float:
        remaining = (
            state.budget.max_seconds
            - state.active_seconds
            - (time.monotonic() - started)
        )
        if state.external_deadline is not None:
            remaining = min(
                remaining, (state.external_deadline - datetime.now(UTC)).total_seconds()
            )
        if remaining <= 0:
            raise InvestigationBudgetExceeded("active time budget exhausted")
        return remaining

    def apply(
        self, state: InvestigationState, decision: InvestigationDecision
    ) -> InvestigationState:
        if state.status in (
            InvestigationStatus.ANSWERED,
            InvestigationStatus.STOPPED,
            InvestigationStatus.FAILED,
        ):
            raise InvestigationPolicyError("investigation is already terminal")
        self._budget(
            state, reads=len(decision.reads), analyses=int(decision.action == "analyze")
        )
        known = {e.evidence_id for e in state.evidence}
        for hypothesis in decision.hypotheses:
            if set(hypothesis.supports + hypothesis.counterevidence) - known:
                raise InvestigationPolicyError("hypothesis cites unknown evidence")
        if decision.analysis is not None and decision.analysis.snapshot_id not in {
            s.snapshot_id for s in state.scopes
        }:
            raise InvestigationPolicyError("analysis needs a fixed snapshot")
        if decision.handoff is not None:
            if decision.handoff.snapshot_id not in {
                scope.snapshot_id for scope in state.scopes
            }:
                raise InvestigationPolicyError("handoff needs a fixed snapshot")
            if decision.handoff.role == "eco" and not self.handoff_permissions.get(
                decision.handoff.snapshot_id
            ):
                raise InvestigationPolicyError(
                    "ECO handoff needs operator-granted permissions for this snapshot"
                )
            self._budget(state, reads=1)
        if decision.answer is not None:
            self._validate_answer(state, decision.answer)
            first_review = not any(item.kind == "verify" for item in state.judgments)
            if decision.answer.claims:
                cited = {
                    eid
                    for claim in decision.answer.claims
                    for eid in claim.evidence_ids
                }
                self._judge(
                    state,
                    "verify",
                    {
                        "claims": [claim.text for claim in decision.answer.claims],
                        "evidence": [
                            {
                                "id": item.evidence_id,
                                "text": json.dumps(
                                    scalar_first(compact(item.content)),
                                    ensure_ascii=False,
                                )[:4000],
                            }
                            for item in state.evidence
                            if item.evidence_id in cited
                        ],
                    },
                )
            if first_review and any(
                advice.kind == "verify"
                and advice.status == "available"
                and any(
                    row.get("verdict") == "contradicted"
                    and float(str(row.get("confidence", 0))) >= 0.8
                    and float(str(row.get("same_subject", 0))) >= 0.5
                    for row in cast(
                        list[dict[str, JsonValue]], advice.payload.get("results", [])
                    )
                )
                for advice in state.judgments
            ):
                state.draft_answer = decision.answer
                state.completion_review_done = True
                self._save(state)
                raise InvestigationPolicyError(
                    "semantic support review found a possible contradiction; "
                    "inspect the "
                    "saved advice and revise or explain with source evidence"
                )
            if (
                decision.action == "answer"
                and decision.answer.outcome == "partial"
                and not state.completion_review_done
                and state.budget.max_seconds - state.active_seconds > 45
                and state.budget.max_tool_calls - state.tool_calls_used >= 4
                and state.budget.max_steps - state.steps_used >= 2
                and state.budget.max_read_bytes - state.read_bytes_used >= 20000
            ):
                state.draft_answer = decision.answer
                state.completion_review_done = True
                self._save(state)
                raise InvestigationPolicyError(
                    "pre-delivery review: useful budget remains. Review this saved "
                    "partial draft against the question, new analysis results and "
                    "accessible evidence. Complete the next discriminating lookup "
                    "if possible; otherwise deliver a scoped partial answer with "
                    "the actual blocking precondition. This review occurs once "
                    "and does not require exhaustive closure or invent missing data."
                )
        state.decisions.append(decision)
        merged_hypotheses = {h.hypothesis_id: h for h in state.hypotheses}
        merged_hypotheses.update({h.hypothesis_id: h for h in decision.hypotheses})
        state.hypotheses = list(merged_hypotheses.values())
        if decision.confirmed_facts:
            self._validate_answer(
                state,
                InvestigationAnswer(
                    summary="interim facts",
                    claims=decision.confirmed_facts,
                    outcome="partial",
                ),
            )
            state.confirmed_facts.extend(decision.confirmed_facts)
        state.missing_evidence = decision.missing_evidence
        state.steps_used += 1
        state.status = InvestigationStatus.ACTIVE
        self._save(state)
        started = time.monotonic()
        already_counted = state.active_seconds
        try:
            if decision.action in ("read", "compare"):
                self._reads(state, decision, started)
            elif decision.action == "analyze":
                assert decision.analysis is not None
                request = decision.analysis.model_copy(
                    update={
                        "request_id": uuid.uuid4().hex[:12],
                        "created_at": datetime.now(UTC),
                        "timeout_seconds": max(
                            1,
                            min(
                                decision.analysis.timeout_seconds,
                                int(self._remaining(state, started)),
                            ),
                        ),
                    }
                )
                receipt = OperationReceipt(
                    operation_id=request.request_id or "",
                    kind="analyze",
                    request=cast(dict[str, JsonValue], request.model_dump(mode="json")),
                    status="planned",
                    seconds=0,
                )
                state.operations.append(receipt)
                state.tool_calls_used += 1
                state.analyses_used += 1
                self._save(state)
                self.analysis.set_timeout(self._remaining(state, started))
                self._submit_planned(state, len(state.operations) - 1)
                state.status = InvestigationStatus.WAITING
            elif decision.action == "wait":
                self.poll(state)
            elif decision.action in ("answer", "handoff"):
                state.answer = decision.answer
                state.confirmed_facts = (
                    [
                        claim
                        for claim in decision.answer.claims
                        if claim.kind in ("fact", "comparison")
                    ]
                    if decision.answer
                    else []
                )
                state.stop_reason = (
                    "scoped answer delivered with stated outcome and limitations"
                )
                if decision.handoff is not None:
                    request = decision.handoff
                    self.export_handoff(
                        state,
                        snapshot_id=request.snapshot_id,
                        role=request.role,
                        objective=request.objective,
                        permissions=self.handoff_permissions.get(
                            request.snapshot_id, []
                        )
                        if request.role == "eco"
                        else [],
                    )
                    state.status = InvestigationStatus.PAUSED
                    state.stop_reason = (
                        "handoff package prepared; awaiting an actual consumer receipt"
                    )
                else:
                    state.status = InvestigationStatus.ANSWERED
            elif decision.action == "pause":
                state.status = InvestigationStatus.PAUSED
                state.stop_reason = (
                    decision.stop_reason or "waiting for a handoff consumer"
                )
            elif decision.action == "stop":
                state.status = InvestigationStatus.STOPPED
                state.stop_reason = decision.stop_reason
                self._cancel_outstanding(state)
        except (OSError, RuntimeError) as exc:
            state.status = InvestigationStatus.PAUSED
            state.stop_reason = "operation failed; persisted intent retained: " + str(
                exc
            )
        finally:
            state.active_seconds = already_counted + time.monotonic() - started
            self._save(state)
        if decision.action in ("read", "compare") and state.evidence:
            self._judge(
                state,
                "rank",
                {
                    "query": state.question,
                    "candidates": [
                        {
                            "id": item.evidence_id,
                            "text": item.locator.uri
                            + " "
                            + json.dumps(
                                scalar_first(compact(item.content)), ensure_ascii=False
                            )[:1700],
                        }
                        for item in state.evidence
                    ],
                },
            )
        return state

    def _reads(
        self,
        state: InvestigationState,
        decision: InvestigationDecision,
        batch_started: float,
    ) -> None:
        for operation in decision.reads:
            self.data.set_timeout(self._remaining(state, batch_started))
            started = time.monotonic()
            operation_id = "op-" + uuid.uuid4().hex
            state.tool_calls_used += 1
            budget_error: InvestigationBudgetExceeded | None = None
            try:
                evidence = (
                    self._evidence_page(state, operation)
                    if operation.path.startswith("/evidence/")
                    else self.data.read(operation, state.scopes)
                )
                size = len(evidence.model_dump_json().encode())
                state.read_bytes_used += size
                if state.read_bytes_used > state.budget.max_read_bytes:
                    raise InvestigationBudgetExceeded(
                        "response exceeds remaining read budget; narrow fields/limit"
                    )
                state.evidence.append(evidence)
                receipt = OperationReceipt(
                    operation_id=operation_id,
                    kind="read",
                    request=cast(
                        dict[str, JsonValue], operation.model_dump(mode="json")
                    ),
                    status="succeeded",
                    seconds=time.monotonic() - started,
                    evidence_id=evidence.evidence_id,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                if isinstance(exc, InvestigationBudgetExceeded):
                    budget_error = exc
                receipt = OperationReceipt(
                    operation_id=operation_id,
                    kind="read",
                    request=cast(
                        dict[str, JsonValue], operation.model_dump(mode="json")
                    ),
                    status="failed",
                    seconds=time.monotonic() - started,
                    error=str(exc),
                )
            state.operations.append(receipt)
            self._save(state)
            if budget_error is not None:
                raise budget_error

    def _evidence_page(
        self, state: InvestigationState, operation: ReadOperation
    ) -> Evidence:
        parts = operation.path.split("/")
        if len(parts) != 4 or parts[3] != "page":
            raise ValueError("saved evidence uses /evidence/{id}/page")
        original = next(
            (item for item in state.evidence if item.evidence_id == parts[2]), None
        )
        if original is None:
            raise ValueError("evidence does not belong to this investigation")
        args = {item.name: item.value for item in operation.arguments}
        if len(args) != len(operation.arguments) or set(args) - {
            "offset",
            "max_characters",
            "pointer",
        }:
            raise ValueError("evidence page accepts offset, max_characters and pointer")
        offset, limit = (
            int(args.get("offset", "0")),
            int(args.get("max_characters", "6000")),
        )
        if offset < 0 or not 1 <= limit <= 12000:
            raise ValueError("invalid saved evidence page range")
        selected = original.content
        pointer = args.get("pointer", "")
        if pointer:
            if not pointer.startswith("/"):
                raise ValueError("evidence pointer must follow RFC6901")
            try:
                for part in pointer[1:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    if isinstance(selected, list):
                        if not key.isdigit() or str(int(key)) != key:
                            raise ValueError("array pointer needs a canonical index")
                        selected = selected[int(key)]
                    elif isinstance(selected, dict):
                        selected = selected[key]
                    else:
                        raise ValueError("evidence pointer traverses a scalar")
            except (KeyError, IndexError) as exc:
                raise ValueError(
                    "evidence pointer does not exist in saved data"
                ) from exc
        text = json.dumps(selected, ensure_ascii=False)
        end = min(len(text), offset + limit)
        return original.model_copy(
            update={
                "evidence_id": "ev-" + uuid.uuid4().hex,
                "content": {
                    "original_evidence_id": original.evidence_id,
                    "pointer": pointer,
                    "text": text[offset:end],
                    "offset": offset,
                    "next_offset": end if end < len(text) else None,
                    "total_characters": len(text),
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "complete": offset == 0 and end == len(text),
                },
                "status": EvidenceStatus.PARTIAL,
                "reason": "page of saved evidence; original coverage is authoritative",
            }
        )

    def retrieve_evidence(
        self,
        state: InvestigationState,
        *,
        evidence_id: str,
        offset: int,
        max_characters: int,
    ) -> dict[str, JsonValue]:
        """Host expansion shares the call, byte and time limits of model actions."""
        started = time.monotonic()
        self._budget(state, reads=1)
        if offset < 0 or not 1 <= max_characters <= 12000:
            raise ValueError("invalid saved evidence page range")
        evidence = next(
            (item for item in state.evidence if item.evidence_id == evidence_id), None
        )
        if evidence is None:
            raise ValueError("evidence does not belong to this investigation")
        payload = evidence.model_dump_json()
        end = min(len(payload), offset + max_characters)
        page: dict[str, JsonValue] = {
            "evidence_id": evidence_id,
            "offset": offset,
            "text": payload[offset:end],
            "next_offset": end if end < len(payload) else None,
            "total_characters": len(payload),
            "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        }
        size = len(json.dumps(page, ensure_ascii=False).encode())
        if state.read_bytes_used + size > state.budget.max_read_bytes:
            raise InvestigationBudgetExceeded("saved evidence page exceeds read budget")
        state.tool_calls_used += 1
        state.read_bytes_used += size
        seconds = time.monotonic() - started
        state.active_seconds += seconds
        state.operations.append(
            OperationReceipt(
                operation_id="op-" + uuid.uuid4().hex,
                kind="evidence_page",
                request={
                    "evidence_id": evidence_id,
                    "offset": offset,
                    "max_characters": max_characters,
                },
                status="succeeded",
                seconds=seconds,
                evidence_id=evidence_id,
            )
        )
        self._save(state)
        return page

    def _submit_planned(self, state: InvestigationState, index: int) -> None:
        receipt = state.operations[index]
        request = AnalysisRequest.model_validate(receipt.request)
        started = time.monotonic()
        ticket = self.analysis.submit(request, state.scopes)
        if ticket.run_id not in {t.run_id for t in state.pending_analyses}:
            state.pending_analyses.append(ticket)
        state.operations[index] = receipt.model_copy(
            update={
                "status": "submitted",
                "run_id": ticket.run_id,
                "seconds": time.monotonic() - started,
            }
        )
        self._save(state)

    def poll(self, state: InvestigationState) -> InvestigationState:
        if state.status in (
            InvestigationStatus.ANSWERED,
            InvestigationStatus.STOPPED,
            InvestigationStatus.FAILED,
        ):
            return state
        started = time.monotonic()
        self.analysis.set_timeout(self._remaining(state, started))
        for index, receipt in enumerate(state.operations):
            if receipt.kind == "analyze" and receipt.status == "planned":
                self._submit_planned(state, index)
        waiting = False
        for index, ticket in enumerate(state.pending_analyses):
            if ticket.status in (
                "failed",
                "cancelled",
                "timed_out",
                "lost",
                "imported",
            ):
                continue
            self._budget(state, reads=1)
            state.tool_calls_used += 1
            updated, scope = self.analysis.poll(ticket)
            state.operations.append(
                OperationReceipt(
                    operation_id="poll-" + uuid.uuid4().hex,
                    kind="poll",
                    request={"run_id": ticket.run_id},
                    status=updated.status,
                    seconds=time.monotonic() - started,
                    run_id=ticket.run_id,
                )
            )
            if (
                updated.failure_evidence is not None
                and updated.failure_evidence.evidence_id
                not in {evidence.evidence_id for evidence in state.evidence}
            ):
                state.evidence.append(updated.failure_evidence)
                state.read_bytes_used += len(
                    updated.failure_evidence.model_dump_json().encode()
                )
            if scope is not None:
                if scope.snapshot_id not in {s.snapshot_id for s in state.scopes}:
                    state.scopes.append(scope)
                updated = updated.model_copy(update={"status": "imported"})
            waiting |= updated.status not in (
                "failed",
                "cancelled",
                "timed_out",
                "lost",
                "imported",
            )
            state.pending_analyses[index] = updated
        state.status = (
            InvestigationStatus.WAITING if waiting else InvestigationStatus.ACTIVE
        )
        self._save(state)
        return state

    def _validate_answer(
        self, state: InvestigationState, answer: InvestigationAnswer
    ) -> None:
        known = {e.evidence_id: e for e in state.evidence}
        for claim in answer.claims:
            if set(claim.evidence_ids) - set(known):
                raise InvestigationPolicyError("answer cites unknown evidence")
            if (
                claim.kind in ("fact", "comparison", "causal")
                and not claim.evidence_ids
            ):
                raise InvestigationPolicyError(
                    "factual or causal claim needs retrieved evidence"
                )
            refs = [known[key] for key in claim.evidence_ids]
            if claim.kind in ("fact", "comparison", "causal") and any(
                ref.status in (EvidenceStatus.INSUFFICIENT, EvidenceStatus.CONFLICTING)
                for ref in refs
            ):
                raise InvestigationPolicyError(
                    "unavailable or conflicting data cannot support a definite fact"
                )
            if claim.kind == "causal" and claim.certainty in ("observed", "supported"):
                if len({ref.scope.snapshot_id for ref in refs}) < 2:
                    raise InvestigationPolicyError(
                        "causal comparison needs evidence from both fixed experiments"
                    )
                if not any(
                    ref.level is not None and ref.level.value == "direct_excerpt"
                    for ref in refs
                ):
                    raise InvestigationPolicyError(
                        "causal conclusion needs a retrieved original source excerpt"
                    )
        if not answer.claims and answer.outcome == "answered":
            raise InvestigationPolicyError(
                "an answered investigation needs scoped claims"
            )

    def run(
        self, investigation_id: str, *, max_iterations: int | None = None
    ) -> InvestigationState:
        if self.model is None:
            raise InvestigationPolicyError(
                "no model configured; use context and explicit apply operations"
            )
        state = self.store.load(investigation_id)
        if state.status == InvestigationStatus.PAUSED:
            try:
                self._budget(state)
            except InvestigationBudgetExceeded as exc:
                return self.stop_for_budget(state, exc)
            self._resume_paused(state)
        iterations = 0
        while state.status not in (
            InvestigationStatus.ANSWERED,
            InvestigationStatus.STOPPED,
            InvestigationStatus.FAILED,
        ):
            if max_iterations is not None and iterations >= max_iterations:
                break
            started = time.monotonic()
            try:
                self._budget(state)
                if state.pending_analyses:
                    poll_started = time.monotonic()
                    self.poll(state)
                    state.active_seconds += time.monotonic() - poll_started
                    self._save(state)
                    if state.status == InvestigationStatus.WAITING:
                        waiting_started = time.monotonic()
                        time.sleep(
                            min(
                                1.0,
                                max(0, state.budget.max_seconds - state.active_seconds),
                            )
                        )
                        state.active_seconds += time.monotonic() - waiting_started
                        self._save(state)
                        continue
                self._budget(state)
                self.model.set_timeout(
                    min(120, state.budget.max_seconds - state.active_seconds)
                )
                model_started = time.monotonic()
                try:
                    decision = self.model.complete(
                        self.context(state), InvestigationDecision
                    )
                finally:
                    state.active_seconds += time.monotonic() - model_started
                    self._save(state)
                self.apply(state, decision)
                iterations += 1
                if state.status == InvestigationStatus.PAUSED:
                    break
            except LLMContractError as exc:
                state.status = InvestigationStatus.PAUSED
                state.stop_reason = "model call failed; raw trace retained: " + str(exc)
                state.steps_used += 1
                state.operations.append(
                    OperationReceipt(
                        operation_id="model-" + uuid.uuid4().hex,
                        kind="model",
                        request={},
                        status="failed",
                        seconds=time.monotonic() - started,
                        error=str(exc),
                    )
                )
                self._save(state)
                break
            except InvestigationPolicyError as exc:
                if isinstance(exc, InvestigationBudgetExceeded):
                    self.stop_for_budget(state, exc)
                    break
                state.steps_used += 1
                state.operations.append(
                    OperationReceipt(
                        operation_id="rejected-" + uuid.uuid4().hex,
                        kind="proposal",
                        request={},
                        status="rejected",
                        seconds=time.monotonic() - started,
                        error=str(exc),
                    )
                )
                self._save(state)
                iterations += 1
            except (OSError, RuntimeError) as exc:
                state.status = InvestigationStatus.PAUSED
                state.stop_reason = "operation failed; resume retained state: " + str(
                    exc
                )
                self._save(state)
                break
        return state

    def _cancel_outstanding(self, state: InvestigationState) -> None:
        """Cancel analyses belonging to this stopped investigation."""
        for index, ticket in enumerate(state.pending_analyses):
            if ticket.status in (
                "imported",
                "failed",
                "cancelled",
                "timed_out",
                "lost",
            ):
                continue
            started = time.monotonic()
            self.analysis.set_timeout(5)
            error = None
            try:
                state.pending_analyses[index] = self.analysis.cancel(ticket)
                status = state.pending_analyses[index].status
            except (OSError, ValueError, RuntimeError) as exc:
                error, status = str(exc), "unknown"
            state.operations.append(
                OperationReceipt(
                    operation_id="cancel-" + uuid.uuid4().hex,
                    kind="cancel",
                    request={"run_id": ticket.run_id},
                    status=status,
                    run_id=ticket.run_id,
                    seconds=time.monotonic() - started,
                    error=error,
                )
            )

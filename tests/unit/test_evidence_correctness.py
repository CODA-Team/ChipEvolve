from datetime import UTC, datetime

from query_agent.application.answerability import AnswerabilityEvaluator
from query_agent.domain.capability import Capability
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
)
from query_agent.domain.query import (
    EvidenceRequirement,
    QueryContext,
    QueryIntent,
    QueryPlan,
    QuerySource,
)


def item(
    *,
    run_id: str,
    stage: str,
    value: float,
    status: EvidenceStatus = EvidenceStatus.SUFFICIENT,
) -> Evidence:
    return Evidence(
        evidence_id=f"{run_id}-{stage}-{value}",
        source_kind=EvidenceSourceKind.EXECUTION_RUN,
        content={"value": value},
        scope=EvidenceScope(design_id="gcd", run_id=run_id, stage=stage),
        locator=EvidenceLocator(uri=f"execution://{run_id}/{stage}/{value}"),
        provenance=EvidenceProvenance(
            provider="fixture",
            source_hash="a" * 64,
            retrieved_at=datetime(2026, 9, 22, tzinfo=UTC),
        ),
        status=status,
        fact_key="metric:WNS",
    )


def plan(context: QueryContext, *, current: bool = False) -> QueryPlan:
    return QueryPlan(
        intent=QueryIntent.METRIC_QUERY,
        evidence_requirements=(
            EvidenceRequirement(
                description="routing WNS",
                required_capabilities=(Capability.EXPLICIT_METRIC,),
                scope=EvidenceScope(
                    design_id=context.design_id,
                    run_id=context.run_id,
                    stage=context.stage,
                ),
                fact_key="metric:WNS",
                requires_current=current,
            ),
        ),
        required_capabilities=(Capability.EXPLICIT_METRIC,),
    )


def context(run_id: str = "run_02", stage: str = "routing") -> QueryContext:
    return QueryContext(
        design_id="gcd",
        run_id=run_id,
        stage=stage,
        source=QuerySource.MANAGED_RUN,
    )


def test_wrong_run_does_not_satisfy_exact_scope() -> None:
    decision = AnswerabilityEvaluator().evaluate(
        plan(context()),
        [item(run_id="run_01", stage="routing", value=-0.20)],
        frozenset({Capability.EXPLICIT_METRIC}),
    )
    assert decision.missing_evidence
    assert not decision.sufficient


def test_wrong_stage_does_not_satisfy_exact_scope() -> None:
    decision = AnswerabilityEvaluator().evaluate(
        plan(context()),
        [item(run_id="run_02", stage="placement", value=-0.20)],
        frozenset({Capability.EXPLICIT_METRIC}),
    )
    assert decision.missing_evidence


def test_correct_scope_is_sufficient() -> None:
    decision = AnswerabilityEvaluator().evaluate(
        plan(context()),
        [item(run_id="run_02", stage="routing", value=-0.20)],
        frozenset({Capability.EXPLICIT_METRIC}),
    )
    assert decision.sufficient
    assert decision.evidence_status is EvidenceStatus.SUFFICIENT


def test_conflicting_same_scope_evidence_is_retained() -> None:
    decision = AnswerabilityEvaluator().evaluate(
        plan(context()),
        [
            item(run_id="run_02", stage="routing", value=-0.20),
            item(run_id="run_02", stage="routing", value=-0.35),
        ],
        frozenset({Capability.EXPLICIT_METRIC}),
    )
    assert decision.evidence_status is EvidenceStatus.CONFLICTING
    assert len(decision.conflicting_evidence) == 2
    assert not decision.sufficient


def test_stale_or_partial_evidence_is_not_current_sufficient() -> None:
    decision = AnswerabilityEvaluator().evaluate(
        plan(context(), current=True),
        [
            item(
                run_id="run_02",
                stage="routing",
                value=-0.20,
                status=EvidenceStatus.PARTIAL,
            )
        ],
        frozenset({Capability.EXPLICIT_METRIC}),
    )
    assert decision.evidence_status is EvidenceStatus.PARTIAL
    assert decision.stale_evidence
    assert decision.missing_evidence

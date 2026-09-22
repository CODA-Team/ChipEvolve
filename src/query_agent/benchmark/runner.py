"""Deterministic evaluator for structured Phase I benchmark cases."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from query_agent.application.answerability import AnswerabilityEvaluator
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.domain.capability import Capability
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
    JsonValue,
)
from query_agent.domain.query import (
    QueryContext,
    QueryIntent,
    QueryRequest,
    QueryStatus,
)


class BenchmarkFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_key: str
    value: JsonValue


class BenchmarkEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    source_kind: EvidenceSourceKind
    content: JsonValue
    scope: EvidenceScope
    locator: str
    provider: str = "benchmark-fixture"
    source_hash: str | None = None
    status: EvidenceStatus = EvidenceStatus.SUFFICIENT
    fact_key: str | None = None
    reason: str | None = None

    def to_domain(self) -> Evidence:
        return Evidence(
            evidence_id=self.evidence_id,
            source_kind=self.source_kind,
            content=self.content,
            scope=self.scope,
            locator=EvidenceLocator(uri=self.locator),
            provenance=EvidenceProvenance(
                provider=self.provider,
                source_hash=self.source_hash,
                retrieved_at=datetime(2026, 9, 22, tzinfo=UTC),
            ),
            status=self.status,
            fact_key=self.fact_key,
            reason=self.reason,
        )


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    context: QueryContext
    expected_intent: QueryIntent
    expected_status: QueryStatus
    expected_evidence_scope: EvidenceScope | None = None
    expected_key_facts: tuple[BenchmarkFact, ...] = ()
    expected_missing_capabilities: tuple[Capability, ...] = ()
    available_capabilities: tuple[Capability, ...] = ()
    evidence: tuple[BenchmarkEvidence, ...] = ()
    notes: str = ""


class BenchmarkDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    cases: tuple[BenchmarkCase, ...] = Field(min_length=30)


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    expected_intent: QueryIntent
    actual_intent: QueryIntent
    expected_status: QueryStatus
    actual_status: QueryStatus
    failure_reasons: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_scopes: tuple[EvidenceScope, ...] = ()


class BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    total: int
    passed: int
    failed: int
    metrics: dict[str, float]
    cases: tuple[CaseResult, ...]

    def to_markdown(self) -> str:
        lines = [
            f"# {self.name}",
            "",
            f"- Total cases: {self.total}",
            f"- Passed: {self.passed}",
            f"- Failed: {self.failed}",
            "",
            "## Metrics",
            "",
            "| Metric | Score |",
            "| --- | ---: |",
        ]
        lines.extend(
            f"| {name} | {value:.3f} |" for name, value in self.metrics.items()
        )
        lines.extend(
            ["", "## Cases", "", "| Case | Result | Reason |", "| --- | --- | --- |"]
        )
        for case in self.cases:
            reason = "; ".join(case.failure_reasons) or "-"
            lines.append(
                f"| {case.case_id} | {'PASS' if case.passed else 'FAIL'} | {reason} |"
            )
        return "\n".join(lines) + "\n"


class BenchmarkRunner:
    """Run cases without network, model calls, or filesystem providers."""

    def __init__(self) -> None:
        self._parser = KeywordIntentParser()
        self._planner = QueryPlanner()
        self._evaluator = AnswerabilityEvaluator()

    def run(self, benchmark_dir: Path) -> BenchmarkReport:
        definition_path = benchmark_dir / "benchmark.json"
        definition = BenchmarkDefinition.model_validate_json(
            definition_path.read_text(encoding="utf-8")
        )
        results = tuple(self._evaluate_case(case) for case in definition.cases)
        passed = sum(1 for result in results if result.passed)
        report = BenchmarkReport(
            name=definition.name,
            version=definition.version,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            metrics=self._metrics(results),
            cases=results,
        )
        (benchmark_dir / "benchmark-results.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        (benchmark_dir / "benchmark-results.md").write_text(
            report.to_markdown(), encoding="utf-8"
        )
        return report

    def _evaluate_case(self, case: BenchmarkCase) -> CaseResult:
        request = QueryRequest(query=case.question, context=case.context)
        intent = self._parser.parse(request)
        plan = self._planner.plan(request, intent)
        evidence = tuple(item.to_domain() for item in case.evidence)
        decision = self._evaluator.evaluate(
            plan, evidence, frozenset(case.available_capabilities)
        )
        actual_status = (
            QueryStatus.UNSUPPORTED
            if intent is QueryIntent.UNKNOWN
            else QueryStatus.ANSWERED
            if decision.sufficient
            else QueryStatus.NEEDS_MORE_DATA
        )
        reasons = list(self._basic_failures(case, intent, actual_status))
        if case.expected_evidence_scope is not None:
            has_expected_scope = any(
                item.scope.matches(case.expected_evidence_scope) for item in evidence
            )
            if case.expected_status is QueryStatus.ANSWERED and not has_expected_scope:
                reasons.append(
                    "expected evidence scope "
                    f"{case.expected_evidence_scope.model_dump()} not present; "
                    f"actual scopes={[item.scope.model_dump() for item in evidence]}"
                )
        for fact in case.expected_key_facts:
            if not any(
                item.fact_key == fact.fact_key and _contains(item.content, fact.value)
                for item in evidence
            ):
                reasons.append(f"missing expected fact {fact.fact_key}={fact.value}")
        if set(decision.missing_capabilities) != set(
            case.expected_missing_capabilities
        ):
            reasons.append(
                "missing capabilities expected="
                f"{sorted(item.value for item in case.expected_missing_capabilities)} "
                "actual="
                f"{sorted(item.value for item in decision.missing_capabilities)}"
            )
        if not all(item.provenance.provider and item.locator.uri for item in evidence):
            reasons.append("evidence provenance coverage is incomplete")
        return CaseResult(
            case_id=case.id,
            passed=not reasons,
            expected_intent=case.expected_intent,
            actual_intent=intent,
            expected_status=case.expected_status,
            actual_status=actual_status,
            failure_reasons=tuple(reasons),
            evidence_ids=tuple(item.evidence_id for item in evidence),
            evidence_scopes=tuple(item.scope for item in evidence),
        )

    @staticmethod
    def _basic_failures(
        case: BenchmarkCase, intent: QueryIntent, status: QueryStatus
    ) -> Iterable[str]:
        if intent is not case.expected_intent:
            yield f"expected intent={case.expected_intent.value}, actual={intent.value}"
        if status is not case.expected_status:
            yield f"expected status={case.expected_status.value}, actual={status.value}"

    @staticmethod
    def _metrics(results: Iterable[CaseResult]) -> dict[str, float]:
        items = tuple(results)
        total = len(items) or 1
        return {
            "intent_accuracy": sum(
                item.actual_intent is item.expected_intent for item in items
            )
            / total,
            "answerability_accuracy": sum(
                item.actual_status is item.expected_status for item in items
            )
            / total,
            "evidence_scope_accuracy": sum(
                not any(
                    "expected evidence scope" in reason
                    for reason in item.failure_reasons
                )
                for item in items
            )
            / total,
            "provenance_coverage": sum(
                not any(
                    "provenance coverage" in reason for reason in item.failure_reasons
                )
                for item in items
            )
            / total,
            "unsupported_query_accuracy": sum(
                (item.actual_status is QueryStatus.UNSUPPORTED)
                == (item.expected_status is QueryStatus.UNSUPPORTED)
                for item in items
            )
            / total,
        }


def _contains(content: JsonValue, expected: JsonValue) -> bool:
    if content == expected:
        return True
    if isinstance(content, str) and isinstance(expected, str):
        return expected in content
    if isinstance(content, list):
        return any(_contains(item, expected) for item in content)
    if isinstance(content, dict):
        return any(_contains(item, expected) for item in content.values())
    return False

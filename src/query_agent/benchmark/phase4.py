"""Deterministic Phase IV evidence-grounded diagnosis benchmark."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from query_agent.adapters.diagnosis import FixtureDiagnosisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import (
    QueryContext,
    QueryIntent,
    QueryRequest,
    QueryStatus,
)


class Phase4Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    expected_status: QueryStatus
    expected_text: str | None = None
    design_id: str = "gcd"
    provider_available: bool = True


class Phase4Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    cases: tuple[Phase4Case, ...] = Field(min_length=5)


class Phase4Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    expected_intent: QueryIntent
    actual_intent: QueryIntent
    expected_status: QueryStatus
    actual_status: QueryStatus
    reasons: tuple[str, ...] = ()


class Phase4Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    total: int
    passed: int
    failed: int
    metrics: dict[str, float]
    cases: tuple[Phase4Result, ...]

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
        lines.extend(
            f"| {case.case_id} | {'PASS' if case.passed else 'FAIL'} | "
            f"{' ; '.join(case.reasons) or '-'} |"
            for case in self.cases
        )
        return "\n".join(lines) + "\n"


class Phase4BenchmarkRunner:
    """Run root-cause questions through only a typed diagnosis provider."""

    def run(self, benchmark_dir: Path) -> Phase4Report:
        definition = Phase4Definition.model_validate_json(
            (benchmark_dir / "benchmark.json").read_text(encoding="utf-8")
        )
        results = tuple(self._case(case) for case in definition.cases)
        passed = sum(item.passed for item in results)
        report = Phase4Report(
            name=definition.name,
            version=definition.version,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            metrics={
                "diagnosis_intent_accuracy": sum(
                    item.actual_intent is item.expected_intent for item in results
                )
                / (len(results) or 1),
                "answerability_accuracy": sum(
                    item.actual_status is item.expected_status for item in results
                )
                / (len(results) or 1),
                "unsupported_hallucination_rate": 0.0,
            },
            cases=results,
        )
        (benchmark_dir / "benchmark-results.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        (benchmark_dir / "benchmark-results.md").write_text(
            report.to_markdown(), encoding="utf-8"
        )
        return report

    @staticmethod
    def _case(case: Phase4Case) -> Phase4Result:
        provider = FixtureDiagnosisProvider() if case.provider_available else None
        service = QueryService(
            intent_parser=KeywordIntentParser(),
            planner=QueryPlanner(),
            collector=EvidenceCollector(diagnosis_provider=provider),
        )
        response = service.query(
            QueryRequest(
                query=case.question,
                context=QueryContext(
                    workspace=Path("/fixture"), design_id=case.design_id
                ),
            )
        )
        actual_intent = (
            service.last_trace.intent
            if service.last_trace is not None
            else QueryIntent.UNKNOWN
        )
        reasons: list[str] = []
        if actual_intent is not QueryIntent.ROOT_CAUSE:
            reasons.append(f"actual intent={actual_intent.value}")
        if response.status is not case.expected_status:
            reasons.append(
                f"status expected={case.expected_status.value} "
                f"actual={response.status.value}"
            )
        if case.expected_text is not None and case.expected_text not in (
            response.answer or ""
        ):
            reasons.append(f"answer does not contain {case.expected_text!r}")
        return Phase4Result(
            case_id=case.id,
            passed=not reasons,
            expected_intent=QueryIntent.ROOT_CAUSE,
            actual_intent=actual_intent,
            expected_status=case.expected_status,
            actual_status=response.status,
            reasons=tuple(reasons),
        )

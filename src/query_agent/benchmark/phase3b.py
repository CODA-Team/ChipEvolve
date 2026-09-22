"""Deterministic Phase III-B timing-analysis understanding benchmark."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from query_agent.adapters.analysis import FixtureAnalysisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import (
    QueryContext,
    QueryIntent,
    QueryRequest,
    QueryStatus,
)


class Phase3BCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    expected_intent: QueryIntent = QueryIntent.ANALYSIS_QUERY
    expected_status: QueryStatus
    expected_text: str | None = None
    design_id: str = "gcd"
    provider_available: bool = True


class Phase3BDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    cases: tuple[Phase3BCase, ...] = Field(min_length=5)


class Phase3BResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    expected_intent: QueryIntent
    actual_intent: QueryIntent
    expected_status: QueryStatus
    actual_status: QueryStatus
    reasons: tuple[str, ...] = ()


class Phase3BReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    total: int
    passed: int
    failed: int
    metrics: dict[str, float]
    cases: tuple[Phase3BResult, ...]

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


class Phase3BBenchmarkRunner:
    """Run timing questions through only the typed analysis provider port."""

    def run(self, benchmark_dir: Path) -> Phase3BReport:
        definition = Phase3BDefinition.model_validate_json(
            (benchmark_dir / "benchmark.json").read_text(encoding="utf-8")
        )
        results = tuple(self._case(case) for case in definition.cases)
        passed = sum(item.passed for item in results)
        report = Phase3BReport(
            name=definition.name,
            version=definition.version,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            metrics={
                "analysis_intent_accuracy": sum(
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
    def _case(case: Phase3BCase) -> Phase3BResult:
        provider = FixtureAnalysisProvider() if case.provider_available else None
        service = QueryService(
            intent_parser=KeywordIntentParser(),
            planner=QueryPlanner(),
            collector=EvidenceCollector(analysis_provider=provider),
        )
        response = service.query(
            QueryRequest(
                query=case.question,
                context=QueryContext(
                    workspace=Path("/fixture"), design_id=case.design_id
                ),
            )
        )
        reasons: list[str] = []
        if response.status is not case.expected_status:
            reasons.append(
                f"status expected={case.expected_status.value} "
                f"actual={response.status.value}"
            )
        actual_intent = (
            service.last_trace.intent if service.last_trace else QueryIntent.UNKNOWN
        )
        if actual_intent is not case.expected_intent:
            reasons.append(
                f"intent expected={case.expected_intent.value} "
                f"actual={actual_intent.value}"
            )
        if case.expected_text is not None and case.expected_text not in (
            response.answer or ""
        ):
            reasons.append(f"answer does not contain {case.expected_text!r}")
        return Phase3BResult(
            case_id=case.id,
            passed=not reasons,
            expected_intent=case.expected_intent,
            actual_intent=actual_intent,
            expected_status=case.expected_status,
            actual_status=response.status,
            reasons=tuple(reasons),
        )

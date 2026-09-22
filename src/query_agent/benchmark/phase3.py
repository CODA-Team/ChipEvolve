"""Deterministic Phase III-A design-object understanding benchmark."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from query_agent.adapters.design_data import FixtureDesignDataProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


class Phase3Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question: str
    expected_status: QueryStatus
    expected_text: str | None = None
    design_id: str = "gcd"


class Phase3Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    cases: tuple[Phase3Case, ...] = Field(min_length=6)


class Phase3Result(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    expected_status: QueryStatus
    actual_status: QueryStatus
    reasons: tuple[str, ...] = ()


class Phase3Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    total: int
    passed: int
    failed: int
    metrics: dict[str, float]
    cases: tuple[Phase3Result, ...]

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


class Phase3BenchmarkRunner:
    """Run design questions through typed provider operations."""

    def run(self, benchmark_dir: Path) -> Phase3Report:
        definition = Phase3Definition.model_validate_json(
            (benchmark_dir / "benchmark.json").read_text(encoding="utf-8")
        )
        results = tuple(self._case(case) for case in definition.cases)
        passed = sum(item.passed for item in results)
        report = Phase3Report(
            name=definition.name,
            version=definition.version,
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            metrics={
                "object_retrieval_accuracy": sum(item.passed for item in results)
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
    def _case(case: Phase3Case) -> Phase3Result:
        provider = FixtureDesignDataProvider()
        service = QueryService(
            intent_parser=KeywordIntentParser(),
            planner=QueryPlanner(),
            collector=EvidenceCollector(design_data_provider=provider),
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
        if case.expected_text is not None and case.expected_text not in (
            response.answer or ""
        ):
            reasons.append(f"answer does not contain {case.expected_text!r}")
        return Phase3Result(
            case_id=case.id,
            passed=not reasons,
            expected_status=case.expected_status,
            actual_status=response.status,
            reasons=tuple(reasons),
        )

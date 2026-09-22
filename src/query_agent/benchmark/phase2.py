"""Externally meaningful deterministic Phase-II context benchmark."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.capability import Capability
from query_agent.domain.experiment import (
    ArtifactRef,
    ExperimentRun,
    ExperimentStage,
    ExperimentStatus,
    MetricObservation,
    ProvenanceRef,
    StageStatus,
)
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)


class Phase2Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    scenario: str
    question: str
    run_ids: tuple[str, ...] = ()
    stage: str = "routing"
    expected_status: QueryStatus
    expected_selection: str | None = None
    expects_conflict: bool = False


class Phase2Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    cases: tuple[Phase2Case, ...] = Field(min_length=6)


class Phase2CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    passed: bool
    expected_status: QueryStatus
    actual_status: QueryStatus
    selected_run_id: str | None = None
    conflict_count: int = 0
    reasons: tuple[str, ...] = ()


class Phase2Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    total: int
    passed: int
    failed: int
    metrics: dict[str, float]
    cases: tuple[Phase2CaseResult, ...]

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


class Phase2BenchmarkRunner:
    """Run context cases through QueryService and the fake provider port."""

    def run(self, benchmark_dir: Path) -> Phase2Report:
        definition = Phase2Definition.model_validate_json(
            (benchmark_dir / "benchmark.json").read_text(encoding="utf-8")
        )
        cases = tuple(self._case(case) for case in definition.cases)
        passed = sum(item.passed for item in cases)
        report = Phase2Report(
            name=definition.name,
            version=definition.version,
            total=len(cases),
            passed=passed,
            failed=len(cases) - passed,
            metrics=self._metrics(cases),
            cases=cases,
        )
        (benchmark_dir / "benchmark-results.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8"
        )
        (benchmark_dir / "benchmark-results.md").write_text(
            report.to_markdown(), encoding="utf-8"
        )
        return report

    def _case(self, case: Phase2Case) -> Phase2CaseResult:
        provider = BenchmarkExperimentProvider(case.scenario)
        service = QueryService(
            intent_parser=KeywordIntentParser(),
            planner=QueryPlanner(),
            collector=EvidenceCollector(experiment_context_provider=provider),
            experiment_context_provider=provider,
        )
        response = service.query(
            QueryRequest(
                query=case.question,
                context=QueryContext(
                    design_id="gcd",
                    run_ids=case.run_ids,
                    stage=case.stage,
                    source=QuerySource.MANAGED_RUN,
                ),
            )
        )
        selection = response.context_selection
        reasons: list[str] = []
        if response.status is not case.expected_status:
            reasons.append(
                f"status expected={case.expected_status.value} "
                f"actual={response.status.value}"
            )
        selected = selection.selected_run_id if selection else None
        if selected != case.expected_selection:
            reasons.append(
                f"selection expected={case.expected_selection!r} actual={selected!r}"
            )
        if bool(response.conflicts) != case.expects_conflict:
            reasons.append(
                "conflict expected="
                f"{case.expects_conflict} actual={bool(response.conflicts)}"
            )
        if case.id == "comparison_aligned" and "difference=" not in (
            response.answer or ""
        ):
            reasons.append(
                "aligned comparison did not report a deterministic difference"
            )
        return Phase2CaseResult(
            case_id=case.id,
            passed=not reasons,
            expected_status=case.expected_status,
            actual_status=response.status,
            selected_run_id=selected,
            conflict_count=len(response.conflicts),
            reasons=tuple(reasons),
        )

    @staticmethod
    def _metrics(results: Sequence[Phase2CaseResult]) -> dict[str, float]:
        total = len(results) or 1
        return {
            "context_selection_accuracy": sum(
                not any("selection expected" in reason for reason in item.reasons)
                for item in results
            )
            / total,
            "wrong_stage_rejection_rate": _scenario_score(results, "wrong_stage"),
            "stale_evidence_rejection_rate": _scenario_score(results, "stale"),
            "conflict_detection_rate": _conflict_score(results),
            "unsupported_hallucination_rate": sum(
                item.actual_status is QueryStatus.ANSWERED
                and item.expected_status is not QueryStatus.ANSWERED
                for item in results
            )
            / total,
            "answerability_accuracy": sum(item.passed for item in results) / total,
        }


def _scenario_score(results: Sequence[Phase2CaseResult], name: str) -> float:
    selected = tuple(item for item in results if name in item.case_id)
    return sum(item.passed for item in selected) / (len(selected) or 1)


def _conflict_score(results: Sequence[Phase2CaseResult]) -> float:
    """Score conflict detection on cases that explicitly contain a conflict."""

    selected = tuple(item for item in results if "conflicting" in item.case_id)
    return sum(item.conflict_count > 0 for item in selected) / (len(selected) or 1)


class BenchmarkExperimentProvider:
    """Small in-process fixture; it implements the same public provider port."""

    def __init__(self, scenario: str) -> None:
        when = datetime(2026, 9, 22, tzinfo=UTC)
        self._runs = (
            _run("run_001", ExperimentStatus.SUCCEEDED, when),
            _run("run_002", ExperimentStatus.FAILED, when.replace(hour=13)),
            _run("run_003", ExperimentStatus.RUNNING, when.replace(hour=14)),
        )
        self._artifacts = (
            ArtifactRef(
                artifact_id="route-report",
                run_id="run_001",
                design_id="gcd",
                stage_key="routing",
                kind="timing_report",
                locator="reports/run_001/routing.rpt",
                source_hash="a" * 64,
                created_at=when,
            ),
        )
        if scenario == "wrong_stage":
            self._artifacts = (
                ArtifactRef(
                    artifact_id="place-report",
                    run_id="run_001",
                    design_id="gcd",
                    stage_key="placement",
                    kind="timing_report",
                    locator="reports/run_001/placement.rpt",
                    source_hash="b" * 64,
                    created_at=when,
                ),
            )
        metric = MetricObservation(
            metric_name="WNS",
            value=-0.2,
            unit="ns",
            run_id="run_001",
            design_id="gcd",
            stage_key="routing",
            artifact_id=(None if scenario == "missing_artifact" else "route-report"),
            source_hash=None if scenario == "missing_artifact" else "a" * 64,
            complete=scenario not in {"stale", "missing_artifact"},
            observed_at=when,
        )
        metrics = [metric]
        if scenario == "wrong_stage":
            metrics = [
                metric.model_copy(
                    update={
                        "value": -0.1,
                        "stage_key": "placement",
                        "artifact_id": "place-report",
                        "source_hash": "b" * 64,
                    }
                )
            ]
        if scenario == "conflict":
            metrics.append(
                metric.model_copy(update={"value": -0.35, "artifact_id": None})
            )
        if scenario == "comparison_mismatch":
            self._runs += (
                _run("run_004", ExperimentStatus.SUCCEEDED, when.replace(hour=15)),
            )
            metrics.append(
                metric.model_copy(
                    update={
                        "run_id": "run_004",
                        "unit": "ps",
                        "artifact_id": "route-report-004",
                    }
                )
            )
        if scenario == "comparison_aligned":
            self._runs += (
                _run("run_004", ExperimentStatus.SUCCEEDED, when.replace(hour=15)),
            )
            self._artifacts += (
                ArtifactRef(
                    artifact_id="route-report-004",
                    run_id="run_004",
                    design_id="gcd",
                    stage_key="routing",
                    kind="timing_report",
                    locator="reports/run_004/routing.rpt",
                    source_hash="c" * 64,
                    created_at=when.replace(hour=15),
                ),
            )
            metrics.append(
                metric.model_copy(
                    update={
                        "run_id": "run_004",
                        "value": -0.3,
                        "artifact_id": "route-report-004",
                        "source_hash": "c" * 64,
                    }
                )
            )
        self._metrics = tuple(metrics)

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.RUN_EVIDENCE,
                Capability.ARTIFACT_DISCOVERY,
                Capability.TEXT_SEARCH,
                Capability.EXPLICIT_METRIC,
            }
        )

    def list_runs(
        self,
        *,
        design_id: str | None = None,
        run_ids: Sequence[str] = (),
        limit: int = 100,
    ) -> Sequence[ExperimentRun]:
        return tuple(
            run
            for run in self._runs
            if (not design_id or run.design_id == design_id)
            and (not run_ids or run.run_id in run_ids)
        )[:limit]

    def get_run(self, run_id: str) -> ExperimentRun:
        return next(run for run in self._runs if run.run_id == run_id)

    def get_stage_state(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ExperimentStage]:
        stages = self.get_run(run_id).stages
        return tuple(
            stage for stage in stages if not stage_key or stage.stage_key == stage_key
        )

    def list_artifacts(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ArtifactRef]:
        return tuple(
            item
            for item in self._artifacts
            if item.run_id == run_id and (not stage_key or item.stage_key == stage_key)
        )

    def list_metrics(
        self,
        run_id: str,
        *,
        metric_name: str | None = None,
        stage_key: str | None = None,
    ) -> Sequence[MetricObservation]:
        return tuple(
            item
            for item in self._metrics
            if item.run_id == run_id
            and (not metric_name or item.metric_name.upper() == metric_name.upper())
            and (not stage_key or item.stage_key == stage_key)
        )

    def get_provenance(self, run_id: str) -> Sequence[ProvenanceRef]:
        return (
            ProvenanceRef(run_id=run_id, provider="benchmark", locator="fixture://run"),
        )


def _run(run_id: str, status: ExperimentStatus, created_at: datetime) -> ExperimentRun:
    stage_status = (
        StageStatus.SUCCEEDED
        if status is ExperimentStatus.SUCCEEDED
        else StageStatus.UNKNOWN
    )
    return ExperimentRun(
        run_id=run_id,
        design_id="gcd",
        status=status,
        created_at=created_at,
        completed_at=created_at if status.completed else None,
        stages=(
            ExperimentStage(stage_key="placement", status=stage_status),
            ExperimentStage(stage_key="routing", status=stage_status),
        ),
    )

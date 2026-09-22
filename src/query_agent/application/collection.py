"""Provider orchestration and typed evidence conversion."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from query_agent.domain.analysis import (
    TimingMetricObservation,
    TimingPathObservation,
)
from query_agent.domain.capability import Capability
from query_agent.domain.design import (
    DesignInstance,
    DesignNet,
    DesignObjectRef,
    DesignPin,
)
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
    JsonValue,
)
from query_agent.domain.experiment import (
    ResolvedExperimentContext,
    canonical_stage_key,
)
from query_agent.domain.query import (
    QueryContext,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QuerySource,
)
from query_agent.domain.trace import ProviderCall
from query_agent.ports.analysis import AnalysisProvider
from query_agent.ports.artifacts import ArtifactProvider
from query_agent.ports.design_data import DesignDataProvider
from query_agent.ports.experiment_context import ExperimentContextProvider
from query_agent.ports.knowledge import KnowledgeProvider
from query_agent.ports.run_evidence import RunEvidenceProvider

from .analysis_queries import AnalysisOperation, AnalysisQuestionParser
from .design_queries import DesignOperation, DesignQuestionParser
from .planning import context_scope, metric_name_from_query


class EvidenceCollector:
    """Call only injected providers and convert their output to Evidence."""

    def __init__(
        self,
        *,
        artifact_provider: ArtifactProvider | None = None,
        run_evidence_provider: RunEvidenceProvider | None = None,
        knowledge_provider: KnowledgeProvider | None = None,
        design_data_provider: DesignDataProvider | None = None,
        analysis_provider: AnalysisProvider | None = None,
        experiment_context_provider: ExperimentContextProvider | None = None,
    ) -> None:
        self.artifact_provider = artifact_provider
        self.run_evidence_provider = run_evidence_provider
        self.knowledge_provider = knowledge_provider
        self.design_data_provider = design_data_provider
        self.analysis_provider = analysis_provider
        self.experiment_context_provider = experiment_context_provider
        self._last_provider_calls: tuple[ProviderCall, ...] = ()

    @property
    def last_provider_calls(self) -> tuple[ProviderCall, ...]:
        return self._last_provider_calls

    @property
    def capabilities(self) -> frozenset[Capability]:
        capabilities: set[Capability] = set()
        if self.artifact_provider is not None:
            capabilities.update(self.artifact_provider.capabilities)
        if self.run_evidence_provider is not None:
            capabilities.update(self.run_evidence_provider.capabilities)
        if self.knowledge_provider is not None:
            capabilities.update(self.knowledge_provider.capabilities)
        if self.design_data_provider is not None:
            capabilities.update(self.design_data_provider.capabilities)
        if self.analysis_provider is not None:
            capabilities.update(self.analysis_provider.capabilities)
        if self.experiment_context_provider is not None:
            capabilities.update(self.experiment_context_provider.capabilities)
        return frozenset(capabilities)

    def available_capabilities(self, context: QueryContext) -> frozenset[Capability]:
        """Capabilities available through the context's authoritative source."""

        capabilities: set[Capability] = set()
        if (
            context.source is QuerySource.LOCAL_WORKSPACE
            and self.artifact_provider is not None
        ):
            capabilities.update(self.artifact_provider.capabilities)
        if (
            context.source is QuerySource.MANAGED_RUN
            and self.run_evidence_provider is not None
        ):
            capabilities.update(self.run_evidence_provider.capabilities)
        if self.knowledge_provider is not None:
            capabilities.update(self.knowledge_provider.capabilities)
        if self.design_data_provider is not None:
            capabilities.update(self.design_data_provider.capabilities)
        if self.analysis_provider is not None:
            capabilities.update(self.analysis_provider.capabilities)
        if self.experiment_context_provider is not None:
            capabilities.update(self.experiment_context_provider.capabilities)
        return frozenset(capabilities)

    def collect(
        self,
        plan: QueryPlan,
        request: QueryRequest,
        resolved_context: ResolvedExperimentContext | None = None,
    ) -> tuple[Evidence, ...]:
        context = request.context
        collected: list[Evidence] = []
        if context.source is QuerySource.MANAGED_RUN:
            if (
                resolved_context is not None
                and self.experiment_context_provider is not None
            ):
                collected.extend(
                    self._collect_experiment_context(plan, resolved_context)
                )
            else:
                collected.extend(self._collect_managed_run(plan, request))
        elif (
            Capability.ARTIFACT_DISCOVERY in plan.required_capabilities
            and self.artifact_provider is not None
        ):
            for artifact in self.artifact_provider.list_artifacts(context):
                collected.append(
                    self._evidence(
                        source_kind=EvidenceSourceKind.WORKSPACE_ARTIFACT,
                        content=artifact.model_dump(mode="json"),
                        locator=artifact.path,
                        context=context,
                    )
                )
        if (
            context.source is QuerySource.LOCAL_WORKSPACE
            and Capability.TEXT_SEARCH in plan.required_capabilities
            and self.artifact_provider is not None
        ):
            matches = self.artifact_provider.search_text(context, request.query)
            for match in matches:
                collected.append(
                    self._evidence(
                        source_kind=EvidenceSourceKind.WORKSPACE_ARTIFACT,
                        content={
                            "line": match.line,
                            "line_number": match.line_number,
                        },
                        locator=f"{match.path}#L{match.line_number}",
                        context=context,
                        fact_key=(
                            f"metric:{metric_name_from_query(request.query)}"
                            if plan.intent is QueryIntent.METRIC_QUERY
                            and metric_name_from_query(request.query) is not None
                            else None
                        ),
                    )
                )
        if (
            Capability.DOMAIN_KNOWLEDGE in plan.required_capabilities
            and self.knowledge_provider is not None
        ):
            collected.extend(self.knowledge_provider.search(request.query, context))
        if (
            Capability.DESIGN_OBJECT_QUERY in plan.required_capabilities
            or Capability.DESIGN_RELATION_QUERY in plan.required_capabilities
        ) and self.design_data_provider is not None:
            collected.extend(self._collect_design_data(request))
        if (
            Capability.SPECIALIZED_ANALYSIS in plan.required_capabilities
            and self.analysis_provider is not None
        ):
            collected.extend(self._collect_analysis_data(request, resolved_context))
        providers = sorted({item.provenance.provider for item in collected})
        self._last_provider_calls = tuple(
            ProviderCall(provider=provider, operation="collect")
            for provider in providers
        )
        return tuple(collected)

    def _collect_analysis_data(
        self,
        request: QueryRequest,
        resolved_context: ResolvedExperimentContext | None,
    ) -> tuple[Evidence, ...]:
        provider = self.analysis_provider
        question = AnalysisQuestionParser().parse(request.query)
        if provider is None or question is None:
            return ()
        context = request.context
        if resolved_context is not None:
            selected_run = resolved_context.selection.selected_run_id
            selected_stage = resolved_context.selection.selected_stage_key
            if selected_run is not None:
                context = context.model_copy(
                    update={
                        "run_id": selected_run,
                        "run_ids": (selected_run,),
                        "stage": selected_stage or context.stage,
                    }
                )
        if question.operation is AnalysisOperation.METRIC:
            items = provider.get_timing_metrics(
                context, metric_name=question.metric_name
            )
            return tuple(self._timing_metric_evidence(item) for item in items)
        items = provider.get_timing_paths(
            context, limit=question.limit, slack_below=question.slack_below
        )
        return tuple(self._timing_path_evidence(item) for item in items)

    @staticmethod
    def _timing_metric_evidence(item: TimingMetricObservation) -> Evidence:
        unit = f" {item.unit}" if item.unit else ""
        return Evidence(
            evidence_id=_analysis_evidence_id(item.provenance.locator, item.fact_key),
            source_kind=EvidenceSourceKind.SPECIALIZED_ANALYSIS,
            content={
                "answer": f"{item.metric_name}={item.value}{unit}",
                "metric": item.metric_name,
                "value": item.value,
                "unit": item.unit,
                "scope": item.scope.model_dump(mode="json"),
            },
            scope=EvidenceScope(
                design_id=item.scope.design_id,
                run_id=item.scope.run_id,
                stage=item.scope.stage,
            ),
            locator=EvidenceLocator(uri=item.provenance.locator),
            provenance=EvidenceProvenance(
                provider=item.provenance.provider,
                source_hash=item.provenance.source_hash,
                retrieved_at=item.provenance.observed_at,
            ),
            status=(
                EvidenceStatus.SUFFICIENT if item.complete else EvidenceStatus.PARTIAL
            ),
            fact_key=item.fact_key,
            reason=None if item.complete else "analysis observation is incomplete",
        )

    @staticmethod
    def _timing_path_evidence(item: TimingPathObservation) -> Evidence:
        answer = f"{item.startpoint} -> {item.endpoint}; slack={item.slack} {item.unit}"
        return Evidence(
            evidence_id=_analysis_evidence_id(item.provenance.locator, item.path_id),
            source_kind=EvidenceSourceKind.SPECIALIZED_ANALYSIS,
            content={
                "answer": answer,
                "path_id": item.path_id,
                "startpoint": item.startpoint,
                "endpoint": item.endpoint,
                "slack": item.slack,
                "unit": item.unit,
                "total_delay": item.total_delay,
                "logic_depth": item.logic_depth,
                "scope": item.scope.model_dump(mode="json"),
            },
            scope=EvidenceScope(
                design_id=item.scope.design_id,
                run_id=item.scope.run_id,
                stage=item.scope.stage,
            ),
            locator=EvidenceLocator(uri=item.provenance.locator),
            provenance=EvidenceProvenance(
                provider=item.provenance.provider,
                source_hash=item.provenance.source_hash,
                retrieved_at=item.provenance.observed_at,
            ),
            status=(
                EvidenceStatus.SUFFICIENT if item.complete else EvidenceStatus.PARTIAL
            ),
            fact_key=item.fact_key,
            reason=None if item.complete else "analysis observation is incomplete",
        )

    def _collect_design_data(self, request: QueryRequest) -> tuple[Evidence, ...]:
        provider = self.design_data_provider
        if provider is None:
            return ()
        question = DesignQuestionParser().parse(request.query)
        if question is None:
            return ()
        context = request.context
        evidence: list[Evidence] = []
        if question.operation is DesignOperation.INSTANCE:
            instance = provider.get_instance(context, question.name)
            if instance is not None:
                evidence.append(self._design_evidence(instance, context))
        elif question.operation is DesignOperation.NET:
            net = provider.get_net(context, question.name)
            if net is not None:
                evidence.append(self._design_evidence(net, context))
        elif question.operation is DesignOperation.PIN:
            pin = provider.get_pin(context, question.name)
            if pin is not None:
                evidence.append(self._design_evidence(pin, context))
        elif question.operation is DesignOperation.LOCATION:
            instance = provider.get_instance(context, question.name)
            if instance is not None:
                location = provider.get_location(context, instance.ref)
                if location is not None:
                    evidence.append(
                        self._design_evidence(
                            instance,
                            context,
                            content={
                                "instance": instance.model_dump(mode="json"),
                                "location": location.model_dump(mode="json"),
                            },
                            fact_key=f"design:location:{instance.ref.name}",
                        )
                    )
        elif question.operation in {
            DesignOperation.FANOUT,
            DesignOperation.CONNECTIONS,
        }:
            net = provider.get_net(context, question.name)
            if net is not None:
                if question.operation is DesignOperation.FANOUT:
                    pins = provider.get_fanout(context, net.ref)
                    if pins:
                        evidence.append(
                            self._design_evidence(
                                net,
                                context,
                                content={
                                    "net": net.model_dump(mode="json"),
                                    "fanout": [
                                        pin.model_dump(mode="json") for pin in pins
                                    ],
                                },
                                fact_key=f"design:fanout:{net.ref.name}",
                            )
                        )
                else:
                    connections = provider.get_connections(context, net.ref)
                    if connections:
                        evidence.append(
                            self._design_evidence(
                                net,
                                context,
                                content={
                                    "net": net.model_dump(mode="json"),
                                    "connections": [
                                        connection.model_dump(mode="json")
                                        for connection in connections
                                    ],
                                },
                                fact_key=f"design:connections:{net.ref.name}",
                            )
                        )
        elif (
            question.operation is DesignOperation.REGION and question.region is not None
        ):
            instances = provider.get_instances_in_region(context, question.region)
            if instances:
                first = instances[0]
                evidence.append(
                    self._design_evidence(
                        first,
                        context,
                        content={
                            "region": question.region.model_dump(mode="json"),
                            "instances": [
                                item.model_dump(mode="json") for item in instances
                            ],
                        },
                        fact_key="design:instances-in-region",
                    )
                )
        self._last_provider_calls = (
            ProviderCall(provider="design-data-provider", operation=question.operation),
        )
        return tuple(evidence)

    @staticmethod
    def _design_evidence(
        item: DesignInstance | DesignNet | DesignPin,
        context: QueryContext,
        *,
        content: JsonValue | None = None,
        fact_key: str | None = None,
    ) -> Evidence:
        payload = content or item.model_dump(mode="json")
        ref: DesignObjectRef = item.ref
        now = datetime.now(UTC)
        digest = hashlib.sha256(f"{ref.locator}:{payload}".encode()).hexdigest()
        return Evidence(
            evidence_id=f"ev-{digest[:24]}",
            source_kind=EvidenceSourceKind.DESIGN_DATA,
            content=payload,
            scope=context_scope(context),
            locator=EvidenceLocator(uri=ref.locator),
            provenance=EvidenceProvenance(
                provider="design-data-provider",
                source_hash=ref.source_hash,
                retrieved_at=now,
            ),
            fact_key=fact_key or f"design:{ref.kind.value}:{ref.name}",
        )

    def _collect_experiment_context(
        self, plan: QueryPlan, resolved: ResolvedExperimentContext
    ) -> tuple[Evidence, ...]:
        """Convert the typed context snapshot into the existing Evidence edge."""

        context = resolved.context
        result: list[Evidence] = []
        selected_ids = {item.run_id for item in context.metrics} | {
            item.run_id for item in context.artifacts
        }
        if resolved.selection.selected_run_id is not None:
            selected_ids.add(resolved.selection.selected_run_id)
        if Capability.RUN_EVIDENCE in plan.required_capabilities:
            for run in context.runs:
                if run.run_id not in selected_ids:
                    continue
                result.append(
                    self._experiment_evidence(
                        content={
                            "run_id": run.run_id,
                            "status": run.status.value,
                            "created_at": (
                                run.created_at.isoformat() if run.created_at else None
                            ),
                        },
                        run_id=run.run_id,
                        design_id=run.design_id,
                        fact_key="run:status",
                    )
                )
                for stage in run.stages:
                    if (
                        resolved.selection.selected_stage_key is not None
                        and stage.canonical_key
                        != canonical_stage_key(resolved.selection.selected_stage_key)
                    ):
                        continue
                    result.append(
                        self._experiment_evidence(
                            content={
                                "stage_key": stage.stage_key,
                                "status": stage.status.value,
                            },
                            run_id=run.run_id,
                            design_id=run.design_id,
                            stage=stage.stage_key,
                            fact_key=f"stage:{stage.stage_key}:status",
                        )
                    )
        if Capability.ARTIFACT_DISCOVERY in plan.required_capabilities:
            for artifact in context.artifacts:
                result.append(
                    self._experiment_evidence(
                        content={
                            "artifact_id": artifact.artifact_id,
                            "kind": artifact.kind,
                            "path": artifact.locator,
                        },
                        run_id=artifact.run_id,
                        design_id=artifact.design_id or context.design_id,
                        stage=artifact.stage_key,
                        fact_key=f"artifact:{artifact.artifact_id}",
                        source_hash=artifact.source_hash,
                    )
                )
        if Capability.EXPLICIT_METRIC in plan.required_capabilities:
            metrics = (
                resolved.comparison.observations
                if resolved.comparison is not None
                else context.metrics
            )
            freshness_by_metric = {
                item.evidence_id: item for item in resolved.freshness
            }
            for metric in metrics:
                freshness = freshness_by_metric.get(
                    f"{metric.run_id}:{metric.fact_key}:"
                    f"{metric.artifact_id or 'unregistered'}"
                )
                metric_status = metric.evidence_status
                metric_reason = (
                    None if metric.complete else "metric source artifact is missing"
                )
                if freshness is not None and freshness.state.value != "current":
                    metric_status = EvidenceStatus.PARTIAL
                    metric_reason = freshness.reason
                result.append(
                    self._experiment_evidence(
                        content={
                            "metric": metric.metric_name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "artifact_id": metric.artifact_id,
                        },
                        run_id=metric.run_id,
                        design_id=metric.design_id or context.design_id,
                        stage=metric.stage_key,
                        fact_key=metric.fact_key,
                        source_hash=metric.source_hash,
                        status=metric_status,
                        reason=metric_reason,
                    )
                )
        self._last_provider_calls = (
            ProviderCall(provider="experiment-context-provider", operation="resolve"),
        )
        return tuple(result)

    @staticmethod
    def _experiment_evidence(
        *,
        content: JsonValue,
        run_id: str,
        design_id: str | None = None,
        stage: str | None = None,
        fact_key: str,
        source_hash: str | None = None,
        status: EvidenceStatus = EvidenceStatus.SUFFICIENT,
        reason: str | None = None,
    ) -> Evidence:
        now = datetime.now(UTC)
        locator = f"experiment://runs/{run_id}/{fact_key}"
        digest = hashlib.sha256(f"{locator}:{content}".encode()).hexdigest()
        return Evidence(
            evidence_id=f"ev-{digest[:24]}",
            source_kind=EvidenceSourceKind.EXECUTION_RUN,
            content=content,
            scope=EvidenceScope(design_id=design_id, run_id=run_id, stage=stage),
            locator=EvidenceLocator(uri=locator),
            provenance=EvidenceProvenance(
                provider="experiment-context-provider",
                source_hash=source_hash,
                retrieved_at=now,
            ),
            status=status,
            fact_key=fact_key,
            reason=reason,
        )

    def _collect_managed_run(
        self, plan: QueryPlan, request: QueryRequest
    ) -> tuple[Evidence, ...]:
        provider = self.run_evidence_provider
        if provider is None:
            return ()
        context = request.context
        collected: list[Evidence] = []
        if Capability.RUN_EVIDENCE in plan.required_capabilities:
            collected.extend(provider.get_run_summary(context))
            collected.extend(provider.get_stage_evidence(context))
        if Capability.ARTIFACT_DISCOVERY in plan.required_capabilities:
            collected.extend(provider.get_artifacts(context))
        if Capability.EXPLICIT_METRIC in plan.required_capabilities:
            contexts = [context]
            if plan.intent is QueryIntent.CROSS_RUN_COMPARE:
                contexts = [
                    context.model_copy(update={"run_id": run_id, "run_ids": ()})
                    for run_id in context.run_ids
                ]
            for metric_context in contexts:
                collected.extend(
                    provider.get_metrics(
                        metric_context,
                        metric_name=metric_name_from_query(request.query),
                    )
                )
        if Capability.TEXT_SEARCH in plan.required_capabilities and plan.intent in {
            QueryIntent.LOG_DIAGNOSIS,
            QueryIntent.ROOT_CAUSE,
        }:
            collected.extend(provider.get_logs(context))
        return tuple(collected)

    @staticmethod
    def _evidence(
        *,
        source_kind: EvidenceSourceKind,
        content: JsonValue,
        locator: str,
        context: QueryContext,
        fact_key: str | None = None,
    ) -> Evidence:
        now = datetime.now(UTC)
        digest = hashlib.sha256(
            f"{source_kind.value}:{locator}:{content}".encode()
        ).hexdigest()
        return Evidence(
            evidence_id=f"ev-{digest[:24]}",
            source_kind=source_kind,
            content=content,  # pydantic validates the JSON-shaped value
            scope=context_scope(context),
            locator=EvidenceLocator(uri=locator),
            provenance=EvidenceProvenance(
                provider="local-artifact-provider",
                retrieved_at=now,
            ),
            fact_key=fact_key,
        )


def _analysis_evidence_id(locator: str, fact_key: str) -> str:
    digest = hashlib.sha256(f"{locator}:{fact_key}".encode()).hexdigest()
    return f"ev-{digest[:24]}"

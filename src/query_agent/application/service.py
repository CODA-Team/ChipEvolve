"""Small ordinary-Python Query Service pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from query_agent.domain.evidence import Evidence, JsonValue
from query_agent.domain.experiment import ResolvedExperimentContext
from query_agent.domain.query import QueryRequest, QueryResponse, QueryStatus
from query_agent.domain.trace import QueryTrace
from query_agent.ports.experiment_context import ExperimentContextProvider

from .answerability import AnswerabilityDecision, AnswerabilityEvaluator
from .collection import EvidenceCollector
from .context import ExperimentContextResolver
from .planning import IntentParser, QueryPlanner


class QueryService:
    """Intent -> plan -> evidence -> sufficiency -> response."""

    def __init__(
        self,
        *,
        intent_parser: IntentParser,
        planner: QueryPlanner,
        collector: EvidenceCollector,
        answerability: AnswerabilityEvaluator | None = None,
        prompt_version: str | None = None,
        model_name: str | None = None,
        experiment_context_provider: ExperimentContextProvider | None = None,
        context_resolver: ExperimentContextResolver | None = None,
    ) -> None:
        self._intent_parser = intent_parser
        self._planner = planner
        self._collector = collector
        self._answerability = answerability or AnswerabilityEvaluator()
        self._prompt_version = prompt_version
        self._model_name = model_name
        self._last_trace: QueryTrace | None = None
        provider = experiment_context_provider or collector.experiment_context_provider
        self._context_resolver = context_resolver or (
            ExperimentContextResolver(provider) if provider is not None else None
        )

    @property
    def last_trace(self) -> QueryTrace | None:
        return self._last_trace

    def query(self, request: QueryRequest) -> QueryResponse:
        intent = self._intent_parser.parse(request)
        plan = self._planner.plan(request, intent)
        resolved: ResolvedExperimentContext | None = None
        if self._context_resolver is not None:
            resolved = self._context_resolver.resolve(request, plan)
        evidence = self._collector.collect(plan, request, resolved)
        decision = self._answerability.evaluate(
            plan,
            evidence,
            self._collector.available_capabilities(request.context),
        )
        if intent.value == "UNKNOWN":
            status = QueryStatus.UNSUPPORTED
        elif not decision.sufficient:
            status = QueryStatus.NEEDS_MORE_DATA
        else:
            status = QueryStatus.ANSWERED
        self._last_trace = QueryTrace(
            request=request,
            intent=intent,
            plan=plan,
            provider_calls=self._collector.last_provider_calls,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            evidence_locators=tuple(item.locator.uri for item in evidence),
            source_hashes=tuple(
                item.provenance.source_hash
                for item in evidence
                if item.provenance.source_hash is not None
            ),
            evidence_status=decision.evidence_status,
            missing_requirements=decision.missing_evidence,
            missing_capabilities=decision.missing_capabilities,
            prompt_version=self._prompt_version,
            model_name=self._model_name,
            final_status=status,
            context_selection=resolved.selection if resolved else None,
            conflicts=resolved.conflicts if resolved else (),
            freshness=resolved.freshness if resolved else (),
        )
        return QueryResponse(
            status=status,
            answer=self._answer(status, evidence, resolved),
            evidence_citations=tuple(item.locator.uri for item in evidence),
            evidence_status=decision.evidence_status,
            reasons=decision.reasons,
            missing_evidence=decision.missing_evidence,
            missing_capabilities=decision.missing_capabilities,
            next_steps=self._next_steps(decision),
            evidence=tuple(evidence),
            context_selection=resolved.selection if resolved else None,
            conflicts=resolved.conflicts if resolved else (),
        )

    @staticmethod
    def _answer(
        status: QueryStatus,
        evidence: Sequence[Evidence],
        resolved: ResolvedExperimentContext | None = None,
    ) -> str | None:
        if status is QueryStatus.NEEDS_MORE_DATA:
            return "NEEDS_MORE_DATA: available evidence does not establish the claim."
        if status is QueryStatus.UNSUPPORTED:
            return "UNSUPPORTED: no Phase I plan is defined for this question."
        if (
            resolved is not None
            and resolved.comparison is not None
            and len(resolved.comparison.observations) >= 2
        ):
            observations = resolved.comparison.observations
            first = observations[0]
            second = observations[1]
            if isinstance(first.value, (int, float)) and isinstance(
                second.value, (int, float)
            ):
                delta = first.value - second.value
                return (
                    f"{first.metric_name} {first.run_id}={first.value}; "
                    f"{second.run_id}={second.value}; difference={delta}"
                )
        if not evidence:
            return None
        return "\n".join(_render_content(item.content) for item in evidence)

    @staticmethod
    def _next_steps(decision: AnswerabilityDecision) -> tuple[str, ...]:
        steps: list[str] = []
        for capability in decision.missing_capabilities:
            steps.append(f"provide capability {capability.value}")
        for requirement in decision.missing_evidence:
            steps.append(f"collect: {requirement.description}")
        return tuple(steps)


def _render_content(content: JsonValue) -> str:
    """Render a grounded, useful field without inventing an interpretation."""

    if isinstance(content, dict):
        values = cast(dict[str, JsonValue], content)
        for key in (
            "answer",
            "script",
            "text",
            "line",
            "value",
            "path",
            "store_key",
            "status",
        ):
            value = values.get(key)
            if value is not None:
                return str(value)
    return str(content)

"""Deterministic Phase I intent parsing and planning."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.query import (
    EvidenceRequirement,
    QueryContext,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    RunSelectionMode,
)

from .analysis_queries import AnalysisQuestionParser


class IntentParser(Protocol):
    """Provider-neutral intent parser."""

    def parse(self, request: QueryRequest) -> QueryIntent:
        """Classify a request without accessing external resources."""

        ...


class KeywordIntentParser:
    """Small deterministic parser used until a typed LLM adapter is added."""

    def parse(self, request: QueryRequest) -> QueryIntent:
        text = request.query.lower()
        if any(token in text for token in ("why", "root cause", "原因")):
            return QueryIntent.ROOT_CAUSE
        if any(token in text for token in ("compare", "difference", "对比", "差多少")):
            return QueryIntent.CROSS_RUN_COMPARE
        if any(
            token in text
            for token in (
                "which instance",
                "which instances",
                "which net",
                "which nets",
                "which pin",
                "which pins",
                "where is instance",
                "location of instance",
                "fanout of net",
                "connections of net",
                "instances in region",
                "instances inside region",
                "哪些 instance",
                "哪些实例",
            )
        ):
            return QueryIntent.DESIGN_OBJECT_QUERY
        if AnalysisQuestionParser().parse(request.query) is not None:
            return QueryIntent.ANALYSIS_QUERY
        if any(token in text for token in ("recommend", "建议", "应该")):
            return QueryIntent.RECOMMENDATION
        if any(
            token in text for token in ("where", "file", "artifact", "在哪", "文件")
        ):
            return QueryIntent.ARTIFACT_DISCOVERY
        if any(
            token in text
            for token in ("run status", "stage status", "stage complete", "状态")
        ):
            return QueryIntent.FLOW_STATUS
        if any(
            token in text for token in ("wns", "tns", "metric", "period", "density")
        ):
            return QueryIntent.METRIC_QUERY
        if any(token in text for token in ("error", "warning", "log", "停止", "报错")):
            return QueryIntent.LOG_DIAGNOSIS
        if any(token in text for token in ("how", "如何", "怎么")):
            return QueryIntent.HOW_TO
        if any(
            token in text
            for token in ("what is", "what does", "meaning", "是什么", "含义")
        ):
            return QueryIntent.DOMAIN_KNOWLEDGE
        return QueryIntent.UNKNOWN


class QueryPlanner:
    """Map intent to explicit evidence and capability requirements."""

    def plan(self, request: QueryRequest, intent: QueryIntent) -> QueryPlan:
        requirements: list[EvidenceRequirement] = []
        capabilities: list[Capability] = []

        def add(
            description: str,
            required: Sequence[Capability],
            *,
            fact_key: str | None = None,
            requires_current: bool = False,
            minimum_items: int = 1,
            exact_scope: bool = True,
        ) -> None:
            capabilities.extend(
                capability for capability in required if capability not in capabilities
            )
            requirements.append(
                EvidenceRequirement(
                    description=description,
                    required_capabilities=tuple(required),
                    scope=context_scope(request.context) if exact_scope else None,
                    fact_key=fact_key,
                    requires_current=requires_current,
                    minimum_items=minimum_items,
                )
            )

        if intent in {QueryIntent.DOMAIN_KNOWLEDGE, QueryIntent.HOW_TO}:
            add(
                "domain/tool knowledge with a citable source",
                [Capability.DOMAIN_KNOWLEDGE],
                exact_scope=False,
            )
        elif intent is QueryIntent.ARTIFACT_DISCOVERY:
            add("workspace artifact metadata", [Capability.ARTIFACT_DISCOVERY])
        elif intent is QueryIntent.FLOW_STATUS:
            add("run or stage status", [Capability.RUN_EVIDENCE])
        elif intent in {QueryIntent.EXPLICIT_FACT, QueryIntent.METRIC_QUERY}:
            add(
                "an explicit fact in a text artifact",
                [Capability.TEXT_SEARCH, Capability.EXPLICIT_METRIC],
                fact_key=(
                    f"metric:{metric_name_from_query(request.query)}"
                    if metric_name_from_query(request.query) is not None
                    else None
                ),
                requires_current=request.context.stage is not None,
            )
        elif intent is QueryIntent.LOG_DIAGNOSIS:
            add(
                "bounded log excerpts containing the reported condition",
                [Capability.TEXT_SEARCH],
            )
        elif intent is QueryIntent.CROSS_RUN_COMPARE:
            add(
                "explicit, semantically aligned metrics for both runs",
                [Capability.EXPLICIT_METRIC],
                fact_key=f"metric:{metric_name_from_query(request.query) or 'UNKNOWN'}",
                minimum_items=2,
                exact_scope=False,
            )
        elif intent is QueryIntent.ROOT_CAUSE:
            add(
                "bounded evidence plus structured design relationships; "
                "experience is not proof",
                [Capability.TEXT_SEARCH, Capability.DESIGN_RELATION_QUERY],
                requires_current=True,
            )
        elif intent is QueryIntent.RECOMMENDATION:
            add(
                "current evidence and domain knowledge",
                [Capability.TEXT_SEARCH, Capability.DOMAIN_KNOWLEDGE],
            )
        elif intent is QueryIntent.DESIGN_OBJECT_QUERY:
            relation = any(
                token in request.query.lower()
                for token in ("fanout", "drive", "drives", "connection", "连接")
            )
            add(
                "typed design-object evidence",
                [
                    Capability.DESIGN_RELATION_QUERY
                    if relation
                    else Capability.DESIGN_OBJECT_QUERY
                ],
                exact_scope=False,
            )
        elif intent is QueryIntent.ANALYSIS_QUERY:
            question = AnalysisQuestionParser().parse(request.query)
            add(
                "typed timing-analysis evidence",
                [Capability.SPECIALIZED_ANALYSIS],
                fact_key=question.fact_key if question is not None else None,
                requires_current=True,
                exact_scope=False,
            )
        elif intent is QueryIntent.UNKNOWN and any(
            token in request.query.lower()
            for token in (
                "which cell",
                "which cells",
                "which instance",
                "which net",
                "哪些 cell",
                "哪些 instance",
            )
        ):
            add("structured design-object evidence", [Capability.DESIGN_OBJECT_QUERY])
        else:
            return QueryPlan(intent=intent)
        selection = RunSelectionMode.AUTO
        if request.context.source.value == "MANAGED_RUN":
            if request.context.run_id is not None:
                selection = RunSelectionMode.EXPLICIT
            elif request.context.run_ids or intent is QueryIntent.CROSS_RUN_COMPARE:
                selection = RunSelectionMode.COMPARISON
            elif any(
                phrase in request.query.lower()
                for phrase in ("current", "当前", "now", "现在")
            ):
                selection = RunSelectionMode.CURRENT
            elif any(
                phrase in request.query.lower()
                for phrase in ("latest completed", "latest valid", "最新完成")
            ):
                selection = RunSelectionMode.LATEST_VALID
            else:
                selection = RunSelectionMode.LATEST_VALID
        return QueryPlan(
            intent=intent,
            evidence_requirements=tuple(requirements),
            required_capabilities=tuple(capabilities),
            run_selection=selection,
        )


def context_scope(context: QueryContext):
    """Keep scope construction in one named application concern."""

    from query_agent.domain.evidence import EvidenceScope

    return EvidenceScope(
        design_id=context.design_id,
        run_id=context.run_id,
        stage=context.stage,
    )


def metric_name_from_query(query: str) -> str | None:
    """Extract only well-known metric labels; values remain deterministic."""

    upper = query.upper()
    for name in ("WNS", "TNS", "VIOLATIONS", "RUNTIME", "DENSITY"):
        if name in upper:
            return name
    return None

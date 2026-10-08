"""Deterministic evidence sufficiency evaluation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence, EvidenceStatus
from query_agent.domain.query import EvidenceRequirement, QueryIntent, QueryPlan


@dataclass(frozen=True)
class AnswerabilityDecision:
    """Evidence coverage result used by the responder."""

    missing_evidence: tuple[EvidenceRequirement, ...]
    missing_capabilities: tuple[Capability, ...]
    evidence_status: EvidenceStatus = EvidenceStatus.SUFFICIENT
    reasons: tuple[str, ...] = ()
    conflicting_evidence: tuple[Evidence, ...] = ()
    stale_evidence: tuple[Evidence, ...] = ()

    @property
    def sufficient(self) -> bool:
        return (
            not self.missing_evidence
            and not self.missing_capabilities
            and self.evidence_status is EvidenceStatus.SUFFICIENT
        )


class AnswerabilityEvaluator:
    """Never infer root causes from missing or weak evidence."""

    def evaluate(
        self,
        plan: QueryPlan,
        evidence: Sequence[Evidence],
        available_capabilities: frozenset[Capability],
    ) -> AnswerabilityDecision:
        missing_capabilities = tuple(
            capability
            for capability in plan.required_capabilities
            if capability not in available_capabilities
        )
        missing: list[EvidenceRequirement] = []
        reasons: list[str] = []
        conflicting: list[Evidence] = []
        stale: list[Evidence] = []
        for requirement in plan.evidence_requirements:
            matching = [
                item
                for item in evidence
                if item.scope.matches(requirement.scope)
                and (
                    requirement.fact_key is None
                    or item.fact_key == requirement.fact_key
                )
            ]
            if len(matching) < requirement.minimum_items:
                missing.append(requirement)
            if any(
                capability not in available_capabilities
                for capability in requirement.required_capabilities
            ):
                missing.append(requirement)
            if any(item.status is EvidenceStatus.PARTIAL for item in matching):
                missing.append(requirement)
                reasons.append(f"incomplete evidence for {requirement.description}")
            if requirement.requires_current:
                stale_items = [
                    item
                    for item in matching
                    if item.status is not EvidenceStatus.SUFFICIENT
                ]
                stale.extend(stale_items)
                if stale_items:
                    reasons.append(
                        f"current evidence requirement has {len(stale_items)} "
                        "partial, stale, or otherwise non-current item(s)"
                    )
                    missing.append(requirement)
            if requirement.fact_key is not None and len(matching) > 1:
                groups: dict[
                    tuple[str | None, str | None, str | None], list[Evidence]
                ] = {}
                for item in matching:
                    scope_key = (
                        item.scope.design_id,
                        item.scope.run_id,
                        item.scope.stage,
                    )
                    groups.setdefault(scope_key, []).append(item)
                for group in groups.values():
                    values = {
                        json.dumps(item.content, sort_keys=True, default=str)
                        for item in group
                    }
                    if len(values) > 1:
                        conflicting.extend(group)
                        reasons.append(
                            f"conflicting evidence for {requirement.fact_key}"
                        )
        missing_evidence = tuple(dict.fromkeys(missing))
        if plan.intent is QueryIntent.UNKNOWN:
            missing_evidence = plan.evidence_requirements
        if conflicting:
            status = EvidenceStatus.CONFLICTING
        elif stale:
            status = EvidenceStatus.PARTIAL
        elif plan.intent is QueryIntent.EXPLICIT_FACT and any(
            item.status is EvidenceStatus.PARTIAL for item in evidence
        ):
            status = EvidenceStatus.PARTIAL
            reasons.append("source excerpt is truncated")
        elif missing_evidence:
            status = EvidenceStatus.INSUFFICIENT
        else:
            status = EvidenceStatus.SUFFICIENT
        return AnswerabilityDecision(
            missing_evidence=missing_evidence,
            missing_capabilities=missing_capabilities,
            evidence_status=status,
            reasons=tuple(dict.fromkeys(reasons)),
            conflicting_evidence=tuple(conflicting),
            stale_evidence=tuple(stale),
        )

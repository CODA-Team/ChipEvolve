"""Use the existing scoped investigation to feed real professional models."""

from query_agent.domain.handoff import HandoffPackage
from query_agent.domain.investigation import InvestigationState
from query_agent.domain.professional import ProfessionalContext


def professional_context(
    state: InvestigationState, source: HandoffPackage
) -> ProfessionalContext:
    if any(scope.design_id != source.scope.design_id for scope in state.scopes):
        raise ValueError("professional context cannot mix designs")
    # model_construct permits computing the canonical identity before validation.
    candidate = ProfessionalContext.model_construct(
        context_id="pending",
        investigation_id=state.investigation_id,
        scope=source.scope,
        fixed_inputs=source.fixed_inputs,
        summary=state.answer.summary
        if state.answer
        else "Investigation has no final diagnosis yet.",
        confirmed_facts=[
            *source.confirmed_facts,
            *(state.answer.claims if state.answer else []),
        ],
        hypotheses=source.hypotheses,
        evidence=source.evidence,
        limitations=[
            *state.missing_evidence,
            *(state.answer.missing_evidence if state.answer else []),
            "Evidence coverage is bounded; this context does not authorize "
            "changing native algorithms, constraints or input facts.",
        ],
    )
    return ProfessionalContext.model_validate(
        {**candidate.model_dump(), "context_id": candidate.fingerprint()}
    )

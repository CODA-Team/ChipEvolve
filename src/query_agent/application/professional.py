"""Use the existing scoped investigation to feed real professional models."""

import hashlib

from query_agent.domain.handoff import HandoffPackage
from query_agent.domain.investigation import AnswerClaim, Hypothesis, InvestigationState
from query_agent.domain.professional import ProfessionalContext


def professional_context(
    state: InvestigationState, source: HandoffPackage
) -> ProfessionalContext:
    if any(scope.design_id != source.scope.design_id for scope in state.scopes):
        raise ValueError("professional context cannot mix designs")
    claims = {
        claim.model_dump_json(): claim
        for claim in [
            *source.confirmed_facts,
            *(state.answer.claims if state.answer else []),
        ]
    }
    evidence_ids = {item.evidence_id for item in source.evidence}
    if any(set(claim.evidence_ids) - evidence_ids for claim in claims.values()):
        raise ValueError("professional claims must retain their evidence")
    facts: list[AnswerClaim] = []
    hypotheses = list(source.hypotheses)
    limitations = [
        *state.missing_evidence,
        *(state.answer.missing_evidence if state.answer else []),
        "Evidence coverage is bounded; this context does not authorize "
        "changing native algorithms, constraints or input facts.",
    ]
    for identity, claim in claims.items():
        if claim.kind == "limitation":
            citations = (
                " [evidence: " + ", ".join(claim.evidence_ids) + "]"
                if claim.evidence_ids
                else ""
            )
            limitations.append(claim.text + citations)
        elif claim.kind == "hypothesis" or claim.certainty in {"possible", "unknown"}:
            hypothesis = Hypothesis(
                hypothesis_id="claim-" + hashlib.sha256(identity.encode()).hexdigest(),
                explanation=claim.text,
                supports=claim.evidence_ids,
                status="supported" if claim.certainty == "supported" else "unverified",
            )
            if not any(
                item.explanation == hypothesis.explanation
                and item.status == hypothesis.status
                and item.supports == hypothesis.supports
                for item in hypotheses
            ):
                hypotheses.append(hypothesis)
        else:
            facts.append(claim)
    # model_construct permits computing the canonical identity before validation.
    candidate = ProfessionalContext.model_construct(
        context_id="pending",
        investigation_id=state.investigation_id,
        scope=source.scope,
        fixed_inputs=source.fixed_inputs,
        summary=state.answer.summary
        if state.answer
        else "Investigation has no final diagnosis yet.",
        confirmed_facts=facts,
        hypotheses=hypotheses,
        evidence=source.evidence,
        limitations=list(dict.fromkeys(limitations)),
    )
    return ProfessionalContext.model_validate(
        {**candidate.model_dump(), "context_id": candidate.fingerprint()}
    )

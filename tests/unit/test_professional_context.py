import pytest

from query_agent.application.handoff import create_handoff
from query_agent.application.professional import professional_context
from query_agent.domain.evidence import EvidenceLocator, EvidenceScope, EvidenceStatus
from query_agent.domain.handoff import EvidenceReference
from query_agent.domain.investigation import (
    AnswerClaim,
    FixedScope,
    InvestigationAnswer,
    InvestigationState,
)
from query_agent.domain.professional import ProfessionalContext


def test_query_diagnosis_remains_scoped_and_is_not_an_edit_permission():
    scope = FixedScope(
        snapshot_id="s",
        design_id="second-design",
        run_id="run",
        revision_id="r",
        stage="finish",
    )
    state = InvestigationState(investigation_id="inv", question="why?", scopes=[scope])
    state.answer = InvestigationAnswer(
        summary="Available evidence is bounded",
        claims=[
            AnswerClaim(
                text="Sampled paths are not full signoff",
                kind="limitation",
                certainty="unknown",
            )
        ],
        outcome="partial",
        missing_evidence=["full timing coverage"],
    )
    source = create_handoff(
        state,
        snapshot_id="s",
        role="code",
        objective="source optimization",
        source_artifacts=[
            {
                "category": "raw_design_database",
                "logical_path": "design.odb",
                "artifact_id": "art",
                "run_id": "producer",
                "sha256": "a" * 64,
                "size_bytes": 10,
            }
        ],
        buffer_permissions=[],
    )
    packet = professional_context(state, source)
    assert packet.scope.design_id == "second-design"
    assert not packet.confirmed_facts
    assert "Sampled paths are not full signoff" in packet.limitations
    assert "full timing coverage" in packet.limitations
    assert "buffer_permissions" not in packet.model_dump()
    altered = packet.model_dump()
    altered["summary"] = "invented cause"
    with pytest.raises(ValueError, match="identity changed"):
        ProfessionalContext.model_validate(altered)
    state.scopes.append(scope.model_copy(update={"design_id": "other"}))
    with pytest.raises(ValueError, match="mix designs"):
        professional_context(state, source)


def test_export_keeps_unconfirmed_claims_out_of_facts_without_mutating_inputs():
    scope = FixedScope(
        snapshot_id="s", design_id="jpeg", run_id="run", revision_id="r", stage="finish"
    )
    fact = AnswerClaim(text="Setup remains negative", kind="fact", certainty="observed")
    possible = AnswerClaim(
        text="Master changes may explain faster propagation",
        kind="hypothesis",
        certainty="possible",
        evidence_ids=["ev"],
    )
    unknown = AnswerClaim(
        text="Routing alone caused the change", kind="causal", certainty="unknown"
    )
    state = InvestigationState(
        investigation_id="inv", question="why?", scopes=[scope], confirmed_facts=[fact]
    )
    state.answer = InvestigationAnswer(
        summary="Improved but infeasible; causes require further evidence",
        claims=[fact, possible, unknown],
        outcome="partial",
    )
    source = create_handoff(
        state,
        snapshot_id="s",
        role="code",
        objective="source optimization",
        source_artifacts=[
            {
                "category": "raw_design_database",
                "logical_path": "design.odb",
                "artifact_id": "art",
                "run_id": "producer",
                "sha256": "a" * 64,
                "size_bytes": 10,
            }
        ],
        buffer_permissions=[],
    )
    source = source.model_copy(
        update={
            "evidence": [
                EvidenceReference(
                    evidence_id="ev",
                    scope=EvidenceScope(design_id="jpeg", run_id="run"),
                    locator=EvidenceLocator(uri="artifact://run/report"),
                    source_hash="b" * 64,
                    status=EvidenceStatus.PARTIAL,
                )
            ]
        }
    )
    original_state, original_source = state.model_dump(), source.model_dump()
    packet = professional_context(state, source)
    assert packet.confirmed_facts == [fact]
    assert {h.explanation for h in packet.hypotheses} == {possible.text, unknown.text}
    assert all(h.status == "unverified" for h in packet.hypotheses)
    assert next(
        h for h in packet.hypotheses if h.explanation == possible.text
    ).supports == ["ev"]
    assert professional_context(state, source).context_id == packet.context_id
    assert state.model_dump() == original_state
    assert source.model_dump() == original_source
    state.answer = state.answer.model_copy(
        update={"claims": [possible.model_copy(update={"evidence_ids": ["missing"]})]}
    )
    with pytest.raises(ValueError, match="claims must retain their evidence"):
        professional_context(state, source)

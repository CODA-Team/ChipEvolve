import pytest

from query_agent.application.handoff import create_handoff
from query_agent.application.professional import professional_context
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
    assert packet.confirmed_facts[0].kind == "limitation"
    assert "full timing coverage" in packet.limitations
    assert "buffer_permissions" not in packet.model_dump()
    altered = packet.model_dump()
    altered["summary"] = "invented cause"
    with pytest.raises(ValueError, match="identity changed"):
        ProfessionalContext.model_validate(altered)
    state.scopes.append(scope.model_copy(update={"design_id": "other"}))
    with pytest.raises(ValueError, match="mix designs"):
        professional_context(state, source)

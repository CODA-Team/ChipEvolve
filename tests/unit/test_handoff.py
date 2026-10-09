"""A downstream task cannot manufacture permissions, identities or confirmed facts."""

from pathlib import Path

import pytest

from query_agent.application.handoff import create_handoff
from query_agent.domain.evidence import JsonValue
from query_agent.domain.handoff import BufferPermission, HandoffPackage
from query_agent.domain.investigation import AnswerClaim, FixedScope, InvestigationState


def package(role: str = "eco") -> HandoffPackage:
    state = InvestigationState(
        investigation_id="inv-a",
        question="why?",
        scopes=[
            FixedScope(
                snapshot_id="s",
                design_id="gcd",
                revision_id="r",
                run_id="run",
                stage="finish",
            )
        ],
    )
    sources: list[dict[str, JsonValue]] = [
        {
            "artifact_id": "art-" + kind,
            "run_id": "run",
            "category": kind,
            "logical_path": kind + ".bin",
            "sha256": "a" * 64,
            "size_bytes": 10,
        }
        for kind in ("raw_design_database", "raw_constraints", "raw_library")
    ]
    return create_handoff(
        state,
        snapshot_id="s",
        role=role,
        objective="Improve setup and check hold",
        source_artifacts=sources,
        buffer_permissions=[
            BufferPermission(
                instance="place178",
                original_master="BUF_X1",
                allowed_masters=["BUF_X4"],
            )
        ]
        if role == "eco"
        else [],
    )


def test_eco_requires_fixed_sources_and_exact_buffer_permissions(
    tmp_path: Path,
) -> None:
    task = package()
    assert task.consumer_status == "ready"
    assert task.budget.max_experiments == 1
    broken = task.model_dump(mode="json")
    broken["buffer_permissions"] = []
    with pytest.raises(ValueError, match="explicit allowed"):
        HandoffPackage.model_validate(broken)
    broken = task.model_dump(mode="json")
    broken["fixed_inputs"] = broken["fixed_inputs"][:1]
    with pytest.raises(ValueError, match="constraints and libraries"):
        HandoffPackage.model_validate(broken)
    broken = task.model_dump(mode="json")
    broken["confirmed_facts"] = [
        AnswerClaim(
            text="already fixed",
            evidence_ids=["unknown"],
            kind="fact",
            certainty="observed",
        ).model_dump(mode="json")
    ]
    with pytest.raises(ValueError, match="packaged evidence"):
        HandoffPackage.model_validate(broken)


@pytest.mark.parametrize("role", ["flow", "code"])
def test_unconnected_roles_cannot_claim_a_working_consumer(role: str) -> None:
    task = package(role)
    assert task.consumer_status == "contract_only"
    changed = task.model_dump(mode="json")
    changed["consumer_status"] = "ready"
    with pytest.raises(ValueError, match="contract-only"):
        HandoffPackage.model_validate(changed)

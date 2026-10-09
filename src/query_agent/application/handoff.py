"""Export tasks from retrieved inputs; no downstream effect is implied."""

import uuid

from query_agent.domain.evidence import JsonValue
from query_agent.domain.handoff import (
    BufferPermission,
    EvidenceReference,
    FixedInput,
    HandoffPackage,
)
from query_agent.domain.investigation import InvestigationState

INPUT_CATEGORIES = {
    "raw_design_database",
    "raw_constraints",
    "raw_library",
    "raw_parasitics",
    "raw_netlist",
    "analysis_script",
    "raw_global_routing",
}


def create_handoff(
    state: InvestigationState,
    *,
    snapshot_id: str,
    role: str,
    objective: str,
    source_artifacts: list[dict[str, JsonValue]],
    buffer_permissions: list[BufferPermission],
) -> HandoffPackage:
    scope = next((s for s in state.scopes if s.snapshot_id == snapshot_id), None)
    if scope is None:
        raise ValueError("handoff must use a fixed investigation snapshot")
    if role not in ("eco", "flow", "code"):
        raise ValueError("unsupported handoff role")
    fixed = [
        FixedInput.model_validate(
            {
                "role": ref["category"],
                **{
                    key: ref[key]
                    for key in (
                        "logical_path",
                        "artifact_id",
                        "run_id",
                        "sha256",
                        "size_bytes",
                    )
                },
            }
        )
        for ref in source_artifacts
        if ref.get("category") in INPUT_CATEGORIES
    ]
    return HandoffPackage(
        handoff_id="handoff-" + uuid.uuid4().hex,
        investigation_id=state.investigation_id,
        role=role,
        objective=objective,
        scope=scope,
        fixed_inputs=fixed,
        confirmed_facts=state.confirmed_facts,
        hypotheses=state.hypotheses,
        evidence=[
            EvidenceReference(
                evidence_id=item.evidence_id,
                scope=item.scope,
                locator=item.locator,
                source_hash=item.provenance.source_hash,
                status=item.status,
            )
            for item in state.evidence
        ],
        buffer_permissions=buffer_permissions,
        evaluation_conditions=[
            "Keep original clocks, SDC, libraries, RC sources, corner "
            "and check settings fixed.",
            "Compare both setup and hold, matched endpoints and area "
            "under the same conditions.",
        ],
        success_conditions=[
            "Return actual accepted task identity, modifications, native "
            "STA and area artifacts.",
            "Declare improvement only for measured better setup with no "
            "introduced hold violation.",
            "Report area delta and any unresolved coverage; no "
            "improvement is a valid outcome.",
        ],
        refusal_conditions=[
            "Missing or changed fixed input bytes or original buffer master.",
            "Any edit outside the explicit buffer permissions or any "
            "changed evaluation condition.",
            "Budget exhausted or no connected receiver for the requested role.",
        ],
        consumer_status="ready" if role == "eco" else "contract_only",
    )

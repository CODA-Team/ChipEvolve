"""Evidence-backed professional context; delivery grants no edit permissions."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .handoff import EvidenceReference, FixedInput
from .investigation import AnswerClaim, FixedScope, Hypothesis


class ProfessionalContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["chip-evolve.design-context.v1"] = (
        "chip-evolve.design-context.v1"
    )
    context_id: str
    investigation_id: str
    scope: FixedScope
    fixed_inputs: list[FixedInput]
    summary: str
    confirmed_facts: list[AnswerClaim]
    hypotheses: list[Hypothesis]
    evidence: list[EvidenceReference]
    limitations: list[str]

    @model_validator(mode="after")
    def check_evidence(self) -> ProfessionalContext:
        ids = {item.evidence_id for item in self.evidence}
        if any(set(claim.evidence_ids) - ids for claim in self.confirmed_facts):
            raise ValueError("professional facts must retain their evidence")
        if self.context_id != self.fingerprint():
            raise ValueError("professional context identity changed")
        return self

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.model_dump(mode="json", exclude={"context_id"}),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

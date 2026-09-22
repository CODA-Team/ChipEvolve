"""Evidence-linked diagnosis vocabulary for Phase IV."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .design import DesignObjectRef


class DiagnosisScope(BaseModel):
    """Design/run/stage scope for one diagnostic finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    stage: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def scope_is_explicit(self) -> DiagnosisScope:
        if self.design_id is None and self.run_id is None and self.stage is None:
            raise ValueError("diagnosis scope must identify a design, run, or stage")
        return self


class DiagnosisProvenance(BaseModel):
    """Origin of a finding, separate from its explanatory claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    observed_at: datetime

    @field_validator("source_hash")
    @classmethod
    def source_hash_is_hex(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError("source_hash must be hexadecimal") from exc
        return value


class DiagnosisSupport(BaseModel):
    """One citable fact that supports a diagnostic finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_kind: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("source_hash")
    @classmethod
    def source_hash_is_hex(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError("source_hash must be hexadecimal") from exc
        return value


class DiagnosisFinding(BaseModel):
    """A bounded diagnostic claim with explicit supporting evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    affected_object: DesignObjectRef | None = None
    cause_object: DesignObjectRef | None = None
    support: tuple[DiagnosisSupport, ...] = Field(min_length=1)
    scope: DiagnosisScope
    provenance: DiagnosisProvenance
    complete: bool = True

    @property
    def fact_key(self) -> str:
        return "diagnosis:finding"

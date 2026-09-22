"""Evidence and bounded artifact read models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]


class EvidenceSourceKind(StrEnum):
    """Where an evidence item came from."""

    WORKSPACE_ARTIFACT = "workspace_artifact"
    KNOWLEDGE = "knowledge"
    EXECUTION_RUN = "execution_run"
    DESIGN_DATA = "design_data"
    SPECIALIZED_ANALYSIS = "specialized_analysis"


class EvidenceStatus(StrEnum):
    """Business meaning of evidence coverage; not a numeric confidence."""

    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"


class EvidenceScope(BaseModel):
    """Optional design/run/stage scope attached to a fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    stage: str | None = Field(default=None, min_length=1)

    def matches(self, required: EvidenceScope | None) -> bool:
        """Return whether this evidence is in the requested exact scope."""

        if required is None:
            return True
        for name in ("design_id", "run_id", "stage"):
            expected = getattr(required, name)
            if expected is not None and getattr(self, name) != expected:
                return False
        return True


class EvidenceLocator(BaseModel):
    """Location in the original source, suitable for a citation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uri: str = Field(min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def line_range_is_ordered(self) -> EvidenceLocator:
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end must not be before line_start")
        return self


class EvidenceProvenance(BaseModel):
    """Small, explicit provenance record for one evidence item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    source_mtime: datetime | None = None
    retrieved_at: datetime

    @field_validator("source_hash")
    @classmethod
    def source_hash_is_hex(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError("source_hash must be hexadecimal") from exc
        return value


class Evidence(BaseModel):
    """A typed, traceable fact or source excerpt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    source_kind: EvidenceSourceKind
    content: JsonValue
    scope: EvidenceScope = Field(default_factory=EvidenceScope)
    locator: EvidenceLocator
    provenance: EvidenceProvenance
    status: EvidenceStatus = EvidenceStatus.SUFFICIENT
    fact_key: str | None = Field(default=None, min_length=1)
    reason: str | None = Field(default=None, min_length=1)


class ArtifactMetadata(BaseModel):
    """Metadata only; binary artifacts are never returned as text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    media_type: str | None = None
    is_binary: bool

    @field_validator("path")
    @classmethod
    def path_is_relative_posix(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact path must be relative to the workspace")
        return value


class TextMatch(BaseModel):
    """One bounded textual search hit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    line_number: int = Field(ge=1)
    line: str


class ArtifactExcerpt(BaseModel):
    """A bounded read from a text artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    offset: int = Field(ge=0)
    content: str
    bytes_read: int = Field(ge=0)
    truncated: bool

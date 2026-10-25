"""Typed, provenance-bearing analysis evidence for Phase III-B."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisScope(BaseModel):
    """Semantic scope attached to one analysis observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    stage: str | None = Field(default=None, min_length=1)
    snapshot_id: str | None = Field(default=None, min_length=1)
    revision_id: str | None = Field(default=None, min_length=1)
    corner: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def scope_is_explicit(self) -> AnalysisScope:
        if all(
            value is None
            for value in (self.design_id, self.run_id, self.stage, self.corner)
        ):
            raise ValueError(
                "analysis scope must identify a design, run, stage, or corner"
            )
        return self


class AnalysisProvenance(BaseModel):
    """Origin of an analysis result, kept separate from its numeric value."""

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


class TimingMetricObservation(BaseModel):
    """One scalar timing-analysis result such as WNS or TNS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str = Field(min_length=1)
    value: float
    unit: str | None = Field(default=None, min_length=1)
    scope: AnalysisScope
    provenance: AnalysisProvenance
    complete: bool = True

    @field_validator("metric_name")
    @classmethod
    def metric_name_is_supported(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"WNS", "TNS"}:
            raise ValueError("timing metric must be WNS or TNS")
        return normalized

    @property
    def fact_key(self) -> str:
        return f"analysis:metric:{self.metric_name.upper()}"


class TimingPathObservation(BaseModel):
    """One bounded timing path result; no timing graph leaks through the port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path_id: str = Field(min_length=1)
    check: Literal["setup", "hold"] | None = None
    startpoint: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    slack: float
    unit: str = Field(min_length=1)
    total_delay: float | None = None
    logic_depth: int | None = Field(default=None, ge=0)
    scope: AnalysisScope
    provenance: AnalysisProvenance
    complete: bool = True

    @property
    def fact_key(self) -> str:
        return "analysis:timing-path"

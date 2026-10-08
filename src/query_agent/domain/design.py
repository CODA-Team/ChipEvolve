"""Typed, read-only design-object vocabulary for Phase III-A."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DesignObjectKind(StrEnum):
    """Object kinds shared by design-data adapters."""

    INSTANCE = "instance"
    NET = "net"
    PIN = "pin"


class DesignObjectRef(BaseModel):
    """Stable identity of one design object, independent of adapter schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_id: str | None = None
    design_id: str = Field(min_length=1)
    kind: DesignObjectKind
    name: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    snapshot_id: str | None = None
    revision_id: str | None = None
    run_id: str | None = None
    stage: str | None = None


class DesignLocation(BaseModel):
    """Physical location with explicit units."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    units: str = Field(min_length=1)


class DesignRegion(BaseModel):
    """Axis-aligned query region."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x_min: float = Field(allow_inf_nan=False)
    y_min: float = Field(allow_inf_nan=False)
    x_max: float = Field(allow_inf_nan=False)
    y_max: float = Field(allow_inf_nan=False)
    units: str = Field(min_length=1)

    @model_validator(mode="after")
    def bounds_are_ordered(self) -> DesignRegion:
        if self.x_max < self.x_min or self.y_max < self.y_min:
            raise ValueError("region maximums must not precede minimums")
        return self


class DesignInstance(BaseModel):
    """Typed instance summary; no cell database object leaks across the port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: DesignObjectRef
    cell_type: str = Field(min_length=1)
    location: DesignLocation | None = None


class DesignNet(BaseModel):
    """Typed net identity and optional driver pin."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: DesignObjectRef
    driver: DesignObjectRef | None = None


class DesignPin(BaseModel):
    """Typed pin identity and ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: DesignObjectRef
    instance: DesignObjectRef | None = None
    direction: str | None = None


class DesignConnection(BaseModel):
    """One directed relationship between two typed design objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: DesignObjectRef
    target: DesignObjectRef
    predicate: str | None = None


def object_ref(
    design_id: str,
    kind: DesignObjectKind,
    name: str,
    *,
    locator: str | None = None,
    source_hash: str | None = None,
) -> DesignObjectRef:
    """Build a canonical fixture/provider-neutral object reference."""

    return DesignObjectRef(
        design_id=design_id,
        kind=kind,
        name=name,
        locator=locator or f"design://{design_id}/{kind.value}/{name}",
        source_hash=source_hash,
    )

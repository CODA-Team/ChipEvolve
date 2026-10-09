"""Advisory semantic judgments never replace facts, scope or permissions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .evidence import JsonValue


class JudgmentAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["route", "rank", "verify"]
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["available", "fallback"]
    payload: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    receipt: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    seconds: float = Field(ge=0)
    error: str | None = None

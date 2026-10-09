"""Typed JEV route, relevance and support advice through one configured launcher."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from query_agent.adapters.llm.budget import CostLedger
from query_agent.domain.evidence import JsonValue
from query_agent.domain.judgment import JudgmentAdvice

from .budgeted import BudgetedJudgment
from .stdio import StdioJudgmentClient

CLASS_CATALOG = [
    {
        "id": "L0",
        "description": (
            "Single recorded fact, identity, count already indexed, "
            "resource/error or source lookup. No comparison, derivation or "
            "causal diagnosis. "
        ),
    },
    {
        "id": "L1",
        "description": (
            "Deterministic comparison, ranking, domain aggregation or geometry "
            "calculation over explicitly fixed records. No causal attribution "
            "or adaptive evidence investigation. "
        ),
    },
    {
        "id": "L2",
        "description": (
            "Causal diagnosis, competing explanations, verification, missing- "
            "detail investigation, targeted analysis or supported recovery "
            "from tool failure. Scope resolution can be its first step; "
            "missing detail alone does not make it unclear. "
        ),
    },
    {
        "id": "unclear",
        "description": (
            "The question explicitly leaves target identities, intended "
            "objective, units or conflicting scope unresolved so meaningful "
            "action first needs clarification. Takes precedence when explicit "
            "ambiguity prevents interpreting the request. "
        ),
    },
]


class RouteRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    classification: Literal["L0", "L1", "L2", "unclear"]
    probabilities: dict[Literal["L0", "L1", "L2", "unclear"], float]
    top_probability: float = Field(ge=0, le=1)
    margin: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def valid_distribution(self) -> RouteRow:
        if set(self.probabilities) != {"L0", "L1", "L2", "unclear"}:
            raise ValueError("incomplete route distribution")
        if (
            any(not 0 <= p <= 1 for p in self.probabilities.values())
            or abs(sum(self.probabilities.values()) - 1) > 0.02
        ):
            raise ValueError("invalid route probabilities")
        if self.probabilities[self.classification] != max(self.probabilities.values()):
            raise ValueError("route label differs from distribution")
        return self


class RankedRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    relevance: float = Field(ge=0, le=1)


class SupportRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    verdict: Literal["verified", "contradicted", "unsupported"]
    probabilities: dict[Literal["supports", "contradicts", "says_nothing"], float]
    confidence: float = Field(ge=0, le=1)
    same_subject: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def valid_distribution(self) -> SupportRow:
        if set(self.probabilities) != {"supports", "contradicts", "says_nothing"}:
            raise ValueError("incomplete support distribution")
        if (
            any(not 0 <= p <= 1 for p in self.probabilities.values())
            or abs(sum(self.probabilities.values()) - 1) > 0.02
        ):
            raise ValueError("invalid support probabilities")
        return self


class JevInvestigationJudgment:
    def __init__(
        self,
        *,
        launcher: Path,
        ledger: CostLedger,
        pricing: Path,
        trace_root: Path,
        threshold: float = 0.85,
        margin: float = 0.5,
    ) -> None:
        self.launcher, self.ledger, self.trace_root = launcher, ledger, trace_root
        self.pricing: dict[str, Any] = json.loads(pricing.read_text())
        self.threshold, self.margin = threshold, margin

    def judge(
        self,
        kind: Literal["route", "rank", "verify"],
        payload: dict[str, JsonValue],
        *,
        seconds: float,
    ) -> JudgmentAdvice:
        started = time.monotonic()
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        receipt: dict[str, JsonValue] = {}
        try:
            with StdioJudgmentClient(
                [str(self.launcher)], timeout=min(15, seconds)
            ) as client:
                judged = BudgetedJudgment(
                    client,
                    ledger=self.ledger,
                    pricing=self.pricing,
                    trace_root=self.trace_root,
                )
                if kind == "route":
                    arguments = {
                        "items": [{"id": "question", "text": payload["question"]}],
                        "classes": CLASS_CATALOG,
                        "purpose": (
                            "EDA workflow depth; not whether a database "
                            "contains evidence."
                        ),
                        "context": (
                            "Labels advise effort. Fixed scope and "
                            "permissions remain code-owned."
                        ),
                    }
                    response = judged.call("jev_classify", arguments)
                    receipt = cast(dict[str, JsonValue], judged.last_receipt or {})
                    rows = TypeAdapter(list[RouteRow]).validate_python(
                        response["results"]
                    )
                    if len(rows) != 1 or rows[0].id != "question":
                        raise ValueError("route identity changed")
                    row = rows[0]
                    advice = row.model_dump(mode="json")
                    advice["automatic"] = (
                        row.top_probability >= self.threshold
                        and row.margin >= self.margin
                    )
                    advice["fallback_to_main"] = not advice["automatic"]
                    advice["thresholds"] = {
                        "probability": self.threshold,
                        "margin": self.margin,
                    }
                elif kind == "rank":
                    response = judged.call("jev_rerank", payload)
                    receipt = cast(dict[str, JsonValue], judged.last_receipt or {})
                    rows = TypeAdapter(list[RankedRow]).validate_python(
                        response["ranked"]
                    )
                    candidates = cast(list[dict[str, Any]], payload["candidates"])
                    if {row.id for row in rows} != {row["id"] for row in candidates}:
                        raise ValueError("evidence ranking lost candidate identities")
                    advice = {
                        "ranked": [row.model_dump(mode="json") for row in rows],
                        "preserve_all_evidence": True,
                    }
                else:
                    response = judged.call("jev_verify", payload)
                    receipt = cast(dict[str, JsonValue], judged.last_receipt or {})
                    rows = TypeAdapter(list[SupportRow]).validate_python(
                        response["results"]
                    )
                    claims = cast(list[str], payload["claims"])
                    if len(rows) != len(claims):
                        raise ValueError("support review lost claims")
                    advice = {
                        "results": [row.model_dump(mode="json") for row in rows],
                        "advisory_only": True,
                    }
            return JudgmentAdvice(
                kind=kind,
                input_sha256=digest,
                status="available",
                payload=cast(dict[str, JsonValue], advice),
                receipt=receipt,
                seconds=time.monotonic() - started,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            return JudgmentAdvice(
                kind=kind,
                input_sha256=digest,
                status="fallback",
                receipt=receipt,
                error=str(exc),
                seconds=time.monotonic() - started,
            )

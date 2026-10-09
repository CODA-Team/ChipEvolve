"""Optional advice remains replaceable and bounded by the application."""

from typing import Literal, Protocol

from query_agent.domain.evidence import JsonValue
from query_agent.domain.judgment import JudgmentAdvice


class InvestigationJudgmentPort(Protocol):
    def judge(
        self,
        kind: Literal["route", "rank", "verify"],
        payload: dict[str, JsonValue],
        *,
        seconds: float,
    ) -> JudgmentAdvice: ...

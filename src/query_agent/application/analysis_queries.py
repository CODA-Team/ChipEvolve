"""Deterministic mapping from timing questions to analysis operations."""

from __future__ import annotations

import re
from enum import StrEnum


class AnalysisOperation(StrEnum):
    METRIC = "metric"
    PATHS = "paths"


class AnalysisQuestion:
    """Parsed request for the narrow timing-analysis provider port."""

    def __init__(
        self,
        operation: AnalysisOperation,
        *,
        metric_name: str | None = None,
        slack_below: float | None = None,
        limit: int = 10,
    ) -> None:
        self.operation = operation
        self.metric_name = metric_name
        self.slack_below = slack_below
        self.limit = limit

    @property
    def fact_key(self) -> str | None:
        if self.operation is AnalysisOperation.PATHS:
            return None
        return f"analysis:metric:{(self.metric_name or 'UNKNOWN').upper()}"


class AnalysisQuestionParser:
    """Recognize only bounded timing summary and path questions."""

    def parse(self, query: str) -> AnalysisQuestion | None:
        raw = query.strip()
        lower = raw.lower()
        if any(
            token in lower
            for token in (
                "critical path",
                "timing path",
                "path slack",
                "worst path",
                "关键路径",
                "时序路径",
            )
        ):
            return AnalysisQuestion(
                AnalysisOperation.PATHS,
                slack_below=self._slack_threshold(raw),
                limit=1 if "critical path" in lower else 10,
            )
        for metric in ("WNS", "TNS"):
            if metric.lower() in lower and any(
                token in lower for token in ("timing", "analysis", "slack", "negative")
            ):
                return AnalysisQuestion(AnalysisOperation.METRIC, metric_name=metric)
        return None

    @staticmethod
    def _slack_threshold(query: str) -> float | None:
        match = re.search(
            r"slack\s+(?:below|under|less\s+than)\s*(-?\d+(?:\.\d+)?)",
            query,
            flags=re.IGNORECASE,
        )
        return float(match.group(1)) if match is not None else None

"""Deterministic mapping from design questions to typed provider operations."""

from __future__ import annotations

import re
from enum import StrEnum

from query_agent.domain.design import DesignRegion


class DesignOperation(StrEnum):
    INSTANCE = "instance"
    NET = "net"
    PIN = "pin"
    LOCATION = "location"
    FANOUT = "fanout"
    CONNECTIONS = "connections"
    REGION = "region"


class DesignQuestion:
    """A small parsed request for the design-data port."""

    def __init__(
        self,
        operation: DesignOperation,
        name: str,
        region: DesignRegion | None = None,
    ) -> None:
        self.operation = operation
        self.name = name
        self.region = region


class DesignQuestionParser:
    """Recognize only stable object-query forms; no provider names are used."""

    _name = r"([A-Za-z_][A-Za-z0-9_./$:-]*)"

    def parse(self, query: str) -> DesignQuestion | None:
        raw = query.strip()
        region_match = re.search(
            r"instances?\s+(?:are\s+)?(?:in|inside)\s+region\s*"
            r"\(?\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*"
            r"(-?\d+(?:\.\d+)?)\s*[, ]\s*"
            r"(-?\d+(?:\.\d+)?)\s*[, ]\s*"
            r"(-?\d+(?:\.\d+)?)\s*\)?",
            raw,
            flags=re.IGNORECASE,
        )
        if region_match is not None:
            x_min, y_min, x_max, y_max = (
                float(value) for value in region_match.groups()
            )
            return DesignQuestion(
                DesignOperation.REGION,
                "region",
                DesignRegion(
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    units="um",
                ),
            )
        patterns = (
            (
                DesignOperation.FANOUT,
                rf"(?:fanout|drive|drives)\s+(?:of\s+)?net\s+{self._name}",
            ),
            (
                DesignOperation.CONNECTIONS,
                rf"connections?\s+(?:of\s+)?(?:net\s+)?{self._name}",
            ),
            (
                DesignOperation.LOCATION,
                rf"(?:where\s+is|location\s+of)\s+(?:instance|cell)\s+{self._name}",
            ),
            (DesignOperation.INSTANCE, rf"(?:instance|cell)\s+{self._name}"),
            (DesignOperation.NET, rf"net\s+{self._name}"),
            (DesignOperation.PIN, rf"pin\s+{self._name}"),
        )
        for operation, pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match is not None:
                return DesignQuestion(operation, match.group(1))
        return None

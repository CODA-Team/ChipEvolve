"""Locked cost reservations shared by every paid call in one configured run.

An unknown provider settlement continues to consume its reservation. Only
confirmed usage releases the unused portion; no automatic retries hide cost.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from query_agent.domain.errors import LLMContractError


class BudgetExceeded(LLMContractError):
    """The configured provider budget cannot reserve another request."""


class CostLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _update(self, operation: Callable[[dict[str, Any]], None]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ledger = cast(dict[str, Any], json.loads(self.path.read_text()))
            operation(ledger)
            temporary = self.path.with_name(self.path.name + "." + uuid.uuid4().hex)
            with temporary.open("x") as output:
                json.dump(ledger, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.path)

    def reserve(self, provider: str, upper_usd: float) -> str:
        if not math.isfinite(upper_usd) or upper_usd <= 0:
            raise ValueError("reservation must be finite and positive")
        request_id = uuid.uuid4().hex

        def reserve(ledger: dict[str, Any]) -> None:
            if provider not in ledger["limits"]:
                raise BudgetExceeded("provider has no configured budget")
            active = sum(
                float(row["upper_usd"])
                for row in ledger["reservations"]
                if row["provider"] == provider
                and row["status"] in ("reserved", "unknown-settlement")
            )
            remaining = (
                float(ledger["limits"][provider])
                - float(ledger["settled"].get(provider, 0))
                - active
            )
            if upper_usd > remaining:
                raise BudgetExceeded(
                    f"{provider} has insufficient remaining reserved budget"
                )
            ledger["reservations"].append(
                {
                    "id": request_id,
                    "provider": provider,
                    "upper_usd": upper_usd,
                    "status": "reserved",
                }
            )

        self._update(reserve)
        return request_id

    def settle(
        self, request_id: str, *, actual_usd: float, usage: dict[str, Any], model: str
    ) -> None:
        if not math.isfinite(actual_usd) or actual_usd < 0:
            raise ValueError("settled cost must be finite and nonnegative")

        def settle(ledger: dict[str, Any]) -> None:
            row = next(r for r in ledger["reservations"] if r["id"] == request_id)
            if row["status"] == "settled":
                raise ValueError("request is already settled")
            row.update(
                status="settled", actual_usd=actual_usd, usage=usage, model=model
            )
            ledger["settled"][row["provider"]] = (
                float(ledger["settled"].get(row["provider"], 0)) + actual_usd
            )

        self._update(settle)

    def unknown(self, request_id: str, reason: str) -> None:
        def unknown(ledger: dict[str, Any]) -> None:
            row = next(r for r in ledger["reservations"] if r["id"] == request_id)
            if row["status"] != "reserved":
                raise ValueError("only an outstanding request may become unknown")
            row.update(status="unknown-settlement", reason=reason)

        self._update(unknown)

"""Cost-bounded JEV calls through the single configured launcher."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from query_agent.adapters.llm.budget import CostLedger

from .stdio import JudgmentTransportError, StdioJudgmentClient


class BudgetedJudgment:
    def __init__(
        self,
        client: StdioJudgmentClient,
        *,
        ledger: CostLedger,
        trace_root: Path,
        pricing: dict[str, Any] | None,
    ) -> None:
        if pricing is not None and pricing.get("id") != "typesafe/jev-1.13":
            raise ValueError("pricing must describe the fixed JEV model")
        self.client, self.ledger, self.trace_root, self.pricing = (
            client,
            ledger,
            trace_root,
            pricing,
        )
        self.last_receipt: dict[str, Any] | None = None

    def call(
        self,
        tool: str,
        arguments: Mapping[str, object],
        *,
        upper_usd: float = 0.1,
    ) -> dict[str, Any]:
        reservation = self.ledger.reserve("jev", upper_usd)
        folder = self.trace_root / uuid.uuid4().hex
        folder.mkdir(parents=True)
        (folder / "request.json").write_text(
            json.dumps(
                {"tool": tool, "arguments": arguments, "pricing": self.pricing},
                indent=2,
            )
        )
        started = time.monotonic()
        try:
            raw = self.client.call(tool, arguments)
            (folder / "response.json").write_text(json.dumps(raw, indent=2))
            blocks = [
                block["text"]
                for block in raw.get("content", [])
                if block.get("type") == "text"
            ]
            if len(blocks) != 1:
                raise JudgmentTransportError("JEV returned no unique JSON response")
            payload = cast(dict[str, Any], json.loads(blocks[0]))
            model = payload.get("model", "")
            if (
                payload.get("provider") != "openrouter"
                or not isinstance(model, str)
                or not (
                    model == "typesafe/jev-1.13"
                    or model.startswith("typesafe/jev-1.13-")
                )
            ):
                raise JudgmentTransportError(
                    "JEV returned an unapproved provider/model"
                )
            usage = payload.get("usage", {})
            if not all(
                type(usage.get(name)) is int and usage[name] >= 0
                for name in ("input_tokens", "output_tokens")
            ):
                raise JudgmentTransportError("JEV returned no confirmed token usage")
            cost = None
            if self.pricing is not None:
                rates = self.pricing["pricing"]
                cost = (
                    usage["input_tokens"] * float(rates["prompt"])
                    + usage["output_tokens"] * float(rates["completion"])
                    + float(rates.get("request", 0))
                )
                if cost > upper_usd:
                    raise JudgmentTransportError(
                        "reported usage exceeds the reserved quote"
                    )
            self.last_receipt = {
                "model": model,
                "provider": "openrouter",
                "usage": usage,
                "quoted_usage_usd": cost,
                "seconds": time.monotonic() - started,
                "trace": str(folder),
                "reservation": reservation,
                "cost_basis": "confirmed tokens; provider invoice not verified",
            }
            (folder / "receipt.json").write_text(
                json.dumps(self.last_receipt, indent=2)
            )
            if cost is not None:
                self.ledger.settle(
                    reservation, actual_usd=cost, usage=usage, model=model
                )
            else:
                self.ledger.unknown(
                    reservation, "usage known; current quote unavailable"
                )
            return payload
        except (OSError, ValueError, JudgmentTransportError) as exc:
            self.ledger.unknown(reservation, type(exc).__name__)
            (folder / "failure.json").write_text(
                json.dumps(
                    {
                        "error": str(exc),
                        "seconds": time.monotonic() - started,
                        "reservation": reservation,
                    },
                    indent=2,
                )
            )
            raise

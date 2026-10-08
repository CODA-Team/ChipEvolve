"""Official DeepSeek Flash through the existing provider-neutral model port."""

from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from query_agent.domain.errors import LLMContractError
from query_agent.ports.llm import OutputModel

from .budget import CostLedger


class DeepSeekFlashModel:
    def __init__(
        self,
        *,
        config: Path,
        ledger: CostLedger,
        trace_root: Path,
        timeout: float = 120,
        max_output_tokens: int = 4096,
    ) -> None:
        settings = cast(dict[str, Any], json.loads(config.read_text()))
        options = next(
            row for row in settings["models"] if row["model"] == "deepseek-flash"
        )
        secret_path = Path(settings["secret_file"]).expanduser()
        if secret_path.stat().st_mode & 0o077:
            raise LLMContractError("model credential file must be user-only")
        secret = json.loads(secret_path.read_text())
        credentials = [
            row for row in secret["models"] if row["label"] == options["label"]
        ]
        if (
            len(credentials) != 1
            or not isinstance(credentials[0].get("key"), str)
            or not credentials[0]["key"]
        ):
            raise LLMContractError("credential label must resolve to one key")
        self._key = str(credentials[0]["key"])
        self._base_url = str(settings["base_url"]).rstrip("/")
        if self._base_url != "https://api.deepseek.com":
            raise LLMContractError(
                "Flash adapter requires the official DeepSeek endpoint"
            )
        self._options = options.get("request_options", {})
        if set(self._options) - {
            "thinking",
            "reasoning_effort",
            "temperature",
            "top_p",
        }:
            raise LLMContractError(
                "request options may not override model or input/output limits"
            )
        self.ledger, self.trace_root = ledger, trace_root
        self.timeout, self.max_output_tokens = timeout, max_output_tokens
        if not 1 <= max_output_tokens <= 8192:
            raise ValueError("output token budget must be between 1 and 8192")
        self.last_receipt: dict[str, Any] | None = None

    def complete(self, prompt: str, response_model: type[OutputModel]) -> OutputModel:
        schema = response_model.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": "Return JSON matching this schema: " + json.dumps(schema),
            },
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": "deepseek-flash",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_output_tokens,
            **self._options,
        }
        # Bytes plus protocol allowance conservatively bound textual input tokens.
        upper = (
            len(json.dumps(payload).encode()) + 1024
        ) * 0.30 / 1e6 + self.max_output_tokens * 1.20 / 1e6
        reservation = self.ledger.reserve("deepseek-flash", upper)
        folder = self.trace_root / uuid.uuid4().hex
        folder.mkdir(parents=True)
        (folder / "request.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )
        started = time.monotonic()
        request = urllib.request.Request(
            self._base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
            (folder / "response.json").write_bytes(raw)
            result = cast(dict[str, Any], json.loads(raw))
            usage = cast(dict[str, Any], result.get("usage", {}))
            if "prompt_tokens" not in usage or "completion_tokens" not in usage:
                raise LLMContractError("Flash returned no usable billing usage")
            cached = int(usage.get("prompt_cache_hit_tokens", 0))
            total_input, output = (
                int(usage["prompt_tokens"]),
                int(usage["completion_tokens"]),
            )
            actual = (
                (total_input - cached) * 0.30 + cached * 0.006 + output * 1.20
            ) / 1e6
            self.ledger.settle(
                reservation, actual_usd=actual, usage=usage, model=str(result["model"])
            )
        except (OSError, ValueError, KeyError, LLMContractError) as exc:
            self.ledger.unknown(reservation, type(exc).__name__)
            (folder / "error.json").write_text(
                json.dumps(
                    {
                        "error_type": type(exc).__name__,
                        "seconds": time.monotonic() - started,
                        "settlement": "unknown-reservation-retained",
                    }
                )
                + "\n"
            )
            raise LLMContractError(
                f"Flash request failed ({type(exc).__name__}); trace={folder}"
            ) from exc
        self.last_receipt = {
            "model": result["model"],
            "usage": usage,
            "actual_usd": actual,
            "seconds": time.monotonic() - started,
            "trace": str(folder),
            "reservation": reservation,
        }
        (folder / "receipt.json").write_text(
            json.dumps(self.last_receipt, indent=2) + "\n"
        )
        try:
            return response_model.model_validate_json(
                result["choices"][0]["message"]["content"]
            )
        except (KeyError, IndexError, TypeError, ValidationError) as exc:
            raise LLMContractError(
                f"Flash output violates typed schema; trace={folder}"
            ) from exc

"""Deterministic structured LanguageModel test adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from query_agent.domain.errors import LLMContractError
from query_agent.domain.evidence import JsonValue

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class FakeLanguageModel:
    """Return pre-seeded payloads and enforce the requested Pydantic schema."""

    def __init__(self, responses: Mapping[str, Mapping[str, JsonValue]]) -> None:
        self._responses = dict(responses)

    def complete(self, prompt: str, response_model: type[OutputModel]) -> OutputModel:
        payload = self._responses.get(prompt)
        if payload is None:
            raise LLMContractError(f"fake model has no response for prompt {prompt!r}")
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMContractError("language model output violated its schema") from exc

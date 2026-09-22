"""Provider-neutral LanguageModel port."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class LanguageModel(Protocol):
    """Generate schema-validated structured output.

    Concrete SDK types may appear only in ``adapters/llm``. Adapters must raise
    ``LLMContractError`` when the model output cannot be validated.
    """

    def complete(self, prompt: str, response_model: type[OutputModel]) -> OutputModel:
        """Return an instance of the requested Pydantic model."""

        ...

"""Shared structured-output retry loop for LLM providers.

A provider subclass only needs to implement `_call(system_prompt, user_message)`
returning the raw JSON string plus usage. `generate` validates the result
against the given Pydantic schema and, on a ValidationError, retries up to
`max_attempts` times with the validation error appended to the user message.
"""

from __future__ import annotations

import abc
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.schema.providers import Usage

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """Raised when every retry attempt fails schema validation."""


def schema_prompt_hint(schema: type[BaseModel]) -> str:
    """Render a schema's JSON shape for inclusion in a system prompt."""
    return (
        "Respond with a single JSON object matching this JSON Schema exactly, "
        "no prose, no markdown fences:\n"
        f"{schema.model_json_schema()}"
    )


class BaseLLMProvider(abc.ABC):
    max_attempts: int = 3

    @abc.abstractmethod
    async def _call(self, *, system_prompt: str, user_message: str) -> tuple[str, Usage]:
        """Make one raw call to the vendor, returning raw JSON text and usage."""
        raise NotImplementedError

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        schema: type[T],
    ) -> tuple[T, Usage]:
        full_system_prompt = f"{system_prompt}\n\n{schema_prompt_hint(schema)}"
        last_error: Exception | None = None
        message = user_message
        for attempt in range(1, self.max_attempts + 1):
            raw_text, usage = await self._call(
                system_prompt=full_system_prompt, user_message=message
            )
            try:
                data = schema.model_validate_json(raw_text)
                return data, usage
            except (ValidationError, ValueError) as exc:
                last_error = exc
                message = (
                    f"{user_message}\n\n"
                    f"Your previous response failed validation (attempt {attempt}):\n"
                    f"{exc}\n\n"
                    "Return a corrected JSON response that satisfies the schema."
                )
        raise StructuredOutputError(
            f"structured output failed after {self.max_attempts} attempts: {last_error}"
        ) from last_error

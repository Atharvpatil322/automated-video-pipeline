from typing import TypeVar

import pytest
from pydantic import BaseModel

from app.providers.llm.base import BaseLLMProvider
from app.schema.providers import Usage

T = TypeVar("T", bound=BaseModel)

ZERO_USAGE = Usage(input_tokens=0, output_tokens=0)


class ScriptedLLMProvider:
    """Implements the LLMProvider protocol directly: `generate` returns the
    next item from a pre-built queue of Pydantic model instances, regardless
    of the requested schema. Use this for agent/orchestrator tests where the
    retry loop itself isn't under test."""

    def __init__(self, responses: list[BaseModel]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate(
        self, *, system_prompt: str, user_message: str, schema: type[T]
    ) -> tuple[T, Usage]:
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        if not self._responses:
            raise AssertionError("ScriptedLLMProvider ran out of scripted responses")
        return self._responses.pop(0), ZERO_USAGE


class ScriptedRawLLMProvider(BaseLLMProvider):
    """Drives the real retry loop in BaseLLMProvider: `_call` returns the
    next raw JSON string from a queue, so tests can script an invalid
    response followed by a valid one."""

    def __init__(self, raw_responses: list[str]):
        self._raw_responses = list(raw_responses)
        self.call_count = 0

    async def _call(self, *, system_prompt: str, user_message: str) -> tuple[str, Usage]:
        self.call_count += 1
        if not self._raw_responses:
            raise AssertionError("ScriptedRawLLMProvider ran out of scripted responses")
        return self._raw_responses.pop(0), ZERO_USAGE


@pytest.fixture
def scripted_llm():
    return ScriptedLLMProvider


@pytest.fixture
def scripted_raw_llm():
    return ScriptedRawLLMProvider

from __future__ import annotations

from groq import AsyncGroq

from app.providers.llm.base import BaseLLMProvider
from app.schema.providers import Usage

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqLLMProvider(BaseLLMProvider):
    """LLM provider backed by Groq's free-tier OpenAI-compatible API.

    Groq's JSON mode (response_format={"type": "json_object"}) guarantees
    syntactically valid JSON but not schema conformance, so the schema itself
    is still described in the system prompt and the base retry loop handles
    Pydantic validation failures.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def _call(self, *, system_prompt: str, user_message: str) -> tuple[str, Usage]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        return content, usage

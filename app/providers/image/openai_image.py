"""OpenAI image provider using gpt-image-1.

Chosen over gpt-image-2.5-sunburst/flare (newer, as of Oct 2026) for
stability/documentation maturity, and over dall-e-2/3 (deprecated, retiring
May 2026). gpt-image-1 has no `response_format` param - it always returns
base64 (`b64_json`). Portrait size 1024x1536 is the closest standard option
to 1080x1920; the renderer cover-fits/crops to the exact platform size.
"""

import base64

from openai import AsyncOpenAI

DEFAULT_MODEL = "gpt-image-1"
PORTRAIT_SIZE = "1024x1536"


class OpenAIImageProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, style: str | None = None) -> bytes:
        full_prompt = f"{prompt}\n\nStyle: {style}" if style else prompt
        response = await self._client.images.generate(
            model=self._model,
            prompt=full_prompt,
            size=PORTRAIT_SIZE,
            n=1,
        )
        return base64.b64decode(response.data[0].b64_json)

"""VLM verification for stock candidates, via Groq's vision-capable model.

Model choice (qwen/qwen3.8-27b) is confirmed via Groq's vision docs page and
the groq-typescript SDK source (two independent sources, Oct 2026), but not
via a live call - verify before relying on it in production.

Deliberately separate from LLMProvider: that Protocol's generate() takes
only system_prompt/user_message strings and has no way to attach an image,
so a dedicated vision call is used here instead of forcing it through that
interface.
"""

from __future__ import annotations

import base64
import json

from groq import AsyncGroq

from app.schema.visuals import VerificationResult

DEFAULT_MODEL = "qwen/qwen3.8-27b"
CONFIDENCE_THRESHOLD = 0.6

_SYSTEM_PROMPT = (
    "You are judging whether a candidate stock photo/video frame matches a "
    "short-form video scene. Be strict: a toy rocket is not a rocket launch, "
    "a drawing is not a photo of the real thing, unrelated or generic stock "
    "footage should be rejected. Respond with a single JSON object: "
    '{"relevant": bool, "confidence": number 0-1, "reason": string}.'
)


class GroqVisionVerifier:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def verify(
        self, image_bytes: bytes, visual_prompt: str, narration: str
    ) -> VerificationResult:
        data_url = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"
        response = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Scene should show: {visual_prompt}\n"
                                f"Narration: {narration}"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return VerificationResult.model_validate(json.loads(content))

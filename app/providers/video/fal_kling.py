"""Video provider: fal.ai's Kling 2.5 Turbo Pro, image-to-video.

Chosen over Gemini's Veo 3.1 ($0.40/s, confirmed via Gemini pricing docs)
for cost: Kling is $0.35 for 5s then $0.07/s after (~$0.07/s effective),
about 5-6x cheaper, confirmed via fal.ai's model page. Tradeoff: needs its
own API key/SDK (`fal-client`) rather than reusing the google-genai client
already used for images.

Two-step flow, both confirmed via the fal_client SDK source (not just
docs): upload the source image to fal's storage with `client.upload()` to
get a URL (Kling's API takes `image_url`, not raw bytes), then
`client.subscribe()` which polls automatically and returns the result dict.
"""

from __future__ import annotations

import httpx
from fal_client import AsyncClient

MODEL_ID = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
# Kling's documented options; 5s is the base tier, 10s is the other offered duration.
SUPPORTED_DURATIONS = [5.0, 10.0]


class FalKlingVideoProvider:
    supported_durations = SUPPORTED_DURATIONS

    def __init__(self, api_key: str) -> None:
        self._client = AsyncClient(key=api_key)

    async def generate(
        self,
        *,
        source_image: bytes,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        negative_prompt: str | None = None,
    ) -> bytes:
        image_url = await self._client.upload(source_image, content_type="image/png")

        duration_str = "5" if duration_seconds <= 5.0 else "10"
        arguments = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": duration_str,
            "aspect_ratio": aspect_ratio,
        }
        if negative_prompt:
            arguments["negative_prompt"] = negative_prompt

        result = await self._client.subscribe(MODEL_ID, arguments=arguments)
        video_url = result["video"]["url"]

        async with httpx.AsyncClient(timeout=180.0) as http_client:
            response = await http_client.get(video_url)
            response.raise_for_status()
            return response.content

"""Gemini image provider using gemini-2.5-flash-image ("nano banana").

NEEDS LIVE VERIFICATION: Google's own docs page (fetched Oct 2026) describes
a newer `client.interactions.create(...)` endpoint for image generation on
gemini-3.1-flash-image, but that resource does not exist anywhere in the
actual python-genai SDK source (checked models.py / _api_client.py) at the
same date, and Imagen's generate_images is confirmed shut down by the same
docs. Going with the SDK-source-confirmed, long-standing pattern instead:
generate_content() with an image-capable model, reading bytes out of
`candidates[0].content.parts[i].inline_data`. No aspect-ratio parameter for
this call could be confirmed, so portrait framing is requested in the
prompt text itself rather than a structured config field. Verify against
current docs/a real call before relying on this in production.
"""

from google import genai

DEFAULT_MODEL = "gemini-2.5-flash-image"
PORTRAIT_HINT = (
    "Compose for a 1080x1920 vertical 9:16 portrait frame; fill the full "
    "height, nothing important near the far left/right edges."
)


class GeminiImageProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, style: str | None = None) -> bytes:
        full_prompt = f"{prompt}\n\n{PORTRAIT_HINT}"
        if style:
            full_prompt += f"\n\nStyle: {style}"

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=full_prompt,
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data

        raise RuntimeError("Gemini response contained no image data")

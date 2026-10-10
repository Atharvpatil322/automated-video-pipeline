"""OpenAI TTS provider. Returns no word timestamps, same as the reference;
pair it with AlignedTTSProvider to get word timings via WordAligner.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.schema.providers import TTSResult

DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"


class OpenAITTSProvider:
    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, voice: str = DEFAULT_VOICE
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._voice = voice

    async def generate(self, text: str) -> TTSResult:
        response = await self._client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=text,
            response_format="mp3",
        )
        audio = response.read()
        return TTSResult(audio=audio, words=[])

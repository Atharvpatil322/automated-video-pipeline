"""ElevenLabs TTS provider using the /with-timestamps endpoint.

That endpoint returns character-level start/end times; this provider groups
characters into words at each whitespace boundary, same as the reference.
"""

from __future__ import annotations

import base64

import httpx

from app.schema.providers import TTSResult, WordTimestamp

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs' default "Rachel" voice
MODEL_ID = "eleven_multilingual_v2"


def aggregate_characters_to_words(
    characters: list[str], start_times: list[float], end_times: list[float]
) -> list[WordTimestamp]:
    """Group character-level timings into words, splitting on whitespace.

    Whitespace characters are dropped; everything else (including
    punctuation and apostrophes) stays attached to the word it borders, so
    "don't" and "well-known," stay single tokens.
    """
    words: list[WordTimestamp] = []
    buffer = ""
    word_start: float | None = None
    word_end: float | None = None

    for char, start, end in zip(characters, start_times, end_times, strict=True):
        if char.isspace():
            if buffer:
                words.append(WordTimestamp(word=buffer, start=word_start, end=word_end))
                buffer = ""
                word_start = None
                word_end = None
            continue
        if word_start is None:
            word_start = start
        buffer += char
        word_end = end

    if buffer:
        words.append(WordTimestamp(word=buffer, start=word_start, end=word_end))

    return words


class ElevenLabsTTSProvider:
    def __init__(self, api_key: str, voice_id: str = DEFAULT_VOICE_ID) -> None:
        self._api_key = api_key
        self._voice_id = voice_id

    async def generate(self, text: str) -> TTSResult:
        url = API_URL.format(voice_id=self._voice_id)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"xi-api-key": self._api_key},
                json={
                    "text": text,
                    "model_id": MODEL_ID,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            response.raise_for_status()
            payload = response.json()

        audio = base64.b64decode(payload["audio_base64"])
        alignment = payload["alignment"]
        words = aggregate_characters_to_words(
            alignment["characters"],
            alignment["character_start_times_seconds"],
            alignment["character_end_times_seconds"],
        )
        return TTSResult(audio=audio, words=words)

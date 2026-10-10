"""Word-level forced alignment for TTS providers that don't return timings.

GroqWhisperAligner is English-only in practice: whisper-large-v3 and
whisper-large-v3-turbo are multilingual models, but the greedy/substring
matching below assumes the transcript and the known script tokenize the
same way, which holds for English and is not verified for other languages.
"""

from __future__ import annotations

import re
from typing import Protocol

from groq import AsyncGroq

from app.schema.providers import WordTimestamp

DEFAULT_MODEL = "whisper-large-v3-turbo"
LOOKAHEAD = 5
MIN_WORD_DURATION = 0.1
SECONDS_PER_CHAR = 0.06
END_EPSILON = 0.01

_PUNCT_RE = re.compile(r"[^\w']+")


def _normalize(word: str) -> str:
    return _PUNCT_RE.sub("", word).lower()


def align_known_script_to_transcript(
    script_words: list[str],
    transcribed: list[tuple[str, float, float]],
) -> list[WordTimestamp]:
    """Map the KNOWN script words onto transcribed (word, start, end) timings.

    The transcript text itself is never trusted as truth - only its timing.
    For each script word, search a lookahead window of the transcript for an
    exact (normalized) match, then a substring match, advancing a pointer so
    matches stay roughly in order. A script word with no match anywhere in
    the remaining transcript is interpolated: placed right after the
    previous word, with a duration of 60ms per character (100ms minimum).
    """
    results: list[WordTimestamp] = []
    pointer = 0
    previous_end = 0.0

    for script_word in script_words:
        target = _normalize(script_word)
        window = transcribed[pointer : pointer + LOOKAHEAD]

        match_offset = next(
            (i for i, (word, _, _) in enumerate(window) if _normalize(word) == target),
            None,
        )
        if match_offset is None and target:
            match_offset = next(
                (
                    i
                    for i, (word, _, _) in enumerate(window)
                    if target in _normalize(word) or _normalize(word) in target
                ),
                None,
            )

        if match_offset is not None:
            _, start, end = window[match_offset]
            pointer += match_offset + 1
        else:
            start = previous_end
            end = start + max(MIN_WORD_DURATION, len(script_word) * SECONDS_PER_CHAR)

        if end <= start:
            end = start + END_EPSILON

        results.append(WordTimestamp(word=script_word, start=start, end=end))
        previous_end = end

    return results


class WordAligner(Protocol):
    async def align(self, audio: bytes, script_words: list[str]) -> list[WordTimestamp]: ...


class GroqWhisperAligner:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def align(self, audio: bytes, script_words: list[str]) -> list[WordTimestamp]:
        transcription = await self._client.audio.transcriptions.create(
            file=("voiceover.mp3", audio),
            model=self._model,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
        words = getattr(transcription, "words", None) or []
        if not words:
            raise RuntimeError(
                "Groq Whisper returned zero words; refusing to produce broken captions"
            )
        transcribed = [(w.word, w.start, w.end) for w in words]
        return align_known_script_to_transcript(script_words, transcribed)

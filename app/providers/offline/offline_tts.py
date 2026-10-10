"""Deterministic offline TTS fake: silent audio of a plausible duration
(150 words/minute) plus evenly spaced word timestamps. Uses ffmpeg (same
dependency the render stage already requires) rather than hand-rolling a
WAV/MP3 encoder.
"""

import tempfile
from pathlib import Path

from app.render.ffmpeg import run_ffmpeg
from app.schema.providers import TTSResult, WordTimestamp

WORDS_PER_MINUTE = 150


class OfflineTTSProvider:
    async def generate(self, text: str) -> TTSResult:
        words = text.split()
        word_count = max(len(words), 1)
        duration_s = max(word_count / WORDS_PER_MINUTE * 60.0, 1.0)
        slot = duration_s / word_count

        timestamps = [
            WordTimestamp(word=w, start=i * slot, end=(i + 1) * slot)
            for i, w in enumerate(words)
        ]

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "silent.mp3"
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=44100:cl=mono",
                    "-t",
                    str(duration_s),
                    "-c:a",
                    "libmp3lame",
                    str(audio_path),
                ]
            )
            audio_bytes = audio_path.read_bytes()

        return TTSResult(audio=audio_bytes, words=timestamps)

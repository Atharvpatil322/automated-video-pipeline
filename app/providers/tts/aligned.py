from app.providers.tts.aligner import WordAligner
from app.schema.providers import TTSProvider, TTSResult


class AlignedTTSProvider:
    """Wraps any TTSProvider. Passes through native word timestamps if the
    inner provider returned them; otherwise runs a WordAligner over the
    generated audio and the known script text.
    """

    def __init__(self, inner: TTSProvider, aligner: WordAligner) -> None:
        self._inner = inner
        self._aligner = aligner

    async def generate(self, text: str) -> TTSResult:
        result = await self._inner.generate(text)
        if result.words:
            return result
        words = await self._aligner.align(result.audio, text.split())
        return TTSResult(audio=result.audio, words=words)

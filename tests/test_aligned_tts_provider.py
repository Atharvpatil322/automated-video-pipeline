from app.providers.tts.aligned import AlignedTTSProvider
from app.schema.providers import TTSResult, WordTimestamp


class FakeInnerProvider:
    def __init__(self, words: list[WordTimestamp]):
        self._words = words
        self.generate_calls: list[str] = []

    async def generate(self, text: str) -> TTSResult:
        self.generate_calls.append(text)
        return TTSResult(audio=b"fake-audio", words=self._words)


class FakeAligner:
    def __init__(self, words: list[WordTimestamp]):
        self._words = words
        self.align_calls: list[tuple[bytes, list[str]]] = []

    async def align(self, audio: bytes, script_words: list[str]) -> list[WordTimestamp]:
        self.align_calls.append((audio, script_words))
        return self._words


async def test_passes_through_native_words_without_calling_aligner():
    native_words = [WordTimestamp(word="hi", start=0.0, end=0.5)]
    inner = FakeInnerProvider(words=native_words)
    aligner = FakeAligner(words=[])
    provider = AlignedTTSProvider(inner=inner, aligner=aligner)

    result = await provider.generate("hi")

    assert result.words == native_words
    assert aligner.align_calls == []


async def test_calls_aligner_when_inner_provider_returns_no_words():
    aligned_words = [WordTimestamp(word="hi", start=0.0, end=0.5)]
    inner = FakeInnerProvider(words=[])
    aligner = FakeAligner(words=aligned_words)
    provider = AlignedTTSProvider(inner=inner, aligner=aligner)

    result = await provider.generate("hi there")

    assert result.words == aligned_words
    assert len(aligner.align_calls) == 1
    audio_arg, script_words_arg = aligner.align_calls[0]
    assert audio_arg == b"fake-audio"
    assert script_words_arg == ["hi", "there"]


async def test_audio_bytes_are_preserved_through_alignment():
    inner = FakeInnerProvider(words=[])
    aligner = FakeAligner(words=[])
    provider = AlignedTTSProvider(inner=inner, aligner=aligner)

    result = await provider.generate("hi")

    assert result.audio == b"fake-audio"

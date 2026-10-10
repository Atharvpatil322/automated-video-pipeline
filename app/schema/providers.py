"""Provider result types and Protocol interfaces.

Every external capability (LLM, TTS, image, stock, video, music) sits behind
a small Protocol here. The pipeline only ever depends on these, never on a
concrete vendor class. Only LLM is implemented in Phase 1; the rest are
declared now so later phases and the factory can type against them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class LLMResult(BaseModel):
    data: dict
    usage: Usage


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float


class TTSResult(BaseModel):
    audio: bytes
    words: list[WordTimestamp]


class StockCandidate(BaseModel):
    id: str
    provider: str
    url: str
    preview_url: str
    width: int
    height: int
    duration: float | None = None
    attribution: str | None = None


class StockAsset(BaseModel):
    file_path: str
    width: int
    height: int
    duration: float | None = None
    attribution: str | None = None


class MusicResult(BaseModel):
    file_path: str
    duration_seconds: float | None = None
    metadata: dict | None = None


class LLMProvider(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        schema: type[T],
    ) -> tuple[T, Usage]:
        """Make one structured-output call, validated against `schema`."""
        ...


class TTSProvider(Protocol):
    async def generate(self, text: str) -> TTSResult: ...


class ImageProvider(Protocol):
    async def generate(self, prompt: str, style: str | None = None) -> bytes: ...


class StockProvider(Protocol):
    async def search_video(self, query: str) -> list[StockCandidate]: ...
    async def search_image(self, query: str) -> list[StockCandidate]: ...
    async def download(self, candidate: StockCandidate, dest_path: Path) -> StockAsset:
        """Download `candidate` to `dest_path` and return its StockAsset."""
        ...


class VideoProvider(Protocol):
    supported_durations: list[float]

    async def generate(
        self,
        *,
        source_image: bytes,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        negative_prompt: str | None = None,
    ) -> bytes: ...


class MusicProvider(Protocol):
    async def generate(self, prompt: str, mood: str) -> MusicResult: ...

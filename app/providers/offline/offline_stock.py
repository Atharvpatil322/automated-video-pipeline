"""Deterministic offline stock fake: a small pool of locally generated
sample images/clips (lazily created once, cached under the system temp
dir), returned as "search results" regardless of query. Verification of
these candidates is handled separately by OfflineVisionVerifier (always
accepts), matching the reference's "stock, free" path with nothing real
to search.
"""

import shutil
import tempfile
from pathlib import Path

from app.render.ffmpeg import run_ffmpeg
from app.schema.providers import StockAsset, StockCandidate

WIDTH, HEIGHT = 1080, 1920
PROVIDER_NAME = "offline"
_SAMPLE_COLORS = ["0x4E6B8C", "0x8C4E6B", "0x6B8C4E"]


def _cache_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "video_pipeline_offline_stock"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _ensure_sample_images(cache_dir: Path) -> list[Path]:
    paths = []
    for i, color in enumerate(_SAMPLE_COLORS):
        path = cache_dir / f"sample-image-{i}.jpg"
        if not path.exists():
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s={WIDTH}x{HEIGHT}",
                    "-frames:v",
                    "1",
                    str(path),
                ]
            )
        paths.append(path)
    return paths


def _ensure_sample_video(cache_dir: Path) -> Path:
    path = cache_dir / "sample-video-0.mp4"
    if not path.exists():
        run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=0x4E4E4E:s={WIDTH}x{HEIGHT}:d=4:r=30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ]
        )
    return path


class OfflineStockProvider:
    def __init__(self) -> None:
        self._cache_dir = _cache_dir()

    async def search_image(self, query: str) -> list[StockCandidate]:
        paths = _ensure_sample_images(self._cache_dir)
        return [
            StockCandidate(
                id=f"offline-img-{i}",
                provider=PROVIDER_NAME,
                url=str(path),
                preview_url=str(path),
                width=WIDTH,
                height=HEIGHT,
                attribution="offline sample image (not real stock footage)",
            )
            for i, path in enumerate(paths)
        ]

    async def search_video(self, query: str) -> list[StockCandidate]:
        path = _ensure_sample_video(self._cache_dir)
        return [
            StockCandidate(
                id="offline-video-0",
                provider=PROVIDER_NAME,
                url=str(path),
                preview_url=str(path),
                width=WIDTH,
                height=HEIGHT,
                duration=4.0,
                attribution="offline sample video (not real stock footage)",
            )
        ]

    async def download(self, candidate: StockCandidate, dest_path: Path) -> StockAsset:
        shutil.copyfile(candidate.url, dest_path)
        return StockAsset(
            file_path=str(dest_path),
            width=candidate.width,
            height=candidate.height,
            duration=candidate.duration,
            attribution=candidate.attribution,
        )

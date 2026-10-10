"""Deterministic offline video fake: ffmpeg loops the still image (phase 1
of the two-phase ai_video flow) into a short silent clip, rather than
calling a real image-to-video model.
"""

import tempfile
from pathlib import Path

from app.render.ffmpeg import run_ffmpeg

SUPPORTED_DURATIONS = [5.0, 10.0]


class OfflineVideoProvider:
    supported_durations = SUPPORTED_DURATIONS

    async def generate(
        self,
        *,
        source_image: bytes,
        prompt: str,
        duration_seconds: float,
        aspect_ratio: str,
        negative_prompt: str | None = None,
    ) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "source.png"
            image_path.write_bytes(source_image)
            video_path = Path(tmp) / "offline.mp4"
            run_ffmpeg(
                [
                    "-loop",
                    "1",
                    "-i",
                    str(image_path),
                    "-t",
                    str(duration_seconds),
                    "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(video_path),
                ]
            )
            return video_path.read_bytes()

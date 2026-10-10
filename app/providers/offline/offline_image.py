"""Deterministic offline image fake: a portrait PNG with the prompt text
burned in via ffmpeg drawtext, so a generated frame is visibly traceable
back to the scene that produced it. (The scene number itself lands in the
filename - `scene-<n>-ai.png` - rather than in the pixels, since
ImageProvider.generate() only receives the prompt string, not the index.)
"""

import tempfile
from pathlib import Path

from app.render.ffmpeg import default_font_file, escape_for_filter, run_ffmpeg

WIDTH, HEIGHT = 1080, 1920


class OfflineImageProvider:
    async def generate(self, prompt: str, style: str | None = None) -> bytes:
        safe_text = prompt.replace("'", "’").replace(":", "\\:")[:120]
        font_file = default_font_file()
        font_clause = f"fontfile='{escape_for_filter(font_file)}':" if font_file else ""
        drawtext = (
            f"drawtext=text='{safe_text}':{font_clause}fontcolor=white:fontsize=36:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=10:box=1:boxcolor=black@0.5:boxborderw=10"
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "offline.png"
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x2A3F54:s={WIDTH}x{HEIGHT}",
                    "-vf",
                    drawtext,
                    "-frames:v",
                    "1",
                    str(output_path),
                ]
            )
            return output_path.read_bytes()

"""Placeholder asset generation, so assembly can be exercised end to end
before Phase 3 (visuals) exists. Not used once real asset resolution lands.
"""

from pathlib import Path

from app.render.ffmpeg import run_ffmpeg
from app.schema.director import DirectorScore, VisualType

_PLACEHOLDER_COLORS = ["0x3366CC", "0xCC6633", "0x33CC66", "0xCC3399", "0x999933"]


def generate_fixture_assets(score: DirectorScore, assets_dir: Path) -> list[str | None]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_paths: list[str | None] = []

    for i, scene in enumerate(score.scenes):
        color = _PLACEHOLDER_COLORS[i % len(_PLACEHOLDER_COLORS)]

        if scene.visual_type == VisualType.TEXT_CARD:
            asset_paths.append(None)
            continue

        if scene.visual_type in (VisualType.AI_IMAGE, VisualType.STOCK_IMAGE):
            path = assets_dir / f"scene-{i}-fixture.png"
            run_ffmpeg(
                ["-f", "lavfi", "-i", f"color=c={color}:s=1080x1920", "-frames:v", "1", str(path)]
            )
        else:  # ai_video, stock_video
            path = assets_dir / f"scene-{i}-fixture.mp4"
            run_ffmpeg(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s=1080x1920:d=3:r=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(path),
                ]
            )
        asset_paths.append(str(path))

    return asset_paths

"""Offline music: a generated sine-wave tone, lazily created once and
cached under the system temp dir - never committed to the repo, matching
the real bundled-music manifest's own "no copyrighted audio committed"
rule. One manifest entry per mood, all pointing at the same tone file, so
resolve_music's mood lookup works regardless of which mood the plan picked.
"""

import tempfile
from pathlib import Path

from app.pipeline.music import MusicManifestEntry
from app.render.ffmpeg import run_ffmpeg

TONE_FILENAME = "offline-tone.mp3"

_MUSIC_MOODS = [
    "epic_cinematic",
    "tense_electronic",
    "chill_lofi",
    "uplifting_pop",
    "mysterious_ambient",
    "warm_acoustic",
    "dark_cinematic",
    "dreamy_ethereal",
]


def offline_music_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / "video_pipeline_offline_music"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tone_path = cache_dir / TONE_FILENAME
    if not tone_path.exists():
        run_ffmpeg(
            [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=220:duration=60",
                "-c:a",
                "libmp3lame",
                str(tone_path),
            ]
        )
    return cache_dir


def offline_music_manifest() -> list[MusicManifestEntry]:
    return [
        MusicManifestEntry(
            id=f"offline-{mood}",
            mood=mood,
            filename=TONE_FILENAME,
            duration=60.0,
            source="generated sine tone, not committed",
            license="n/a (offline placeholder)",
        )
        for mood in _MUSIC_MOODS
    ]

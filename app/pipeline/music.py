"""Bundled background music resolution.

`resolve_music` never raises: a missing manifest, an unknown mood, or every
candidate file being absent on disk all just mean "no music" (None), same
as the reference's `resolveMusic`. No real audio is bundled in this repo -
`assets/music/manifest.json` lists tracks by filename, and
`validate_manifest` only warns (at startup) about files that don't exist.
"""

import json
import random
from pathlib import Path

from pydantic import BaseModel

DEFAULT_MANIFEST_PATH = Path(__file__).parent.parent.parent / "assets" / "music" / "manifest.json"
DEFAULT_MUSIC_DIR = DEFAULT_MANIFEST_PATH.parent


class MusicManifestEntry(BaseModel):
    id: str
    mood: str
    filename: str
    duration: float | None = None
    source: str | None = None
    license: str | None = None


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> list[MusicManifestEntry]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    return [MusicManifestEntry.model_validate(entry) for entry in raw]


def validate_manifest(manifest: list[MusicManifestEntry], music_dir: Path) -> list[str]:
    """Return a warning string per manifest entry whose file is missing.
    Never raises - matches the reference, which only warns at worker start.
    """
    warnings = []
    for entry in manifest:
        if not (music_dir / entry.filename).exists():
            warnings.append(f"music track '{entry.id}' missing on disk: {entry.filename}")
    return warnings


def resolve_music(
    mood: str,
    *,
    no_music: bool = False,
    manifest: list[MusicManifestEntry] | None = None,
    music_dir: Path = DEFAULT_MUSIC_DIR,
    rng: random.Random | None = None,
) -> Path | None:
    if no_music:
        return None

    manifest = load_manifest() if manifest is None else manifest
    if not manifest:
        return None

    rng = rng or random.Random()

    candidates = [entry for entry in manifest if entry.mood == mood]
    if not candidates:
        candidates = list(manifest)  # fall back to any track, any mood

    # Prefer a track that actually exists on disk; shuffle so repeated
    # calls don't always pick the same fallback when several are missing.
    shuffled = candidates.copy()
    rng.shuffle(shuffled)
    for entry in shuffled:
        path = music_dir / entry.filename
        if path.exists():
            return path

    return None

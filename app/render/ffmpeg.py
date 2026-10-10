"""Thin subprocess wrapper around the ffmpeg/ffprobe CLI binaries."""

import os
import shutil
import subprocess
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    pass


class FFmpegError(RuntimeError):
    pass


# drawtext needs a font. By default it resolves one through fontconfig,
# which this environment (and plenty of minimal Docker images) doesn't
# have configured, producing "Fontconfig error: Cannot load default config
# file" - found by actually running an offline end-to-end render, not by
# inspection. `fontfile=` bypasses fontconfig entirely by pointing at a
# real file on disk, so we look for one up front rather than depending on
# font-name resolution (`font=Space Grotesk` etc.) being available at all.
_CANDIDATE_FONT_FILES = [
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def default_font_file() -> str | None:
    """A real font file path for ffmpeg's `fontfile=`, or None if none of
    the common system locations exist (caller falls back to `font=` by
    name, which needs fontconfig and may not work).
    """
    for candidate in _CANDIDATE_FONT_FILES:
        if Path(candidate).exists():
            return candidate
    return None


def escape_for_filter(path: str) -> str:
    """A path for use inside an ffmpeg filter argument's value.

    Tried colon-escaping (`\\:`) and quoting (`'...'`) for a Windows
    drive-letter colon first - neither parses in this ffmpeg build's
    filtergraph parser (confirmed by actually running it, not by reading
    docs). The reliable fix is to avoid the colon altogether: express the
    path relative to the current working directory (which is also
    ffmpeg's cwd, since run_ffmpeg never changes it) whenever that's
    possible - i.e. same drive on Windows. Falls back to colon-escaping
    for the rare case for a different drive, which may still not parse.
    """
    posix = path.replace("\\", "/")
    try:
        relative = os.path.relpath(posix, start=os.getcwd())
        return relative.replace("\\", "/")
    except ValueError:
        return posix.replace(":", "\\:")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotFoundError(
            "ffmpeg was not found on PATH. Install it and make sure 'ffmpeg' "
            "is runnable from a shell before rendering."
        )


def run_ffmpeg(args: list[str]) -> None:
    require_ffmpeg()
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed (exit {result.returncode}): {result.stderr.strip()}")


def probe_duration_seconds(path: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise FFmpegNotFoundError("ffprobe was not found on PATH.")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {result.stderr.strip()}")
    return float(result.stdout.strip())

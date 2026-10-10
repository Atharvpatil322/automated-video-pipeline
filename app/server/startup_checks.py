"""Fail fast, with a clear message, rather than let the first job die deep
inside a render call because the container image is missing ffmpeg or any
usable font. Both the api and worker containers run this at startup -
cheap, and whichever process would otherwise be the one to discover the
problem (the worker, usually, well into a job) is no longer the first to
find out.
"""

from app.render.ffmpeg import FFmpegNotFoundError, default_font_file, require_ffmpeg


def check_render_dependencies() -> None:
    try:
        require_ffmpeg()
    except FFmpegNotFoundError as exc:
        raise RuntimeError(
            "Startup check failed: ffmpeg is not installed or not on PATH. "
            "Install ffmpeg (see README) before starting this service."
        ) from exc

    if default_font_file() is None:
        raise RuntimeError(
            "Startup check failed: no usable font file found for ffmpeg's drawtext/ass "
            "filters (checked common system font paths). Install a font package "
            "(e.g. fonts-dejavu-core on Debian/Ubuntu) before starting this service."
        )

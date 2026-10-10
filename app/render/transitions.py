"""Transition -> FFmpeg `xfade` filter type mapping.

xfade's built-in types (see https://ffmpeg.org/ffmpeg-filters.html#xfade)
don't include a 3D flip/rotation, so `flip` has no exact equivalent:
mapped to `squeezeh` (a horizontal squeeze-then-reveal) as the closest
available dynamic approximation. Documented here rather than silently
guessed, per the brief.
"""

from app.schema.director import Transition

XFADE_TYPE: dict[Transition, str | None] = {
    Transition.NONE: None,  # hard cut; handled as a plain concat, not xfade
    Transition.CROSSFADE: "fade",
    Transition.SLIDE_LEFT: "slideleft",
    Transition.SLIDE_RIGHT: "slideright",
    Transition.WIPE: "wipeleft",
    Transition.FLIP: "squeezeh",  # approximation - no exact equivalent, see module docstring
}


def xfade_type_for(transition: Transition) -> str | None:
    return XFADE_TYPE[transition]

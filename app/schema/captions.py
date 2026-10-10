from enum import StrEnum


class CaptionStyle(StrEnum):
    BOLD_OUTLINE = "bold_outline"
    COLOR_HIGHLIGHT = "color_highlight"
    CLEAN = "clean"
    KARAOKE_SWEEP = "karaoke_sweep"
    GRADIENT_RISE = "gradient_rise"
    BLOCK_IMPACT = "block_impact"
    BOX_HIGHLIGHT = "box_highlight"


class WordState(StrEnum):
    UNSPOKEN = "unspoken"
    ACTIVE = "active"
    SPOKEN = "spoken"

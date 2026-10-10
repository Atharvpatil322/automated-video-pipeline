from typing import Literal

from pydantic import BaseModel

from app.schema.captions import CaptionStyle
from app.schema.director import Transition

PacingTier = Literal["fast", "moderate", "cinematic"]


class ColorPalette(BaseModel):
    background: str
    accent: str
    text: str


class ArchetypeConfig(BaseModel):
    """Archetype fields: pacing drives the director, the renderer-phase
    fields drive captions/text-card/transitions, and the visuals-phase
    fields below are the "style bible" injected into the image prompter so
    every scene looks consistent without the director repeating style words.
    """

    key: str
    scene_pacing: PacingTier

    caption_style: CaptionStyle = CaptionStyle.CLEAN
    caption_chunk_size: int = 5
    caption_linger_s: float = 0.3

    color_palette: ColorPalette = ColorPalette(
        background="#000000", accent="#FFFFFF", text="#FFFFFF"
    )
    text_card_font: str = "Inter"
    motion_intensity: float = 1.0

    default_transition: Transition = Transition.NONE
    transition_duration_frames: int = 15

    art_style: str = ""
    lighting: str = ""
    composition_rules: str = ""
    cultural_markers: str = ""
    mood: str = ""
    anti_artifact_guidance: str = ""
    visual_color_palette: list[str] = []

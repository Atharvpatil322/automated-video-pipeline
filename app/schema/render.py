from pydantic import BaseModel

from app.config.archetype import ColorPalette
from app.schema.captions import CaptionStyle
from app.schema.director import Motion, Transition, VisualType
from app.schema.providers import WordTimestamp


class SceneRenderSpec(BaseModel):
    index: int
    visual_type: VisualType
    asset_path: str | None
    motion: Motion
    script_line: str
    start_frame: int
    duration_frames: int
    transition: Transition
    transition_duration_frames: int


class RenderSpec(BaseModel):
    scenes: list[SceneRenderSpec]
    total_frames: int
    fps: int
    width: int
    height: int
    words: list[WordTimestamp]
    caption_style: CaptionStyle
    caption_chunk_size: int
    caption_linger_s: float
    color_palette: ColorPalette
    text_card_font: str
    motion_intensity: float
    voiceover_path: str | None = None
    music_path: str | None = None

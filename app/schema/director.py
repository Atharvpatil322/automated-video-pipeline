from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class VisualType(StrEnum):
    AI_IMAGE = "ai_image"
    AI_VIDEO = "ai_video"
    STOCK_IMAGE = "stock_image"
    STOCK_VIDEO = "stock_video"
    TEXT_CARD = "text_card"


class Motion(StrEnum):
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_RIGHT = "pan_right"
    PAN_LEFT = "pan_left"
    STATIC = "static"


class Transition(StrEnum):
    NONE = "none"
    CROSSFADE = "crossfade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    WIPE = "wipe"
    FLIP = "flip"


class MusicMood(StrEnum):
    EPIC_CINEMATIC = "epic_cinematic"
    TENSE_ELECTRONIC = "tense_electronic"
    CHILL_LOFI = "chill_lofi"
    UPLIFTING_POP = "uplifting_pop"
    MYSTERIOUS_AMBIENT = "mysterious_ambient"
    WARM_ACOUSTIC = "warm_acoustic"
    DARK_CINEMATIC = "dark_cinematic"
    DREAMY_ETHEREAL = "dreamy_ethereal"


class Scene(BaseModel):
    visual_type: VisualType
    visual_prompt: str = Field(min_length=1)
    motion: Motion
    script_line: str = Field(min_length=1)
    transition: Transition | None = None

    @model_validator(mode="after")
    def ai_video_motion_is_static(self) -> "Scene":
        if self.visual_type == VisualType.AI_VIDEO and self.motion != Motion.STATIC:
            raise ValueError("motion must be 'static' for ai_video scenes")
        return self


class DirectorScore(BaseModel):
    emotional_arc: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    music_mood: MusicMood
    scenes: list[Scene] = Field(min_length=3, max_length=16)

    @model_validator(mode="after")
    def golden_rule_no_more_than_two_consecutive_same_type(self) -> "DirectorScore":
        run_type: VisualType | None = None
        run_length = 0
        for i, scene in enumerate(self.scenes):
            if scene.visual_type == run_type:
                run_length += 1
            else:
                run_type = scene.visual_type
                run_length = 1
            if run_length > 2:
                raise ValueError(
                    f"golden rule violated: scene {i} is the 3rd consecutive "
                    f"'{scene.visual_type.value}' scene"
                )
        return self

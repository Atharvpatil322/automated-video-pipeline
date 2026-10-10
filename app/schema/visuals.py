from typing import Literal

from pydantic import BaseModel, Field

from app.schema.director import Motion, VisualType

SceneVisualStatus = Literal["generated", "fallback", "failed", "no_asset"]

ResolutionMethod = Literal[
    "text_card",
    "ai_image",
    "stock_verified",
    "stock_unverified",
    "ai_fallback",
    "video_generated",
    "video_fallback_still",
]


class ImagePromptResult(BaseModel):
    prompt: str = Field(min_length=1)


class QueryReformulationResult(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)


class VerificationResult(BaseModel):
    relevant: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class SceneVisualResult(BaseModel):
    scene_index: int
    # The actual resolved asset type (e.g. a stock_image scene that fell back
    # to AI image reports `ai_image` here) - the renderer should trust this
    # over the director's original scene.visual_type.
    visual_type: VisualType
    path: str | None
    status: SceneVisualStatus
    attempts: int
    fallback_reason: str | None = None
    method: ResolutionMethod | None = None
    provider: str | None = None
    query: str | None = None
    confidence: float | None = None
    attribution: str | None = None
    motion_override: Motion | None = None


class VisualsResult(BaseModel):
    scenes: list[SceneVisualResult]

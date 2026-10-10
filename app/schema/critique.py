from pydantic import BaseModel, Field


class CritiqueResult(BaseModel):
    score: float = Field(ge=1, le=10)
    strengths: list[str]
    weaknesses: list[str]
    revision_needed: bool
    revision_instructions: str | None = None
    weakest_scene_index: int | None = Field(default=None, ge=0)

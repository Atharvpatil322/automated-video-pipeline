"""Job state as stored in MongoDB - the source of truth for the API.
Redis is transport only (queue + pub/sub), never read back for state.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore
from app.schema.research import ResearchResult

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
StageName = Literal["research", "director", "tts", "visuals", "assembly", "critic"]
StageStatus = Literal["pending", "running", "completed", "skipped", "error"]

ALL_STAGES: tuple[StageName, ...] = (
    "research",
    "director",
    "tts",
    "visuals",
    "assembly",
    "critic",
)


class StageRecord(BaseModel):
    status: StageStatus = "pending"
    detail: dict[str, Any] | None = None
    reason: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    duration_s: float | None = None


class JobOptions(BaseModel):
    topic: str
    archetype: str = "infographic"
    platform: str = "youtube"
    direction: str | None = None
    tts_provider: str = "elevenlabs"
    image_provider: str = "openai"
    no_tts: bool = False
    no_visuals: bool = False
    no_video: bool = False
    no_music: bool = False
    no_critic: bool = False
    score: DirectorScore | None = None  # supplied for replay


class JobDocument(BaseModel):
    id: str
    status: JobStatus = "queued"
    options: JobOptions
    stages: dict[StageName, StageRecord] = Field(
        default_factory=lambda: {name: StageRecord() for name in ALL_STAGES}
    )
    score: DirectorScore | None = None
    research: ResearchResult | None = None
    review: CritiqueResult | None = None
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    cost_estimate: dict[str, Any] | None = None
    cost_actual: dict[str, Any] | None = None
    cancel_requested: bool = False
    error: str | None = None
    run_dir: str | None = None  # relative to the jobs directory
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobCreateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    archetype: str = "infographic"
    platform: str = "youtube"
    direction: str | None = Field(default=None, max_length=10_000)
    tts_provider: str = "elevenlabs"
    image_provider: str = "openai"
    no_tts: bool = False
    no_visuals: bool = False
    no_video: bool = False
    no_music: bool = False
    no_critic: bool = False
    score: DirectorScore | None = None
    keys: dict[str, str] = Field(default_factory=dict)


class JobCreateResponse(BaseModel):
    id: str
    topic: str
    archetype: str
    status: JobStatus


class JobSummary(BaseModel):
    id: str
    status: JobStatus
    topic: str
    created_at: datetime
    updated_at: datetime

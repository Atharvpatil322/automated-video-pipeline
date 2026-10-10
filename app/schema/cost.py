from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    llm: float = 0.0
    tts: float = 0.0
    images: float = 0.0
    video: float = 0.0
    stock: float = 0.0
    vlm: float = 0.0

    @property
    def total(self) -> float:
        return self.llm + self.tts + self.images + self.video + self.stock + self.vlm


class CostEstimate(BaseModel):
    breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    notes: list[str] = Field(default_factory=list)

    @property
    def total(self) -> float:
        return self.breakdown.total


class CostActual(BaseModel):
    breakdown: CostBreakdown = Field(default_factory=CostBreakdown)

    @property
    def total(self) -> float:
        return self.breakdown.total

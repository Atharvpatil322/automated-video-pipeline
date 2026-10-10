from pydantic import BaseModel, Field


class ResearchResult(BaseModel):
    summary: str = Field(min_length=1)
    key_facts: list[str]
    mood: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)

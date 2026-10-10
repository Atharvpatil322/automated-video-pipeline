import pytest
from pydantic import ValidationError

from app.schema.research import ResearchResult


def test_valid_research_result():
    result = ResearchResult(
        summary="A short summary.",
        key_facts=["fact one", "fact two"],
        mood="inspiring",
        sources=[],
    )
    assert result.mood == "inspiring"


def test_summary_cannot_be_empty():
    with pytest.raises(ValidationError):
        ResearchResult(summary="", key_facts=[], mood="inspiring", sources=[])


def test_sources_defaults_to_empty_list():
    result = ResearchResult(summary="s", key_facts=[], mood="m")
    assert result.sources == []

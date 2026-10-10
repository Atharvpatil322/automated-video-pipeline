from app.agents.research import research
from app.schema.research import ResearchResult


async def test_research_returns_parsed_result(scripted_llm):
    expected = ResearchResult(summary="s", key_facts=["f1"], mood="curious", sources=[])
    llm = scripted_llm([expected])

    result, usage = await research("some topic", llm)

    assert result == expected
    assert "some topic" in llm.calls[0]["user_message"]

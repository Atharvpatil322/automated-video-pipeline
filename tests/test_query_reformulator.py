from app.agents.query_reformulator import reformulate_query
from app.schema.visuals import QueryReformulationResult


async def test_returns_list_of_queries_and_usage(scripted_llm):
    llm = scripted_llm(
        [QueryReformulationResult(queries=["a dog", "a park bench", "autumn trees"])]
    )

    queries, usage = await reformulate_query("a happy dog running in a park", llm)

    assert queries == ["a dog", "a park bench", "autumn trees"]
    assert usage is not None


async def test_original_query_is_in_the_message(scripted_llm):
    llm = scripted_llm([QueryReformulationResult(queries=["x"])])

    await reformulate_query("a happy dog running in a park", llm)

    assert "a happy dog running in a park" in llm.calls[0]["user_message"]

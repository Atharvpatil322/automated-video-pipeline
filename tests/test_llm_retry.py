import pytest

from app.providers.llm.base import StructuredOutputError
from app.schema.research import ResearchResult


async def test_retries_once_on_validation_error_then_succeeds(scripted_raw_llm):
    invalid_json = '{"summary": "", "key_facts": [], "mood": "x", "sources": []}'
    valid_json = '{"summary": "ok", "key_facts": [], "mood": "x", "sources": []}'
    provider = scripted_raw_llm([invalid_json, valid_json])

    data, usage = await provider.generate(
        system_prompt="sys", user_message="topic: x", schema=ResearchResult
    )

    assert data.summary == "ok"
    assert provider.call_count == 2


async def test_second_attempt_message_includes_validation_error(scripted_raw_llm):
    invalid_json = '{"summary": "", "key_facts": [], "mood": "x", "sources": []}'
    valid_json = '{"summary": "ok", "key_facts": [], "mood": "x", "sources": []}'
    provider = scripted_raw_llm([invalid_json, valid_json])

    captured_messages = []
    original_call = provider._call

    async def spy_call(*, system_prompt, user_message):
        captured_messages.append(user_message)
        return await original_call(system_prompt=system_prompt, user_message=user_message)

    provider._call = spy_call

    await provider.generate(system_prompt="sys", user_message="topic: x", schema=ResearchResult)

    assert captured_messages[0] == "topic: x"
    assert "failed validation" in captured_messages[1]


async def test_raises_structured_output_error_after_max_attempts(scripted_raw_llm):
    always_invalid = '{"summary": "", "key_facts": [], "mood": "x", "sources": []}'
    provider = scripted_raw_llm([always_invalid] * 3)

    with pytest.raises(StructuredOutputError):
        await provider.generate(system_prompt="sys", user_message="topic: x", schema=ResearchResult)

    assert provider.call_count == 3

from app.agents.video_prompter import generate_motion_prompt
from app.schema.visuals import ImagePromptResult


async def test_returns_prompt_string_and_usage(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="slow push in, gentle handheld drift")])

    prompt, usage = await generate_motion_prompt("a dog in a park", "narration line", llm)

    assert prompt == "slow push in, gentle handheld drift"
    assert usage is not None


async def test_scene_and_narration_appear_in_message(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="x")])

    await generate_motion_prompt("a dog in a park", "the dog runs happily", llm)

    message = llm.calls[0]["user_message"]
    assert "a dog in a park" in message
    assert "the dog runs happily" in message

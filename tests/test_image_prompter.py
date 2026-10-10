from app.agents.image_prompter import optimize_image_prompt
from app.config.archetype import ArchetypeConfig
from app.schema.visuals import ImagePromptResult


def make_archetype() -> ArchetypeConfig:
    return ArchetypeConfig(
        key="test",
        scene_pacing="fast",
        art_style="flat vector illustration",
        lighting="even flat lighting",
        composition_rules="centered subject",
        cultural_markers="neutral",
        mood="confident",
        anti_artifact_guidance="no extra limbs",
        visual_color_palette=["#000000", "#FFFFFF"],
    )


async def test_returns_prompt_string_and_usage(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="a rewritten prompt")])

    prompt, usage = await optimize_image_prompt(
        "a dog in a park", "narration", make_archetype(), llm
    )

    assert prompt == "a rewritten prompt"
    assert usage is not None


async def test_style_bible_fields_appear_in_the_message(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="x")])

    await optimize_image_prompt("a dog in a park", "narration", make_archetype(), llm)

    message = llm.calls[0]["user_message"]
    assert "flat vector illustration" in message
    assert "even flat lighting" in message
    assert "no extra limbs" in message


async def test_safety_feedback_is_included_when_provided(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="x")])

    await optimize_image_prompt(
        "a dog in a park",
        "narration",
        make_archetype(),
        llm,
        safety_feedback="rejected: violence",
    )

    message = llm.calls[0]["user_message"]
    assert "rejected for safety reasons" in message
    assert "rejected: violence" in message


async def test_no_safety_feedback_by_default(scripted_llm):
    llm = scripted_llm([ImagePromptResult(prompt="x")])

    await optimize_image_prompt("a dog in a park", "narration", make_archetype(), llm)

    message = llm.calls[0]["user_message"]
    assert "rejected for safety" not in message

import pytest

from app.agents.director import director_generate, director_revise
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.research import ResearchResult


def make_score(archetype: str = "infographic") -> DirectorScore:
    def scene(visual_type: VisualType) -> Scene:
        return Scene(
            visual_type=visual_type,
            visual_prompt="headline",
            motion=Motion.STATIC,
            script_line="line",
            transition=Transition.NONE,
        )

    return DirectorScore(
        emotional_arc="curiosity-to-wisdom",
        archetype=archetype,
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD),
            scene(VisualType.STOCK_IMAGE),
            scene(VisualType.TEXT_CARD),
        ],
    )


async def test_director_generate_raises_on_unknown_archetype(scripted_llm):
    llm = scripted_llm([make_score()])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])

    with pytest.raises(ValueError, match="unknown archetype"):
        await director_generate("topic", research_result, "not-a-real-archetype", llm)


async def test_director_generate_includes_pacing_in_prompt(scripted_llm):
    llm = scripted_llm([make_score()])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])

    await director_generate("topic", research_result, "infographic", llm)

    assert "fast" in llm.calls[0]["user_message"]


async def test_director_revise_forces_archetype_back_to_original(scripted_llm):
    drifted = make_score(archetype="warm_editorial")
    llm = scripted_llm([drifted])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])
    original = make_score(archetype="infographic")

    revised, _ = await director_revise(
        original, ["weak hook"], "sharpen the hook", research_result, llm
    )

    assert revised.archetype == "infographic"

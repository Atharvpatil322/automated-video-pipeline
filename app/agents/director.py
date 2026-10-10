from pathlib import Path

from app.config.pacing import pacing_instruction
from app.config.playbook import load_full_playbook
from app.config.registry import get_archetype
from app.schema.director import DirectorScore
from app.schema.providers import LLMProvider, Usage
from app.schema.research import ResearchResult

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "creative-director.md"

_FALLBACK_PROMPT = (
    "You are the creative director for a short-form vertical video. Turn the "
    "research into a complete scene-by-scene plan following the hard rules."
)


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


def _build_system_prompt() -> str:
    return f"{_load_prompt()}\n\n{load_full_playbook()}"


def _build_generate_message(topic: str, research: ResearchResult, archetype: str) -> str:
    archetype_config = get_archetype(archetype)
    return (
        f"Topic: {topic}\n\n"
        f"Research summary: {research.summary}\n"
        f"Key facts: {research.key_facts}\n"
        f"Mood: {research.mood}\n\n"
        f"Archetype: {archetype}\n"
        f"{pacing_instruction(archetype_config.scene_pacing)}"
    )


async def director_generate(
    topic: str,
    research: ResearchResult,
    archetype: str,
    llm: LLMProvider,
) -> tuple[DirectorScore, Usage]:
    data, usage = await llm.generate(
        system_prompt=_build_system_prompt(),
        user_message=_build_generate_message(topic, research, archetype),
        schema=DirectorScore,
    )
    return data, usage


async def director_revise(
    score: DirectorScore,
    weaknesses: list[str],
    revision_instructions: str | None,
    research: ResearchResult,
    llm: LLMProvider,
) -> tuple[DirectorScore, Usage]:
    original_archetype = score.archetype
    message = (
        f"Current plan:\n{score.model_dump_json()}\n\n"
        f"Critic's weaknesses: {weaknesses}\n"
        f"Critic's revision instructions: {revision_instructions}\n\n"
        f"Research summary: {research.summary}\n"
        f"Key facts: {research.key_facts}\n\n"
        "Revise the plan to address the weaknesses above. Keep the same "
        f"archetype ('{original_archetype}')."
    )
    data, usage = await llm.generate(
        system_prompt=_build_system_prompt(),
        user_message=message,
        schema=DirectorScore,
    )
    if data.archetype != original_archetype:
        data = data.model_copy(update={"archetype": original_archetype})
    return data, usage

from pathlib import Path

from app.config.playbook import load_playbook_sections
from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore
from app.schema.providers import LLMProvider, Usage

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "critic.md"

_FALLBACK_PROMPT = "You are the critic reviewing a short-form video plan."


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


def _build_system_prompt() -> str:
    playbook_excerpt = load_playbook_sections(["Pacing Rules", "Critic Rubric"])
    return f"{_load_prompt()}\n\n{playbook_excerpt}"


async def critique(
    score: DirectorScore,
    topic: str,
    pacing_tier: str,
    llm: LLMProvider,
) -> tuple[CritiqueResult, Usage]:
    message = (
        f"Topic: {topic}\n"
        f"Pacing tier: {pacing_tier}\n\n"
        f"Plan:\n{score.model_dump_json()}"
    )
    data, usage = await llm.generate(
        system_prompt=_build_system_prompt(),
        user_message=message,
        schema=CritiqueResult,
    )
    return data, usage

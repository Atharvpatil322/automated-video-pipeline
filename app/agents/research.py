from pathlib import Path

from app.schema.providers import LLMProvider, Usage
from app.schema.research import ResearchResult

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "researcher.md"

_FALLBACK_PROMPT = "Research this topic for a short-form video script."


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


async def research(topic: str, llm: LLMProvider) -> tuple[ResearchResult, Usage]:
    system_prompt = _load_prompt()
    data, usage = await llm.generate(
        system_prompt=system_prompt,
        user_message=f"Topic: {topic}",
        schema=ResearchResult,
    )
    return data, usage

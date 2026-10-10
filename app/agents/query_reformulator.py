from pathlib import Path

from app.schema.providers import LLMProvider, Usage
from app.schema.visuals import QueryReformulationResult

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "query-reformulator.md"

_FALLBACK_PROMPT = (
    "Rewrite a failed stock-search query into 2-3 more literal alternatives."
)


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


async def reformulate_query(original_query: str, llm: LLMProvider) -> tuple[list[str], Usage]:
    data, usage = await llm.generate(
        system_prompt=_load_prompt(),
        user_message=f"Original query: {original_query}",
        schema=QueryReformulationResult,
    )
    return data.queries, usage

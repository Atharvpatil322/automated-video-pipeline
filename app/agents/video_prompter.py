from pathlib import Path

from app.schema.providers import LLMProvider, Usage
from app.schema.visuals import ImagePromptResult

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "video-prompter.md"

_FALLBACK_PROMPT = "Write a short camera/motion prompt to animate this still image."


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


async def generate_motion_prompt(
    visual_prompt: str, script_line: str, llm: LLMProvider
) -> tuple[str, Usage]:
    data, usage = await llm.generate(
        system_prompt=_load_prompt(),
        user_message=f"Scene: {visual_prompt}\nNarration: {script_line}",
        schema=ImagePromptResult,
    )
    return data.prompt, usage

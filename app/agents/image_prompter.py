from pathlib import Path

from app.config.archetype import ArchetypeConfig
from app.schema.providers import LLMProvider, Usage
from app.schema.visuals import ImagePromptResult

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "image-prompter.md"

_FALLBACK_PROMPT = (
    "You rewrite a short scene description into a complete AI image generation "
    "prompt, applying the given style bible consistently."
)


def _load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text()
    return _FALLBACK_PROMPT


def _style_bible_text(archetype: ArchetypeConfig) -> str:
    return (
        f"Art style: {archetype.art_style}\n"
        f"Lighting: {archetype.lighting}\n"
        f"Composition rules: {archetype.composition_rules}\n"
        f"Cultural markers: {archetype.cultural_markers}\n"
        f"Mood: {archetype.mood}\n"
        f"Anti-artifact guidance: {archetype.anti_artifact_guidance}\n"
        f"Color palette: {', '.join(archetype.visual_color_palette)}"
    )


async def optimize_image_prompt(
    visual_prompt: str,
    script_line: str,
    archetype: ArchetypeConfig,
    llm: LLMProvider,
    *,
    safety_feedback: str | None = None,
    negative_examples: list[str] | None = None,
) -> tuple[str, Usage]:
    """Rewrite a scene's visual_prompt into a full image-generation prompt,
    injecting the archetype's style bible. When `safety_feedback` is set
    (the safety-rejection retry path), the message asks for a rewrite that
    removes the flagged content while keeping style and mood - mirrors the
    reference's single softened-prompt retry. `negative_examples` is the
    stock-resolver fallback path: descriptions of rejected stock candidates,
    fed in as things this image should not look like.
    """
    message = (
        f"Scene description: {visual_prompt}\n"
        f"Narration for this scene: {script_line}\n\n"
        f"Style bible:\n{_style_bible_text(archetype)}"
    )
    if safety_feedback:
        message += (
            f"\n\nThe previous prompt was rejected for safety reasons: "
            f"{safety_feedback}\nRemove any violence, gore, weapons or other "
            "unsafe content while keeping the same style and mood."
        )
    if negative_examples:
        message += "\n\nAvoid: " + "; ".join(negative_examples)

    data, usage = await llm.generate(
        system_prompt=_load_prompt(),
        user_message=message,
        schema=ImagePromptResult,
    )
    return data.prompt, usage

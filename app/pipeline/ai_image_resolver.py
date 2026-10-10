"""AI-image generation shared by the visuals stage's ai_image path, the
stock resolver's fallback, and the first phase of the ai_video flow.

Pulled out of app/pipeline/visuals.py so stock_resolver.py and
video_resolver.py can reuse it without an import cycle back into visuals.py.
"""

from pathlib import Path

from app.agents.image_prompter import optimize_image_prompt
from app.config.archetype import ArchetypeConfig
from app.pipeline.safety import is_safety_rejection
from app.schema.director import Scene, VisualType
from app.schema.providers import ImageProvider, LLMProvider
from app.schema.visuals import SceneVisualResult


async def generate_ai_image(
    index: int,
    scene: Scene,
    archetype: ArchetypeConfig,
    llm: LLMProvider,
    image: ImageProvider,
    assets_dir: Path,
    *,
    negative_examples: list[str] | None = None,
    filename_suffix: str = "ai",
) -> SceneVisualResult:
    """One try, then one safety-softened retry, matching the reference."""
    safety_feedback: str | None = None
    last_reason = "safety rejection on both attempts"

    for attempt in (1, 2):
        try:
            prompt, _ = await optimize_image_prompt(
                scene.visual_prompt,
                scene.script_line,
                archetype,
                llm,
                safety_feedback=safety_feedback,
                negative_examples=negative_examples,
            )
        except Exception:
            prompt = scene.visual_prompt  # prompt optimization failed, use original

        try:
            image_bytes = await image.generate(prompt)
        except Exception as exc:
            if is_safety_rejection(exc) and attempt == 1:
                safety_feedback = str(exc)
                last_reason = f"safety rejection: {exc}"
                continue
            return SceneVisualResult(
                scene_index=index,
                visual_type=scene.visual_type,
                path=None,
                status="failed",
                attempts=attempt,
                fallback_reason=str(exc),
            )

        path = assets_dir / f"scene-{index}-{filename_suffix}.png"
        path.write_bytes(image_bytes)
        return SceneVisualResult(
            scene_index=index,
            visual_type=VisualType.AI_IMAGE,
            path=str(path),
            status="generated",
            attempts=attempt,
            fallback_reason=None,
            method="ai_image",
        )

    return SceneVisualResult(
        scene_index=index,
        visual_type=scene.visual_type,
        path=None,
        status="failed",
        attempts=2,
        fallback_reason=last_reason,
    )

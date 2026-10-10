"""Two-phase ai_video resolution: generate a still image, then animate it.

Matches the reference's video-resolver.ts: phase 1 is the same AI-image
path used elsewhere, phase 2 sends that image plus a motion/camera prompt
to an image-to-video provider. Duration is the smallest supported duration
that is at least the scene's own length; if the scene is longer than every
supported duration, the longest is used and the render layer trims it
(never loops a generated video). Any failure in phase 2 falls back to the
phase-1 still, with motion forced to zoom_in so it isn't a frozen frame,
and a logged reason - never raises out of the scene.
"""

from pathlib import Path

from app.agents.video_prompter import generate_motion_prompt
from app.config.archetype import ArchetypeConfig
from app.pipeline.ai_image_resolver import generate_ai_image
from app.schema.director import Motion, Scene
from app.schema.providers import ImageProvider, LLMProvider, VideoProvider
from app.schema.visuals import SceneVisualResult

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, flickering, warping, deformed hands, morphing faces, extra limbs"
)
ASPECT_RATIO = "9:16"


def _pick_duration(supported: list[float], scene_duration_s: float) -> float:
    at_least = sorted(d for d in supported if d >= scene_duration_s)
    if at_least:
        return at_least[0]
    return max(supported)


def _fallback_to_still(result: SceneVisualResult, reason: str) -> SceneVisualResult:
    if result.status != "generated":
        return result.model_copy(
            update={"fallback_reason": f"{reason}; still-image fallback also failed"}
        )
    return result.model_copy(
        update={
            "status": "fallback",
            "method": "video_fallback_still",
            "fallback_reason": reason,
            "motion_override": Motion.ZOOM_IN,
        }
    )


async def resolve_ai_video(
    *,
    index: int,
    scene: Scene,
    archetype: ArchetypeConfig,
    llm: LLMProvider,
    image: ImageProvider,
    video: VideoProvider,
    assets_dir: Path,
    scene_duration_s: float,
) -> SceneVisualResult:
    still_result = await generate_ai_image(
        index, scene, archetype, llm, image, assets_dir, filename_suffix="ai-video-src"
    )
    if still_result.status != "generated":
        return still_result  # phase 1 itself failed, nothing to animate

    try:
        image_bytes = Path(still_result.path).read_bytes()
    except OSError as exc:
        return _fallback_to_still(still_result, f"could not read generated still: {exc}")

    try:
        motion_prompt, _ = await generate_motion_prompt(scene.visual_prompt, scene.script_line, llm)
    except Exception:
        motion_prompt = scene.visual_prompt  # motion prompting failed, use the scene description

    negative_prompt = DEFAULT_NEGATIVE_PROMPT
    if archetype.anti_artifact_guidance:
        negative_prompt = f"{negative_prompt}, {archetype.anti_artifact_guidance}"

    duration = _pick_duration(video.supported_durations, scene_duration_s)

    try:
        video_bytes = await video.generate(
            source_image=image_bytes,
            prompt=motion_prompt,
            duration_seconds=duration,
            aspect_ratio=ASPECT_RATIO,
            negative_prompt=negative_prompt,
        )
    except Exception as exc:
        return _fallback_to_still(still_result, f"video generation failed: {exc}")

    video_path = assets_dir / f"scene-{index}-video.mp4"
    video_path.write_bytes(video_bytes)

    return SceneVisualResult(
        scene_index=index,
        visual_type=scene.visual_type,
        path=str(video_path),
        status="generated",
        attempts=still_result.attempts + 1,
        method="video_generated",
    )

"""Visuals stage: one asset per scene, resolved concurrently.

ai_image and text_card resolve directly. stock_image/stock_video go
through the adaptive stock resolver (search -> verify -> reformulate ->
AI-image fallback). ai_video goes through the two-phase video resolver
(generate a still, then animate it), falling back to the still on failure.

Every scene is wrapped in its own try/except: a failure yields a `None`
asset and a logged reason, never a crashed run, matching the reference's
"fail soft" visuals stage.
"""

import asyncio
import json
from pathlib import Path

from app.config.archetype import ArchetypeConfig
from app.config.registry import get_archetype
from app.pipeline.ai_image_resolver import generate_ai_image
from app.pipeline.callbacks import NullCallbacks, PipelineCallbacks
from app.pipeline.cost import DEFAULT_VIDEO_DURATION_S, CostTracker
from app.pipeline.stock_resolver import resolve_stock
from app.pipeline.video_resolver import resolve_ai_video
from app.schema.director import DirectorScore, Motion, Scene, VisualType
from app.schema.providers import ImageProvider, LLMProvider, StockProvider, VideoProvider
from app.schema.visuals import SceneVisualResult, VisualsResult

DEFAULT_CONCURRENCY = 4
DEFAULT_VIDEO_CONCURRENCY = 3


def _resolve_text_card(index: int, scene: Scene) -> SceneVisualResult:
    return SceneVisualResult(
        scene_index=index,
        visual_type=scene.visual_type,
        path=None,
        status="no_asset",
        attempts=0,
        fallback_reason=None,
        method="text_card",
    )


async def _resolve_scene(
    index: int,
    scene: Scene,
    archetype: ArchetypeConfig,
    llm: LLMProvider,
    image: ImageProvider,
    stock_providers: list[StockProvider],
    verifier,
    video: VideoProvider | None,
    video_semaphore: asyncio.Semaphore,
    assets_dir: Path,
    scene_duration_s: float,
    log_attempts: list[dict],
    use_video: bool,
) -> SceneVisualResult:
    try:
        if scene.visual_type == VisualType.TEXT_CARD:
            return _resolve_text_card(index, scene)

        if scene.visual_type == VisualType.AI_IMAGE:
            return await generate_ai_image(index, scene, archetype, llm, image, assets_dir)

        if scene.visual_type in (VisualType.STOCK_IMAGE, VisualType.STOCK_VIDEO):
            return await resolve_stock(
                index=index,
                scene=scene,
                archetype=archetype,
                stock_providers=stock_providers,
                verifier=verifier,
                llm=llm,
                image=image,
                assets_dir=assets_dir,
                log_attempts=log_attempts,
            )

        if scene.visual_type == VisualType.AI_VIDEO:
            if not use_video or video is None:
                reason = "video disabled" if not use_video else "no video provider configured"
                result = await generate_ai_image(index, scene, archetype, llm, image, assets_dir)
                if result.status == "generated":
                    return result.model_copy(
                        update={
                            "status": "fallback",
                            "method": "video_fallback_still",
                            "fallback_reason": f"video skipped: {reason}",
                            "motion_override": Motion.ZOOM_IN,
                        }
                    )
                return result.model_copy(
                    update={"fallback_reason": f"video skipped: {reason}; {result.fallback_reason}"}
                )
            async with video_semaphore:
                return await resolve_ai_video(
                    index=index,
                    scene=scene,
                    archetype=archetype,
                    llm=llm,
                    image=image,
                    video=video,
                    assets_dir=assets_dir,
                    scene_duration_s=scene_duration_s,
                )

        return SceneVisualResult(
            scene_index=index,
            visual_type=scene.visual_type,
            path=None,
            status="failed",
            attempts=0,
            fallback_reason=f"unhandled visual_type {scene.visual_type}",
        )
    except Exception as exc:
        return SceneVisualResult(
            scene_index=index,
            visual_type=scene.visual_type,
            path=None,
            status="failed",
            attempts=1,
            fallback_reason=str(exc),
        )


def _append_log(run_dir: Path, visuals_log: list[dict], stock_attempts: list[dict]) -> None:
    log_path = run_dir / "log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    log["visuals"] = visuals_log
    log["stock_attempts"] = stock_attempts
    log_path.write_text(json.dumps(log, indent=2))


async def run_visuals_stage(
    *,
    score: DirectorScore,
    archetype: str,
    llm: LLMProvider,
    image: ImageProvider,
    run_dir: Path,
    stock_providers: list[StockProvider] | None = None,
    verifier=None,
    video: VideoProvider | None = None,
    scene_durations: list[float] | None = None,
    use_video: bool = True,
    concurrency: int = DEFAULT_CONCURRENCY,
    video_concurrency: int = DEFAULT_VIDEO_CONCURRENCY,
    dry_run_exit: bool = False,
    cost_rejected: bool = False,
    callbacks: PipelineCallbacks | None = None,
    cost_tracker: CostTracker | None = None,
    video_provider_name: str = "fal",
) -> VisualsResult | None:
    callbacks = callbacks or NullCallbacks()
    if dry_run_exit or cost_rejected or callbacks.is_cancelled():
        reason = "dry_run" if dry_run_exit else "cost_rejected" if cost_rejected else "cancelled"
        callbacks.on_stage_skip("visuals", reason)
        return None

    callbacks.on_stage_start("visuals")

    archetype_config = get_archetype(archetype)
    assets_dir = run_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    video_semaphore = asyncio.Semaphore(video_concurrency)
    stock_providers = stock_providers or []
    durations = scene_durations or [3.0] * len(score.scenes)
    stock_attempts: list[dict] = []

    async def bound(index: int, scene: Scene) -> SceneVisualResult:
        async with semaphore:
            result = await _resolve_scene(
                index,
                scene,
                archetype_config,
                llm,
                image,
                stock_providers,
                verifier,
                video,
                video_semaphore,
                assets_dir,
                durations[index],
                stock_attempts,
                use_video,
            )
            callbacks.on_progress("visuals", {"scene_index": index, "status": result.status})
            return result

    scene_results = list(
        await asyncio.gather(*(bound(i, s) for i, s in enumerate(score.scenes)))
    )
    visuals_result = VisualsResult(scenes=scene_results)

    if cost_tracker:
        for r in scene_results:
            if r.status not in ("generated", "fallback"):
                continue
            if r.method == "video_generated":
                cost_tracker.add_video(video_provider_name, DEFAULT_VIDEO_DURATION_S)
            elif r.visual_type == VisualType.AI_IMAGE:
                cost_tracker.add_image()
        for _ in stock_attempts:
            cost_tracker.add_vlm_call()

    (run_dir / "visuals.json").write_text(visuals_result.model_dump_json(indent=2))
    _append_log(
        run_dir,
        [
            {
                "scene_index": r.scene_index,
                "status": r.status,
                "method": r.method,
                "fallback_reason": r.fallback_reason,
            }
            for r in scene_results
        ],
        stock_attempts,
    )

    callbacks.on_stage_complete("visuals", {"scenes": len(scene_results)})
    return visuals_result

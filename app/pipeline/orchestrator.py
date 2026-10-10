"""The director stage: generate, critique, revise.

Mirrors the reference's plan-level critic-revise loop, which runs entirely
before any paid asset generation:

1. Generate a plan, then evaluate it with the critic.
2. Remember the highest-scoring plan seen so far.
3. Stop if the score is 7 or higher or the critic says no revision is needed.
4. Otherwise revise and go again, at most `max_rounds` times.
5. Use the best-scoring plan, not necessarily the latest one.
6. Any exception stops the loop and proceeds with the best plan so far.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

from app.agents.critic import critique
from app.agents.director import director_generate, director_revise
from app.config.platforms import get_platform
from app.config.registry import get_archetype
from app.pipeline.callbacks import NullCallbacks, PipelineCallbacks
from app.pipeline.captions import build_ass_document
from app.pipeline.cost import CostTracker
from app.pipeline.music import resolve_music
from app.pipeline.render_spec import score_to_render_spec
from app.pipeline.word_timing import SceneTiming, scene_duration, split_words_into_scenes
from app.render.assemble import burn_captions, concat_with_transitions, mux_audio
from app.render.scene_clips import build_scene_clip
from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore
from app.schema.providers import LLMProvider, TTSProvider, WordTimestamp
from app.schema.research import ResearchResult
from app.schema.visuals import VisualsResult

PASS_THRESHOLD = 7.0
MAX_REVISION_ROUNDS = 2


async def run_director_stage(
    *,
    topic: str,
    archetype: str,
    research_result: ResearchResult,
    llm: LLMProvider,
    callbacks: PipelineCallbacks | None = None,
    cost_tracker: CostTracker | None = None,
) -> tuple[DirectorScore, CritiqueResult | None, dict[str, Any]]:
    callbacks = callbacks or NullCallbacks()
    pacing_tier = get_archetype(archetype).scene_pacing

    callbacks.on_stage_start("director")
    current_score, usage = await director_generate(topic, research_result, archetype, llm)
    if cost_tracker:
        cost_tracker.add_llm_usage("director_generate", usage)

    best_score = current_score
    best_critique: CritiqueResult | None = None
    best_rating = float("-inf")
    evaluations = 0
    revisions = 0

    try:
        for round_num in range(MAX_REVISION_ROUNDS + 1):
            if callbacks.is_cancelled():
                break
            result, critique_usage = await critique(current_score, topic, pacing_tier, llm)
            if cost_tracker:
                cost_tracker.add_llm_usage("critic", critique_usage)
            evaluations += 1
            callbacks.on_progress(
                "director",
                {"revision": {"round": round_num, "score": result.score}},
            )

            if result.score > best_rating:
                best_rating = result.score
                best_score = current_score
                best_critique = result

            if result.score >= PASS_THRESHOLD or not result.revision_needed:
                break
            if round_num >= MAX_REVISION_ROUNDS:
                break

            current_score, revise_usage = await director_revise(
                current_score,
                result.weaknesses,
                result.revision_instructions,
                research_result,
                llm,
            )
            if cost_tracker:
                cost_tracker.add_llm_usage("director_revise", revise_usage)
            revisions += 1
    except Exception as exc:  # noqa: BLE001 - deliberately broad, matches reference's "fail soft" loop
        callbacks.on_stage_error("director_revise_loop", exc)

    callbacks.on_stage_complete(
        "director",
        {"evaluations": evaluations, "revisions": revisions, "best_score": best_rating},
    )
    return best_score, best_critique, {"evaluations": evaluations, "revisions": revisions}


class TTSStageOutput(NamedTuple):
    audio_path: Path
    words: list[WordTimestamp]
    scene_timings: list[SceneTiming]


async def run_tts_stage(
    *,
    score: DirectorScore,
    run_dir: Path,
    tts: TTSProvider,
    dry_run_exit: bool = False,
    cost_rejected: bool = False,
    callbacks: PipelineCallbacks | None = None,
    cost_tracker: CostTracker | None = None,
) -> TTSStageOutput | None:
    """One TTS call for the whole script, then split words/timing per scene.

    Checks dry-run/cost-rejected/cancel first, like every stage after the
    director. Unlike the director's critic-revise loop, a TTS failure is not
    caught here: the reference treats a failed voiceover as fatal.
    """
    callbacks = callbacks or NullCallbacks()
    if dry_run_exit or cost_rejected or callbacks.is_cancelled():
        reason = "dry_run" if dry_run_exit else "cost_rejected" if cost_rejected else "cancelled"
        callbacks.on_stage_skip("tts", reason)
        return None

    callbacks.on_stage_start("tts")

    full_text = " ".join(scene.script_line for scene in score.scenes)
    result = await tts.generate(full_text)
    if cost_tracker:
        cost_tracker.add_tts(len(full_text))

    expected_counts = [len(scene.script_line.split()) for scene in score.scenes]
    scenes_words = split_words_into_scenes(result.words, expected_counts)
    scene_timings = [scene_duration(words) for words in scenes_words]

    audio_path = run_dir / "voiceover.mp3"
    audio_path.write_bytes(result.audio)
    (run_dir / "words.json").write_text(
        json.dumps([w.model_dump() for w in result.words], indent=2)
    )
    (run_dir / "scene_timings.json").write_text(
        json.dumps([t._asdict() for t in scene_timings], indent=2)
    )

    callbacks.on_progress("tts", {"word_count": len(result.words)})
    callbacks.on_stage_complete(
        "tts", {"word_count": len(result.words), "scenes": len(scene_timings)}
    )
    return TTSStageOutput(audio_path=audio_path, words=result.words, scene_timings=scene_timings)


class AssemblyStageOutput(NamedTuple):
    final_video_path: Path


async def run_assembly_stage(
    *,
    score: DirectorScore,
    scene_timings: list[SceneTiming],
    asset_paths: list[str | None],
    words: list[WordTimestamp],
    archetype: str,
    platform: str,
    run_dir: Path,
    voiceover_path: Path,
    visuals_result: VisualsResult | None = None,
    no_music: bool = False,
    music_manifest: list | None = None,
    music_dir: Path | None = None,
    dry_run_exit: bool = False,
    cost_rejected: bool = False,
    callbacks: PipelineCallbacks | None = None,
) -> AssemblyStageOutput | None:
    """Scene clips -> transitions -> caption burn-in -> audio mux -> final.mp4.

    Same skip conditions as TTS, no try/except: the reference treats a
    failed assembly as fatal, same as a failed voiceover.
    """
    callbacks = callbacks or NullCallbacks()
    if dry_run_exit or cost_rejected or callbacks.is_cancelled():
        reason = "dry_run" if dry_run_exit else "cost_rejected" if cost_rejected else "cancelled"
        callbacks.on_stage_skip("assembly", reason)
        return None

    callbacks.on_stage_start("assembly")

    archetype_config = get_archetype(archetype)
    platform_config = get_platform(platform)

    resolved_visual_types = None
    motion_overrides = None
    if visuals_result is not None:
        by_index = {r.scene_index: r for r in visuals_result.scenes}
        resolved_visual_types = [
            by_index[i].visual_type if i in by_index else None for i in range(len(score.scenes))
        ]
        motion_overrides = [
            by_index[i].motion_override if i in by_index else None for i in range(len(score.scenes))
        ]

    render_spec = score_to_render_spec(
        score,
        scene_timings,
        asset_paths,
        archetype_config,
        platform_config,
        words,
        voiceover_path=str(voiceover_path),
        resolved_visual_types=resolved_visual_types,
        motion_overrides=motion_overrides,
    )

    work_dir = run_dir / "_render"
    work_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for spec in render_spec.scenes:
        clip_path = work_dir / f"scene-{spec.index}.mp4"
        build_scene_clip(
            output_path=clip_path,
            visual_type=spec.visual_type,
            asset_path=spec.asset_path,
            motion=spec.motion,
            script_line=spec.script_line,
            motion_intensity=render_spec.motion_intensity,
            background_hex=render_spec.color_palette.background,
            text_hex=render_spec.color_palette.text,
            font=render_spec.text_card_font,
            width=render_spec.width,
            height=render_spec.height,
            fps=render_spec.fps,
            duration_frames=spec.duration_frames,
        )
        clip_paths.append(clip_path)

    silent_video_path = work_dir / "video_silent.mp4"
    concat_with_transitions(clip_paths, render_spec.scenes, render_spec.fps, silent_video_path)

    ass_text = build_ass_document(
        render_spec.words,
        style=render_spec.caption_style,
        chunk_size=render_spec.caption_chunk_size,
        linger_s=render_spec.caption_linger_s,
        palette=render_spec.color_palette,
        width=render_spec.width,
        height=render_spec.height,
    )
    ass_path = work_dir / "captions.ass"
    ass_path.write_text(ass_text, encoding="utf-8")

    captioned_video_path = work_dir / "video_captioned.mp4"
    burn_captions(silent_video_path, ass_path, captioned_video_path)

    music_kwargs = {}
    if music_manifest is not None:
        music_kwargs["manifest"] = music_manifest
    if music_dir is not None:
        music_kwargs["music_dir"] = music_dir
    music_path = resolve_music(score.music_mood.value, no_music=no_music, **music_kwargs)

    final_path = run_dir / "final.mp4"
    mux_audio(captioned_video_path, voiceover_path, music_path, final_path)

    callbacks.on_stage_complete("assembly", {"final_video": str(final_path)})
    return AssemblyStageOutput(final_video_path=final_path)


async def run_critic_stage(
    *,
    score: DirectorScore,
    topic: str,
    archetype: str,
    llm: LLMProvider,
    run_dir: Path,
    dry_run_exit: bool = False,
    cost_rejected: bool = False,
    no_critic: bool = False,
    callbacks: PipelineCallbacks | None = None,
    cost_tracker: CostTracker | None = None,
) -> CritiqueResult | None:
    """Stage 6: re-run the same critic agent on the final plan, purely for
    an informational review.json - it never triggers a re-run or revision
    (that already happened, plan-level, in the director stage). A failure
    here must not fail the run: caught, logged via on_stage_error, and the
    stage is reported as having produced no review rather than raising.
    """
    callbacks = callbacks or NullCallbacks()
    if dry_run_exit or cost_rejected or no_critic or callbacks.is_cancelled():
        reason = (
            "dry_run"
            if dry_run_exit
            else "cost_rejected"
            if cost_rejected
            else "no_critic"
            if no_critic
            else "cancelled"
        )
        callbacks.on_stage_skip("critic", reason)
        return None

    callbacks.on_stage_start("critic")
    try:
        pacing_tier = get_archetype(archetype).scene_pacing
        review, usage = await critique(score, topic, pacing_tier, llm)
        if cost_tracker:
            cost_tracker.add_llm_usage("critic", usage)
    except Exception as exc:  # noqa: BLE001 - this stage must never fail the run
        callbacks.on_stage_error("critic", exc)
        return None

    (run_dir / "review.json").write_text(review.model_dump_json(indent=2))
    callbacks.on_progress("critic", {"review": review.model_dump()})
    callbacks.on_stage_complete("critic", {"score": review.score})
    return review

"""Pure mapping from a DirectorScore + resolved assets to a RenderSpec.

Mirrors the reference's mapScoreToProps, with one deliberate deviation:
scene start/duration frames are derived directly from each scene's own
audio timestamps (scene_timings), not from summing per-scene durations and
then subtracting transition overlap. The reference's own "design note"
flags that subtract-then-stretch-the-last-scene approach as a source of
drift risk; locking boundaries to the audio timeline removes the question
entirely, at the cost of making transitions a purely visual effect handled
by padding clips at the FFmpeg layer (see app/render/assemble.py) rather
than something that shrinks the overall timeline.
"""

from app.config.archetype import ArchetypeConfig
from app.config.platforms import PlatformConfig
from app.pipeline.word_timing import DURATION_PADDING_SECONDS, SceneTiming
from app.schema.director import DirectorScore, Motion, Transition, VisualType
from app.schema.providers import WordTimestamp
from app.schema.render import RenderSpec, SceneRenderSpec


def _resolve_transition(
    scene_transition: Transition | None, archetype: ArchetypeConfig
) -> Transition:
    if scene_transition is not None:
        return scene_transition
    return archetype.default_transition


def score_to_render_spec(
    score: DirectorScore,
    scene_timings: list[SceneTiming],
    asset_paths: list[str | None],
    archetype: ArchetypeConfig,
    platform: PlatformConfig,
    words: list[WordTimestamp],
    voiceover_path: str | None = None,
    music_path: str | None = None,
    resolved_visual_types: list[VisualType | None] | None = None,
    motion_overrides: list[Motion | None] | None = None,
) -> RenderSpec:
    """`resolved_visual_types`/`motion_overrides` come from the visuals
    stage's VisualsResult: a scene can resolve to a different asset type
    than the director planned (e.g. stock_image falling back to ai_image,
    or ai_video falling back to a still with motion forced to zoom_in).
    When omitted, the director's own scene.visual_type/scene.motion are
    used unchanged.
    """
    if not (len(score.scenes) == len(scene_timings) == len(asset_paths)):
        raise ValueError("scenes, scene_timings and asset_paths must be the same length")

    fps = platform.fps
    scene_count = len(score.scenes)

    start_frames = [0] * scene_count
    for i in range(1, scene_count):
        start_frames[i] = round(scene_timings[i].start * fps)

    duration_frames = [0] * scene_count
    for i in range(scene_count - 1):
        duration_frames[i] = max(1, start_frames[i + 1] - start_frames[i])

    last_own_frames = round(scene_timings[-1].duration * fps)
    voiceover_end = words[-1].end if words else scene_timings[-1].end
    voiceover_end_frame = round((voiceover_end + DURATION_PADDING_SECONDS) * fps)
    duration_frames[-1] = max(1, last_own_frames, voiceover_end_frame - start_frames[-1])

    render_scenes = []
    for i, scene in enumerate(score.scenes):
        transition = _resolve_transition(scene.transition, archetype)
        transition_frames = (
            archetype.transition_duration_frames if transition != Transition.NONE else 0
        )
        visual_type = scene.visual_type
        if resolved_visual_types is not None and resolved_visual_types[i] is not None:
            visual_type = resolved_visual_types[i]
        motion = scene.motion
        if motion_overrides is not None and motion_overrides[i] is not None:
            motion = motion_overrides[i]
        render_scenes.append(
            SceneRenderSpec(
                index=i,
                visual_type=visual_type,
                asset_path=asset_paths[i],
                motion=motion,
                script_line=scene.script_line,
                start_frame=start_frames[i],
                duration_frames=duration_frames[i],
                transition=transition,
                transition_duration_frames=transition_frames,
            )
        )

    total_frames = start_frames[-1] + duration_frames[-1]

    return RenderSpec(
        scenes=render_scenes,
        total_frames=total_frames,
        fps=fps,
        width=platform.width,
        height=platform.height,
        words=words,
        caption_style=archetype.caption_style,
        caption_chunk_size=archetype.caption_chunk_size,
        caption_linger_s=archetype.caption_linger_s,
        color_palette=archetype.color_palette,
        text_card_font=archetype.text_card_font,
        motion_intensity=archetype.motion_intensity,
        voiceover_path=voiceover_path,
        music_path=music_path,
    )

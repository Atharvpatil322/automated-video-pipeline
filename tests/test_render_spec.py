from app.config.archetype import ArchetypeConfig, ColorPalette
from app.config.platforms import PlatformConfig
from app.pipeline.render_spec import score_to_render_spec
from app.pipeline.word_timing import SceneTiming
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.providers import WordTimestamp

FPS = 30


def make_platform() -> PlatformConfig:
    return PlatformConfig(
        key="test", width=1080, height=1920, fps=FPS, max_duration_s=60,
        recommended_duration_s=(10, 50), codec="h264",
    )


def make_archetype(
    default_transition=Transition.CROSSFADE, transition_frames=15
) -> ArchetypeConfig:
    return ArchetypeConfig(
        key="test",
        scene_pacing="fast",
        color_palette=ColorPalette(background="#000000", accent="#FFFFFF", text="#FFFFFF"),
        text_card_font="Inter",
        motion_intensity=1.0,
        default_transition=default_transition,
        transition_duration_frames=transition_frames,
    )


def make_scene(visual_type, transition=None, line="hello world") -> Scene:
    return Scene(
        visual_type=visual_type,
        visual_prompt="prompt",
        motion=Motion.STATIC,
        script_line=line,
        transition=transition,
    )


def make_score(scenes: list[Scene]) -> DirectorScore:
    return DirectorScore(
        emotional_arc="arc", archetype="test", music_mood="uplifting_pop", scenes=scenes
    )


def words_at(*starts_ends: tuple[float, float]) -> list[WordTimestamp]:
    return [WordTimestamp(word="w", start=s, end=e) for s, e in starts_ends]


def test_scene_start_frames_follow_audio_timestamps_not_accumulated_durations():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 2.0, 2.5), SceneTiming(2.0, 4.0, 2.5), SceneTiming(4.0, 6.0, 2.5)]
    words = words_at((0.0, 2.0), (2.0, 4.0), (4.0, 6.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(), make_platform(), words
    )

    assert [s.start_frame for s in spec.scenes] == [0, 60, 120]


def test_transition_cascade_uses_scene_value_when_set():
    scenes = [
        make_scene(VisualType.TEXT_CARD, transition=Transition.WIPE),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 2.0, 2.5), SceneTiming(2.0, 4.0, 2.5), SceneTiming(4.0, 6.0, 2.5)]
    words = words_at((0.0, 2.0), (2.0, 4.0), (4.0, 6.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(default_transition=Transition.NONE),
        make_platform(), words,
    )

    assert spec.scenes[0].transition == Transition.WIPE


def test_transition_cascade_falls_back_to_archetype_default_when_scene_is_none():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 2.0, 2.5), SceneTiming(2.0, 4.0, 2.5), SceneTiming(4.0, 6.0, 2.5)]
    words = words_at((0.0, 2.0), (2.0, 4.0), (4.0, 6.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(default_transition=Transition.WIPE),
        make_platform(), words,
    )

    assert spec.scenes[0].transition == Transition.WIPE


def test_transition_duration_frames_zero_when_transition_is_none():
    scenes = [
        make_scene(VisualType.TEXT_CARD, transition=Transition.NONE),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 2.0, 2.5), SceneTiming(2.0, 4.0, 2.5), SceneTiming(4.0, 6.0, 2.5)]
    words = words_at((0.0, 2.0), (2.0, 4.0), (4.0, 6.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(transition_frames=15),
        make_platform(), words,
    )

    assert spec.scenes[0].transition_duration_frames == 0


def test_total_frames_does_not_shrink_from_transitions_since_boundaries_are_audio_locked():
    scenes = [
        make_scene(VisualType.TEXT_CARD, transition=Transition.CROSSFADE),
        make_scene(VisualType.STOCK_IMAGE, transition=Transition.CROSSFADE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 2.0, 2.5), SceneTiming(2.0, 4.0, 2.5), SceneTiming(4.0, 6.0, 2.5)]
    words = words_at((0.0, 2.0), (2.0, 4.0), (4.0, 6.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(), make_platform(), words
    )

    # last scene starts at frame 120 (4.0s*30fps); its own duration covers to
    # the voiceover end (6.0s) + 0.5s padding = 6.5s -> frame 195
    assert spec.total_frames == 195


def test_last_scene_stretches_to_cover_voiceover_end_padding():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    # last scene's own computed duration (1.5s) undershoots the full
    # voiceover's last word end + 0.5s padding
    timings = [
        SceneTiming(0.0, 1.0, 2.0),
        SceneTiming(1.0, 2.0, 2.0),
        SceneTiming(2.0, 3.0, 1.5),
    ]
    words = words_at((0.0, 1.0), (1.0, 2.0), (2.0, 3.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(), make_platform(), words
    )

    expected_end_frame = round((3.0 + 0.5) * FPS)
    assert spec.scenes[-1].start_frame + spec.scenes[-1].duration_frames == expected_end_frame


def test_platform_fps_width_height_propagate():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 1.0, 2.0), SceneTiming(1.0, 2.0, 2.0), SceneTiming(2.0, 3.0, 2.0)]
    words = words_at((0.0, 1.0), (1.0, 2.0), (2.0, 3.0))

    spec = score_to_render_spec(
        score, timings, [None, None, None], make_archetype(), make_platform(), words
    )

    assert (spec.fps, spec.width, spec.height) == (30, 1080, 1920)


def test_rejects_mismatched_input_lengths():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    timings = [SceneTiming(0.0, 1.0, 2.0)]
    words = words_at((0.0, 1.0))

    import pytest

    with pytest.raises(ValueError, match="same length"):
        score_to_render_spec(score, timings, [None, None], make_archetype(), make_platform(), words)

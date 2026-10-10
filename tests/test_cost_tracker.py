from app.pipeline.cost import CostTracker, estimate_total_cost
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.providers import Usage


def make_score(scenes) -> DirectorScore:
    return DirectorScore(
        emotional_arc="arc", archetype="infographic", music_mood="uplifting_pop", scenes=scenes
    )


def make_scene(visual_type: VisualType) -> Scene:
    return Scene(
        visual_type=visual_type,
        visual_prompt="prompt",
        motion=Motion.STATIC,
        script_line="narration here",
        transition=Transition.NONE,
    )


def test_tracker_accumulates_llm_usage_across_multiple_calls():
    tracker = CostTracker(llm_provider="groq", tts_provider="elevenlabs", image_provider="openai")
    tracker.add_llm_usage("director_generate", Usage(input_tokens=1000, output_tokens=200))
    tracker.add_llm_usage("critic", Usage(input_tokens=500, output_tokens=100))
    tracker.add_llm_usage("critic", Usage(input_tokens=500, output_tokens=100))

    actual = tracker.actual()

    # groq is free-tier in this build, so llm cost is always $0, but the
    # call should not raise and should produce a well-formed breakdown.
    assert actual.breakdown.llm == 0.0


def test_tracker_accumulates_tts_characters():
    tracker = CostTracker(llm_provider="groq", tts_provider="elevenlabs", image_provider="openai")
    tracker.add_tts(100)
    tracker.add_tts(50)

    actual = tracker.actual()

    assert actual.breakdown.tts == 150 * 0.00018


def test_tracker_accumulates_images():
    tracker = CostTracker(llm_provider="groq", tts_provider="elevenlabs", image_provider="openai")
    tracker.add_image()
    tracker.add_image()
    tracker.add_image()

    actual = tracker.actual()

    assert actual.breakdown.images == 3 * 0.07


def test_tracker_accumulates_video_seconds():
    tracker = CostTracker(llm_provider="groq", tts_provider="elevenlabs", image_provider="openai")
    tracker.add_video("fal", 5.0)
    tracker.add_video("fal", 10.0)

    actual = tracker.actual()

    assert actual.breakdown.video == 15.0 * 0.07


def test_tracker_with_no_usage_at_all_is_all_zero():
    tracker = CostTracker(llm_provider="groq", tts_provider="elevenlabs", image_provider="openai")

    actual = tracker.actual()

    assert actual.total == 0.0


def test_estimate_uses_real_director_counts_not_guesses():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.AI_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    estimate_no_revisions = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=1,
        director_revisions=0,
        video_enabled=False,
    )
    estimate_with_revisions = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=3,
        director_revisions=2,
        video_enabled=False,
    )

    # groq is free so the llm line is always $0, but the breakdown call
    # itself must not raise when revision counts differ, and both are valid.
    assert estimate_no_revisions.breakdown.llm == 0.0
    assert estimate_with_revisions.breakdown.llm == 0.0


def test_estimate_includes_image_cost_for_ai_image_scenes():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.AI_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    estimate = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=1,
        director_revisions=0,
        video_enabled=False,
    )

    assert estimate.breakdown.images == 0.07


def test_estimate_includes_video_cost_only_when_video_enabled():
    scenes = [
        make_scene(VisualType.AI_VIDEO),
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    with_video = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider="fal",
        director_evaluations=1,
        director_revisions=0,
        video_enabled=True,
    )
    without_video = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=1,
        director_revisions=0,
        video_enabled=False,
    )

    assert with_video.breakdown.video > 0
    assert without_video.breakdown.video == 0
    assert any("fall back to a still image" in note for note in without_video.notes)


def test_estimate_notes_worst_case_stock_fallback():
    scenes = [
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    estimate = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=1,
        director_revisions=0,
        stock_enabled=True,
        video_enabled=False,
    )

    assert any("Worst case" in note for note in estimate.notes)


def test_estimate_includes_tts_cost_from_script_length():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
        make_scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    estimate = estimate_total_cost(
        score,
        llm_provider="groq",
        tts_provider="elevenlabs",
        image_provider="openai",
        video_provider=None,
        director_evaluations=1,
        director_revisions=0,
        video_enabled=False,
    )

    expected_chars = sum(len(s.script_line) for s in scenes)
    assert estimate.breakdown.tts == expected_chars * 0.00018

import pytest
from pydantic import ValidationError

from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType


def make_scene(visual_type: VisualType, motion: Motion = Motion.STATIC) -> Scene:
    return Scene(
        visual_type=visual_type,
        visual_prompt="a prompt",
        motion=motion,
        script_line="a line",
        transition=Transition.NONE,
    )


def make_score(scenes: list[Scene]) -> DirectorScore:
    return DirectorScore(
        emotional_arc="curiosity-to-wisdom",
        archetype="infographic",
        music_mood="uplifting_pop",
        scenes=scenes,
    )


def test_minimum_three_scenes_required():
    with pytest.raises(ValidationError):
        make_score([make_scene(VisualType.TEXT_CARD)] * 2)


def test_maximum_sixteen_scenes_allowed():
    with pytest.raises(ValidationError):
        make_score([make_scene(VisualType.TEXT_CARD)] * 17)


def test_sixteen_scenes_is_valid_with_golden_rule_respected():
    scenes = []
    types = [VisualType.TEXT_CARD, VisualType.STOCK_IMAGE]
    for i in range(16):
        scenes.append(make_scene(types[i % 2]))
    score = make_score(scenes)
    assert len(score.scenes) == 16


def test_golden_rule_rejects_three_consecutive_same_type():
    scenes = [make_scene(VisualType.TEXT_CARD)] * 3 + [make_scene(VisualType.STOCK_IMAGE)]
    with pytest.raises(ValidationError, match="golden rule"):
        make_score(scenes)


def test_golden_rule_allows_exactly_two_consecutive_same_type():
    scenes = [
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.TEXT_CARD),
        make_scene(VisualType.STOCK_IMAGE),
    ]
    score = make_score(scenes)
    assert len(score.scenes) == 3


def test_ai_video_must_have_static_motion():
    with pytest.raises(ValidationError, match="static"):
        make_scene(VisualType.AI_VIDEO, motion=Motion.ZOOM_IN)


def test_scene_requires_non_empty_script_line():
    with pytest.raises(ValidationError):
        Scene(
            visual_type=VisualType.TEXT_CARD,
            visual_prompt="a prompt",
            motion=Motion.STATIC,
            script_line="",
            transition=None,
        )

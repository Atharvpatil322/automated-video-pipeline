from app.config.archetype import ArchetypeConfig
from app.pipeline.video_resolver import _pick_duration, resolve_ai_video
from app.schema.director import Motion, Scene, Transition, VisualType
from app.schema.providers import Usage
from app.schema.visuals import ImagePromptResult


def make_archetype(anti_artifact_guidance: str = "") -> ArchetypeConfig:
    return ArchetypeConfig(
        key="test", scene_pacing="fast", anti_artifact_guidance=anti_artifact_guidance
    )


def make_scene() -> Scene:
    return Scene(
        visual_type=VisualType.AI_VIDEO,
        visual_prompt="a dog running through a field",
        motion=Motion.STATIC,
        script_line="narration",
        transition=Transition.NONE,
    )


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def generate(self, *, system_prompt, user_message, schema):
        return self._responses.pop(0), Usage(input_tokens=0, output_tokens=0)


class FakeImageProvider:
    async def generate(self, prompt, style=None):
        return b"fake-still-png"


class FakeVideoProvider:
    supported_durations = [5.0, 10.0]

    def __init__(self, behavior):
        self._behavior = behavior
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        result = self._behavior(kwargs)
        if isinstance(result, Exception):
            raise result
        return result


def test_pick_duration_rounds_up_to_smallest_supported():
    assert _pick_duration([5.0, 10.0], 3.0) == 5.0
    assert _pick_duration([5.0, 10.0], 7.0) == 10.0


def test_pick_duration_uses_longest_when_scene_exceeds_all_supported():
    assert _pick_duration([5.0, 10.0], 20.0) == 10.0


async def test_successful_video_generation_returns_generated_status(tmp_path):
    llm = ScriptedLLM([ImagePromptResult(prompt="slow push in")])
    video = FakeVideoProvider(lambda kwargs: b"fake-mp4-bytes")

    result = await resolve_ai_video(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        llm=llm,
        image=FakeImageProvider(),
        video=video,
        assets_dir=tmp_path,
        scene_duration_s=4.0,
    )

    assert result.status == "generated"
    assert result.method == "video_generated"
    assert result.path.endswith("-video.mp4")
    assert video.calls[0]["duration_seconds"] == 5.0
    assert video.calls[0]["aspect_ratio"] == "9:16"


async def test_video_failure_falls_back_to_still_image_with_zoom_in(tmp_path):
    llm = ScriptedLLM([ImagePromptResult(prompt="slow push in")])
    video = FakeVideoProvider(lambda kwargs: RuntimeError("provider timed out"))

    result = await resolve_ai_video(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        llm=llm,
        image=FakeImageProvider(),
        video=video,
        assets_dir=tmp_path,
        scene_duration_s=4.0,
    )

    assert result.status == "fallback"
    assert result.method == "video_fallback_still"
    assert result.motion_override == Motion.ZOOM_IN
    assert "provider timed out" in result.fallback_reason
    assert result.path is not None  # the still image path, from phase 1


async def test_negative_prompt_includes_archetype_anti_artifact_guidance(tmp_path):
    llm = ScriptedLLM([ImagePromptResult(prompt="slow push in")])
    video = FakeVideoProvider(lambda kwargs: b"fake-mp4-bytes")

    await resolve_ai_video(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(anti_artifact_guidance="no extra limbs"),
        llm=llm,
        image=FakeImageProvider(),
        video=video,
        assets_dir=tmp_path,
        scene_duration_s=4.0,
    )

    assert "no extra limbs" in video.calls[0]["negative_prompt"]


async def test_motion_prompt_failure_falls_back_to_visual_prompt(tmp_path):
    llm = ScriptedLLM([])  # exhausted immediately -> motion prompting fails
    video = FakeVideoProvider(lambda kwargs: b"fake-mp4-bytes")

    result = await resolve_ai_video(
        index=0,
        scene=make_scene(),
        archetype=make_archetype(),
        llm=llm,
        image=FakeImageProvider(),
        video=video,
        assets_dir=tmp_path,
        scene_duration_s=4.0,
    )

    assert result.status == "generated"
    assert video.calls[0]["prompt"] == "a dog running through a field"

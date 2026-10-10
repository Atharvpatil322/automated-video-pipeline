import asyncio
import json

from app.pipeline.cost import estimate_image_cost
from app.pipeline.visuals import run_visuals_stage
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.visuals import ImagePromptResult


def scene(visual_type: VisualType, line: str = "line") -> Scene:
    return Scene(
        visual_type=visual_type,
        visual_prompt="a dog in a park",
        motion=Motion.STATIC,
        script_line=line,
        transition=Transition.NONE,
    )


def make_score(scenes: list[Scene]) -> DirectorScore:
    return DirectorScore(
        emotional_arc="arc", archetype="infographic", music_mood="uplifting_pop", scenes=scenes
    )


class ScriptedPromptLLM:
    """Always returns a valid optimized prompt; used where the test only
    cares about the image-provider side of resolution."""

    def __init__(self):
        self.calls = []

    async def generate(self, *, system_prompt, user_message, schema):
        self.calls.append({"system_prompt": system_prompt, "user_message": user_message})
        from app.schema.providers import Usage

        return ImagePromptResult(prompt="optimized prompt"), Usage(input_tokens=0, output_tokens=0)


class FakeImageProvider:
    def __init__(self, behavior):
        """`behavior` is a callable(call_index) -> bytes, or raising an exception."""
        self._behavior = behavior
        self.call_count = 0
        self.concurrent = 0
        self.max_concurrent = 0

    async def generate(self, prompt: str, style: str | None = None) -> bytes:
        self.call_count += 1
        call_index = self.call_count
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            await asyncio.sleep(0.01)
            return self._behavior(call_index)
        finally:
            self.concurrent -= 1


def always_succeeds(_call_index: int) -> bytes:
    return b"fake-png-bytes"


async def test_concurrency_limit_is_respected(tmp_path):
    scenes = [
        scene(VisualType.AI_IMAGE),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.AI_IMAGE),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.AI_IMAGE),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)

    await run_visuals_stage(
        score=score,
        archetype="infographic",
        llm=ScriptedPromptLLM(),
        image=image,
        run_dir=tmp_path,
        concurrency=2,
    )

    assert image.max_concurrent <= 2


async def test_one_failing_scene_does_not_fail_others(tmp_path):
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.AI_IMAGE)]
    score = make_score(scenes)

    def behavior(call_index: int) -> bytes:
        if call_index == 1:
            raise RuntimeError("boom")
        return b"fake-png-bytes"

    image = FakeImageProvider(behavior)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    statuses = {r.scene_index: r.status for r in result.scenes}
    assert statuses[1] == "no_asset"  # text_card
    # exactly one of the two ai_image scenes failed, the other generated
    ai_statuses = {statuses[0], statuses[2]}
    assert ai_statuses == {"failed", "generated"}


async def test_safety_rejection_retry_succeeds_on_second_attempt(tmp_path):
    # only one scene calls the image provider, so call_index is unambiguous
    # even though scenes resolve concurrently
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.TEXT_CARD)]
    score = make_score(scenes)

    def behavior(call_index: int) -> bytes:
        if call_index == 1:
            raise RuntimeError("rejected: this content violates our safety policy")
        return b"fake-png-bytes"

    image = FakeImageProvider(behavior)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    scene0 = next(r for r in result.scenes if r.scene_index == 0)
    assert scene0.status == "generated"
    assert scene0.attempts == 2
    assert scene0.path is not None


async def test_safety_rejection_fails_twice_resolves_to_none(tmp_path):
    scenes = [
        scene(VisualType.AI_IMAGE),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)

    def always_rejected(_call_index: int) -> bytes:
        raise RuntimeError("blocked by content policy")

    image = FakeImageProvider(always_rejected)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    scene0 = result.scenes[0]
    assert scene0.status == "failed"
    assert scene0.path is None
    assert scene0.attempts == 2


async def test_stock_image_with_no_providers_configured_falls_back_to_ai_image(tmp_path):
    # No stock_providers passed -> resolver has nothing to search, falls
    # straight through to the AI-image fallback (real stock behavior is
    # covered in tests/test_stock_resolver.py with fake stock providers).
    scenes = [
        scene(VisualType.STOCK_IMAGE),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    scene0 = result.scenes[0]
    assert scene0.status == "fallback"
    assert "no stock_image candidate verified" in scene0.fallback_reason
    assert scene0.path is not None


async def test_stock_video_with_no_providers_configured_falls_back_to_ai_image(tmp_path):
    scenes = [
        scene(VisualType.STOCK_VIDEO),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    assert "no stock_video candidate verified" in result.scenes[0].fallback_reason


async def test_ai_video_with_no_video_provider_falls_back_to_still_image(tmp_path):
    # video=None (default) -> treated like "no video provider configured",
    # same path as --no-video (real two-phase flow is covered in
    # tests/test_video_resolver.py with a fake video provider).
    scenes = [
        scene(VisualType.AI_VIDEO, line="short line"),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    scene0 = result.scenes[0]
    assert "no video provider configured" in scene0.fallback_reason
    assert scene0.status == "fallback"
    assert scene0.motion_override == Motion.ZOOM_IN


async def test_text_card_resolves_without_any_provider_call(tmp_path):
    scenes = [
        scene(VisualType.TEXT_CARD),
        scene(VisualType.STOCK_IMAGE),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    llm = ScriptedPromptLLM()
    image = FakeImageProvider(always_succeeds)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=llm, image=image, run_dir=tmp_path
    )

    text_card_result = result.scenes[0]
    assert text_card_result.status == "no_asset"
    assert text_card_result.path is None
    assert text_card_result.attempts == 0
    # only the stock_image scene's fallback should have triggered any calls
    assert image.call_count == 1


async def test_visuals_json_and_log_json_are_written(tmp_path):
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.TEXT_CARD)]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)

    result = await run_visuals_stage(
        score=score, archetype="infographic", llm=ScriptedPromptLLM(), image=image, run_dir=tmp_path
    )

    visuals_json = json.loads((tmp_path / "visuals.json").read_text())
    assert len(visuals_json["scenes"]) == 3
    assert visuals_json["scenes"][0]["status"] == result.scenes[0].status

    log_json = json.loads((tmp_path / "log.json").read_text())
    assert "visuals" in log_json
    assert len(log_json["visuals"]) == 3


class RecordingCallbacks:
    def __init__(self, cancelled: bool = False):
        self._cancelled = cancelled
        self.skipped = []

    def on_run_dir(self, path):
        pass

    def on_stage_start(self, stage):
        pass

    def on_stage_complete(self, stage, detail):
        pass

    def on_stage_skip(self, stage, reason):
        self.skipped.append((stage, reason))

    def on_stage_error(self, stage, error):
        pass

    def on_progress(self, stage, data):
        pass

    def on_cost_estimate(self, estimate):
        return True

    def on_actual_cost(self, cost):
        pass

    def on_log(self, log):
        pass

    def is_cancelled(self):
        return self._cancelled


async def test_skips_on_dry_run_without_calling_image_provider(tmp_path):
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.TEXT_CARD)]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)
    callbacks = RecordingCallbacks()

    result = await run_visuals_stage(
        score=score,
        archetype="infographic",
        llm=ScriptedPromptLLM(),
        image=image,
        run_dir=tmp_path,
        dry_run_exit=True,
        callbacks=callbacks,
    )

    assert result is None
    assert image.call_count == 0
    assert callbacks.skipped == [("visuals", "dry_run")]


async def test_skips_on_cost_rejected(tmp_path):
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.TEXT_CARD)]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)
    callbacks = RecordingCallbacks()

    result = await run_visuals_stage(
        score=score,
        archetype="infographic",
        llm=ScriptedPromptLLM(),
        image=image,
        run_dir=tmp_path,
        cost_rejected=True,
        callbacks=callbacks,
    )

    assert result is None
    assert callbacks.skipped == [("visuals", "cost_rejected")]


async def test_skips_on_cancellation(tmp_path):
    scenes = [scene(VisualType.AI_IMAGE), scene(VisualType.TEXT_CARD), scene(VisualType.TEXT_CARD)]
    score = make_score(scenes)
    image = FakeImageProvider(always_succeeds)
    callbacks = RecordingCallbacks(cancelled=True)

    result = await run_visuals_stage(
        score=score,
        archetype="infographic",
        llm=ScriptedPromptLLM(),
        image=image,
        run_dir=tmp_path,
        callbacks=callbacks,
    )

    assert result is None
    assert callbacks.skipped == [("visuals", "cancelled")]


def test_estimate_image_cost_known_provider():
    assert estimate_image_cost("openai", 5) == 5 * 0.07


def test_estimate_image_cost_unknown_provider_is_zero():
    assert estimate_image_cost("unknown", 10) == 0.0


class FakeVideoProvider:
    supported_durations = [5.0, 10.0]

    def __init__(self):
        self.concurrent = 0
        self.max_concurrent = 0

    async def generate(self, **kwargs):
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            await asyncio.sleep(0.01)
            return b"fake-mp4-bytes"
        finally:
            self.concurrent -= 1


async def test_video_concurrency_limit_is_respected(tmp_path):
    scenes = [
        scene(VisualType.AI_VIDEO),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.AI_VIDEO),
        scene(VisualType.TEXT_CARD),
        scene(VisualType.AI_VIDEO),
        scene(VisualType.TEXT_CARD),
    ]
    score = make_score(scenes)
    video = FakeVideoProvider()

    await run_visuals_stage(
        score=score,
        archetype="infographic",
        llm=ScriptedPromptLLM(),
        image=FakeImageProvider(always_succeeds),
        run_dir=tmp_path,
        video=video,
        video_concurrency=2,
    )

    assert video.max_concurrent <= 2

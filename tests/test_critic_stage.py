import json

from app.pipeline.orchestrator import run_critic_stage
from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType


def make_score() -> DirectorScore:
    def scene(visual_type: VisualType) -> Scene:
        return Scene(
            visual_type=visual_type,
            visual_prompt="headline",
            motion=Motion.STATIC,
            script_line="line",
            transition=Transition.NONE,
        )

    return DirectorScore(
        emotional_arc="arc",
        archetype="infographic",
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD),
            scene(VisualType.STOCK_IMAGE),
            scene(VisualType.TEXT_CARD),
        ],
    )


class RecordingCallbacks:
    def __init__(self, cancelled: bool = False):
        self._cancelled = cancelled
        self.skipped = []
        self.errors = []
        self.completed = []

    def on_run_dir(self, path):
        pass

    def on_stage_start(self, stage):
        pass

    def on_stage_complete(self, stage, detail):
        self.completed.append((stage, detail))

    def on_stage_skip(self, stage, reason):
        self.skipped.append((stage, reason))

    def on_stage_error(self, stage, error):
        self.errors.append((stage, error))

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


async def test_writes_review_json_and_returns_review(tmp_path, scripted_llm):
    review = CritiqueResult(
        score=8,
        strengths=["good hook"],
        weaknesses=[],
        revision_needed=False,
        revision_instructions=None,
        weakest_scene_index=None,
    )
    llm = scripted_llm([review])

    result = await run_critic_stage(
        score=make_score(), topic="topic", archetype="infographic", llm=llm, run_dir=tmp_path
    )

    assert result == review
    data = json.loads((tmp_path / "review.json").read_text())
    assert data["score"] == 8


async def test_critic_failure_does_not_fail_the_run(tmp_path):
    class FailingLLM:
        async def generate(self, **kwargs):
            raise RuntimeError("critic LLM unavailable")

    callbacks = RecordingCallbacks()

    result = await run_critic_stage(
        score=make_score(),
        topic="topic",
        archetype="infographic",
        llm=FailingLLM(),
        run_dir=tmp_path,
        callbacks=callbacks,
    )

    assert result is None
    assert not (tmp_path / "review.json").exists()
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0][0] == "critic"


async def test_skips_on_no_critic_flag(tmp_path, scripted_llm):
    llm = scripted_llm([])
    callbacks = RecordingCallbacks()

    result = await run_critic_stage(
        score=make_score(),
        topic="topic",
        archetype="infographic",
        llm=llm,
        run_dir=tmp_path,
        no_critic=True,
        callbacks=callbacks,
    )

    assert result is None
    assert callbacks.skipped == [("critic", "no_critic")]


async def test_skips_on_dry_run(tmp_path, scripted_llm):
    llm = scripted_llm([])
    callbacks = RecordingCallbacks()

    result = await run_critic_stage(
        score=make_score(),
        topic="topic",
        archetype="infographic",
        llm=llm,
        run_dir=tmp_path,
        dry_run_exit=True,
        callbacks=callbacks,
    )

    assert result is None
    assert callbacks.skipped == [("critic", "dry_run")]


async def test_skips_on_cancellation(tmp_path, scripted_llm):
    llm = scripted_llm([])
    callbacks = RecordingCallbacks(cancelled=True)

    result = await run_critic_stage(
        score=make_score(),
        topic="topic",
        archetype="infographic",
        llm=llm,
        run_dir=tmp_path,
        callbacks=callbacks,
    )

    assert result is None
    assert callbacks.skipped == [("critic", "cancelled")]


async def test_never_triggers_a_revision_even_when_revision_needed_is_true(tmp_path, scripted_llm):
    # the final critic is purely informational: revision_needed=True here
    # must not cause any further director call - there's no mechanism for
    # one, and run_critic_stage never calls director_generate/revise.
    review = CritiqueResult(
        score=3,
        strengths=[],
        weaknesses=["weak hook"],
        revision_needed=True,
        revision_instructions="fix it",
        weakest_scene_index=0,
    )
    llm = scripted_llm([review])

    result = await run_critic_stage(
        score=make_score(), topic="topic", archetype="infographic", llm=llm, run_dir=tmp_path
    )

    assert result == review
    assert len(llm.calls) == 1  # exactly one critic call, nothing else

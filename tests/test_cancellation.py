from app.pipeline.orchestrator import run_director_stage
from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.research import ResearchResult


def make_score(arc: str) -> DirectorScore:
    def scene(visual_type: VisualType) -> Scene:
        return Scene(
            visual_type=visual_type,
            visual_prompt="headline",
            motion=Motion.STATIC,
            script_line="line",
            transition=Transition.NONE,
        )

    return DirectorScore(
        emotional_arc=arc,
        archetype="infographic",
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD),
            scene(VisualType.STOCK_IMAGE),
            scene(VisualType.TEXT_CARD),
        ],
    )


def make_critique(score: float, revision_needed: bool) -> CritiqueResult:
    return CritiqueResult(
        score=score,
        strengths=[],
        weaknesses=["weak"],
        revision_needed=revision_needed,
        revision_instructions="fix" if revision_needed else None,
        weakest_scene_index=0,
    )


class FakeCancelAfterNCallbacks:
    """is_cancelled() returns False the first `trigger_after` times it's
    checked, then True forever - simulates Ctrl+C landing mid-loop.
    """

    def __init__(self, trigger_after: int):
        self._trigger_after = trigger_after
        self._checks = 0

    def on_run_dir(self, path):
        pass

    def on_stage_start(self, stage):
        pass

    def on_stage_complete(self, stage, detail):
        pass

    def on_stage_skip(self, stage, reason):
        pass

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

    def is_cancelled(self) -> bool:
        self._checks += 1
        return self._checks > self._trigger_after


async def test_revise_loop_stops_when_cancelled_between_rounds(scripted_llm):
    score_v1 = make_score("v1")
    critique_v1 = make_critique(score=4, revision_needed=True)
    # if cancellation did not stop the loop, these would be consumed next:
    score_v2 = make_score("v2")
    critique_v2 = make_critique(score=9, revision_needed=False)

    llm = scripted_llm([score_v1, critique_v1, score_v2, critique_v2])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])
    # allow exactly one is_cancelled() check (the first round) before cancelling
    callbacks = FakeCancelAfterNCallbacks(trigger_after=1)

    best_score, best_critique, meta = await run_director_stage(
        topic="topic",
        archetype="infographic",
        research_result=research_result,
        llm=llm,
        callbacks=callbacks,
    )

    # round 0 ran fully (critique + the resulting revise), but the
    # cancellation check at the top of round 1 stopped it before
    # critique_v2 was ever consumed - so the best plan is still v1, the
    # only one that was actually scored.
    assert best_score.emotional_arc == "v1"
    assert meta == {"evaluations": 1, "revisions": 1}
    assert len(llm._responses) == 1  # critique_v2 never consumed


async def test_cancelled_before_any_round_skips_the_critique_entirely(scripted_llm):
    # is_cancelled() is checked at the very top of round 0, before that
    # round's critique call - if it's already true, no critique happens at
    # all and director_generate's own plan is returned as-is.
    score_v1 = make_score("v1")
    critique_v1 = make_critique(score=9, revision_needed=False)
    llm = scripted_llm([score_v1, critique_v1])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])
    callbacks = FakeCancelAfterNCallbacks(trigger_after=0)

    best_score, best_critique, meta = await run_director_stage(
        topic="topic",
        archetype="infographic",
        research_result=research_result,
        llm=llm,
        callbacks=callbacks,
    )

    assert best_score.emotional_arc == "v1"
    assert best_critique is None
    assert meta == {"evaluations": 0, "revisions": 0}
    assert len(llm._responses) == 1  # critique_v1 never consumed

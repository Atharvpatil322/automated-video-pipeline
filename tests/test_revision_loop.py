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
        strengths=["ok"],
        weaknesses=["weak hook"],
        revision_needed=revision_needed,
        revision_instructions="sharpen the hook" if revision_needed else None,
        weakest_scene_index=0,
    )


async def test_stops_immediately_when_first_critique_passes(scripted_llm):
    score_v1 = make_score("v1")
    critique_pass = make_critique(score=8, revision_needed=False)
    llm = scripted_llm([score_v1, critique_pass])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])

    best_score, best_critique, meta = await run_director_stage(
        topic="topic", archetype="infographic", research_result=research_result, llm=llm
    )

    assert best_score.emotional_arc == "v1"
    assert meta == {"evaluations": 1, "revisions": 0}


async def test_revises_once_then_keeps_best_scoring_plan(scripted_llm):
    score_v1 = make_score("v1")
    critique_fail = make_critique(score=4, revision_needed=True)
    score_v2 = make_score("v2")
    critique_pass = make_critique(score=9, revision_needed=False)
    llm = scripted_llm([score_v1, critique_fail, score_v2, critique_pass])
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])

    best_score, best_critique, meta = await run_director_stage(
        topic="topic", archetype="infographic", research_result=research_result, llm=llm
    )

    assert best_score.emotional_arc == "v2"
    assert best_critique.score == 9
    assert meta == {"evaluations": 2, "revisions": 1}


async def test_keeps_best_plan_even_if_later_round_scores_worse(scripted_llm):
    score_v1 = make_score("v1")
    critique_v1 = make_critique(score=6.5, revision_needed=True)
    score_v2 = make_score("v2")
    critique_v2 = make_critique(score=3, revision_needed=True)
    score_v3 = make_score("v3")
    critique_v3 = make_critique(score=5, revision_needed=True)
    llm = scripted_llm(
        [score_v1, critique_v1, score_v2, critique_v2, score_v3, critique_v3]
    )
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])

    best_score, best_critique, meta = await run_director_stage(
        topic="topic", archetype="infographic", research_result=research_result, llm=llm
    )

    assert best_score.emotional_arc == "v1"
    assert best_critique.score == 6.5
    assert meta == {"evaluations": 3, "revisions": 2}

import argparse
import json

import app.cli as cli
from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.research import ResearchResult


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
        emotional_arc="curiosity-to-wisdom",
        archetype="infographic",
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD),
            scene(VisualType.STOCK_IMAGE),
            scene(VisualType.TEXT_CARD),
        ],
    )


def make_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        topic="a topic",
        archetype="infographic",
        dry_run=False,
        score=None,
        from_stage="tts",
        tts_provider="elevenlabs",
        no_tts=False,
        no_music=False,
        platform="youtube",
        image_provider="openai",
        no_visuals=True,
        no_video=True,
        no_critic=True,
        fixture_assets=False,
        yes=True,
        max_cost=None,
        offline=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


async def test_run_dry_run_writes_score_json_and_stops(monkeypatch, tmp_path, scripted_llm):
    monkeypatch.chdir(tmp_path)
    research_result = ResearchResult(summary="s", key_facts=[], mood="m", sources=[])
    critique_pass = CritiqueResult(
        score=8,
        strengths=["ok"],
        weaknesses=[],
        revision_needed=False,
        revision_instructions=None,
        weakest_scene_index=None,
    )
    llm = scripted_llm([research_result, make_score(), critique_pass])
    monkeypatch.setattr(cli, "create_llm_provider", lambda keys, provider="groq": llm)

    args = make_args(dry_run=True)
    await cli._run(args)

    score_files = list(tmp_path.glob("output/*/score.json"))
    assert len(score_files) == 1
    data = json.loads(score_files[0].read_text())
    assert data["archetype"] == "infographic"

    log_files = list(tmp_path.glob("output/*/log.json"))
    assert len(log_files) == 1
    log_data = json.loads(log_files[0].read_text())
    assert log_data["run_status"] == "dry_run"


async def test_replay_loads_and_validates_saved_score(tmp_path):
    score_path = tmp_path / "score.json"
    score_path.write_text(make_score().model_dump_json())

    args = make_args(score=str(score_path), no_tts=True)
    await cli._replay(args)  # should not raise

    log_data = json.loads((tmp_path / "log.json").read_text())
    assert log_data["run_status"] == "completed"
    assert log_data["stages"]["tts"]["status"] == "skipped"


async def test_replay_from_stage_critic_skips_earlier_stages_and_runs_critic(
    tmp_path, scripted_llm, monkeypatch
):
    score_path = tmp_path / "score.json"
    score_path.write_text(make_score().model_dump_json())
    (tmp_path / "run_meta.json").write_text(
        json.dumps({"topic": "resumed topic", "archetype": "infographic"})
    )

    review = CritiqueResult(
        score=8,
        strengths=["ok"],
        weaknesses=[],
        revision_needed=False,
        revision_instructions=None,
        weakest_scene_index=None,
    )
    llm = scripted_llm([review])
    monkeypatch.setattr(cli, "create_llm_provider", lambda keys, provider="groq": llm)

    args = make_args(score=str(score_path), from_stage="critic", no_critic=False)
    await cli._replay(args)

    log_data = json.loads((tmp_path / "log.json").read_text())
    assert log_data["stages"]["critic"]["status"] == "completed"
    assert "tts" not in log_data["stages"]
    assert "visuals" not in log_data["stages"]
    assert "assembly" not in log_data["stages"]
    assert (tmp_path / "review.json").exists()
    assert "resumed topic" in llm.calls[0]["user_message"]

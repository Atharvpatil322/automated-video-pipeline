"""End-to-end offline run: every provider is a deterministic local fake,
so this needs no API keys and no network - only ffmpeg, which the render
and offline-fake providers both already require. Skips if ffmpeg/ffprobe
aren't on PATH.
"""

import argparse
import json
import shutil

import pytest

import app.cli as cli
from app.pipeline.word_timing import DURATION_PADDING_SECONDS
from app.render.ffmpeg import probe_duration_seconds

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

pytestmark = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg/ffprobe not found on PATH")


def make_offline_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        topic="the history of lighthouses",
        archetype="infographic",
        dry_run=False,
        score=None,
        from_stage="tts",
        tts_provider="elevenlabs",  # overridden to "offline" by --offline anyway
        no_tts=False,
        no_music=False,
        platform="youtube",
        image_provider="openai",  # overridden to "offline" by --offline anyway
        no_visuals=False,
        no_video=False,
        no_critic=False,
        fixture_assets=False,
        yes=True,
        max_cost=None,
        offline=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


async def test_offline_run_produces_a_real_final_video(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    args = make_offline_args()
    await cli._run(args)

    run_dirs = list(tmp_path.glob("output/*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    for filename in ("final.mp4", "review.json", "cost.json", "visuals.json", "log.json"):
        assert (run_dir / filename).exists(), f"missing {filename}"

    log_data = json.loads((run_dir / "log.json").read_text())
    assert log_data["run_status"] == "completed"
    assert log_data["stages"]["assembly"]["status"] == "completed"
    assert log_data["stages"]["critic"]["status"] == "completed"

    cost_data = json.loads((run_dir / "cost.json").read_text())
    assert cost_data["estimate"]["breakdown"]["llm"] == 0.0
    assert cost_data["estimate"]["breakdown"]["tts"] == 0.0
    assert cost_data["estimate"]["breakdown"]["images"] == 0.0
    assert cost_data["actual"]["breakdown"]["llm"] == 0.0

    words = json.loads((run_dir / "words.json").read_text())
    voiceover_end = words[-1]["end"]
    expected_duration = voiceover_end + DURATION_PADDING_SECONDS

    actual_duration = probe_duration_seconds(run_dir / "final.mp4")
    assert abs(actual_duration - expected_duration) <= 0.3


async def test_offline_run_is_free_per_the_cost_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    args = make_offline_args(topic="a different topic entirely")
    await cli._run(args)

    run_dir = next(tmp_path.glob("output/*"))
    log_data = json.loads((run_dir / "log.json").read_text())
    estimate = log_data["cost_estimate"]["breakdown"]
    assert sum(estimate.values()) == 0.0


async def test_different_topics_produce_different_plans(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    await cli._run(make_offline_args(topic="lighthouses", no_tts=True, no_critic=True))
    await cli._run(make_offline_args(topic="volcanoes", no_tts=True, no_critic=True))

    run_dirs = sorted(tmp_path.glob("output/*"))
    assert len(run_dirs) == 2
    score_a = json.loads((run_dirs[0] / "score.json").read_text())
    score_b = json.loads((run_dirs[1] / "score.json").read_text())
    assert score_a["scenes"] != score_b["scenes"]


async def test_offline_resume_from_visuals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    await cli._run(make_offline_args(no_visuals=True, no_critic=True))
    run_dir = next(tmp_path.glob("output/*"))
    score_path = run_dir / "score.json"

    replay_args = make_offline_args(
        score=str(score_path), from_stage="visuals", no_visuals=False, no_critic=True
    )
    await cli._replay(replay_args)

    assert (run_dir / "visuals.json").exists()
    assert (run_dir / "final.mp4").exists()


async def test_offline_cancel_between_stages_stops_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_init = cli.CLICallbacks.__init__

    def cancel_after_director(self, run_log, *, auto_yes, max_cost):
        original_init(self, run_log, auto_yes=auto_yes, max_cost=max_cost)
        self._cancelled = True

    monkeypatch.setattr(cli.CLICallbacks, "__init__", cancel_after_director)

    args = make_offline_args()
    await cli._run(args)

    run_dir = next(tmp_path.glob("output/*"))
    log_data = json.loads((run_dir / "log.json").read_text())
    assert log_data["run_status"] == "cancelled"
    assert not (run_dir / "final.mp4").exists()

import json

import pytest

from app.pipeline.loaders import load_run_meta, load_tts_output, load_visuals_result
from app.schema.providers import WordTimestamp
from app.schema.visuals import SceneVisualResult, VisualsResult


def test_load_tts_output_raises_clear_error_when_voiceover_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="voiceover.mp3"):
        load_tts_output(tmp_path, "visuals")


def test_load_tts_output_raises_clear_error_when_words_json_missing(tmp_path):
    (tmp_path / "voiceover.mp3").write_bytes(b"fake audio")
    with pytest.raises(FileNotFoundError, match="words.json"):
        load_tts_output(tmp_path, "visuals")


def test_load_tts_output_reconstructs_from_artifacts(tmp_path):
    (tmp_path / "voiceover.mp3").write_bytes(b"fake audio")
    words = [WordTimestamp(word="hi", start=0.0, end=0.5)]
    (tmp_path / "words.json").write_text(json.dumps([w.model_dump() for w in words]))
    timings = [{"start": 0.0, "end": 0.5, "duration": 2.0}]
    (tmp_path / "scene_timings.json").write_text(json.dumps(timings))

    output = load_tts_output(tmp_path, "visuals")

    assert output.audio_path == tmp_path / "voiceover.mp3"
    assert output.words == words
    assert output.scene_timings[0].duration == 2.0


def test_load_visuals_result_raises_clear_error_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="visuals.json"):
        load_visuals_result(tmp_path, "assembly")


def test_load_visuals_result_reconstructs_from_artifact(tmp_path):
    result = VisualsResult(
        scenes=[
            SceneVisualResult(
                scene_index=0,
                visual_type="text_card",
                path=None,
                status="no_asset",
                attempts=0,
            )
        ]
    )
    (tmp_path / "visuals.json").write_text(result.model_dump_json())

    loaded = load_visuals_result(tmp_path, "assembly")

    assert loaded == result


def test_load_run_meta_returns_empty_dict_when_missing(tmp_path):
    assert load_run_meta(tmp_path) == {}


def test_load_run_meta_reads_topic_and_archetype(tmp_path):
    (tmp_path / "run_meta.json").write_text(json.dumps({"topic": "cats", "archetype": "x"}))

    meta = load_run_meta(tmp_path)

    assert meta == {"topic": "cats", "archetype": "x"}

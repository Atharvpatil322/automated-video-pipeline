import json

from app.pipeline.run_log import RunLog


def test_write_creates_log_json_with_run_status_and_topic(tmp_path):
    log = RunLog(tmp_path, topic="my topic", archetype="infographic")
    log.run_status = "completed"
    log.write()

    data = json.loads((tmp_path / "log.json").read_text())
    assert data["run_status"] == "completed"
    assert data["topic"] == "my topic"
    assert data["archetype"] == "infographic"


def test_stage_lifecycle_is_recorded():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        run_dir = Path(d)
        log = RunLog(run_dir, topic="t", archetype="a")
        log.stage_start("tts")
        log.stage_complete("tts", {"word_count": 10})
        log.stage_skip("visuals", "no_visuals")
        log.stage_error("assembly", RuntimeError("boom"))
        log.write()

        data = json.loads((run_dir / "log.json").read_text())
        assert data["stages"]["tts"]["status"] == "completed"
        assert data["stages"]["tts"]["detail"] == {"word_count": 10}
        assert data["stages"]["visuals"]["status"] == "skipped"
        assert data["stages"]["visuals"]["reason"] == "no_visuals"
        assert data["stages"]["assembly"]["status"] == "error"
        assert "boom" in data["stages"]["assembly"]["error"]


def test_write_merges_on_top_of_existing_log_json_keys(tmp_path):
    existing = {"visuals": [{"scene_index": 0, "status": "generated"}]}
    (tmp_path / "log.json").write_text(json.dumps(existing))

    log = RunLog(tmp_path, topic="t", archetype="a")
    log.run_status = "completed"
    log.write()

    data = json.loads((tmp_path / "log.json").read_text())
    assert data["run_status"] == "completed"
    assert data["visuals"] == [{"scene_index": 0, "status": "generated"}]


def test_write_creates_run_dir_if_missing(tmp_path):
    run_dir = tmp_path / "nested" / "run"
    log = RunLog(run_dir, topic="t", archetype="a")
    log.run_status = "failed"
    log.write()

    assert (run_dir / "log.json").exists()


def test_cost_fields_default_to_none():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        log = RunLog(Path(d), topic="t", archetype="a")
        log.write()
        data = json.loads((Path(d) / "log.json").read_text())
        assert data["cost_estimate"] is None
        assert data["cost_actual"] is None

"""Load stage artifacts already present in a run directory, for --from-stage
resume. Raises a clear, specific error when something a stage needs is
missing rather than failing deep inside that stage.
"""

import json
from pathlib import Path

from app.pipeline.orchestrator import TTSStageOutput
from app.pipeline.word_timing import SceneTiming
from app.schema.providers import WordTimestamp
from app.schema.visuals import VisualsResult


def require_file(path: Path, stage: str, what: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"cannot resume at stage '{stage}': missing {what} ({path}). "
            "Run the pipeline from an earlier stage first."
        )
    return path


def load_tts_output(run_dir: Path, stage: str) -> TTSStageOutput:
    audio_path = require_file(run_dir / "voiceover.mp3", stage, "voiceover.mp3")
    words_path = require_file(run_dir / "words.json", stage, "words.json")
    timings_path = require_file(run_dir / "scene_timings.json", stage, "scene_timings.json")

    words = [WordTimestamp.model_validate(w) for w in json.loads(words_path.read_text())]
    timings = [SceneTiming(**t) for t in json.loads(timings_path.read_text())]
    return TTSStageOutput(audio_path=audio_path, words=words, scene_timings=timings)


def load_visuals_result(run_dir: Path, stage: str) -> VisualsResult:
    visuals_path = require_file(run_dir / "visuals.json", stage, "visuals.json")
    return VisualsResult.model_validate_json(visuals_path.read_text())


def load_run_meta(run_dir: Path) -> dict:
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text())

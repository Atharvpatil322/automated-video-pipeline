from app.pipeline.orchestrator import run_tts_stage
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.providers import TTSResult, WordTimestamp


def make_score() -> DirectorScore:
    def scene(visual_type: VisualType, line: str) -> Scene:
        return Scene(
            visual_type=visual_type,
            visual_prompt="headline",
            motion=Motion.STATIC,
            script_line=line,
            transition=Transition.NONE,
        )

    return DirectorScore(
        emotional_arc="curiosity-to-wisdom",
        archetype="infographic",
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD, "hello there"),
            scene(VisualType.STOCK_IMAGE, "world"),
            scene(VisualType.TEXT_CARD, "goodbye now"),
        ],
    )


class FakeTTSProvider:
    def __init__(self):
        self.generate_calls: list[str] = []

    async def generate(self, text: str) -> TTSResult:
        self.generate_calls.append(text)
        words = [
            WordTimestamp(word=w, start=float(i), end=float(i) + 0.4)
            for i, w in enumerate(text.split())
        ]
        return TTSResult(audio=b"audio-bytes", words=words)


class RecordingCallbacks:
    def __init__(self, cancelled: bool = False):
        self._cancelled = cancelled
        self.skipped: list[tuple[str, str]] = []
        self.started: list[str] = []
        self.completed: list[str] = []

    def on_run_dir(self, path):
        pass

    def on_stage_start(self, stage):
        self.started.append(stage)

    def on_stage_complete(self, stage, detail):
        self.completed.append(stage)

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


async def test_runs_tts_and_writes_files_when_nothing_blocks_it(tmp_path):
    tts = FakeTTSProvider()
    score = make_score()

    output = await run_tts_stage(score=score, run_dir=tmp_path, tts=tts)

    assert output is not None
    assert (tmp_path / "voiceover.mp3").read_bytes() == b"audio-bytes"
    assert (tmp_path / "words.json").exists()
    assert (tmp_path / "scene_timings.json").exists()
    assert len(output.scene_timings) == 3
    assert tts.generate_calls == ["hello there world goodbye now"]


async def test_joins_all_script_lines_into_one_call_never_per_scene(tmp_path):
    tts = FakeTTSProvider()
    score = make_score()

    await run_tts_stage(score=score, run_dir=tmp_path, tts=tts)

    assert len(tts.generate_calls) == 1


async def test_skips_on_dry_run_without_calling_tts(tmp_path):
    tts = FakeTTSProvider()
    callbacks = RecordingCallbacks()

    output = await run_tts_stage(
        score=make_score(), run_dir=tmp_path, tts=tts, dry_run_exit=True, callbacks=callbacks
    )

    assert output is None
    assert tts.generate_calls == []
    assert callbacks.skipped == [("tts", "dry_run")]
    assert not (tmp_path / "voiceover.mp3").exists()


async def test_skips_on_cost_rejected_without_calling_tts(tmp_path):
    tts = FakeTTSProvider()
    callbacks = RecordingCallbacks()

    output = await run_tts_stage(
        score=make_score(), run_dir=tmp_path, tts=tts, cost_rejected=True, callbacks=callbacks
    )

    assert output is None
    assert tts.generate_calls == []
    assert callbacks.skipped == [("tts", "cost_rejected")]


async def test_skips_on_cancellation_without_calling_tts(tmp_path):
    tts = FakeTTSProvider()
    callbacks = RecordingCallbacks(cancelled=True)

    output = await run_tts_stage(score=make_score(), run_dir=tmp_path, tts=tts, callbacks=callbacks)

    assert output is None
    assert tts.generate_calls == []
    assert callbacks.skipped == [("tts", "cancelled")]

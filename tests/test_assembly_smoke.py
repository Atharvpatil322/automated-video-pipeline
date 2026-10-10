import shutil

import pytest

from app.config.archetype import ArchetypeConfig, ColorPalette
from app.config.platforms import PlatformConfig
from app.pipeline.captions import build_ass_document
from app.pipeline.render_spec import score_to_render_spec
from app.pipeline.word_timing import SceneTiming
from app.render.assemble import burn_captions, concat_with_transitions, mux_audio
from app.render.ffmpeg import probe_duration_seconds, run_ffmpeg
from app.render.scene_clips import build_scene_clip
from app.schema.captions import CaptionStyle
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.providers import WordTimestamp

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

pytestmark = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg/ffprobe not found on PATH")

FPS = 30
WIDTH, HEIGHT = 320, 568  # small for a fast smoke test


def _score() -> DirectorScore:
    def scene(visual_type: VisualType, line: str, transition: Transition | None) -> Scene:
        return Scene(
            visual_type=visual_type,
            visual_prompt="prompt",
            motion=Motion.STATIC,
            script_line=line,
            transition=transition,
        )

    return DirectorScore(
        emotional_arc="arc",
        archetype="smoke",
        music_mood="uplifting_pop",
        scenes=[
            scene(VisualType.TEXT_CARD, "one", Transition.CROSSFADE),
            scene(VisualType.STOCK_IMAGE, "two", Transition.NONE),
            scene(VisualType.TEXT_CARD, "three", None),
        ],
    )


async def test_renders_a_three_scene_video_with_expected_total_duration(tmp_path):
    score = _score()
    timings = [
        SceneTiming(0.0, 1.0, 1.0),
        SceneTiming(1.0, 2.0, 1.0),
        SceneTiming(2.0, 3.0, 1.0),
    ]
    words = [
        WordTimestamp(word="one", start=0.0, end=1.0),
        WordTimestamp(word="two", start=1.0, end=2.0),
        WordTimestamp(word="three", start=2.0, end=3.0),
    ]

    archetype = ArchetypeConfig(
        key="smoke",
        scene_pacing="fast",
        caption_style=CaptionStyle.CLEAN,
        color_palette=ColorPalette(background="#112233", accent="#FFFFFF", text="#FFFFFF"),
        text_card_font="Arial",
        motion_intensity=1.0,
        default_transition=Transition.NONE,
        transition_duration_frames=10,
    )
    platform = PlatformConfig(
        key="smoke", width=WIDTH, height=HEIGHT, fps=FPS, max_duration_s=60,
        recommended_duration_s=(1, 60), codec="h264",
    )

    spec = score_to_render_spec(score, timings, [None, None, None], archetype, platform, words)

    work_dir = tmp_path / "_render"
    work_dir.mkdir()

    clip_paths = []
    for scene_spec in spec.scenes:
        clip_path = work_dir / f"scene-{scene_spec.index}.mp4"
        build_scene_clip(
            output_path=clip_path,
            visual_type=scene_spec.visual_type,
            asset_path=scene_spec.asset_path,
            motion=scene_spec.motion,
            script_line=scene_spec.script_line,
            motion_intensity=spec.motion_intensity,
            background_hex=spec.color_palette.background,
            text_hex=spec.color_palette.text,
            font=spec.text_card_font,
            width=spec.width,
            height=spec.height,
            fps=spec.fps,
            duration_frames=scene_spec.duration_frames,
        )
        clip_paths.append(clip_path)

    silent_video = work_dir / "silent.mp4"
    concat_with_transitions(clip_paths, spec.scenes, spec.fps, silent_video)

    ass_text = build_ass_document(
        spec.words,
        style=spec.caption_style,
        chunk_size=spec.caption_chunk_size,
        linger_s=spec.caption_linger_s,
        palette=spec.color_palette,
        width=spec.width,
        height=spec.height,
    )
    ass_path = work_dir / "captions.ass"
    ass_path.write_text(ass_text, encoding="utf-8")

    captioned_video = work_dir / "captioned.mp4"
    burn_captions(silent_video, ass_path, captioned_video)

    voiceover_path = tmp_path / "voiceover.mp3"
    run_ffmpeg(
        [
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "3",
            "-c:a", "libmp3lame", str(voiceover_path),
        ]
    )

    final_path = tmp_path / "final.mp4"
    mux_audio(captioned_video, voiceover_path, None, final_path)

    assert final_path.exists()
    actual_duration = probe_duration_seconds(final_path)
    expected_duration = spec.total_frames / spec.fps
    assert abs(actual_duration - expected_duration) <= 0.2

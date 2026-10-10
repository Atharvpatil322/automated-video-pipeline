from unittest.mock import patch

from app.render.scene_clips import build_scene_clip
from app.schema.director import Motion, VisualType


def test_missing_asset_path_falls_back_to_black_clip_instead_of_crashing(tmp_path):
    output = tmp_path / "scene.mp4"
    with (
        patch("app.render.scene_clips._black_clip") as fake_black,
        patch("app.render.scene_clips._still_image_clip") as fake_still,
    ):
        build_scene_clip(
            output_path=output,
            visual_type=VisualType.AI_IMAGE,
            asset_path=None,
            motion=Motion.STATIC,
            script_line="line",
            motion_intensity=1.0,
            background_hex="#000000",
            text_hex="#FFFFFF",
            font="Inter",
            width=1080,
            height=1920,
            fps=30,
            duration_frames=60,
        )

    fake_black.assert_called_once()
    fake_still.assert_not_called()


def test_nonexistent_asset_file_falls_back_to_black_clip(tmp_path):
    output = tmp_path / "scene.mp4"
    nonexistent = tmp_path / "does-not-exist.png"
    with patch("app.render.scene_clips._black_clip") as fake_black:
        build_scene_clip(
            output_path=output,
            visual_type=VisualType.STOCK_IMAGE,
            asset_path=str(nonexistent),
            motion=Motion.STATIC,
            script_line="line",
            motion_intensity=1.0,
            background_hex="#000000",
            text_hex="#FFFFFF",
            font="Inter",
            width=1080,
            height=1920,
            fps=30,
            duration_frames=60,
        )

    fake_black.assert_called_once()


def test_text_card_never_falls_back_to_black_even_without_an_asset(tmp_path):
    output = tmp_path / "scene.mp4"
    with (
        patch("app.render.scene_clips._black_clip") as fake_black,
        patch("app.render.scene_clips._text_card_clip") as fake_text,
    ):
        build_scene_clip(
            output_path=output,
            visual_type=VisualType.TEXT_CARD,
            asset_path=None,
            motion=Motion.STATIC,
            script_line="narration goes here",
            motion_intensity=1.0,
            background_hex="#000000",
            text_hex="#FFFFFF",
            font="Inter",
            width=1080,
            height=1920,
            fps=30,
            duration_frames=60,
        )

    fake_black.assert_not_called()
    fake_text.assert_called_once()


def test_existing_video_asset_uses_video_clip_path(tmp_path):
    output = tmp_path / "scene.mp4"
    existing = tmp_path / "clip.mp4"
    existing.write_bytes(b"not a real video, just needs to exist")

    with (
        patch("app.render.scene_clips._black_clip") as fake_black,
        patch("app.render.scene_clips._video_clip") as fake_video,
    ):
        build_scene_clip(
            output_path=output,
            visual_type=VisualType.STOCK_VIDEO,
            asset_path=str(existing),
            motion=Motion.STATIC,
            script_line="line",
            motion_intensity=1.0,
            background_hex="#000000",
            text_hex="#FFFFFF",
            font="Inter",
            width=1080,
            height=1920,
            fps=30,
            duration_frames=60,
        )

    fake_black.assert_not_called()
    fake_video.assert_called_once()

"""Build one silent video clip per scene, dispatched by visual_type.

Cover-fit for images/video: scale up to cover the target frame, then crop
to exact size (`scale=...:force_original_aspect_ratio=increase,crop=W:H`).
Ken Burns motion is done with ffmpeg's `zoompan` filter; the zoom/pan
magnitude is `motion_intensity` scaled the same way the reference scales
its Remotion beat components (zoom: 15% * intensity; pan: 50px * intensity
at a constant 1.15x hold).

Any missing/None asset renders a black frame instead of raising - a failed
scene is a visual gap, never a crashed run.
"""

from pathlib import Path

from app.render.ffmpeg import default_font_file, escape_for_filter, run_ffmpeg
from app.schema.director import Motion, VisualType

COVER_FIT = "scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"


def _black_clip(output_path: Path, width: int, height: int, fps: int, duration_s: float) -> None:
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:r={fps}:d={duration_s}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def _text_card_clip(
    output_path: Path,
    script_line: str,
    *,
    background_hex: str,
    text_hex: str,
    font: str,
    width: int,
    height: int,
    fps: int,
    duration_s: float,
) -> None:
    safe_text = script_line.replace("'", "’").replace(":", "\\:")
    font_file = default_font_file()
    font_clause = f"fontfile='{escape_for_filter(font_file)}'" if font_file else f"font={font}"
    drawtext = (
        f"drawtext=text='{safe_text}':fontcolor={text_hex}:fontsize=72:"
        f"{font_clause}:x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    )
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c={background_hex}:s={width}x{height}:r={fps}:d={duration_s}",
            "-vf",
            drawtext,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def _ken_burns_filter(
    motion: Motion, intensity: float, width: int, height: int, frames: int
) -> str:
    frames = max(frames, 1)
    zoom_amount = 0.15 * intensity
    pan_px = 50 * intensity

    if motion == Motion.ZOOM_IN:
        zoom_expr = f"1+{zoom_amount}*on/{frames}"
        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == Motion.ZOOM_OUT:
        zoom_expr = f"1+{zoom_amount}-{zoom_amount}*on/{frames}"
        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == Motion.PAN_LEFT:
        zoom_expr = "1.15"
        x_expr = f"(iw-iw/zoom)/2+{pan_px}*(1-on/{frames})"
        y_expr = "ih/2-(ih/zoom/2)"
    elif motion == Motion.PAN_RIGHT:
        zoom_expr = "1.15"
        x_expr = f"(iw-iw/zoom)/2-{pan_px}*(1-on/{frames})"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # static
        zoom_expr = "1"
        x_expr, y_expr = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

    return (
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}"
    )


def _still_image_clip(
    output_path: Path,
    asset_path: Path,
    *,
    motion: Motion,
    motion_intensity: float,
    width: int,
    height: int,
    fps: int,
    duration_frames: int,
) -> None:
    cover = COVER_FIT.format(w=width * 2, h=height * 2)
    ken_burns = _ken_burns_filter(motion, motion_intensity, width, height, duration_frames)
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(asset_path),
            "-vf",
            f"{cover},{ken_burns},fps={fps}",
            "-frames:v",
            str(duration_frames),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def _video_clip(
    output_path: Path,
    asset_path: Path,
    *,
    width: int,
    height: int,
    fps: int,
    duration_s: float,
) -> None:
    cover = COVER_FIT.format(w=width, h=height)
    run_ffmpeg(
        [
            "-stream_loop",
            "-1",
            "-i",
            str(asset_path),
            "-vf",
            f"{cover},fps={fps}",
            "-t",
            str(duration_s),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def build_scene_clip(
    *,
    output_path: Path,
    visual_type: VisualType,
    asset_path: str | None,
    motion: Motion,
    script_line: str,
    motion_intensity: float,
    background_hex: str,
    text_hex: str,
    font: str,
    width: int,
    height: int,
    fps: int,
    duration_frames: int,
) -> None:
    duration_s = duration_frames / fps

    if visual_type == VisualType.TEXT_CARD:
        _text_card_clip(
            output_path,
            script_line,
            background_hex=background_hex,
            text_hex=text_hex,
            font=font,
            width=width,
            height=height,
            fps=fps,
            duration_s=duration_s,
        )
        return

    resolved_asset = Path(asset_path) if asset_path else None
    if resolved_asset is None or not resolved_asset.exists():
        _black_clip(output_path, width, height, fps, duration_s)
        return

    if visual_type in (VisualType.AI_IMAGE, VisualType.STOCK_IMAGE):
        _still_image_clip(
            output_path,
            resolved_asset,
            motion=motion,
            motion_intensity=motion_intensity,
            width=width,
            height=height,
            fps=fps,
            duration_frames=duration_frames,
        )
        return

    # stock_video, ai_video
    _video_clip(
        output_path, resolved_asset, width=width, height=height, fps=fps, duration_s=duration_s
    )

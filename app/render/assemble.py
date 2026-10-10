"""Concat scene clips with transitions, burn in captions, mux audio.

Transition handling note: scene durations in RenderSpec are locked to the
audio timeline (see app/pipeline/render_spec.py). FFmpeg's `xfade` filter
eats `duration` seconds out of the combined length when it overlaps two
clips, which would shrink the timeline below what the audio/captions
expect. To cancel that out exactly, the outgoing clip of every
transitioning boundary is first padded with `tpad` (a frozen hold of its
last frame) for the transition's own duration, so the xfade's overlap
consumes the padding rather than real content, and the net length after
the crossfade equals `cumulative_so_far + next_clip_duration` - i.e.
nothing shrinks.
"""

from pathlib import Path

from app.render.ffmpeg import default_font_file, escape_for_filter, run_ffmpeg
from app.render.transitions import xfade_type_for
from app.schema.render import SceneRenderSpec


def concat_with_transitions(
    clip_paths: list[Path], specs: list[SceneRenderSpec], fps: int, output_path: Path
) -> None:
    if len(clip_paths) != len(specs):
        raise ValueError("clip_paths and specs must be the same length")
    if not clip_paths:
        raise ValueError("need at least one scene clip")

    if len(clip_paths) == 1:
        run_ffmpeg(["-i", str(clip_paths[0]), "-c", "copy", str(output_path)])
        return

    inputs: list[str] = []
    for clip in clip_paths:
        inputs += ["-i", str(clip)]

    durations = [spec.duration_frames / fps for spec in specs]
    filters = ["[0:v]null[v0]"]
    current_label = "v0"
    cumulative = durations[0]

    for i in range(1, len(clip_paths)):
        outgoing_transition = specs[i - 1].transition
        xfade_type = xfade_type_for(outgoing_transition)

        if xfade_type is None:  # Transition.NONE -> hard cut, plain concat
            filters.append(f"[{current_label}][{i}:v]concat=n=2:v=1:a=0[v{i}]")
            cumulative += durations[i]
        else:
            dur_s = specs[i - 1].transition_duration_frames / fps
            padded_label = f"pad{i}"
            filters.append(
                f"[{current_label}]tpad=stop_mode=clone:stop_duration={dur_s}[{padded_label}]"
            )
            filters.append(
                f"[{padded_label}][{i}:v]xfade=transition={xfade_type}:"
                f"duration={dur_s}:offset={cumulative}[v{i}]"
            )
            cumulative += durations[i]

        current_label = f"v{i}"

    filter_complex = ";".join(filters)
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            f"[{current_label}]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def burn_captions(video_path: Path, ass_path: Path, output_path: Path) -> None:
    escaped = escape_for_filter(str(ass_path))
    # libass resolves the ASS style's font ("Arial") through fontconfig by
    # default, which may not be configured (see app/render/ffmpeg.py's
    # default_font_file docstring - found the same way, by actually
    # running a render). fontsdir points libass at a directory to search
    # directly, independent of fontconfig.
    ass_filter = f"ass={escaped}"
    font_file = default_font_file()
    if font_file:
        fontsdir = escape_for_filter(str(Path(font_file).parent))
        ass_filter += f":fontsdir={fontsdir}"
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-vf",
            ass_filter,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )


def mux_audio(
    video_path: Path,
    voiceover_path: Path,
    music_path: Path | None,
    output_path: Path,
    *,
    music_volume: float = 0.15,
) -> None:
    """Mux voiceover (full volume) and an optional looped, fixed-volume
    music bed (no ducking, matching the reference) onto the video.

    No `-shortest`: the video is deliberately ~0.5s longer than the
    voiceover (render_spec's tail padding, so the last line of narration
    isn't cut off mid-breath) - `-shortest` would trim that padding right
    back off, defeating the point. Found by actually measuring a rendered
    offline video's duration against the voiceover, not by inspection.
    """
    if music_path is None:
        run_ffmpeg(
            [
                "-i",
                str(video_path),
                "-i",
                str(voiceover_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(output_path),
            ]
        )
        return

    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-i",
            str(voiceover_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter_complex",
            f"[2:a]volume={music_volume}[m];"
            f"[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            str(output_path),
        ]
    )

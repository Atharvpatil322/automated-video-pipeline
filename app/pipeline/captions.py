"""Caption chunking, word-state and ASS subtitle generation.

Chunking/word-state/window logic is pure (no I/O, no FFmpeg). ASS style
mapping intentionally simplifies several of the 7 archetype caption
styles, since ASS/libass has no spring physics or per-frame transform
animation:

- bold_outline: thick static outline, no animation.
- color_highlight: active word recolors via inline override, no motion.
- clean: minimal styling, smallest outline.
- karaoke_sweep: the one style with real motion - a per-word `\\kf` fill
  sweep, which is what ASS karaoke tags are built for.
- gradient_rise: approximated as a per-chunk fade-in (`\\fad`); there is no
  practical way to animate a vertical "rise" per character in ASS without
  per-frame \\move hacks, so this is the most simplified of the seven.
- block_impact: bold, larger font; no "impact" pop/scale animation.
- box_highlight: BorderStyle=3 gives a real opaque box behind the text,
  which is the one effect ASS reproduces exactly.

All seven get the same karaoke (`\\k`) word-level timing tags for the
unspoken/active/spoken progression; styles differ in color/outline/box.
"""

from app.config.archetype import ColorPalette
from app.schema.captions import CaptionStyle, WordState
from app.schema.providers import WordTimestamp

DEFAULT_CHUNK_SIZE = 5
DEFAULT_LINGER_S = 0.3


def chunk_words(words: list[WordTimestamp], chunk_size: int) -> list[list[WordTimestamp]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [words[i : i + chunk_size] for i in range(0, len(words), chunk_size)]


def word_state(word: WordTimestamp, t: float) -> WordState:
    if t < word.start:
        return WordState.UNSPOKEN
    if t < word.end:
        return WordState.ACTIVE
    return WordState.SPOKEN


def compute_chunk_windows(
    chunks: list[list[WordTimestamp]], linger_s: float
) -> list[tuple[float, float]]:
    """(start, end) for each chunk: starts at its first word, stays on
    screen through its last word plus `linger_s`, but is cut short if the
    next chunk's first word has already started by then.
    """
    windows = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        start = chunk[0].start
        end = chunk[-1].end + linger_s
        if i + 1 < len(chunks) and chunks[i + 1]:
            next_start = chunks[i + 1][0].start
            end = min(end, next_start)
        windows.append((start, max(end, start)))
    return windows


def _ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = round((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


_STYLE_DEFS: dict[CaptionStyle, dict] = {
    CaptionStyle.BOLD_OUTLINE: {"bold": -1, "outline": 4, "border_style": 1, "fontsize": 72},
    CaptionStyle.COLOR_HIGHLIGHT: {"bold": 0, "outline": 1, "border_style": 1, "fontsize": 64},
    CaptionStyle.CLEAN: {"bold": 0, "outline": 1, "border_style": 1, "fontsize": 60},
    CaptionStyle.KARAOKE_SWEEP: {"bold": 0, "outline": 2, "border_style": 1, "fontsize": 64},
    CaptionStyle.GRADIENT_RISE: {"bold": 0, "outline": 1, "border_style": 1, "fontsize": 64},
    CaptionStyle.BLOCK_IMPACT: {"bold": -1, "outline": 2, "border_style": 1, "fontsize": 76},
    CaptionStyle.BOX_HIGHLIGHT: {"bold": 0, "outline": 0, "border_style": 3, "fontsize": 64},
}


def _hex_to_ass_bgr(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H00{b}{g}{r}".upper()


def _build_style_line(style: CaptionStyle, palette: ColorPalette) -> str:
    cfg = _STYLE_DEFS[style]
    primary = _hex_to_ass_bgr(palette.text)
    secondary = _hex_to_ass_bgr(palette.accent)
    outline_color = "&H00000000"
    back_color = "&H80000000" if cfg["border_style"] == 3 else "&H00000000"
    return (
        f"Style: Default,Arial,{cfg['fontsize']},{primary},{secondary},"
        f"{outline_color},{back_color},{cfg['bold']},0,0,0,100,100,0,0,"
        f"{cfg['border_style']},{cfg['outline']},0,2,60,60,160,0"
    )


def _dialogue_text(chunk: list[WordTimestamp], style: CaptionStyle) -> str:
    """Build the ASS text for one chunk, using \\k (hard karaoke) tags per
    word so playback highlights the active word via the style's secondary
    color. karaoke_sweep uses \\kf for a continuous fill sweep instead.
    """
    tag = "kf" if style == CaptionStyle.KARAOKE_SWEEP else "k"
    parts = []
    for word in chunk:
        centiseconds = max(1, round((word.end - word.start) * 100))
        parts.append(f"{{\\{tag}{centiseconds}}}{word.word}")
    text = " ".join(parts)
    if style == CaptionStyle.GRADIENT_RISE:
        text = "{\\fad(200,0)}" + text
    return text


def build_ass_document(
    words: list[WordTimestamp],
    *,
    style: CaptionStyle,
    chunk_size: int,
    linger_s: float,
    palette: ColorPalette,
    width: int,
    height: int,
) -> str:
    chunks = chunk_words(words, chunk_size)
    windows = compute_chunk_windows(chunks, linger_s)
    non_empty_chunks = [c for c in chunks if c]

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,"
        "Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"{_build_style_line(style, palette)}\n"
        "\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )

    lines = []
    for chunk, (start, end) in zip(non_empty_chunks, windows, strict=True):
        text = _dialogue_text(chunk, style)
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Default,,0,0,0,,{text}"
        )

    return header + "\n".join(lines) + "\n"

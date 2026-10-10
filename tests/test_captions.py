from app.config.archetype import ColorPalette
from app.pipeline.captions import (
    build_ass_document,
    chunk_words,
    compute_chunk_windows,
    word_state,
)
from app.schema.captions import CaptionStyle, WordState
from app.schema.providers import WordTimestamp


def words(n: int, gap: float = 0.0) -> list[WordTimestamp]:
    out = []
    t = 0.0
    for i in range(n):
        out.append(WordTimestamp(word=f"w{i}", start=t, end=t + 0.4))
        t += 0.4 + gap
    return out


def test_chunk_words_default_size_five():
    chunks = chunk_words(words(12), chunk_size=5)
    assert [len(c) for c in chunks] == [5, 5, 2]


def test_chunk_words_archetype_override_size_four():
    chunks = chunk_words(words(9), chunk_size=4)
    assert [len(c) for c in chunks] == [4, 4, 1]


def test_chunk_words_rejects_non_positive_size():
    import pytest

    with pytest.raises(ValueError):
        chunk_words(words(5), chunk_size=0)


def test_word_state_unspoken_active_spoken():
    word = WordTimestamp(word="hi", start=1.0, end=2.0)
    assert word_state(word, 0.5) == WordState.UNSPOKEN
    assert word_state(word, 1.5) == WordState.ACTIVE
    assert word_state(word, 2.5) == WordState.SPOKEN


def test_chunk_window_includes_linger_after_last_word():
    chunks = [words(2)]  # single chunk: w0 [0,0.4), w1 [0.4,0.8)
    windows = compute_chunk_windows(chunks, linger_s=0.3)
    assert windows == [(0.0, 0.8 + 0.3)]


def test_chunk_window_cut_short_by_next_chunk_start():
    all_words = words(4)
    chunks = [all_words[:2], all_words[2:]]  # second chunk starts at 0.8
    # with a large linger, the first window would run past 0.8 - must clip
    windows = compute_chunk_windows(chunks, linger_s=5.0)
    assert windows[0][1] == chunks[1][0].start


def test_chunk_window_skips_empty_chunks():
    windows = compute_chunk_windows([[], words(1)], linger_s=0.3)
    assert len(windows) == 1


def test_build_ass_document_has_required_sections():
    doc = build_ass_document(
        words(10),
        style=CaptionStyle.CLEAN,
        chunk_size=5,
        linger_s=0.3,
        palette=ColorPalette(background="#000000", accent="#FF0000", text="#FFFFFF"),
        width=1080,
        height=1920,
    )
    assert "[Script Info]" in doc
    assert "[V4+ Styles]" in doc
    assert "[Events]" in doc
    assert doc.count("Dialogue:") == 2  # 10 words / chunk_size 5


def test_build_ass_document_includes_karaoke_tags_for_each_word():
    doc = build_ass_document(
        words(3),
        style=CaptionStyle.CLEAN,
        chunk_size=5,
        linger_s=0.3,
        palette=ColorPalette(background="#000000", accent="#FF0000", text="#FFFFFF"),
        width=1080,
        height=1920,
    )
    assert doc.count("\\k") == 3


def test_karaoke_sweep_style_uses_fill_karaoke_tag():
    doc = build_ass_document(
        words(2),
        style=CaptionStyle.KARAOKE_SWEEP,
        chunk_size=5,
        linger_s=0.3,
        palette=ColorPalette(background="#000000", accent="#FF0000", text="#FFFFFF"),
        width=1080,
        height=1920,
    )
    assert "\\kf" in doc


def test_box_highlight_style_uses_opaque_box_border_style():
    doc = build_ass_document(
        words(2),
        style=CaptionStyle.BOX_HIGHLIGHT,
        chunk_size=5,
        linger_s=0.3,
        palette=ColorPalette(background="#000000", accent="#FF0000", text="#FFFFFF"),
        width=1080,
        height=1920,
    )
    style_line = next(line for line in doc.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    # BorderStyle is the 16th comma-separated field (0-indexed 15)
    assert fields[15] == "3"


def test_empty_word_list_produces_no_dialogue_lines():
    doc = build_ass_document(
        [],
        style=CaptionStyle.CLEAN,
        chunk_size=5,
        linger_s=0.3,
        palette=ColorPalette(background="#000000", accent="#FF0000", text="#FFFFFF"),
        width=1080,
        height=1920,
    )
    assert doc.count("Dialogue:") == 0

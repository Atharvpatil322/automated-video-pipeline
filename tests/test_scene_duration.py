from app.pipeline.word_timing import scene_duration
from app.schema.providers import WordTimestamp


def test_duration_is_span_plus_half_second_padding():
    words = [WordTimestamp(word="hi", start=1.0, end=3.0)]
    start, end, duration = scene_duration(words)
    assert start == 1.0
    assert end == 3.0
    assert duration == 2.5


def test_duration_spans_first_word_start_to_last_word_end():
    words = [
        WordTimestamp(word="a", start=1.0, end=1.4),
        WordTimestamp(word="b", start=1.4, end=1.8),
        WordTimestamp(word="c", start=1.8, end=4.0),
    ]
    start, end, duration = scene_duration(words)
    assert start == 1.0
    assert end == 4.0
    assert duration == 3.5


def test_duration_floors_at_two_seconds():
    words = [WordTimestamp(word="hi", start=1.0, end=1.2)]
    _, _, duration = scene_duration(words)
    assert duration == 2.0


def test_no_words_gives_three_second_placeholder():
    start, end, duration = scene_duration([])
    assert duration == 3.0
    assert end == 3.0

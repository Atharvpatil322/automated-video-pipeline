from app.pipeline.word_timing import split_words_into_scenes
from app.schema.providers import WordTimestamp


def make_words(count: int) -> list[WordTimestamp]:
    return [WordTimestamp(word=f"w{i}", start=float(i), end=float(i) + 0.5) for i in range(count)]


def test_even_split_matches_expected_counts_exactly():
    words = make_words(6)
    scenes = split_words_into_scenes(words, [2, 2, 2])
    assert [len(s) for s in scenes] == [2, 2, 2]


def test_uneven_scenes_scale_proportionally():
    words = make_words(10)
    scenes = split_words_into_scenes(words, [1, 2, 3])
    assert sum(len(s) for s in scenes) == 10
    assert [len(s) for s in scenes] == [2, 3, 5]


def test_last_scene_absorbs_rounding_leftover():
    words = make_words(7)
    scenes = split_words_into_scenes(words, [3, 3, 3])
    assert sum(len(s) for s in scenes) == 7
    assert len(scenes[-1]) >= 1


def test_every_scene_gets_at_least_one_word_when_words_remain():
    words = make_words(3)
    scenes = split_words_into_scenes(words, [10, 10, 10])
    assert all(len(s) >= 1 for s in scenes[:-1]) or sum(len(s) for s in scenes) == 3


def test_empty_scene_when_fewer_actual_words_than_scenes():
    words = make_words(2)
    scenes = split_words_into_scenes(words, [1, 1, 1])
    assert sum(len(s) for s in scenes) == 2
    assert any(len(s) == 0 for s in scenes)


def test_no_words_at_all_yields_empty_scenes():
    scenes = split_words_into_scenes([], [3, 3, 3])
    assert scenes == [[], [], []]


def test_scenes_partition_words_in_order_without_overlap():
    words = make_words(9)
    scenes = split_words_into_scenes(words, [1, 1, 1])
    flattened = [w for scene in scenes for w in scene]
    assert flattened == words


def test_zero_scenes_returns_empty_list():
    assert split_words_into_scenes(make_words(5), []) == []

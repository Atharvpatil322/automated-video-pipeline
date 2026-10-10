"""Pure functions mapping a flat word-timestamp list onto scenes.

No I/O here. `split_words_into_scenes` exists because TTS word counts often
differ from the script's own word count (numbers and abbreviations expand
when spoken), so each scene's share of words is scaled proportionally
rather than counted directly from `script_line.split()`.
"""

from typing import NamedTuple

from app.schema.providers import WordTimestamp

MIN_DURATION_SECONDS = 2.0
NO_WORDS_DURATION_SECONDS = 3.0
DURATION_PADDING_SECONDS = 0.5


class SceneTiming(NamedTuple):
    start: float
    end: float
    duration: float


def split_words_into_scenes(
    words: list[WordTimestamp], expected_word_counts: list[int]
) -> list[list[WordTimestamp]]:
    """Split `words` across `len(expected_word_counts)` scenes, in
    proportion to each scene's expected (script) word count. Every scene
    gets at least one word if any words remain to distribute; the last
    scene absorbs whatever rounding leaves over.
    """
    scene_count = len(expected_word_counts)
    if scene_count == 0:
        return []
    total_actual = len(words)
    total_expected = sum(expected_word_counts)

    if total_actual == 0:
        return [[] for _ in range(scene_count)]

    if total_expected == 0:
        # No basis for proportions; split as evenly as possible.
        expected_word_counts = [1] * scene_count
        total_expected = scene_count

    allocations = []
    running_total = 0
    for expected in expected_word_counts[:-1]:
        share = max(1, round(expected / total_expected * total_actual))
        share = min(share, total_actual - running_total)
        allocations.append(share)
        running_total += share
    allocations.append(total_actual - running_total)

    scenes: list[list[WordTimestamp]] = []
    cursor = 0
    for count in allocations:
        scenes.append(words[cursor : cursor + count])
        cursor += count
    return scenes


def scene_duration(scene_words: list[WordTimestamp]) -> SceneTiming:
    """Return (start, end, duration) for one scene's word slice.

    duration = (last word end - first word start) + 0.5s, floored at 2s.
    A scene with no timed words at all gets a fixed 3s placeholder, matching
    the reference orchestrator's behavior for untimed scenes.
    """
    if not scene_words:
        return SceneTiming(0.0, NO_WORDS_DURATION_SECONDS, NO_WORDS_DURATION_SECONDS)

    start = scene_words[0].start
    end = scene_words[-1].end
    duration = max(MIN_DURATION_SECONDS, (end - start) + DURATION_PADDING_SECONDS)
    return SceneTiming(start, end, duration)

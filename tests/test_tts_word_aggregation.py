from app.providers.tts.elevenlabs import aggregate_characters_to_words


def chars(text: str, step: float = 0.1):
    """Build (characters, start_times, end_times) with each char `step`
    seconds long, back to back starting at 0."""
    starts = [i * step for i in range(len(text))]
    ends = [s + step for s in starts]
    return list(text), starts, ends


def test_simple_words_split_on_whitespace():
    characters, starts, ends = chars("hi there")
    words = aggregate_characters_to_words(characters, starts, ends)
    assert [w.word for w in words] == ["hi", "there"]


def test_apostrophe_stays_attached_to_its_word():
    characters, starts, ends = chars("don't stop")
    words = aggregate_characters_to_words(characters, starts, ends)
    assert [w.word for w in words] == ["don't", "stop"]


def test_trailing_punctuation_stays_attached():
    characters, starts, ends = chars("well-known, yes.")
    words = aggregate_characters_to_words(characters, starts, ends)
    assert [w.word for w in words] == ["well-known,", "yes."]


def test_multiple_spaces_produce_no_empty_words():
    characters, starts, ends = chars("a    b")
    words = aggregate_characters_to_words(characters, starts, ends)
    assert [w.word for w in words] == ["a", "b"]


def test_word_start_and_end_span_its_characters():
    characters, starts, ends = chars("hi there", step=0.1)
    words = aggregate_characters_to_words(characters, starts, ends)
    hi = words[0]
    assert hi.start == 0.0
    assert hi.end == 0.2  # 2 characters * 0.1s each, end of 2nd char

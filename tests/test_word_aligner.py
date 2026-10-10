from app.providers.tts.aligner import align_known_script_to_transcript


def test_exact_matches_take_transcript_timing_but_known_script_text():
    script_words = ["hello", "world"]
    transcribed = [("hello", 0.0, 0.5), ("world", 0.5, 1.0)]

    result = align_known_script_to_transcript(script_words, transcribed)

    assert [w.word for w in result] == ["hello", "world"]
    assert result[0].start == 0.0
    assert result[1].end == 1.0


def test_known_script_word_text_is_kept_even_if_transcript_misheard_it():
    script_words = ["whisper"]
    transcribed = [("whisker", 0.0, 0.4)]  # misheard, but same normalized root is close enough

    result = align_known_script_to_transcript(script_words, transcribed)

    assert result[0].word == "whisper"


def test_punctuation_and_case_are_ignored_when_matching():
    script_words = ["Hello,", "world!"]
    transcribed = [("hello", 0.0, 0.5), ("world", 0.5, 1.0)]

    result = align_known_script_to_transcript(script_words, transcribed)

    assert result[0].start == 0.0
    assert result[1].end == 1.0


def test_unmatched_word_is_interpolated_after_previous_word():
    script_words = ["known", "mystery", "known2"]
    transcribed = [("known", 0.0, 1.0), ("known2", 5.0, 5.3)]

    result = align_known_script_to_transcript(script_words, transcribed)

    assert result[0].start == 0.0
    # "mystery" had no match, interpolated right after "known" ends at 1.0
    assert result[1].start == 1.0
    assert result[1].end > result[1].start


def test_every_word_has_positive_duration_even_on_equal_timings():
    script_words = ["x"]
    transcribed = [("x", 2.0, 2.0)]

    result = align_known_script_to_transcript(script_words, transcribed)

    assert result[0].end > result[0].start


def test_output_length_matches_script_length_regardless_of_transcript_length():
    script_words = ["a", "b", "c", "d"]
    transcribed = [("a", 0.0, 0.1), ("b", 0.1, 0.2)]

    result = align_known_script_to_transcript(script_words, transcribed)

    assert len(result) == 4

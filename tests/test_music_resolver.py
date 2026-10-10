import random

from app.pipeline.music import MusicManifestEntry, resolve_music, validate_manifest


def make_entry(id_: str, mood: str, filename: str) -> MusicManifestEntry:
    return MusicManifestEntry(id=id_, mood=mood, filename=filename)


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-audio-bytes")


def test_no_music_flag_always_returns_none_even_with_tracks_available(tmp_path):
    entry = make_entry("a", "chill_lofi", "a.mp3")
    touch(tmp_path / "a.mp3")

    result = resolve_music("chill_lofi", no_music=True, manifest=[entry], music_dir=tmp_path)

    assert result is None


def test_picks_a_track_matching_the_requested_mood(tmp_path):
    entry = make_entry("a", "chill_lofi", "a.mp3")
    other = make_entry("b", "epic_cinematic", "b.mp3")
    touch(tmp_path / "a.mp3")
    touch(tmp_path / "b.mp3")

    result = resolve_music(
        "chill_lofi", manifest=[entry, other], music_dir=tmp_path, rng=random.Random(0)
    )

    assert result == tmp_path / "a.mp3"


def test_unknown_mood_falls_back_to_any_track(tmp_path):
    entry = make_entry("a", "chill_lofi", "a.mp3")
    touch(tmp_path / "a.mp3")

    result = resolve_music(
        "mood_with_no_tracks", manifest=[entry], music_dir=tmp_path, rng=random.Random(0)
    )

    assert result == tmp_path / "a.mp3"


def test_empty_manifest_returns_none_without_error(tmp_path):
    result = resolve_music("chill_lofi", manifest=[], music_dir=tmp_path)

    assert result is None


def test_missing_files_on_disk_never_raises_and_returns_none(tmp_path):
    entry = make_entry("a", "chill_lofi", "missing.mp3")  # not written to disk

    result = resolve_music("chill_lofi", manifest=[entry], music_dir=tmp_path)

    assert result is None


def test_falls_through_to_a_track_that_exists_when_preferred_mood_track_is_missing(tmp_path):
    missing = make_entry("a", "chill_lofi", "missing.mp3")
    present = make_entry("b", "chill_lofi", "present.mp3")
    touch(tmp_path / "present.mp3")

    result = resolve_music(
        "chill_lofi", manifest=[missing, present], music_dir=tmp_path, rng=random.Random(1)
    )

    assert result == tmp_path / "present.mp3"


def test_validate_manifest_warns_about_missing_files_but_does_not_raise(tmp_path):
    present = make_entry("a", "chill_lofi", "present.mp3")
    missing = make_entry("b", "chill_lofi", "missing.mp3")
    touch(tmp_path / "present.mp3")

    warnings = validate_manifest([present, missing], tmp_path)

    assert len(warnings) == 1
    assert "missing.mp3" in warnings[0]


def test_validate_manifest_no_warnings_when_all_files_present(tmp_path):
    present = make_entry("a", "chill_lofi", "present.mp3")
    touch(tmp_path / "present.mp3")

    assert validate_manifest([present], tmp_path) == []

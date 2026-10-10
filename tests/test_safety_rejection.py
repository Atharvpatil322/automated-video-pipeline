from app.pipeline.safety import is_safety_rejection


def test_detects_safety_phrase():
    assert is_safety_rejection(Exception("Your request was rejected due to safety reasons"))


def test_detects_content_policy_phrase():
    assert is_safety_rejection(Exception("Image generation failed: content_policy_violation"))


def test_detects_blocked_phrase_case_insensitive():
    assert is_safety_rejection(Exception("Response BLOCKED by moderation"))


def test_unrelated_error_is_not_a_safety_rejection():
    assert not is_safety_rejection(Exception("connection timed out"))


def test_rate_limit_error_is_not_a_safety_rejection():
    assert not is_safety_rejection(Exception("429 rate limit exceeded"))

"""Provider-neutral safety-rejection detection.

Matches the reference: there's no shared error type across image vendors,
so a rejection is detected by phrase-matching the error text rather than a
vendor-specific exception/finish-reason check.
"""

_REJECTION_PHRASES = (
    "safety",
    "content policy",
    "content_policy",
    "content moderation",
    "blocked",
    "flagged",
)


def is_safety_rejection(error: Exception) -> bool:
    text = str(error).lower()
    return any(phrase in text for phrase in _REJECTION_PHRASES)

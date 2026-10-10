from app.schema.visuals import VerificationResult


class OfflineVisionVerifier:
    """Always accepts - offline mode has no real vision model to call."""

    async def verify(
        self, image_bytes: bytes, visual_prompt: str, narration: str
    ) -> VerificationResult:
        return VerificationResult(relevant=True, confidence=0.9, reason="offline: auto-accepted")

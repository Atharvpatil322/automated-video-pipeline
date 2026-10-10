from app.providers.image.gemini_image import GeminiImageProvider
from app.providers.image.openai_image import OpenAIImageProvider
from app.providers.llm.groq_llm import GroqLLMProvider
from app.providers.offline.offline_image import OfflineImageProvider
from app.providers.offline.offline_llm import OfflineLLMProvider
from app.providers.offline.offline_stock import OfflineStockProvider
from app.providers.offline.offline_tts import OfflineTTSProvider
from app.providers.offline.offline_video import OfflineVideoProvider
from app.providers.offline.offline_vision import OfflineVisionVerifier
from app.providers.stock.pexels import PexelsStockProvider
from app.providers.stock.pixabay import PixabayStockProvider
from app.providers.tts.aligned import AlignedTTSProvider
from app.providers.tts.aligner import GroqWhisperAligner
from app.providers.tts.elevenlabs import ElevenLabsTTSProvider
from app.providers.tts.openai_tts import OpenAITTSProvider
from app.providers.video.fal_kling import FalKlingVideoProvider
from app.providers.vision.groq_vision import GroqVisionVerifier
from app.schema.providers import (
    ImageProvider,
    LLMProvider,
    StockProvider,
    TTSProvider,
    VideoProvider,
)

# "offline" is the one deterministic, no-network, no-key provider set, kept
# as a plain string switch in each factory function below rather than a
# separate code path per stage - this is the single place that decides
# whether any given capability is real or faked.
OFFLINE = "offline"


def create_llm_provider(keys: dict[str, str], provider: str = "groq") -> LLMProvider:
    """Build the LLM provider from a per-job keys map.

    Phase 1 supports a single real vendor (Groq); Phase 6 adds 'offline'.
    Keys are never read from environment/global state inside provider
    classes; the factory is the only place allowed to fall back to
    `os.environ` when a job omits a key.
    """
    if provider == OFFLINE:
        return OfflineLLMProvider()

    api_key = keys.get("groq")
    if not api_key:
        raise ValueError("missing 'groq' API key in job keys")
    return GroqLLMProvider(api_key=api_key)


def create_tts_provider(keys: dict[str, str], provider: str) -> TTSProvider:
    """Build the TTS provider from a per-job keys map.

    'elevenlabs' returns native word timestamps. 'openai' does not, so it is
    wrapped in AlignedTTSProvider backed by Groq's hosted Whisper, which
    needs its own 'groq' key alongside the TTS vendor's key.
    """
    if provider == OFFLINE:
        return OfflineTTSProvider()

    if provider == "elevenlabs":
        api_key = keys.get("elevenlabs")
        if not api_key:
            raise ValueError("missing 'elevenlabs' API key in job keys")
        return ElevenLabsTTSProvider(api_key=api_key)

    if provider == "openai":
        openai_key = keys.get("openai")
        if not openai_key:
            raise ValueError("missing 'openai' API key in job keys")
        groq_key = keys.get("groq")
        if not groq_key:
            raise ValueError("missing 'groq' API key in job keys (needed for word alignment)")
        inner = OpenAITTSProvider(api_key=openai_key)
        aligner = GroqWhisperAligner(api_key=groq_key)
        return AlignedTTSProvider(inner=inner, aligner=aligner)

    raise ValueError(f"unknown tts provider '{provider}'")


def create_image_provider(keys: dict[str, str], provider: str) -> ImageProvider:
    if provider == OFFLINE:
        return OfflineImageProvider()

    if provider == "openai":
        api_key = keys.get("openai")
        if not api_key:
            raise ValueError("missing 'openai' API key in job keys")
        return OpenAIImageProvider(api_key=api_key)

    if provider == "gemini":
        api_key = keys.get("gemini")
        if not api_key:
            raise ValueError("missing 'gemini' API key in job keys")
        return GeminiImageProvider(api_key=api_key)

    raise ValueError(f"unknown image provider '{provider}'")


def create_stock_providers(keys: dict[str, str], offline: bool = False) -> list[StockProvider]:
    """Ordered provider list, primary first. Both real providers are
    skipped (not errors) when their key is absent, since stock is optional
    - the resolver falls back to AI image generation when the list is
    empty. Offline mode uses one local fake provider instead.
    """
    if offline:
        return [OfflineStockProvider()]

    providers: list[StockProvider] = []
    if api_key := keys.get("pexels"):
        providers.append(PexelsStockProvider(api_key=api_key))
    if api_key := keys.get("pixabay"):
        providers.append(PixabayStockProvider(api_key=api_key))
    return providers


def create_vision_verifier(keys: dict[str, str], offline: bool = False) -> GroqVisionVerifier:
    if offline:
        return OfflineVisionVerifier()

    api_key = keys.get("groq")
    if not api_key:
        raise ValueError("missing 'groq' API key in job keys (needed for stock verification)")
    return GroqVisionVerifier(api_key=api_key)


def create_video_provider(keys: dict[str, str], offline: bool = False) -> VideoProvider | None:
    """Returns None (not an error) when no 'fal' key is configured - the
    visuals stage treats a missing video provider as ai_video being
    unavailable and falls back to the still image. Offline mode always
    returns the local fake rather than None, so --offline exercises the
    real ai_video code path end to end.
    """
    if offline:
        return OfflineVideoProvider()

    api_key = keys.get("fal")
    if not api_key:
        return None
    return FalKlingVideoProvider(api_key=api_key)

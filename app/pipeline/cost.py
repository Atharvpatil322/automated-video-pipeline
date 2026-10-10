"""Cost estimation and actual-usage tracking. Prices live only here, in one
module with a dated comment, so every other module just reports quantities
(characters, images, seconds, tokens) and this file is the only place that
turns a quantity into a dollar amount.
"""

from app.schema.cost import CostActual, CostBreakdown, CostEstimate
from app.schema.director import DirectorScore, VisualType
from app.schema.providers import Usage

# Priced Oct 2026.
TTS_PRICE_PER_CHAR: dict[str, float] = {
    "elevenlabs": 0.00018,
    "openai": 0.00005,
}

# gpt-image-1 at the "1024x1536"/medium quality tier we request;
# gemini-2.5-flash-image per Google's per-image rate.
IMAGE_PRICE_PER_IMAGE: dict[str, float] = {
    "openai": 0.07,
    "gemini": 0.04,
}

# Pexels/Pixabay are free-tier APIs; stock search+download costs $0.
STOCK_PRICE_PER_SEARCH: dict[str, float] = {
    "pexels": 0.0,
    "pixabay": 0.0,
}

# fal.ai's Kling 2.5 Turbo Pro: $0.35 for the first 5s, then $0.07/s after -
# averaged here to a flat per-second rate since the estimate only knows the
# planned duration, not which tier it lands in.
VIDEO_PRICE_PER_SECOND: dict[str, float] = {
    "fal": 0.07,
}

# Groq is this build's only LLM vendor (Phase 1) and is free-tier, so every
# LLM/VLM call - director, critic, image/query/video prompters, stock
# verification - prices at $0 here. Swapping in a priced vendor only means
# adding its $/million-token rate to this table; nothing else changes.
LLM_PRICE_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "groq": (0.0, 0.0),  # (input, output)
}

# Fixed token assumptions per agent call, same approach as the reference:
# an estimate can't know real usage before the call happens, so each call
# type gets a documented (input, output) guess.
AGENT_TOKEN_ASSUMPTIONS: dict[str, tuple[int, int]] = {
    "research": (2000, 1000),
    "director_generate": (5000, 2000),
    "director_revise": (5000, 2000),
    "critic": (3000, 500),
    "image_prompter": (800, 200),
    "query_reformulator": (1500, 300),
    "video_prompter": (800, 200),
}

MAX_STOCK_SEARCH_ATTEMPTS = 4
DEFAULT_VIDEO_DURATION_S = 5.0


def estimate_tts_cost(provider: str, character_count: int) -> float:
    price = TTS_PRICE_PER_CHAR.get(provider, 0.0)
    return price * character_count


def estimate_image_cost(provider: str, image_count: int) -> float:
    price = IMAGE_PRICE_PER_IMAGE.get(provider, 0.0)
    return price * image_count


def estimate_video_cost(provider: str, total_duration_seconds: float) -> float:
    price = VIDEO_PRICE_PER_SECOND.get(provider, 0.0)
    return price * total_duration_seconds


def _llm_call_cost(llm_provider: str, call_type: str, call_count: int = 1) -> float:
    input_tokens, output_tokens = AGENT_TOKEN_ASSUMPTIONS[call_type]
    input_price, output_price = LLM_PRICE_PER_MILLION_TOKENS.get(llm_provider, (0.0, 0.0))
    per_call = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return per_call * call_count


def estimate_total_cost(
    score: DirectorScore,
    *,
    llm_provider: str,
    tts_provider: str,
    image_provider: str,
    video_provider: str | None,
    director_evaluations: int,
    director_revisions: int,
    include_final_critic: bool = True,
    stock_enabled: bool = False,
    video_enabled: bool = True,
) -> CostEstimate:
    """Called after the director stage finishes (so `director_evaluations`/
    `director_revisions` are real counts, not guesses), before TTS.
    """
    notes: list[str] = []

    character_count = sum(len(scene.script_line) for scene in score.scenes)
    tts_cost = estimate_tts_cost(tts_provider, character_count)

    ai_image_scenes = sum(1 for s in score.scenes if s.visual_type == VisualType.AI_IMAGE)
    ai_video_scenes = sum(1 for s in score.scenes if s.visual_type == VisualType.AI_VIDEO)
    stock_scenes = sum(
        1 for s in score.scenes if s.visual_type in (VisualType.STOCK_IMAGE, VisualType.STOCK_VIDEO)
    )

    images_cost = estimate_image_cost(image_provider, ai_image_scenes)
    if ai_video_scenes and video_enabled and video_provider:
        images_cost += estimate_image_cost(image_provider, ai_video_scenes)  # phase 1 of ai_video

    video_cost = 0.0
    if ai_video_scenes and video_enabled and video_provider:
        video_cost = estimate_video_cost(
            video_provider, ai_video_scenes * DEFAULT_VIDEO_DURATION_S
        )
    elif ai_video_scenes:
        notes.append(
            f"{ai_video_scenes} ai_video scene(s) will fall back to a still image "
            "(no video provider / --no-video)."
        )

    llm_cost = (
        _llm_call_cost(llm_provider, "research")
        + _llm_call_cost(llm_provider, "director_generate")
        + _llm_call_cost(llm_provider, "director_revise", director_revisions)
        + _llm_call_cost(llm_provider, "critic", director_evaluations)
        + _llm_call_cost(llm_provider, "image_prompter", ai_image_scenes)
        + _llm_call_cost(llm_provider, "image_prompter", ai_video_scenes)  # the still
        + _llm_call_cost(llm_provider, "video_prompter", ai_video_scenes)
    )
    if include_final_critic:
        llm_cost += _llm_call_cost(llm_provider, "critic")

    vlm_cost = 0.0
    if stock_enabled and stock_scenes:
        vlm_cost = stock_scenes * MAX_STOCK_SEARCH_ATTEMPTS * LLM_PRICE_PER_MILLION_TOKENS.get(
            "groq", (0.0, 0.0)
        )[0]
        llm_cost += _llm_call_cost(llm_provider, "query_reformulator", stock_scenes)

    if stock_scenes:
        worst_case_stock_fallback = estimate_image_cost(image_provider, stock_scenes)
        notes.append(
            f"Worst case if all {stock_scenes} stock scene(s) fall back to AI image: "
            f"+${worst_case_stock_fallback:.4f} (not included in the total above)."
        )

    breakdown = CostBreakdown(
        llm=llm_cost, tts=tts_cost, images=images_cost, video=video_cost, stock=0.0, vlm=vlm_cost
    )
    return CostEstimate(breakdown=breakdown, notes=notes)


class CostTracker:
    """Accumulates real usage during a run; `actual()` turns it into a
    priced CostActual at the end, using the same price tables as the
    estimate so the two are directly comparable.
    """

    def __init__(self, llm_provider: str, tts_provider: str, image_provider: str) -> None:
        self._llm_provider = llm_provider
        self._tts_provider = tts_provider
        self._image_provider = image_provider
        self._llm_tokens: dict[str, tuple[int, int]] = {}
        self._tts_characters = 0
        self._image_count = 0
        self._video_seconds = 0.0
        self._video_provider: str | None = None
        self._vlm_calls = 0

    def add_llm_usage(self, call_type: str, usage: Usage) -> None:
        current_in, current_out = self._llm_tokens.get(call_type, (0, 0))
        self._llm_tokens[call_type] = (
            current_in + usage.input_tokens,
            current_out + usage.output_tokens,
        )

    def add_tts(self, character_count: int) -> None:
        self._tts_characters += character_count

    def add_image(self) -> None:
        self._image_count += 1

    def add_video(self, provider: str, seconds: float) -> None:
        self._video_provider = provider
        self._video_seconds += seconds

    def add_vlm_call(self) -> None:
        self._vlm_calls += 1

    def actual(self) -> CostActual:
        input_price, output_price = LLM_PRICE_PER_MILLION_TOKENS.get(
            self._llm_provider, (0.0, 0.0)
        )
        llm_cost = sum(
            (tokens_in * input_price + tokens_out * output_price) / 1_000_000
            for tokens_in, tokens_out in self._llm_tokens.values()
        )
        tts_cost = estimate_tts_cost(self._tts_provider, self._tts_characters)
        images_cost = estimate_image_cost(self._image_provider, self._image_count)
        video_cost = (
            estimate_video_cost(self._video_provider, self._video_seconds)
            if self._video_provider
            else 0.0
        )
        vlm_cost = self._vlm_calls * LLM_PRICE_PER_MILLION_TOKENS.get("groq", (0.0, 0.0))[0]

        return CostActual(
            breakdown=CostBreakdown(
                llm=llm_cost, tts=tts_cost, images=images_cost, video=video_cost, vlm=vlm_cost
            )
        )

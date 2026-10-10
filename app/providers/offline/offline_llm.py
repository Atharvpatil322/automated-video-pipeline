"""Deterministic offline LLM fake: no network, no API key.

Dispatches on the requested schema class and builds a valid instance
directly (no JSON round-trip, no retry loop needed - it's always valid).
Scene count/text are derived from the topic (via a stable hash) so
different topics produce different plans, while the same topic always
reproduces the same plan.
"""

from __future__ import annotations

import re

from app.schema.critique import CritiqueResult
from app.schema.director import DirectorScore, Motion, Scene, Transition, VisualType
from app.schema.providers import Usage
from app.schema.research import ResearchResult
from app.schema.visuals import ImagePromptResult, QueryReformulationResult, VerificationResult

_ZERO_USAGE = Usage(input_tokens=0, output_tokens=0)

# Cycled per scene index; guarantees no 3 consecutive scenes share a
# visual_type (never even 2 in a row, here) regardless of scene count.
_VISUAL_TYPE_CYCLE = [
    VisualType.AI_IMAGE,
    VisualType.TEXT_CARD,
    VisualType.STOCK_IMAGE,
    VisualType.TEXT_CARD,
    VisualType.AI_VIDEO,
    VisualType.TEXT_CARD,
]

_MUSIC_MOODS = [
    "epic_cinematic",
    "tense_electronic",
    "chill_lofi",
    "uplifting_pop",
    "mysterious_ambient",
    "warm_acoustic",
    "dark_cinematic",
    "dreamy_ethereal",
]


def _topic_seed(topic: str) -> int:
    return sum(ord(c) for c in topic) or 1


def _extract_topic(user_message: str) -> str:
    match = re.search(r"Topic:\s*(.+)", user_message)
    return match.group(1).strip() if match else "the topic"


def _extract_archetype(user_message: str) -> str:
    match = re.search(r"Archetype:\s*(\w+)", user_message) or re.search(
        r"archetype \('(\w+)'\)", user_message
    )
    return match.group(1) if match else "infographic"


def _build_research_result(user_message: str) -> ResearchResult:
    topic = _extract_topic(user_message)
    return ResearchResult(
        summary=f"An offline-generated overview of {topic}.",
        key_facts=[f"{topic} fact one.", f"{topic} fact two.", f"{topic} fact three."],
        mood="curious",
        sources=[],
    )


def _build_director_score(user_message: str) -> DirectorScore:
    topic = _extract_topic(user_message)
    archetype = _extract_archetype(user_message)
    seed = _topic_seed(topic)
    scene_count = 5 + (seed % 4)  # 5-8, safely within every pacing tier's range

    scenes = []
    for i in range(scene_count):
        visual_type = _VISUAL_TYPE_CYCLE[i % len(_VISUAL_TYPE_CYCLE)]
        if i == 0:
            line = f"Did you know {topic} is more interesting than you think?"
        elif i == scene_count - 1:
            line = f"Follow for more about {topic} like this."
        else:
            line = f"Here is fact number {i} about {topic} that most people miss."
        scenes.append(
            Scene(
                visual_type=visual_type,
                visual_prompt=f"Scene {i}: {topic}, illustrating fact {i}",
                motion=Motion.STATIC if visual_type == VisualType.AI_VIDEO else Motion.ZOOM_IN,
                script_line=line,
                transition=Transition.NONE if i == scene_count - 1 else None,
            )
        )

    return DirectorScore(
        emotional_arc="curiosity-to-wisdom",
        archetype=archetype,
        music_mood=_MUSIC_MOODS[seed % len(_MUSIC_MOODS)],
        scenes=scenes,
    )


def _build_critique_result() -> CritiqueResult:
    return CritiqueResult(
        score=8,
        strengths=["clear hook", "consistent pacing"],
        weaknesses=[],
        revision_needed=False,
        revision_instructions=None,
        weakest_scene_index=None,
    )


def _build_image_prompt_result(user_message: str) -> ImagePromptResult:
    match = re.search(r"Scene description:\s*(.+)", user_message)
    description = match.group(1).strip() if match else "offline scene"
    return ImagePromptResult(prompt=f"[offline] {description}")


def _build_query_reformulation_result(user_message: str) -> QueryReformulationResult:
    topic = _extract_topic(user_message) if "Topic:" in user_message else "offline query"
    match = re.search(r"Original query:\s*(.+)", user_message)
    base = match.group(1).strip() if match else topic
    return QueryReformulationResult(queries=[f"{base} alternative"])


def _build_verification_result() -> VerificationResult:
    return VerificationResult(relevant=True, confidence=0.9, reason="offline: auto-accepted")


class OfflineLLMProvider:
    async def generate(self, *, system_prompt: str, user_message: str, schema: type):
        if schema is ResearchResult:
            return _build_research_result(user_message), _ZERO_USAGE
        if schema is DirectorScore:
            return _build_director_score(user_message), _ZERO_USAGE
        if schema is CritiqueResult:
            return _build_critique_result(), _ZERO_USAGE
        if schema is ImagePromptResult:
            return _build_image_prompt_result(user_message), _ZERO_USAGE
        if schema is QueryReformulationResult:
            return _build_query_reformulation_result(user_message), _ZERO_USAGE
        if schema is VerificationResult:
            return _build_verification_result(), _ZERO_USAGE
        raise ValueError(f"OfflineLLMProvider has no fake response for schema {schema}")

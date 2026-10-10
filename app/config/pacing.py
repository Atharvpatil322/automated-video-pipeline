from typing import NamedTuple

from app.config.archetype import PacingTier


class PacingBudget(NamedTuple):
    min_scenes: int
    max_scenes: int
    min_words_per_scene: int
    max_words_per_scene: int
    min_total_words: int
    max_total_words: int


PACING_TIERS: dict[PacingTier, PacingBudget] = {
    "fast": PacingBudget(8, 12, 8, 12, 90, 120),
    "moderate": PacingBudget(7, 10, 10, 16, 100, 140),
    "cinematic": PacingBudget(5, 8, 15, 22, 90, 130),
}


def pacing_instruction(tier: PacingTier) -> str:
    budget = PACING_TIERS[tier]
    return (
        f"Pacing tier '{tier}': {budget.min_scenes}-{budget.max_scenes} scenes, "
        f"{budget.min_words_per_scene}-{budget.max_words_per_scene} words per scene, "
        f"{budget.min_total_words}-{budget.max_total_words} total words."
    )

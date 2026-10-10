import json
from functools import lru_cache
from pathlib import Path

from app.config.archetype import ArchetypeConfig

ARCHETYPES_DIR = Path(__file__).parent / "archetypes"


@lru_cache
def load_archetypes() -> dict[str, ArchetypeConfig]:
    registry: dict[str, ArchetypeConfig] = {}
    for path in sorted(ARCHETYPES_DIR.glob("*.json")):
        config = ArchetypeConfig.model_validate(json.loads(path.read_text()))
        registry[config.key] = config
    return registry


def get_archetype(key: str) -> ArchetypeConfig:
    registry = load_archetypes()
    if key not in registry:
        raise ValueError(
            f"unknown archetype '{key}', available: {sorted(registry)}"
        )
    return registry[key]

from fastapi import APIRouter

from app.config.platforms import PLATFORMS
from app.config.registry import load_archetypes
from app.server.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "offline": get_settings().offline}


@router.get("/archetypes")
async def archetypes() -> list[str]:
    return sorted(load_archetypes())


@router.get("/platforms")
async def platforms() -> list[str]:
    return sorted(PLATFORMS)


@router.get("/providers")
async def providers() -> dict[str, list[str]]:
    return {
        "llm": ["groq", "offline"],
        "tts": ["elevenlabs", "openai", "offline"],
        "image": ["openai", "gemini", "offline"],
        "stock": ["pexels", "pixabay", "offline"],
        "video": ["fal", "offline"],
    }

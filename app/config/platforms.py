from pydantic import BaseModel


class PlatformConfig(BaseModel):
    key: str
    width: int
    height: int
    fps: int
    max_duration_s: int
    recommended_duration_s: tuple[int, int]
    codec: str


PLATFORMS: dict[str, PlatformConfig] = {
    "youtube": PlatformConfig(
        key="youtube", width=1080, height=1920, fps=30,
        max_duration_s=60, recommended_duration_s=(40, 55), codec="h264",
    ),
    "tiktok": PlatformConfig(
        key="tiktok", width=1080, height=1920, fps=30,
        max_duration_s=180, recommended_duration_s=(40, 60), codec="h264",
    ),
    "instagram": PlatformConfig(
        key="instagram", width=1080, height=1920, fps=30,
        max_duration_s=90, recommended_duration_s=(40, 55), codec="h264",
    ),
}


def get_platform(key: str) -> PlatformConfig:
    if key not in PLATFORMS:
        raise ValueError(f"unknown platform '{key}', available: {sorted(PLATFORMS)}")
    return PLATFORMS[key]

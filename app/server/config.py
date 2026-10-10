from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "video_pipeline"
    redis_url: str = "redis://localhost:6379"
    jobs_dir: str = "output"
    offline: bool = False
    job_timeout_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
    api_token: str | None = None
    max_jobs: int | None = None
    max_request_body_bytes: int = 15_000  # direction text (10KB) plus headroom

    @field_validator("api_token", "max_jobs", mode="before")
    @classmethod
    def _blank_env_string_means_unset(cls, value):
        """An unset-but-present env var (`API_TOKEN=`, `MAX_JOBS=` in a
        .env file or docker-compose's `environment:`) arrives as `""`, not
        absent - pydantic-settings otherwise tries to parse "" as an int
        for max_jobs and crashes Settings() entirely at container startup.
        Found by actually constructing Settings() with that env var set,
        not by reading the pydantic-settings docs.
        """
        return None if value == "" else value


_settings: Settings | None = None


def set_settings(settings: Settings) -> None:
    """Test hook: pin a specific Settings instance rather than re-reading
    env vars on every call.
    """
    global _settings
    _settings = settings


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

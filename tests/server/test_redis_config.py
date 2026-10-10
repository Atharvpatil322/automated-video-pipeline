"""Regression test for a bug found in a live docker-compose run:
WorkerSettings.redis_settings was arq's own `RedisSettings()` default
(host="localhost") instead of being built from the configured REDIS_URL -
inside the worker's own container, "localhost" is the worker itself, not
the `redis` compose service, so every job failed with a connection error.
"""

import importlib

from app.server.config import Settings, set_settings
from app.server.redis_settings import build_redis_settings


def test_build_redis_settings_uses_the_given_url_not_localhost():
    settings = build_redis_settings("redis://redis:6379/0")
    assert settings.host == "redis"
    assert settings.port == 6379


def test_build_redis_settings_increases_retry_tolerance_over_arq_defaults():
    from arq.connections import RedisSettings

    default = RedisSettings()
    tuned = build_redis_settings("redis://redis:6379/0")
    assert tuned.conn_retries > default.conn_retries
    assert tuned.conn_retry_delay >= default.conn_retry_delay


def test_worker_settings_redis_host_matches_configured_redis_url(monkeypatch):
    """The actual regression: WorkerSettings.redis_settings.host must never
    be "localhost" when REDIS_URL points somewhere else - reload the
    module fresh against a non-localhost setting, the same way a real
    worker process picks it up once at startup.
    """
    custom = Settings(
        mongo_url="mongodb://mongo:27017",
        redis_url="redis://redis:6379/0",
        jobs_dir="/tmp/jobs",
        offline=True,
    )
    set_settings(custom)

    import app.worker as worker_module

    importlib.reload(worker_module)

    assert worker_module.WorkerSettings.redis_settings.host == "redis"
    assert worker_module.WorkerSettings.redis_settings.host != "localhost"

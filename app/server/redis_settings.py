"""One place to turn a REDIS_URL into arq's RedisSettings, so every
connection (the worker's own queue connection, the API's enqueue pool)
points at the same configured host - never arq's `RedisSettings()`
default of localhost, which silently works in local dev and silently
breaks in docker-compose (the worker's "localhost" is itself, not the
`redis` service).
"""

from arq.connections import RedisSettings

# ARQ's own defaults (conn_retries=5, conn_retry_delay=1s -> ~5s total) can
# lose a race against a Redis container that's still starting, even with
# a compose healthcheck gate (first scheduling delay, slow CI host, etc).
CONN_RETRIES = 10
CONN_RETRY_DELAY = 2


def build_redis_settings(redis_url: str) -> RedisSettings:
    settings = RedisSettings.from_dsn(redis_url)
    settings.conn_retries = CONN_RETRIES
    settings.conn_retry_delay = CONN_RETRY_DELAY
    return settings

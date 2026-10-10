"""Per-job API keys: never an ARQ job argument, never written to Mongo.

Chosen approach (b) of the two offered: the API writes keys to a
short-lived Redis string (`job:{id}:keys`, TTL = job_timeout + buffer) that
only the worker ever reads, and the worker deletes it as soon as it's read
(a GET+DELETE, not a GET that leaves the value sitting there for the TTL).
This keeps keys out of both Mongo (the durable store) and the ARQ queue's
own job-argument payload in Redis.

Also holds a small redaction registry: any secret value ever handed to
store_job_keys gets scrubbed from log output for the life of the process,
via a logging.Filter installed in app/main.py.
"""

import json
import logging
from pathlib import Path

from redis.asyncio import Redis


class PathTraversalError(ValueError):
    pass


def safe_join(base_dir: Path, relative_path: str) -> Path:
    """Resolve `relative_path` under `base_dir`, raising if it would
    escape it (`../`, an absolute path, a symlink pointing outside, etc).
    """
    base_resolved = base_dir.resolve()
    candidate = (base_resolved / relative_path).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(f"path '{relative_path}' escapes the jobs directory") from None
    return candidate

_known_secrets: set[str] = set()


def register_secret(value: str) -> None:
    if value:
        _known_secrets.add(value)


def redact_text(text: str) -> str:
    for secret in _known_secrets:
        if secret and secret in text:
            text = text.replace(secret, "***REDACTED***")
    return text


class SecretRedactingFilter(logging.Filter):
    """Redacts against the *fully formatted* message (msg % args), not
    just string-typed args - a secret can arrive as part of a dict, a
    model's repr, or any other object a log call happens to pass, and
    those only ever become a plain string once %-formatting runs. Found
    by a test that logged a dict containing a key: redacting only
    string-typed args missed it entirely.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            formatted = record.getMessage()
        except Exception:
            return True
        redacted = redact_text(formatted)
        if redacted != formatted:
            record.msg = redacted
            record.args = ()
        return True


def _keys_redis_key(job_id: str) -> str:
    return f"job:{job_id}:keys"


async def store_job_keys(redis: Redis, job_id: str, keys: dict[str, str], ttl_seconds: int) -> None:
    for value in keys.values():
        register_secret(value)
    if not keys:
        return
    await redis.set(_keys_redis_key(job_id), json.dumps(keys), ex=ttl_seconds)


async def pop_job_keys(redis: Redis, job_id: str) -> dict[str, str]:
    """Read and immediately delete - the worker calls this exactly once,
    at job start, so the key material doesn't linger in Redis for the
    rest of the TTL.
    """
    key = _keys_redis_key(job_id)
    raw = await redis.get(key)
    if raw is None:
        return {}
    await redis.delete(key)
    keys: dict[str, str] = json.loads(raw)
    for value in keys.values():
        register_secret(value)
    return keys

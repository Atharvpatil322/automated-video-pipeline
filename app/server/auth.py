"""Optional bearer-token auth. A no-op when API_TOKEN isn't set, so local/
offline development needs nothing extra; set it to lock the API down once
deployed somewhere reachable.
"""

from fastapi import Header, HTTPException

from app.server.config import get_settings


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_token:
        return
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


async def require_api_token_or_query(
    authorization: str | None = Header(default=None), token: str | None = None
) -> None:
    """Same check as `require_api_token`, plus a `?token=` query param
    fallback - used only by the files route, whose URLs are loaded by
    plain <video>/<img> tags that cannot set an Authorization header.
    Every other route keeps header-only auth.
    """
    settings = get_settings()
    if not settings.api_token:
        return
    if authorization == f"Bearer {settings.api_token}":
        return
    if token == settings.api_token:
        return
    raise HTTPException(status_code=401, detail="missing or invalid bearer token")

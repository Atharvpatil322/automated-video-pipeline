"""Pexels stock provider.

Free tier: 200 requests/hour, 20,000/month (per-key, confirmed via Pexels'
API docs). Attribution is required by their terms: "a prominent link to
Pexels" plus photographer credit - recorded on StockCandidate/StockAsset
so the resolver can carry it through to visuals.json.
"""

from pathlib import Path

import httpx

from app.schema.providers import StockAsset, StockCandidate

SEARCH_PHOTOS_URL = "https://api.pexels.com/v1/search"
SEARCH_VIDEOS_URL = "https://api.pexels.com/videos/search"
PROVIDER_NAME = "pexels"


class PexelsStockProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self._api_key}

    async def search_image(self, query: str) -> list[StockCandidate]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEARCH_PHOTOS_URL,
                headers=self._headers(),
                params={"query": query, "orientation": "portrait", "per_page": 10},
            )
            response.raise_for_status()
            payload = response.json()

        candidates = []
        for photo in payload.get("photos", []):
            candidates.append(
                StockCandidate(
                    id=str(photo["id"]),
                    provider=PROVIDER_NAME,
                    url=photo["src"]["large2x"],
                    preview_url=photo["src"]["medium"],
                    width=photo["width"],
                    height=photo["height"],
                    duration=None,
                    attribution=f"Photo by {photo['photographer']} on Pexels ({photo['url']})",
                )
            )
        return candidates

    async def search_video(self, query: str) -> list[StockCandidate]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEARCH_VIDEOS_URL,
                headers=self._headers(),
                params={"query": query, "orientation": "portrait", "per_page": 10},
            )
            response.raise_for_status()
            payload = response.json()

        candidates = []
        for video in payload.get("videos", []):
            video_files = sorted(
                (f for f in video["video_files"] if f.get("width") and f.get("height")),
                key=lambda f: f["width"] * f["height"],
                reverse=True,
            )
            if not video_files:
                continue
            best = video_files[0]
            candidates.append(
                StockCandidate(
                    id=str(video["id"]),
                    provider=PROVIDER_NAME,
                    url=best["link"],
                    preview_url=video["image"],
                    width=best["width"],
                    height=best["height"],
                    duration=float(video.get("duration") or 0) or None,
                    attribution=f"Video by {video['user']['name']} on Pexels ({video['url']})",
                )
            )
        return candidates

    async def download(self, candidate: StockCandidate, dest_path: Path) -> StockAsset:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(candidate.url)
            response.raise_for_status()
            dest_path.write_bytes(response.content)

        return StockAsset(
            file_path=str(dest_path),
            width=candidate.width,
            height=candidate.height,
            duration=candidate.duration,
            attribution=candidate.attribution,
        )

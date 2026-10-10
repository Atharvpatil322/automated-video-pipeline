"""Pixabay stock provider.

Free tier: 100 requests/60s per key (confirmed via Pixabay's API docs).
Attribution is "kindly requested" rather than strictly mandated, but we
record it on StockCandidate/StockAsset anyway to carry through consistently
with Pexels.
"""

from pathlib import Path

import httpx

from app.schema.providers import StockAsset, StockCandidate

SEARCH_IMAGES_URL = "https://pixabay.com/api/"
SEARCH_VIDEOS_URL = "https://pixabay.com/api/videos/"
PROVIDER_NAME = "pixabay"


class PixabayStockProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search_image(self, query: str) -> list[StockCandidate]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEARCH_IMAGES_URL,
                params={
                    "key": self._api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": "vertical",
                    "per_page": 10,
                },
            )
            response.raise_for_status()
            payload = response.json()

        candidates = []
        for hit in payload.get("hits", []):
            candidates.append(
                StockCandidate(
                    id=str(hit["id"]),
                    provider=PROVIDER_NAME,
                    url=hit["largeImageURL"],
                    preview_url=hit["previewURL"],
                    width=hit["imageWidth"],
                    height=hit["imageHeight"],
                    duration=None,
                    attribution=f"Image by {hit['user']} on Pixabay ({hit['pageURL']})",
                )
            )
        return candidates

    async def search_video(self, query: str) -> list[StockCandidate]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                SEARCH_VIDEOS_URL,
                params={"key": self._api_key, "q": query, "per_page": 10},
            )
            response.raise_for_status()
            payload = response.json()

        candidates = []
        for hit in payload.get("hits", []):
            videos = hit.get("videos", {})
            best = videos.get("large") or videos.get("medium") or videos.get("small")
            if not best:
                continue
            candidates.append(
                StockCandidate(
                    id=str(hit["id"]),
                    provider=PROVIDER_NAME,
                    url=best["url"],
                    preview_url=videos.get("tiny", best).get("url", best["url"]),
                    width=best["width"],
                    height=best["height"],
                    duration=float(hit.get("duration") or 0) or None,
                    attribution=f"Video by {hit['user']} on Pixabay ({hit['pageURL']})",
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

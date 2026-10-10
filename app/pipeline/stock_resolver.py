"""Adaptive stock resolver: search -> verify -> reformulate -> AI fallback.

Mirrors the reference's adaptive-resolver.ts:
1. Start with the director's own visual_prompt as the query. Try each
   stock provider in order (fallback on error/empty). Budget: 4 search
   calls total per scene.
2. Take the top 3 candidates for images, top 1 for video (downloads are
   expensive). Skip ids already seen.
3. A VLM judges each candidate against visual_prompt + narration; accepted
   at confidence >= 0.6. If the verifier itself errors, the candidate is
   accepted unverified (confidence -1) rather than blocking the scene.
4. If nothing is accepted after the first query, one LLM reformulation
   produces 2-3 alternative queries, tried within the same budget.
5. If still nothing, falls back to an AI image, with up to 3 rejected
   candidates' descriptions fed in as negative examples.
"""

from pathlib import Path
from typing import Protocol

import httpx

from app.agents.query_reformulator import reformulate_query
from app.config.archetype import ArchetypeConfig
from app.pipeline.ai_image_resolver import generate_ai_image
from app.schema.director import Scene, VisualType
from app.schema.providers import ImageProvider, LLMProvider, StockCandidate, StockProvider
from app.schema.visuals import SceneVisualResult, VerificationResult

MAX_SEARCH_ATTEMPTS = 4
TOP_N_IMAGES = 3
TOP_N_VIDEOS = 1
CONFIDENCE_THRESHOLD = 0.6
MAX_NEGATIVE_EXAMPLES = 3


class VisionVerifier(Protocol):
    async def verify(
        self, image_bytes: bytes, visual_prompt: str, narration: str
    ) -> VerificationResult: ...


async def _fetch_preview_bytes(candidate: StockCandidate) -> bytes:
    if not candidate.preview_url.startswith(("http://", "https://")):
        # offline mode's candidates point at local sample files, not URLs
        return Path(candidate.preview_url).read_bytes()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(candidate.preview_url)
        response.raise_for_status()
        return response.content


def _asset_extension(candidate: StockCandidate, is_video: bool) -> str:
    if is_video:
        return "mp4"
    return "jpg"


async def resolve_stock(
    *,
    index: int,
    scene: Scene,
    archetype: ArchetypeConfig,
    stock_providers: list[StockProvider],
    verifier: VisionVerifier,
    llm: LLMProvider,
    image: ImageProvider,
    assets_dir: Path,
    log_attempts: list[dict],
) -> SceneVisualResult:
    is_video = scene.visual_type == VisualType.STOCK_VIDEO
    top_n = TOP_N_VIDEOS if is_video else TOP_N_IMAGES

    pending_queries = [scene.visual_prompt]
    seen_ids: set[str] = set()
    rejected_descriptions: list[str] = []
    attempts_used = 0
    reformulated = False

    while pending_queries and attempts_used < MAX_SEARCH_ATTEMPTS:
        query = pending_queries.pop(0)

        for provider in stock_providers:
            if attempts_used >= MAX_SEARCH_ATTEMPTS:
                break
            attempts_used += 1

            try:
                candidates = (
                    await provider.search_video(query)
                    if is_video
                    else await provider.search_image(query)
                )
            except Exception as exc:
                log_attempts.append(
                    {"scene_index": index, "query": query, "found": False, "error": str(exc)}
                )
                continue

            candidates = [c for c in candidates if c.id not in seen_ids][:top_n]
            if not candidates:
                log_attempts.append({"scene_index": index, "query": query, "found": False})
                continue

            for candidate in candidates:
                seen_ids.add(candidate.id)

                try:
                    preview_bytes = await _fetch_preview_bytes(candidate)
                except Exception as exc:
                    log_attempts.append(
                        {
                            "scene_index": index,
                            "query": query,
                            "provider": candidate.provider,
                            "candidate_id": candidate.id,
                            "error": str(exc),
                        }
                    )
                    continue

                try:
                    verification = await verifier.verify(
                        preview_bytes, scene.visual_prompt, scene.script_line
                    )
                except Exception as exc:
                    # the verifier itself errored: accept unverified rather
                    # than block the scene (matches the reference).
                    accepted = await _accept_candidate(
                        candidate, provider, index, is_video, assets_dir
                    )
                    if accepted is None:
                        log_attempts.append(
                            {
                                "scene_index": index,
                                "query": query,
                                "provider": candidate.provider,
                                "candidate_id": candidate.id,
                                "error": f"verifier errored ({exc}) and download also failed",
                            }
                        )
                        continue
                    log_attempts.append(
                        {
                            "scene_index": index,
                            "query": query,
                            "provider": candidate.provider,
                            "candidate_id": candidate.id,
                            "method": "stock_unverified",
                            "confidence": -1,
                        }
                    )
                    return SceneVisualResult(
                        scene_index=index,
                        visual_type=scene.visual_type,
                        path=accepted.file_path,
                        status="generated",
                        attempts=attempts_used,
                        method="stock_unverified",
                        provider=candidate.provider,
                        query=query,
                        confidence=-1,
                        attribution=accepted.attribution,
                    )

                verified = verification.relevant and verification.confidence >= (
                    CONFIDENCE_THRESHOLD
                )
                log_attempts.append(
                    {
                        "scene_index": index,
                        "query": query,
                        "provider": candidate.provider,
                        "candidate_id": candidate.id,
                        "confidence": verification.confidence,
                        "verified": verified,
                        "reason": verification.reason,
                    }
                )

                if not verified:
                    rejected_descriptions.append(verification.reason)
                    continue

                accepted = await _accept_candidate(candidate, provider, index, is_video, assets_dir)
                if accepted is None:
                    continue
                return SceneVisualResult(
                    scene_index=index,
                    visual_type=scene.visual_type,
                    path=accepted.file_path,
                    status="generated",
                    attempts=attempts_used,
                    method="stock_verified",
                    provider=candidate.provider,
                    query=query,
                    confidence=verification.confidence,
                    attribution=accepted.attribution,
                )

        if not reformulated and attempts_used < MAX_SEARCH_ATTEMPTS:
            reformulated = True
            try:
                new_queries, _ = await reformulate_query(scene.visual_prompt, llm)
                pending_queries.extend(new_queries)
            except Exception:
                pass  # reformulation failing just means we fall through to AI fallback

    fallback_reason = (
        f"fallback: no {scene.visual_type.value} candidate verified within budget"
    )
    result = await generate_ai_image(
        index,
        scene,
        archetype,
        llm,
        image,
        assets_dir,
        negative_examples=rejected_descriptions[:MAX_NEGATIVE_EXAMPLES],
    )
    if result.status == "generated":
        return result.model_copy(update={"status": "fallback", "fallback_reason": fallback_reason})
    return result.model_copy(
        update={
            "fallback_reason": (
                f"{fallback_reason}; AI image fallback also failed: {result.fallback_reason}"
            )
        }
    )


async def _accept_candidate(
    candidate: StockCandidate,
    provider: StockProvider,
    index: int,
    is_video: bool,
    assets_dir: Path,
):
    ext = _asset_extension(candidate, is_video)
    dest_path = assets_dir / f"scene-{index}-stock.{ext}"
    try:
        return await provider.download(candidate, dest_path)
    except Exception:
        return None

"""The pipeline, run as an ARQ job: research -> director -> [cost gate,
auto-approved] -> tts -> visuals -> assembly -> critic. Mirrors app/cli.py's
`_run_pipeline_from`, reporting through ServerCallbacks (Mongo + Redis)
instead of print statements, and writing the same on-disk artifacts
(score.json, voiceover.mp3, visuals.json, final.mp4, review.json) under
the job's own run directory so the files route can serve them.

The pipeline itself still knows nothing about HTTP/Mongo/Redis - this
module is the "worker" side of the callbacks boundary, same role app/cli.py
plays for the CLI.
"""

from datetime import datetime
from pathlib import Path

from app.agents.research import research
from app.pipeline.cost import CostTracker, estimate_total_cost
from app.pipeline.orchestrator import (
    run_assembly_stage,
    run_critic_stage,
    run_director_stage,
    run_tts_stage,
)
from app.pipeline.utils import create_run_dir
from app.pipeline.visuals import run_visuals_stage
from app.providers.factory import (
    create_image_provider,
    create_llm_provider,
    create_stock_providers,
    create_tts_provider,
    create_video_provider,
    create_vision_verifier,
)
from app.providers.offline.offline_music import offline_music_dir, offline_music_manifest
from app.schema.job import JobOptions
from app.server.callbacks import ServerCallbacks
from app.server.config import Settings
from app.server.db import jobs_collection
from app.server.pubsub import publish_event


async def _set(job_id: str, update: dict) -> None:
    update["updated_at"] = datetime.utcnow()
    await jobs_collection().update_one({"id": job_id}, {"$set": update})


async def run_job(
    job_id: str, options: JobOptions, keys: dict[str, str], settings: Settings
) -> None:
    offline = settings.offline
    # BUG (found via a live docker-compose job): offline mode swaps the
    # actual provider *implementations* (see "offline" branches below) but
    # was still pricing cost_estimate/cost_actual against whatever
    # tts_provider/image_provider the request asked for - an OFFLINE job
    # showed a non-zero cost for TTS/images it never actually paid for.
    # app/cli.py's _apply_offline_overrides does this same substitution
    # for the CLI path; this is its server-side equivalent.
    llm_provider_name = "offline" if offline else "groq"
    tts_provider_name = "offline" if offline else options.tts_provider
    image_provider_name = "offline" if offline else options.image_provider
    video_provider_name = "offline" if offline else "fal"

    callbacks = ServerCallbacks(job_id)
    await callbacks.prime_cancelled()

    jobs_dir = Path(settings.jobs_dir)
    run_dir = create_run_dir(options.topic, base_dir=jobs_dir)
    callbacks.on_run_dir(run_dir)
    await _set(
        job_id,
        {"status": "running", "started_at": datetime.utcnow(), "run_dir": str(run_dir)},
    )
    await callbacks.flush()

    cost_tracker = CostTracker(
        llm_provider=llm_provider_name,
        tts_provider=tts_provider_name,
        image_provider=image_provider_name,
    )

    try:
        llm = create_llm_provider(keys, llm_provider_name)

        if options.score is not None:
            # replay path: research/director are already done
            callbacks.on_stage_skip("research", "replay")
            callbacks.on_stage_skip("director", "replay")
            score = options.score
            director_meta = {"evaluations": 0, "revisions": 0}
        else:
            callbacks.on_stage_start("research")
            research_result, research_usage = await research(options.topic, llm)
            cost_tracker.add_llm_usage("research", research_usage)
            callbacks.on_stage_complete("research", {"mood": research_result.mood})
            await callbacks.flush()

            score, critique_result, director_meta = await run_director_stage(
                topic=options.topic,
                archetype=options.archetype,
                research_result=research_result,
                llm=llm,
                callbacks=callbacks,
                cost_tracker=cost_tracker,
            )
        await _set(job_id, {"score": score.model_dump(mode="json")})
        await callbacks.flush()

        # each stage below re-checks callbacks.is_cancelled() itself at its
        # own boundary; nothing stale to snapshot here.

        estimate = estimate_total_cost(
            score,
            llm_provider=llm_provider_name,
            tts_provider=tts_provider_name,
            image_provider=image_provider_name,
            video_provider=video_provider_name if not options.no_video else None,
            director_evaluations=director_meta["evaluations"],
            director_revisions=director_meta["revisions"],
            include_final_critic=not options.no_critic,
            stock_enabled=offline or bool(keys.get("pexels") or keys.get("pixabay")),
            video_enabled=not options.no_video,
        )
        # Worker mode always auto-approves (on_cost_estimate returns True),
        # matching the reference - so `cost_rejected` is always False below;
        # only cancellation (checked fresh inside each stage) can stop things.
        callbacks.on_cost_estimate(estimate.model_dump())
        await callbacks.flush()

        tts_output = None
        if not options.no_tts:
            tts = create_tts_provider(keys, tts_provider_name)
            tts_output = await run_tts_stage(
                score=score,
                run_dir=run_dir,
                tts=tts,
                callbacks=callbacks,
                cost_tracker=cost_tracker,
                dry_run_exit=False,
                cost_rejected=False,
            )
        else:
            callbacks.on_stage_skip("tts", "no_tts")
        await callbacks.flush()

        asset_paths: list[str | None] = [None] * len(score.scenes)
        visuals_result = None
        if not options.no_visuals and tts_output is not None:
            image = create_image_provider(keys, image_provider_name)
            stock_providers = create_stock_providers(keys, offline=offline)
            verifier = (
                create_vision_verifier(keys, offline=offline)
                if (stock_providers or offline)
                else None
            )
            video = None if options.no_video else create_video_provider(keys, offline=offline)
            visuals_result = await run_visuals_stage(
                score=score,
                archetype=options.archetype,
                llm=llm,
                image=image,
                run_dir=run_dir,
                stock_providers=stock_providers,
                verifier=verifier,
                video=video,
                scene_durations=[t.duration for t in tts_output.scene_timings],
                use_video=not options.no_video,
                callbacks=callbacks,
                cost_tracker=cost_tracker,
                video_provider_name=video_provider_name,
                dry_run_exit=False,
                cost_rejected=False,
            )
            if visuals_result is not None:
                asset_paths = [r.path for r in visuals_result.scenes]
        else:
            reason = "no_visuals" if options.no_visuals else "no_voiceover"
            callbacks.on_stage_skip("visuals", reason)
        await callbacks.flush()

        if tts_output is not None:
            music_manifest = offline_music_manifest() if offline else None
            music_dir = offline_music_dir() if offline else None
            await run_assembly_stage(
                score=score,
                scene_timings=tts_output.scene_timings,
                asset_paths=asset_paths,
                words=tts_output.words,
                archetype=options.archetype,
                platform=options.platform,
                run_dir=run_dir,
                voiceover_path=tts_output.audio_path,
                visuals_result=visuals_result,
                no_music=options.no_music,
                music_manifest=music_manifest,
                music_dir=music_dir,
                callbacks=callbacks,
                dry_run_exit=False,
                cost_rejected=False,
            )
        else:
            callbacks.on_stage_skip("assembly", "no_voiceover")
        await callbacks.flush()

        await run_critic_stage(
            score=score,
            topic=options.topic,
            archetype=options.archetype,
            llm=llm,
            run_dir=run_dir,
            no_critic=options.no_critic,
            callbacks=callbacks,
            cost_tracker=cost_tracker,
            dry_run_exit=False,
            cost_rejected=False,
        )
        await callbacks.flush()

        callbacks.on_actual_cost(cost_tracker.actual().model_dump())
        await callbacks.flush()

        final_status = "cancelled" if callbacks.is_cancelled() else "completed"
        await _set(job_id, {"status": final_status, "finished_at": datetime.utcnow()})
        await publish_event(job_id, f"job.{final_status}", {"status": final_status})
    except Exception as exc:
        await _set(
            job_id,
            {"status": "failed", "error": str(exc), "finished_at": datetime.utcnow()},
        )
        await publish_event(job_id, "job.failed", {"error": str(exc)})
        raise

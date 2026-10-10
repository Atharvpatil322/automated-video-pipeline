"""Phase 1-5 CLI: research -> director -> [cost gate] -> TTS -> visuals ->
assembly -> critic (review).

    python -m app.cli run --topic "..." --archetype infographic [--dry-run]
        [--no-tts] [--tts-provider elevenlabs|openai] [--no-music]
        [--platform youtube] [--no-visuals] [--image-provider openai|gemini]
        [--no-video] [--no-critic] [--fixture-assets]
        [--yes] [--max-cost 5.00]
    python -m app.cli replay --score output/.../score.json
        [--from-stage {tts,visuals,assembly,critic}] [same flags]

--fixture-assets generates placeholder images/clips instead of calling a
real image provider, for offline testing of TTS/assembly; it overrides
--no-visuals, --image-provider and --no-video when set.

Cooperative cancel: Ctrl+C sets a flag checked between stages (and inside
the director's revise loop) - the current stage finishes, then the run
stops with status "cancelled".
"""

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

from app.agents.research import research
from app.pipeline.cost import CostTracker, estimate_total_cost
from app.pipeline.fixtures import generate_fixture_assets
from app.pipeline.loaders import load_run_meta, load_tts_output, load_visuals_result
from app.pipeline.orchestrator import (
    TTSStageOutput,
    run_assembly_stage,
    run_critic_stage,
    run_director_stage,
    run_tts_stage,
)
from app.pipeline.run_log import RunLog
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
from app.schema.director import DirectorScore
from app.schema.visuals import VisualsResult


def _keys_from_env() -> dict[str, str]:
    keys = {}
    for env_var, key_name in [
        ("GROQ_API_KEY", "groq"),
        ("ELEVENLABS_API_KEY", "elevenlabs"),
        ("OPENAI_API_KEY", "openai"),
        ("GEMINI_API_KEY", "gemini"),
        ("PEXELS_API_KEY", "pexels"),
        ("PIXABAY_API_KEY", "pixabay"),
        ("FAL_API_KEY", "fal"),
    ]:
        if value := os.environ.get(env_var):
            keys[key_name] = value
    return keys


def _keys(args: argparse.Namespace) -> dict[str, str]:
    return {} if args.offline else _keys_from_env()


def _llm_provider_name(args: argparse.Namespace) -> str:
    return "offline" if args.offline else "groq"


def _video_provider_name(args: argparse.Namespace) -> str:
    return "offline" if args.offline else "fal"


def _apply_offline_overrides(args: argparse.Namespace) -> None:
    """--offline is the single switch: it forces every per-stage provider
    choice to the deterministic fake, regardless of what --tts-provider/
    --image-provider were otherwise set to. The dispatch itself lives in
    app/providers/factory.py; this just makes sure every call site asks
    the factory for 'offline'.
    """
    if args.offline:
        args.tts_provider = "offline"
        args.image_provider = "offline"


def should_proceed(
    total_cost: float, *, max_cost: float | None, auto_yes: bool, prompt_fn=input
) -> bool:
    """Pure decision for the cost gate, injectable for tests."""
    if max_cost is not None and total_cost > max_cost:
        print(f"Estimated cost ${total_cost:.4f} exceeds --max-cost ${max_cost:.4f}; rejecting.")
        return False
    if auto_yes:
        return True
    answer = prompt_fn(f"Proceed with estimated cost ${total_cost:.4f}? [y/N] ")
    return answer.strip().lower().startswith("y")


class CLICallbacks:
    """Implements PipelineCallbacks for the CLI: prints progress, records
    stage timing into a RunLog, runs the cost gate, and turns Ctrl+C into a
    cooperative cancel flag checked between stages.
    """

    def __init__(self, run_log: RunLog, *, auto_yes: bool, max_cost: float | None) -> None:
        self._run_log = run_log
        self._auto_yes = auto_yes
        self._max_cost = max_cost
        self._cancelled = False
        self._previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._on_sigint)

    def _on_sigint(self, signum, frame) -> None:
        if self._cancelled:
            # second Ctrl+C: restore default behavior so the user can force-quit
            signal.signal(signal.SIGINT, self._previous_sigint)
            raise KeyboardInterrupt
        print("\nCancelling after the current stage finishes (Ctrl+C again to force)...")
        self._cancelled = True

    def restore_signal_handler(self) -> None:
        signal.signal(signal.SIGINT, self._previous_sigint)

    def on_run_dir(self, path: Path) -> None:
        print(f"Run directory: {path}")

    def on_stage_start(self, stage: str) -> None:
        print(f"[{stage}] starting...")
        self._run_log.stage_start(stage)

    def on_stage_complete(self, stage: str, detail: dict) -> None:
        print(f"[{stage}] done: {detail}")
        self._run_log.stage_complete(stage, detail)

    def on_stage_skip(self, stage: str, reason: str) -> None:
        print(f"[{stage}] skipped ({reason})")
        self._run_log.stage_skip(stage, reason)

    def on_stage_error(self, stage: str, error: Exception) -> None:
        print(f"[{stage}] error (stage continues/is non-fatal per its own policy): {error}")
        self._run_log.stage_error(stage, error)

    def on_progress(self, stage: str, data: dict) -> None:
        if stage == "visuals":
            print(f"  scene {data['scene_index']}: {data['status']}")
        elif stage == "critic" and "review" in data:
            print(f"  final critic score: {data['review']['score']}/10")
        elif stage == "director" and "revision" in data:
            rev = data["revision"]
            print(f"  round {rev['round']}: critic score {rev['score']}")

    def on_cost_estimate(self, estimate: dict) -> bool:
        total = estimate["breakdown"]["llm"] + estimate["breakdown"]["tts"] + estimate[
            "breakdown"
        ]["images"] + estimate["breakdown"]["video"] + estimate["breakdown"]["stock"] + estimate[
            "breakdown"
        ]["vlm"]
        print(f"Estimated cost: ${total:.4f}")
        for note in estimate.get("notes", []):
            print(f"  note: {note}")
        self._run_log.cost_estimate = estimate
        return should_proceed(total, max_cost=self._max_cost, auto_yes=self._auto_yes)

    def on_actual_cost(self, cost: dict) -> None:
        self._run_log.cost_actual = cost

    def on_log(self, log: dict) -> None:
        pass

    def is_cancelled(self) -> bool:
        return self._cancelled


async def _run_tts(
    score: DirectorScore,
    run_dir: Path,
    args: argparse.Namespace,
    callbacks: CLICallbacks,
    cost_tracker: CostTracker,
) -> TTSStageOutput | None:
    tts = create_tts_provider(_keys(args), args.tts_provider)
    return await run_tts_stage(
        score=score,
        run_dir=run_dir,
        tts=tts,
        callbacks=callbacks,
        cost_tracker=cost_tracker,
    )


async def _run_visuals(
    score: DirectorScore,
    run_dir: Path,
    tts_output: TTSStageOutput,
    args: argparse.Namespace,
    callbacks: CLICallbacks,
    cost_tracker: CostTracker,
) -> tuple[list[str | None], VisualsResult | None]:
    if args.fixture_assets:
        print("Generating placeholder scene assets (--fixture-assets, offline testing)...")
        return generate_fixture_assets(score, run_dir / "assets"), None

    if args.no_visuals:
        callbacks.on_stage_skip("visuals", "no_visuals")
        return [None] * len(score.scenes), None

    keys = _keys(args)
    llm = create_llm_provider(keys, _llm_provider_name(args))
    image = create_image_provider(keys, args.image_provider)
    stock_providers = create_stock_providers(keys, offline=args.offline)
    verifier = (
        create_vision_verifier(keys, offline=args.offline)
        if (stock_providers or args.offline)
        else None
    )
    video = None if args.no_video else create_video_provider(keys, offline=args.offline)

    visuals_result = await run_visuals_stage(
        score=score,
        archetype=args.archetype,
        llm=llm,
        image=image,
        run_dir=run_dir,
        stock_providers=stock_providers,
        verifier=verifier,
        video=video,
        scene_durations=[t.duration for t in tts_output.scene_timings],
        use_video=not args.no_video,
        callbacks=callbacks,
        cost_tracker=cost_tracker,
        video_provider_name=_video_provider_name(args),
    )
    if visuals_result is None:
        return [None] * len(score.scenes), None
    return [r.path for r in visuals_result.scenes], visuals_result


async def _run_assembly(
    score: DirectorScore,
    run_dir: Path,
    tts_output: TTSStageOutput,
    asset_paths: list[str | None],
    visuals_result: VisualsResult | None,
    args: argparse.Namespace,
    callbacks: CLICallbacks,
) -> None:
    music_manifest = offline_music_manifest() if args.offline else None
    music_dir = offline_music_dir() if args.offline else None

    output = await run_assembly_stage(
        score=score,
        scene_timings=tts_output.scene_timings,
        asset_paths=asset_paths,
        words=tts_output.words,
        archetype=args.archetype,
        platform=args.platform,
        run_dir=run_dir,
        voiceover_path=tts_output.audio_path,
        visuals_result=visuals_result,
        no_music=args.no_music,
        music_manifest=music_manifest,
        music_dir=music_dir,
        callbacks=callbacks,
    )
    if output:
        print(f"Wrote {output.final_video_path}")


async def _run_critic(
    score: DirectorScore,
    topic: str,
    run_dir: Path,
    args: argparse.Namespace,
    callbacks: CLICallbacks,
    cost_tracker: CostTracker,
) -> None:
    if args.no_critic:
        callbacks.on_stage_skip("critic", "no_critic")
        return
    llm = create_llm_provider(_keys(args), _llm_provider_name(args))
    await run_critic_stage(
        score=score,
        topic=topic,
        archetype=args.archetype,
        llm=llm,
        run_dir=run_dir,
        no_critic=args.no_critic,
        callbacks=callbacks,
        cost_tracker=cost_tracker,
    )


def _skip_remaining(callbacks: CLICallbacks, reason: str, stages: tuple[str, ...]) -> None:
    for stage in stages:
        callbacks.on_stage_skip(stage, reason)


def _print_cost_breakdown(run_log: RunLog) -> None:
    if not run_log.cost_estimate:
        return
    est = run_log.cost_estimate["breakdown"]
    print("Cost breakdown (estimate -> actual):")
    for line in ("llm", "tts", "images", "video", "stock", "vlm"):
        actual = run_log.cost_actual["breakdown"][line] if run_log.cost_actual else 0.0
        print(f"  {line}: ${est[line]:.4f} -> ${actual:.4f}")
    est_total = sum(est.values())
    actual_total = sum(run_log.cost_actual["breakdown"].values()) if run_log.cost_actual else 0.0
    print(f"  total: ${est_total:.4f} -> ${actual_total:.4f}")


async def _run_pipeline_from(
    *,
    from_stage: str,
    score: DirectorScore,
    topic: str,
    run_dir: Path,
    args: argparse.Namespace,
    callbacks: CLICallbacks,
    cost_tracker: CostTracker,
    tts_output: TTSStageOutput | None = None,
    visuals_result: VisualsResult | None = None,
    asset_paths: list[str | None] | None = None,
) -> None:
    stages_after = {
        "tts": ("tts", "visuals", "assembly", "critic"),
        "visuals": ("visuals", "assembly", "critic"),
        "assembly": ("assembly", "critic"),
        "critic": ("critic",),
    }[from_stage]

    needs_tts = bool({"tts", "visuals", "assembly"} & set(stages_after))

    if "tts" in stages_after:
        if args.no_tts:
            callbacks.on_stage_skip("tts", "no_tts")
        else:
            tts_output = await _run_tts(score, run_dir, args, callbacks, cost_tracker)

    if needs_tts and tts_output is None:
        skip_stages = tuple(s for s in stages_after if s not in ("tts", "critic"))
        _skip_remaining(callbacks, "no_voiceover", skip_stages)
        if "critic" in stages_after:
            await _run_critic(score, topic, run_dir, args, callbacks, cost_tracker)
        return

    if "visuals" in stages_after:
        asset_paths, visuals_result = await _run_visuals(
            score, run_dir, tts_output, args, callbacks, cost_tracker
        )

    if "assembly" in stages_after:
        await _run_assembly(
            score, run_dir, tts_output, asset_paths or [], visuals_result, args, callbacks
        )

    if "critic" in stages_after:
        await _run_critic(score, topic, run_dir, args, callbacks, cost_tracker)


async def _run(args: argparse.Namespace) -> None:
    _apply_offline_overrides(args)
    run_dir = create_run_dir(args.topic)
    (run_dir / "run_meta.json").write_text(
        json.dumps({"topic": args.topic, "archetype": args.archetype}, indent=2)
    )

    run_log = RunLog(run_dir, topic=args.topic, archetype=args.archetype)
    callbacks = CLICallbacks(run_log, auto_yes=args.yes, max_cost=args.max_cost)
    cost_tracker = CostTracker(
        llm_provider=_llm_provider_name(args),
        tts_provider=args.tts_provider,
        image_provider=args.image_provider,
    )
    callbacks.on_run_dir(run_dir)

    try:
        llm = create_llm_provider(_keys(args), _llm_provider_name(args))

        print("Researching...")
        research_result, research_usage = await research(args.topic, llm)
        cost_tracker.add_llm_usage("research", research_usage)
        print(f"Research mood: {research_result.mood}")

        print("Generating plan (critic-revise loop)...")
        score, critique_result, meta = await run_director_stage(
            topic=args.topic,
            archetype=args.archetype,
            research_result=research_result,
            llm=llm,
            callbacks=callbacks,
            cost_tracker=cost_tracker,
        )

        score_path = run_dir / "score.json"
        score_path.write_text(score.model_dump_json(indent=2))
        print(f"Wrote {score_path}")
        if critique_result:
            print(f"Best critic score: {critique_result.score}/10")

        if args.dry_run:
            run_log.run_status = "dry_run"
            _skip_remaining(callbacks, "dry_run", ("tts", "visuals", "assembly", "critic"))
            return

        if callbacks.is_cancelled():
            run_log.run_status = "cancelled"
            _skip_remaining(callbacks, "cancelled", ("tts", "visuals", "assembly", "critic"))
            return

        estimate = estimate_total_cost(
            score,
            llm_provider=_llm_provider_name(args),
            tts_provider=args.tts_provider,
            image_provider=args.image_provider,
            video_provider=_video_provider_name(args) if not args.no_video else None,
            director_evaluations=meta["evaluations"],
            director_revisions=meta["revisions"],
            include_final_critic=not args.no_critic,
            stock_enabled=(
                args.offline or bool(_keys(args).get("pexels") or _keys(args).get("pixabay"))
            ),
            video_enabled=not args.no_video,
        )
        proceed = callbacks.on_cost_estimate(estimate.model_dump())
        if not proceed:
            run_log.run_status = "cost_rejected"
            _skip_remaining(callbacks, "cost_rejected", ("tts", "visuals", "assembly", "critic"))
            return

        await _run_pipeline_from(
            from_stage="tts",
            score=score,
            topic=args.topic,
            run_dir=run_dir,
            args=args,
            callbacks=callbacks,
            cost_tracker=cost_tracker,
        )
        callbacks.on_actual_cost(cost_tracker.actual().model_dump())
        run_log.run_status = "completed"
    except Exception:
        run_log.run_status = "failed"
        raise
    finally:
        if callbacks.is_cancelled() and run_log.run_status not in ("cost_rejected", "dry_run"):
            run_log.run_status = "cancelled"
        callbacks.restore_signal_handler()
        run_log.write()
        _print_cost_breakdown(run_log)


async def _replay(args: argparse.Namespace) -> None:
    _apply_offline_overrides(args)
    score_path = Path(args.score)
    run_dir = score_path.parent
    score = DirectorScore.model_validate_json(score_path.read_text())
    args.archetype = score.archetype

    meta = load_run_meta(run_dir)
    topic = meta.get("topic", args.topic or "")
    if not topic and args.from_stage == "critic":
        print("Error: no topic found in run_meta.json and --topic not given.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded valid DirectorScore from {score_path} ({len(score.scenes)} scenes)")
    print(f"Resuming from stage: {args.from_stage}")

    run_log = RunLog(run_dir, topic=topic, archetype=args.archetype)
    callbacks = CLICallbacks(run_log, auto_yes=args.yes, max_cost=args.max_cost)
    cost_tracker = CostTracker(
        llm_provider=_llm_provider_name(args),
        tts_provider=args.tts_provider,
        image_provider=args.image_provider,
    )

    tts_output = None
    visuals_result = None
    asset_paths = None
    try:
        if args.from_stage in ("visuals", "assembly"):
            tts_output = load_tts_output(run_dir, args.from_stage)
        if args.from_stage == "assembly":
            visuals_result = load_visuals_result(run_dir, args.from_stage)
            asset_paths = [r.path for r in visuals_result.scenes]

        await _run_pipeline_from(
            from_stage=args.from_stage,
            score=score,
            topic=topic,
            run_dir=run_dir,
            args=args,
            callbacks=callbacks,
            cost_tracker=cost_tracker,
            tts_output=tts_output,
            visuals_result=visuals_result,
            asset_paths=asset_paths,
        )
        callbacks.on_actual_cost(cost_tracker.actual().model_dump())
        run_log.run_status = "completed"
    except Exception:
        run_log.run_status = "failed"
        raise
    finally:
        callbacks.restore_signal_handler()
        run_log.write()
        _print_cost_breakdown(run_log)


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tts-provider", default="elevenlabs", choices=["elevenlabs", "openai"])
    parser.add_argument("--no-tts", action="store_true")
    parser.add_argument("--no-music", action="store_true")
    parser.add_argument(
        "--platform", default="youtube", choices=["youtube", "tiktok", "instagram"]
    )
    parser.add_argument("--image-provider", default="openai", choices=["openai", "gemini"])
    parser.add_argument("--no-visuals", action="store_true")
    parser.add_argument("--no-video", action="store_true")
    parser.add_argument("--no-critic", action="store_true")
    parser.add_argument("--fixture-assets", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--max-cost", type=float, default=None)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use deterministic local fakes for every provider; no API keys, no network",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="video-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run research + director + TTS + visuals + assembly + critic"
    )
    run_parser.add_argument("--topic", required=True)
    run_parser.add_argument("--archetype", default="infographic")
    run_parser.add_argument("--dry-run", action="store_true")
    _add_shared_args(run_parser)
    run_parser.set_defaults(handler=_run)

    replay_parser = subparsers.add_parser(
        "replay", help="Resume a run from a saved artifact onward"
    )
    replay_parser.add_argument("--score", required=True)
    replay_parser.add_argument("--topic", default=None, help="only needed to resume at 'critic'")
    replay_parser.add_argument(
        "--from-stage", default="tts", choices=["tts", "visuals", "assembly", "critic"]
    )
    _add_shared_args(replay_parser)
    replay_parser.set_defaults(handler=_replay)

    args = parser.parse_args()
    try:
        asyncio.run(args.handler(args))
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""ServerCallbacks: updates Mongo and publishes to the job's Redis channel.

Deliberate design note: `PipelineCallbacks` (app/pipeline/callbacks.py) is a
sync Protocol - every stage function across four phases calls
`callbacks.on_stage_start(...)` etc. as plain (non-awaited) calls. Rather
than retrofit every one of those call sites to `await`, each method here
schedules its Mongo write + Redis publish as a fire-and-forget asyncio
task and records it; `flush()` awaits everything pending so far. The job
runner calls `flush()` after every stage, so Mongo/Redis are never more
than one stage behind, and always fully caught up by job completion.
"""

import asyncio
from datetime import datetime
from typing import Any

# noqa: F401 - imported only to document the Protocol this class satisfies
from app.pipeline.callbacks import PipelineCallbacks  # noqa: F401
from app.server.db import jobs_collection
from app.server.pubsub import publish_event


class ServerCallbacks:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._stage_starts: dict[str, float] = {}
        self._pending: list[asyncio.Task] = []
        self._cancelled = False

    def _spawn(self, coro) -> None:
        self._pending.append(asyncio.ensure_future(coro))

    async def flush(self) -> None:
        if not self._pending:
            return
        pending, self._pending = self._pending, []
        await asyncio.gather(*pending, return_exceptions=True)

    async def _set(self, update: dict[str, Any]) -> None:
        update["updated_at"] = datetime.utcnow()
        await jobs_collection().update_one({"id": self.job_id}, {"$set": update})

    async def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        await publish_event(self.job_id, event_type, data)

    def on_run_dir(self, path) -> None:
        self._spawn(self._set({"run_dir": str(path)}))

    def on_stage_start(self, stage: str) -> None:
        self._stage_starts[stage] = asyncio.get_event_loop().time()

        async def go() -> None:
            await self._set(
                {
                    f"stages.{stage}.status": "running",
                    f"stages.{stage}.started_at": datetime.utcnow(),
                }
            )
            await self._publish(f"stage.{stage}", {"status": "running"})

        self._spawn(go())

    def _duration(self, stage: str) -> float | None:
        start = self._stage_starts.get(stage)
        if start is None:
            return None
        return round(asyncio.get_event_loop().time() - start, 3)

    def on_stage_complete(self, stage: str, detail: dict[str, Any]) -> None:
        duration = self._duration(stage)

        async def go() -> None:
            await self._set(
                {
                    f"stages.{stage}.status": "completed",
                    f"stages.{stage}.detail": detail,
                    f"stages.{stage}.duration_s": duration,
                }
            )
            await self._publish(f"stage.{stage}", {"status": "completed", "detail": detail})

        self._spawn(go())

    def on_stage_skip(self, stage: str, reason: str) -> None:
        async def go() -> None:
            await self._set({f"stages.{stage}.status": "skipped", f"stages.{stage}.reason": reason})
            await self._publish(f"stage.{stage}", {"status": "skipped", "reason": reason})

        self._spawn(go())

    def on_stage_error(self, stage: str, error: Exception) -> None:
        duration = self._duration(stage)

        async def go() -> None:
            await self._set(
                {
                    f"stages.{stage}.status": "error",
                    f"stages.{stage}.error": str(error),
                    f"stages.{stage}.duration_s": duration,
                }
            )
            await self._publish(f"stage.{stage}", {"status": "error", "error": str(error)})

        self._spawn(go())

    def on_progress(self, stage: str, data: dict[str, Any]) -> None:
        async def go() -> None:
            if stage == "director" and "revision" in data:
                await jobs_collection().update_one(
                    {"id": self.job_id},
                    {
                        "$push": {"revision_history": data["revision"]},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
            elif stage == "critic" and "review" in data:
                await self._set({"review": data["review"]})
            await self._publish(f"progress.{stage}", data)

        self._spawn(go())

    def on_cost_estimate(self, estimate: dict[str, Any]) -> bool:
        # Worker mode: auto-approve, matching the reference ("the worker's
        # onCostEstimate stores the estimate and returns true immediately").
        self._spawn(self._set({"cost_estimate": estimate}))
        self._spawn(self._publish("cost.estimate", estimate))
        return True

    def on_actual_cost(self, cost: dict[str, Any]) -> None:
        self._spawn(self._set({"cost_actual": cost}))

    def on_log(self, log: dict[str, Any]) -> None:
        pass

    async def prime_cancelled(self) -> None:
        """Seed `_cancelled` synchronously once, before the first stage
        runs - otherwise the very first is_cancelled() call would see the
        default False regardless of Mongo's actual state.
        """
        await self._refresh_cancelled()

    async def _refresh_cancelled(self) -> None:
        doc = await jobs_collection().find_one({"id": self.job_id}, {"cancel_requested": 1})
        self._cancelled = bool(doc and doc.get("cancel_requested"))

    def is_cancelled(self) -> bool:
        """Reads Mongo's `cancel_requested`, same as the reference's
        isCancelled re-reading meta.json each time. Since this method is
        sync (the Protocol it satisfies is sync) but Mongo access is
        async-only, each call returns the value as of the *previous*
        refresh and kicks off a fresh refresh in the background for the
        *next* call - exact within one check's latency, which is well
        inside "cooperative, stage-granularity" cancellation.
        """
        self._spawn(self._refresh_cancelled())
        return self._cancelled

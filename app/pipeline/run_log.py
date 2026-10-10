"""Accumulates the run-wide log.json: run_status, per-stage timings, and
the cost estimate/actual. Written in a `finally` block by the caller so a
failed or cancelled run still leaves a log, matching the reference.

Other stages (currently just visuals, for its stock-attempts log) write
their own keys directly into log.json; `write()` merges on top of whatever
is already there rather than overwriting it.
"""

import json
import time
from pathlib import Path
from typing import Any

RunStatus = str  # "completed" | "failed" | "cancelled" | "cost_rejected" | "dry_run"


class RunLog:
    def __init__(self, run_dir: Path, topic: str, archetype: str) -> None:
        self.run_dir = run_dir
        self.topic = topic
        self.archetype = archetype
        self.run_status: RunStatus = "running"
        self.stages: dict[str, dict[str, Any]] = {}
        self.cost_estimate: dict | None = None
        self.cost_actual: dict | None = None
        self._stage_starts: dict[str, float] = {}

    def stage_start(self, stage: str) -> None:
        self._stage_starts[stage] = time.monotonic()
        self.stages[stage] = {"status": "running"}

    def _duration(self, stage: str) -> float:
        start = self._stage_starts.get(stage)
        return round(time.monotonic() - start, 3) if start is not None else 0.0

    def stage_complete(self, stage: str, detail: dict[str, Any]) -> None:
        self.stages[stage] = {
            "status": "completed",
            "duration_s": self._duration(stage),
            "detail": detail,
        }

    def stage_skip(self, stage: str, reason: str) -> None:
        self.stages[stage] = {"status": "skipped", "reason": reason}

    def stage_error(self, stage: str, error: Exception) -> None:
        self.stages[stage] = {
            "status": "error",
            "duration_s": self._duration(stage),
            "error": str(error),
        }

    def write(self) -> None:
        log_path = self.run_dir / "log.json"
        existing = json.loads(log_path.read_text()) if log_path.exists() else {}
        existing.update(
            {
                "topic": self.topic,
                "archetype": self.archetype,
                "run_status": self.run_status,
                "stages": self.stages,
                "cost_estimate": self.cost_estimate,
                "cost_actual": self.cost_actual,
            }
        )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(existing, indent=2, default=str))

        cost_path = self.run_dir / "cost.json"
        cost_path.write_text(
            json.dumps(
                {"estimate": self.cost_estimate, "actual": self.cost_actual}, indent=2, default=str
            )
        )

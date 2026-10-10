"""The pipeline's only output channel.

The pipeline engine never prints or serves anything itself; it reports
through this interface so the CLI, worker and web UI can share the same
engine. Implementations may be sync or async-looking no-ops for stages a
caller doesn't care about.
"""

from pathlib import Path
from typing import Any, Protocol


class PipelineCallbacks(Protocol):
    def on_run_dir(self, path: Path) -> None: ...
    def on_stage_start(self, stage: str) -> None: ...
    def on_stage_complete(self, stage: str, detail: dict[str, Any]) -> None: ...
    def on_stage_skip(self, stage: str, reason: str) -> None: ...
    def on_stage_error(self, stage: str, error: Exception) -> None: ...
    def on_progress(self, stage: str, data: dict[str, Any]) -> None: ...
    def on_cost_estimate(self, estimate: dict[str, Any]) -> bool:
        """Return True to proceed with spend."""
        ...

    def on_actual_cost(self, cost: dict[str, Any]) -> None: ...
    def on_log(self, log: dict[str, Any]) -> None: ...
    def is_cancelled(self) -> bool: ...


class NullCallbacks:
    """No-op callbacks; useful as a default or in tests."""

    def on_run_dir(self, path: Path) -> None:
        pass

    def on_stage_start(self, stage: str) -> None:
        pass

    def on_stage_complete(self, stage: str, detail: dict[str, Any]) -> None:
        pass

    def on_stage_skip(self, stage: str, reason: str) -> None:
        pass

    def on_stage_error(self, stage: str, error: Exception) -> None:
        pass

    def on_progress(self, stage: str, data: dict[str, Any]) -> None:
        pass

    def on_cost_estimate(self, estimate: dict[str, Any]) -> bool:
        return True

    def on_actual_cost(self, cost: dict[str, Any]) -> None:
        pass

    def on_log(self, log: dict[str, Any]) -> None:
        pass

    def is_cancelled(self) -> bool:
        return False

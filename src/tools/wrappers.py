from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolTrace:
    tool_name: str
    inputs: dict
    output: Any
    status: str  # "ok" | "error"
    elapsed_ms: float
    error: str | None = None


@dataclass
class TraceLog:
    traces: list[ToolTrace] = field(default_factory=list)

    def add(self, trace: ToolTrace) -> None:
        self.traces.append(trace)


def traced_call(
    tool_name: str,
    fn: Callable,
    log: TraceLog,
    **kwargs: Any,
) -> Any:
    start = time.monotonic()
    try:
        result = fn(**kwargs)
        elapsed = (time.monotonic() - start) * 1000
        log.add(ToolTrace(
            tool_name=tool_name,
            inputs=kwargs,
            output=result,
            status="ok",
            elapsed_ms=round(elapsed, 1),
        ))
        return result
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        log.add(ToolTrace(
            tool_name=tool_name,
            inputs=kwargs,
            output=None,
            status="error",
            elapsed_ms=round(elapsed, 1),
            error=str(exc),
        ))
        raise
